"""
TaskOrchestrator — 异步任务调度与编排引擎

基于事件驱动的任务调度器，支持：
- 优先级任务队列（异步 PriorityQueue）
- DAG 依赖解析与拓扑执行
- ToolEnabledAgent 工作池
- 事件总线集成（任务生命周期事件）
- 任务结果聚合与重试
- 健康监控与统计

@file: agents/task_orchestrator.py
@date: 2026-04-29
"""

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from ai_novels.agents.base import BaseAgent, Message, MessageType
from ai_novels.agents.workflow_orchestrator import (
    HandoffType,
    TaskState,
    WorkflowDefinition,
    WorkflowOrchestrator,
    WorkflowStage,
    WorkflowTask,
)
from ai_novels.core.event_bus import EventBus, EventPriority, EventType
from ai_novels.utils.logger import get_logger

_logger = get_logger()


class TaskPriority(Enum):
    """任务优先级"""

    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3
    BACKGROUND = 4


class WorkerState(Enum):
    """工作器状态"""

    IDLE = "idle"
    BUSY = "busy"
    OFFLINE = "offline"
    ERROR = "error"


@dataclass
class QueuedTask:
    """队列中的任务项"""

    task_id: str
    priority: TaskPriority
    agent_name: str
    payload: Dict[str, Any]
    enqueue_time: float = field(default_factory=time.time)
    correlation_id: Optional[str] = None
    timeout: float = 300.0  # 秒
    max_retries: int = 3
    retry_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "priority": self.priority.value,
            "agent_name": self.agent_name,
            "enqueue_time": self.enqueue_time,
            "correlation_id": self.correlation_id,
            "timeout": self.timeout,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
        }


@dataclass
class WorkerSlot:
    """工作器槽位"""

    agent: BaseAgent
    state: WorkerState = WorkerState.IDLE
    current_task: Optional[str] = None
    total_tasks: int = 0
    failed_tasks: int = 0
    last_heartbeat: float = field(default_factory=time.time)

    @property
    def is_available(self) -> bool:
        return self.state == WorkerState.IDLE

    def heartbeat(self) -> None:
        self.last_heartbeat = time.time()

    def assign(self, task_id: str) -> None:
        self.state = WorkerState.BUSY
        self.current_task = task_id

    def release(self, success: bool = True) -> None:
        self.state = WorkerState.IDLE
        self.current_task = None
        self.total_tasks += 1
        if not success:
            self.failed_tasks += 1


@dataclass
class DAGTaskNode:
    """DAG 任务节点"""

    task_id: str
    agent_name: str
    payload: Dict[str, Any]
    dependencies: List[str] = field(default_factory=list)
    dependents: List[str] = field(default_factory=list)
    state: TaskState = TaskState.INBOX
    result: Any = None
    error: Optional[str] = None
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    priority: TaskPriority = TaskPriority.NORMAL

    @property
    def is_ready(self) -> bool:
        """依赖是否全部完成"""
        return self.state == TaskState.INBOX and len(self.dependencies) == 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "agent_name": self.agent_name,
            "state": self.state.value,
            "dependencies": self.dependencies,
            "dependents": self.dependents,
            "priority": self.priority.value,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "error": self.error,
        }


class TaskOrchestrator:
    """任务调度编排器

    核心能力:
    1. 优先级任务队列: async PriorityQueue
    2. DAG 依赖执行: 拓扑排序 + 动态依赖解除
    3. 工作器池: ToolEnabledAgent 注册与调度
    4. 事件驱动: EventBus 发布任务生命周期事件
    5. 结果聚合: 多任务结果合并
    """

    def __init__(
        self,
        event_bus: Optional[EventBus] = None,
        max_workers: int = 4,
        enable_dag: bool = True,
    ):
        self._event_bus = event_bus
        self._max_workers = max_workers
        self._enable_dag = enable_dag

        # 任务队列 (priority, enqueue_time, task_id)
        self._queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self._queued_tasks: Dict[str, QueuedTask] = {}
        self._queue_lock = asyncio.Lock()

        # 工作器池
        self._workers: Dict[str, WorkerSlot] = {}
        self._worker_lock = asyncio.Lock()

        # DAG 任务图
        self._dag_nodes: Dict[str, DAGTaskNode] = {}
        self._dag_lock = asyncio.Lock()

        # 任务结果缓存
        self._results: Dict[str, Any] = {}
        self._result_lock = asyncio.Lock()

        # 运行状态
        self._running = False
        self._dispatcher_task: Optional[asyncio.Task] = None
        self._shutdown_event = asyncio.Event()

        # 暂停的任务集合
        self._paused_tasks: Set[str] = set()

        # 统计
        self._stats = {
            "submitted": 0,
            "completed": 0,
            "failed": 0,
            "retried": 0,
            "cancelled": 0,
        }

        # 底层工作流编排器（用于复杂工作流定义）
        self._workflow_engine = WorkflowOrchestrator()

    # ---- 生命周期 ----

    async def start(self) -> None:
        """启动调度器"""
        if self._running:
            return
        self._running = True
        self._shutdown_event.clear()
        self._dispatcher_task = asyncio.create_task(self._dispatch_loop())
        _logger.agent(f"TaskOrchestrator started with max_workers={self._max_workers}")

        if self._event_bus:
            await self._event_bus.publish_type(
                EventType.SYSTEM_STARTUP,
                payload={"component": "TaskOrchestrator", "max_workers": self._max_workers},
                source="task_orchestrator",
            )

    async def shutdown(self, wait: bool = True, timeout: float = 30.0) -> None:
        """关闭调度器"""
        if not self._running:
            return
        self._running = False
        self._shutdown_event.set()

        if self._dispatcher_task and wait:
            try:
                await asyncio.wait_for(self._dispatcher_task, timeout=timeout)
            except asyncio.TimeoutError:
                self._dispatcher_task.cancel()
                try:
                    await self._dispatcher_task
                except asyncio.CancelledError:
                    pass

        _logger.agent("TaskOrchestrator shutdown")

    # ---- 工作器管理 ----

    def register_worker(self, agent: BaseAgent) -> bool:
        """注册 BaseAgent 作为工作器"""
        if agent.name in self._workers:
            return False

        self._workers[agent.name] = WorkerSlot(agent=agent)
        _logger.agent(f"Worker registered: {agent.name}")
        return True

    def unregister_worker(self, agent_name: str) -> bool:
        """注销工作器"""
        if agent_name not in self._workers:
            return False
        del self._workers[agent_name]
        _logger.agent(f"Worker unregistered: {agent_name}")
        return True

    def list_workers(self) -> List[Dict[str, Any]]:
        """列出所有工作器状态"""
        return [
            {
                "name": name,
                "state": slot.state.value,
                "current_task": slot.current_task,
                "total_tasks": slot.total_tasks,
                "failed_tasks": slot.failed_tasks,
                "idle": slot.is_available,
            }
            for name, slot in self._workers.items()
        ]

    def get_available_workers(self) -> List[str]:
        """获取可用工作器名称列表"""
        return [
            name for name, slot in self._workers.items() if slot.is_available
        ]

    def list_tasks(self) -> List[Dict[str, Any]]:
        """列出所有队列中的任务"""
        tasks = []
        for task_id, queued in self._queued_tasks.items():
            task_info = queued.to_dict()
            # 检查是否有结果
            result = self._results.get(task_id)
            if result:
                task_info["result"] = result
                task_info["status"] = "completed" if result.get("success") else "failed"
            else:
                task_info["status"] = "pending"
            tasks.append(task_info)
        return tasks

    # ---- 任务提交 ----

    async def submit(
        self,
        agent_name: str,
        payload: Dict[str, Any],
        *,
        priority: TaskPriority = TaskPriority.NORMAL,
        correlation_id: Optional[str] = None,
        timeout: float = 300.0,
        max_retries: int = 3,
        task_id: Optional[str] = None,
    ) -> str:
        """提交单个任务到队列

        Args:
            agent_name: 执行任务的 Agent 名称
            payload: 任务负载
            priority: 优先级
            correlation_id: 关联ID
            timeout: 超时（秒）
            max_retries: 最大重试次数
            task_id: 自定义任务ID（None 则自动生成）

        Returns:
            任务ID
        """
        task_id = task_id or str(uuid.uuid4())
        queued = QueuedTask(
            task_id=task_id,
            priority=priority,
            agent_name=agent_name,
            payload=payload,
            correlation_id=correlation_id or task_id,
            timeout=timeout,
            max_retries=max_retries,
        )

        async with self._queue_lock:
            self._queued_tasks[task_id] = queued

        await self._queue.put((priority.value, time.time(), task_id))
        self._stats["submitted"] += 1

        # 发布事件
        if self._event_bus:
            await self._event_bus.publish_type(
                EventType.TASK_CREATED,
                payload={
                    "task_id": task_id,
                    "agent_name": agent_name,
                    "priority": priority.value,
                    "correlation_id": queued.correlation_id,
                },
                source="task_orchestrator",
            )

        _logger.agent(f"Task submitted: {task_id} -> {agent_name} (priority={priority.name})")
        return task_id

    async def submit_batch(
        self,
        tasks: List[Tuple[str, Dict[str, Any]]],
        *,
        priority: TaskPriority = TaskPriority.NORMAL,
        correlation_id: Optional[str] = None,
    ) -> List[str]:
        """批量提交任务

        Args:
            tasks: [(agent_name, payload), ...]

        Returns:
            任务ID列表
        """
        ids = []
        base_cid = correlation_id or str(uuid.uuid4())
        for i, (agent_name, payload) in enumerate(tasks):
            cid = f"{base_cid}:{i}"
            tid = await self.submit(
                agent_name, payload, priority=priority, correlation_id=cid
            )
            ids.append(tid)
        return ids

    async def submit_dag(
        self,
        nodes: List[DAGTaskNode],
        *,
        correlation_id: Optional[str] = None,
    ) -> str:
        """提交 DAG 任务图

        Args:
            nodes: DAG 节点列表

        Returns:
            DAG 根任务ID / 批处理ID
        """
        dag_id = correlation_id or str(uuid.uuid4())

        async with self._dag_lock:
            for node in nodes:
                node.state = TaskState.INBOX
                self._dag_nodes[node.task_id] = node

            # 构建反向依赖（dependents）
            for node in nodes:
                for dep_id in node.dependencies:
                    if dep_id in self._dag_nodes:
                        self._dag_nodes[dep_id].dependents.append(node.task_id)

        # 将所有就绪节点入队
        ready_nodes = [n for n in nodes if n.is_ready]
        for node in ready_nodes:
            await self.submit(
                node.agent_name,
                node.payload,
                priority=node.priority,
                correlation_id=f"{dag_id}:{node.task_id}",
                task_id=node.task_id,
            )

        _logger.agent(f"DAG submitted: {dag_id} with {len(nodes)} nodes")
        return dag_id

    # ---- 任务结果查询 ----

    async def get_result(self, task_id: str, timeout: Optional[float] = None) -> Any:
        """等待并获取任务结果

        Args:
            task_id: 任务ID
            timeout: 等待超时（秒），None 则一直等待

        Returns:
            任务结果

        Raises:
            TimeoutError: 超时
            KeyError: 任务不存在
        """
        if task_id not in self._queued_tasks:
            raise KeyError(f"Task {task_id} not found")

        deadline = None
        if timeout:
            deadline = time.time() + timeout

        while True:
            async with self._result_lock:
                if task_id in self._results:
                    return self._results[task_id]

            if deadline and time.time() > deadline:
                raise TimeoutError(f"Task {task_id} result timeout")

            await asyncio.sleep(0.1)

    def get_result_nowait(self, task_id: str) -> Any:
        """非阻塞获取结果"""
        return self._results.get(task_id)

    async def cancel(self, task_id: str) -> bool:
        """取消任务"""
        async with self._queue_lock:
            task = self._queued_tasks.get(task_id)
            if not task:
                return False
            self._stats["cancelled"] += 1
            self._results[task_id] = {"success": False, "error": "cancelled"}
            return True

    async def pause(self, task_id: str) -> bool:
        """暂停任务"""
        if task_id in self._results:
            return False  # 已完成的任务不能暂停
        self._paused_tasks.add(task_id)
        return True

    async def resume(self, task_id: str) -> bool:
        """恢复暂停的任务"""
        if task_id in self._paused_tasks:
            self._paused_tasks.discard(task_id)
            return True
        return False

    def is_paused(self, task_id: str) -> bool:
        """检查任务是否暂停"""
        return task_id in self._paused_tasks

    # ---- 核心调度循环 ----

    async def _dispatch_loop(self) -> None:
        """调度器主循环"""
        while self._running:
            try:
                # 等待 shutdown 或队列中有任务
                if self._queue.empty():
                    await asyncio.wait_for(
                        self._shutdown_event.wait(), timeout=0.5
                    )
                    if self._shutdown_event.is_set():
                        break
                    continue

                # 获取任务
                priority, enqueue_time, task_id = await self._queue.get()

                async with self._queue_lock:
                    queued = self._queued_tasks.get(task_id)
                    if not queued:
                        continue

                # 找可用工作器
                worker_name = await self._find_worker(queued.agent_name)
                if not worker_name:
                    # 无可用工作器，重新入队（稍后重试）
                    await self._queue.put((priority, enqueue_time, task_id))
                    await asyncio.sleep(0.2)
                    continue

                # 分配执行
                asyncio.create_task(self._execute_task(worker_name, queued))

            except asyncio.TimeoutError:
                continue
            except Exception as e:
                _logger.agent_error(f"Dispatch loop error: {e}")
                await asyncio.sleep(1)

    async def _find_worker(self, preferred_agent: str) -> Optional[str]:
        """查找可用工作器"""
        # 优先匹配指定 Agent
        if preferred_agent in self._workers:
            slot = self._workers[preferred_agent]
            if slot.is_available:
                return preferred_agent

        # 任意可用工作器
        available = self.get_available_workers()
        if available:
            return available[0]

        return None

    async def _execute_task(self, worker_name: str, queued: QueuedTask) -> None:
        """执行任务"""
        worker = self._workers.get(worker_name)
        if not worker:
            return

        worker.assign(queued.task_id)
        start_time = time.time()

        # 发布开始事件
        if self._event_bus:
            await self._event_bus.publish_type(
                EventType.TASK_STARTED,
                payload={
                    "task_id": queued.task_id,
                    "worker": worker_name,
                    "agent_name": queued.agent_name,
                    "correlation_id": queued.correlation_id,
                },
                source="task_orchestrator",
            )

        try:
            # 暂停检查：如果任务被暂停则等待恢复
            while queued.task_id in self._paused_tasks:
                if not self._running:
                    return
                await asyncio.sleep(0.5)

            # 发布 Agent 开始事件
            if self._event_bus:
                await self._event_bus.publish_type(
                    EventType.AGENT_STARTED,
                    payload={
                        "task_id": queued.task_id,
                        "agent_name": queued.agent_name,
                        "stage": "processing",
                        "progress": 0.1,
                        "worker": worker_name,
                        "payload": queued.payload,
                    },
                    source="task_orchestrator",
                )

            # 执行
            agent = worker.agent
            message = Message(
                id=queued.task_id,
                type=MessageType.TEXT,
                content=queued.payload.get("content", ""),
                metadata={
                    "task_id": queued.task_id,
                    "payload": queued.payload,
                    "correlation_id": queued.correlation_id,
                },
            )

            # 使用 aprocess 获取完整上下文能力
            if hasattr(agent, "aprocess"):
                response = await asyncio.wait_for(
                    agent.aprocess(message),
                    timeout=queued.timeout,
                )
            else:
                # 降级到同步 process
                loop = asyncio.get_event_loop()
                response = await asyncio.wait_for(
                    loop.run_in_executor(None, agent.process, message),
                    timeout=queued.timeout,
                )

            result = response.content if response else None

            async with self._result_lock:
                self._results[queued.task_id] = {
                    "success": True,
                    "result": result,
                    "worker": worker_name,
                    "elapsed": time.time() - start_time,
                }

            self._stats["completed"] += 1
            worker.release(success=True)

            # 发布完成事件
            if self._event_bus:
                await self._event_bus.publish_type(
                    EventType.TASK_COMPLETED,
                    payload={
                        "task_id": queued.task_id,
                        "worker": worker_name,
                        "elapsed": time.time() - start_time,
                    },
                    source="task_orchestrator",
                )

            # 发布 Agent 完成事件
            if self._event_bus:
                await self._event_bus.publish_type(
                    EventType.AGENT_COMPLETED,
                    payload={
                        "task_id": queued.task_id,
                        "agent_name": queued.agent_name,
                        "stage": "completed",
                        "progress": 1.0,
                        "elapsed": time.time() - start_time,
                        "result_length": len(str(result)) if result else 0,
                    },
                    source="task_orchestrator",
                )

            # 触发 DAG 下游节点
            if self._enable_dag:
                await self._trigger_downstream(queued.task_id, result)

        except asyncio.TimeoutError:
            await self._handle_task_failure(
                queued, worker, "timeout", start_time, worker_name
            )
        except Exception as e:
            await self._handle_task_failure(
                queued, worker, str(e), start_time, worker_name
            )

    async def _handle_task_failure(
        self,
        queued: QueuedTask,
        worker: WorkerSlot,
        error: str,
        start_time: float,
        worker_name: str,
    ) -> None:
        """处理任务失败"""
        queued.retry_count += 1

        if queued.retry_count <= queued.max_retries:
            # 重试
            self._stats["retried"] += 1
            _logger.agent(
                f"Task {queued.task_id} failed, retrying {queued.retry_count}/{queued.max_retries}"
            )
            await self._queue.put(
                (queued.priority.value, time.time(), queued.task_id)
            )
            worker.release(success=True)  # 工作器本身没问题
        else:
            # 最终失败
            async with self._result_lock:
                self._results[queued.task_id] = {
                    "success": False,
                    "error": error,
                    "worker": worker_name,
                    "elapsed": time.time() - start_time,
                    "retries": queued.retry_count,
                }
            self._stats["failed"] += 1
            worker.release(success=False)

            if self._event_bus:
                await self._event_bus.publish_type(
                    EventType.TASK_FAILED,
                    payload={
                        "task_id": queued.task_id,
                        "worker": worker_name,
                        "error": error,
                        "retries": queued.retry_count,
                    },
                    source="task_orchestrator",
                    priority=EventPriority.HIGH,
                )
                await self._event_bus.publish_type(
                    EventType.AGENT_FAILED,
                    payload={
                        "task_id": queued.task_id,
                        "agent_name": queued.agent_name,
                        "error": error,
                        "stage": "failed",
                    },
                    source="task_orchestrator",
                    priority=EventPriority.HIGH,
                )

            # DAG 失败传播
            if self._enable_dag:
                await self._fail_downstream(queued.task_id, error)

    # ---- DAG 管理 ----

    async def _trigger_downstream(self, task_id: str, result: Any) -> None:
        """触发下游任务"""
        async with self._dag_lock:
            node = self._dag_nodes.get(task_id)
            if not node:
                return

            node.state = TaskState.DONE
            node.result = result
            node.completed_at = time.time()

            # 解除下游依赖
            for dependent_id in node.dependents:
                dep_node = self._dag_nodes.get(dependent_id)
                if dep_node and task_id in dep_node.dependencies:
                    dep_node.dependencies.remove(task_id)

                    # 如果全部依赖解除，入队
                    if dep_node.is_ready:
                        await self.submit(
                            dep_node.agent_name,
                            dep_node.payload,
                            priority=dep_node.priority,
                            correlation_id=f"dag:{dependent_id}",
                            task_id=dependent_id,
                        )

    async def _fail_downstream(self, task_id: str, error: str) -> None:
        """传播失败到下游"""
        async with self._dag_lock:
            node = self._dag_nodes.get(task_id)
            if not node:
                return

            node.state = TaskState.FAILED
            node.error = error

            # 递归标记下游为失败
            to_visit = list(node.dependents)
            visited: Set[str] = set()
            while to_visit:
                dep_id = to_visit.pop()
                if dep_id in visited:
                    continue
                visited.add(dep_id)

                dep_node = self._dag_nodes.get(dep_id)
                if dep_node:
                    dep_node.state = TaskState.FAILED
                    dep_node.error = f"Upstream {task_id} failed: {error}"
                    to_visit.extend(dep_node.dependents)

    async def get_dag_status(self, dag_id: str) -> Optional[Dict[str, Any]]:
        """获取 DAG 执行状态"""
        async with self._dag_lock:
            nodes = [
                n.to_dict()
                for n in self._dag_nodes.values()
                if n.payload.get("dag_id") == dag_id
            ]
            if not nodes:
                return None

            total = len(nodes)
            done = sum(1 for n in nodes if n["state"] == TaskState.DONE.value)
            failed = sum(1 for n in nodes if n["state"] == TaskState.FAILED.value)
            pending = sum(1 for n in nodes if n["state"] == TaskState.INBOX.value)

            return {
                "dag_id": dag_id,
                "total": total,
                "done": done,
                "failed": failed,
                "pending": pending,
                "progress": done / total if total > 0 else 0,
                "nodes": nodes,
            }

    # ---- 工作流适配 ----

    def register_workflow(self, workflow: WorkflowDefinition) -> None:
        """注册工作流定义"""
        self._workflow_engine.register_workflow(workflow)
        _logger.agent(f"Workflow registered: {workflow.name}")

    async def execute_workflow(
        self,
        workflow_name: str,
        initial_data: Dict[str, Any],
    ) -> Optional[str]:
        """执行命名工作流（适配旧 WorkflowOrchestrator）

        Returns:
            任务ID
        """
        workflow = self._workflow_engine._workflows.get(workflow_name)
        if not workflow:
            return None

        # 将工作流阶段转换为 DAG 节点
        nodes = []
        stage_map: Dict[str, DAGTaskNode] = {}

        for stage in workflow.stages:
            node = DAGTaskNode(
                task_id=str(uuid.uuid4()),
                agent_name=stage.agent_name,
                payload={
                    "stage_name": stage.name,
                    "input_mapping": stage.input_mapping,
                    "output_mapping": stage.output_mapping,
                    "initial_data": initial_data,
                },
                priority=TaskPriority.NORMAL,
            )
            stage_map[stage.name] = node
            nodes.append(node)

        # 建立依赖关系
        for stage in workflow.stages:
            node = stage_map[stage.name]
            # 根据 input_mapping 推断依赖
            for source in stage.input_mapping.values():
                if source.startswith("output."):
                    # 依赖前一阶段的输出
                    prev_stage = self._find_source_stage(workflow, source)
                    if prev_stage and prev_stage.name in stage_map:
                        dep_id = stage_map[prev_stage.name].task_id
                        if dep_id not in node.dependencies:
                            node.dependencies.append(dep_id)

        # 如果没有推断出依赖，按顺序依赖
        if all(len(n.dependencies) == 0 for n in nodes[1:]):
            for i in range(1, len(nodes)):
                nodes[i].dependencies.append(nodes[i - 1].task_id)

        dag_id = await self.submit_dag(nodes)
        return dag_id

    def _find_source_stage(
        self, workflow: WorkflowDefinition, source: str
    ) -> Optional[WorkflowStage]:
        """查找数据源阶段"""
        # 简化：output.xxx 对应某阶段的 output_mapping 中的 target
        path = source.replace("output.", "").split(".")[0]
        for stage in workflow.stages:
            for key, target in stage.output_mapping.items():
                if target.startswith(f"output.{path}"):
                    return stage
        return None

    # ---- 统计与健康 ----

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            **self._stats,
            "queue_size": self._queue.qsize() if hasattr(self._queue, "qsize") else 0,
            "workers": len(self._workers),
            "available_workers": len(self.get_available_workers()),
            "dag_nodes": len(self._dag_nodes),
            "results_cached": len(self._results),
        }

    def get_health(self) -> Dict[str, Any]:
        """健康检查"""
        workers = self.list_workers()
        idle_count = sum(1 for w in workers if w["idle"])
        busy_count = sum(1 for w in workers if not w["idle"])

        return {
            "running": self._running,
            "workers_total": len(workers),
            "workers_idle": idle_count,
            "workers_busy": busy_count,
            "dispatcher_alive": (
                self._dispatcher_task is not None and not self._dispatcher_task.done()
            ),
            "stats": self.get_stats(),
        }

    def clear_results(self) -> None:
        """清空结果缓存"""
        self._results.clear()
