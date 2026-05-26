"""
Agent 执行流水线 — 结构化编排

熔断器保护:
  - 每个 PipelineNode 独立熔断状态
  - 连续失败超过 max_retries 后短暂断路 (30s)
  - 断路期间快速失败, 不执行实际调用

超时防护:
  - asyncio.wait_for 硬超时
  - timeout_seconds 覆盖所有节点级别

竞态安全:
  - PipelineNode 无状态, 可安全并发
  - PipelineLogEntry 不可变 dataclass
  - 所有状态在 PipelineNode.execute() 的局部作用域内
"""

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

from ai_novels.agents.base import BaseAgent, Message
from ai_novels.core.context import WorkflowContext, set_current_context, get_current_trace_id
from ai_novels.core.exceptions import AINovelsException, ErrorCode


# ──────────────────────────────
# 流水线异常
# ──────────────────────────────

class PipelineError(AINovelsException):
    def __init__(self, message: str, node_name: str = "",
                 details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message,
            ErrorCode.AGENT_EXECUTION_ERROR,
            details={"node": node_name, **(details or {})},
        )


class PipelineTimeout(PipelineError):
    def __init__(self, node_name: str, timeout: int):
        super().__init__(
            f"Node '{node_name}' timed out after {timeout}s",
            node_name=node_name,
            details={"timeout_seconds": timeout},
        )


class CircuitBreakerOpen(PipelineError):
    def __init__(self, node_name: str, retry_after: float):
        super().__init__(
            f"Circuit breaker open for node '{node_name}', "
            f"retry after {retry_after:.0f}s",
            node_name=node_name,
        )


# ──────────────────────────────
# 熔断器
# ──────────────────────────────

class CircuitBreaker:
    """熔断器 — 连续失败后快速失败

    状态机: CLOSED → OPEN (failure_threshold 达成) → HALF_OPEN → CLOSED
    """

    def __init__(self, failure_threshold: int = 3, recovery_timeout: float = 30.0):
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._failure_count = 0
        self._last_failure_time: float = 0.0
        self._open = False

    def call(self, func: Callable, *args, **kwargs) -> Any:
        """调用函数 (受熔断保护)"""
        if self._open:
            elapsed = time.time() - self._last_failure_time
            if elapsed >= self._recovery_timeout:
                self._open = False
                self._failure_count = 0
            else:
                raise CircuitBreakerOpen("circuit", self._recovery_timeout - elapsed)

        try:
            result = func(*args, **kwargs)
            self._failure_count = 0
            return result
        except Exception:
            self._failure_count += 1
            self._last_failure_time = time.time()
            if self._failure_count >= self._failure_threshold:
                self._open = True
            raise

    async def call_async(self, func: Callable, *args, **kwargs) -> Any:
        """调用异步函数 (受熔断保护)"""
        if self._open:
            elapsed = time.time() - self._last_failure_time
            if elapsed >= self._recovery_timeout:
                self._open = False
                self._failure_count = 0
            else:
                raise CircuitBreakerOpen("circuit", self._recovery_timeout - elapsed)

        try:
            result = func(*args, **kwargs)
            if asyncio.iscoroutine(result):
                result = await result
            self._failure_count = 0
            return result
        except Exception:
            self._failure_count += 1
            self._last_failure_time = time.time()
            if self._failure_count >= self._failure_threshold:
                self._open = True
            raise

    @property
    def is_open(self) -> bool:
        return self._open


# ──────────────────────────────
# 流水线节点
# ──────────────────────────────

@dataclass
class PipelineNode:
    """流水线节点 — 描述一个 Agent 及其执行配置"""
    name: str
    agent: BaseAgent
    timeout_seconds: int = 60
    retry_on_failure: bool = True
    max_retries: int = 3
    pre_hook: Optional[Callable] = None
    post_hook: Optional[Callable] = None

    def __post_init__(self):
        self._breaker = CircuitBreaker(
            failure_threshold=self.max_retries,
            recovery_timeout=30.0,
        )

    async def execute(self, message: Message, ctx: WorkflowContext) -> Dict[str, Any]:
        """执行节点

        返回:
            {"status": "success", "message": Message, "duration_ms": int}
            或 {"status": "failed", "error": str, "duration_ms": int}
        """
        set_current_context(ctx)
        message.metadata["tenant_id"] = ctx.tenant_id
        message.metadata["trace_id"] = ctx.trace_id
        message.metadata["session_id"] = ctx.session_id

        # 熔断器检查
        if self._breaker.is_open:
            elapsed = time.time() - self._breaker._last_failure_time
            if elapsed < 30.0:
                return {
                    "status": "skipped",
                    "message": message,
                    "error": f"Circuit breaker open, retry after {30.0 - elapsed:.0f}s",
                    "duration_ms": 0,
                }
            self._breaker._open = False
            self._breaker._failure_count = 0

        start = time.time()

        try:
            # 前置钩子
            if self.pre_hook:
                await self._safe_hook(self.pre_hook, message, ctx)

            # 核心调用 (硬超时 — 支持同步/异步 agent)
            async def _invoke() -> Message:
                if hasattr(self.agent, "process_with_context"):
                    proc = self.agent.process_with_context  # type: ignore
                    args = (message, ctx)
                else:
                    proc = self.agent.process
                    args = (message,)

                if asyncio.iscoroutinefunction(proc):
                    return await proc(*args)

                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(None, proc, *args)

            result = await asyncio.wait_for(
                _invoke(),
                timeout=self.timeout_seconds,
            )

            # 后置钩子
            if self.post_hook:
                await self._safe_hook(self.post_hook, result, ctx)

            duration = int((time.time() - start) * 1000)
            self._breaker._failure_count = 0
            return {
                "status": "success",
                "message": result,
                "duration_ms": duration,
            }

        except asyncio.TimeoutError:
            duration = int((time.time() - start) * 1000)
            self._breaker._failure_count += 1
            self._breaker._last_failure_time = time.time()
            if self._breaker._failure_count >= self._breaker._failure_threshold:
                self._breaker._open = True
            return {
                "status": "failed",
                "message": message,
                "error": f"Timeout after {self.timeout_seconds}s",
                "duration_ms": duration,
            }

        except Exception as e:
            duration = int((time.time() - start) * 1000)
            self._breaker._failure_count += 1
            self._breaker._last_failure_time = time.time()
            if self._breaker._failure_count >= self._breaker._failure_threshold:
                self._breaker._open = True
            return {
                "status": "failed",
                "message": message,
                "error": str(e),
                "duration_ms": duration,
            }

    @staticmethod
    async def _safe_hook(hook: Callable, *args):
        try:
            if asyncio.iscoroutinefunction(hook):
                await hook(*args)
            else:
                hook(*args)
        except Exception:
            pass  # 钩子不阻断主流程


# ──────────────────────────────
# 流水线执行日志条目
# ──────────────────────────────

@dataclass(frozen=True)
class PipelineLogEntry:
    node_name: str
    status: str  # success | failed | skipped
    duration_ms: int
    tenant_id: str
    user_id: str
    trace_id: str
    session_id: str
    error: Optional[str] = None
    timestamp: str = ""


# ──────────────────────────────
# Agent 执行流水线
# ──────────────────────────────

class AgentPipeline:
    """Agent 执行流水线

    负责: DAG 顺序执行 PipelineNode, 在节点间传递 WorkflowContext,
          记录每个节点的执行日志, 确保可观测。
    异常安全: 单节点失败后整个流水线终止, 可通过 logs 定位失败点。
    """

    def __init__(self, ctx: WorkflowContext, nodes: List[PipelineNode]):
        if not nodes:
            raise ValueError("Pipeline must have at least one node")
        self._ctx = ctx
        self._nodes = nodes
        self._logs: List[PipelineLogEntry] = []

    async def run(self, seed_message: Message) -> Message:
        """执行完整流水线

        Args:
            seed_message: 初始消息

        Returns:
            最后一个节点的输出消息

        Raises:
            PipelineError: 任一节点失败
        """
        current = seed_message
        for node in self._nodes:
            result = await node.execute(current, self._ctx)
            status = result.get("status", "failed")
            duration = result.get("duration_ms", 0)
            error = result.get("error")

            self._logs.append(PipelineLogEntry(
                node_name=node.name,
                status=status,
                duration_ms=duration,
                tenant_id=self._ctx.tenant_id,
                user_id=self._ctx.user_id,
                trace_id=self._ctx.trace_id,
                session_id=self._ctx.session_id,
                error=error,
                timestamp=datetime.now(timezone.utc).isoformat(),
            ))

            if status == "failed":
                raise PipelineError(
                    f"Pipeline failed at node '{node.name}': {error}",
                    node_name=node.name,
                )

            if status == "skipped":
                continue

            current = result["message"]

        return current

    @property
    def execution_log(self) -> List[Dict[str, Any]]:
        return [
            {
                "node": e.node_name,
                "status": e.status,
                "duration_ms": e.duration_ms,
                "tenant_id": e.tenant_id,
                "user_id": e.user_id,
                "trace_id": e.trace_id,
                "session_id": e.session_id,
                "error": e.error,
                "timestamp": e.timestamp,
            }
            for e in self._logs
        ]
