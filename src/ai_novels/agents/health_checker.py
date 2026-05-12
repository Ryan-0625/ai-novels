"""
HealthCheckerAgent - 健康检查智能体（已废弃）

@file: agents/health_checker.py
@date: 2026-03-12
@author: AI-Novels Team
@version: 1.0
@description: 组件健康检查 — 请使用 ai_novels.utils.health_checker 替代
"""

import warnings
import time

warnings.warn(
    "HealthCheckerAgent is deprecated. "
    "Use ai_novels.utils.health_checker.check_component_health() "
    "or ai_novels.utils.health_checker.check_system_health() instead.",
    DeprecationWarning,
    stacklevel=2,
)
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from enum import Enum

from .base import BaseAgent, AgentConfig, Message, MessageType


class ComponentType(Enum):
    """组件类型"""
    DATABASE = "database"
    LLM = "llm"
    MESSAGE_QUEUE = "message_queue"
    CACHE = "cache"
    FILE_SYSTEM = "file_system"


class HealthStatus(Enum):
    """健康状态"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class ComponentHealth:
    """组件健康状态"""
    name: str
    component_type: ComponentType
    status: HealthStatus
    latency_ms: int
    details: Dict[str, Any]
    last_check: float

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "type": self.component_type.value,
            "status": self.status.value,
            "latency_ms": self.latency_ms,
            "details": self.details,
            "last_check": self.last_check
        }


class HealthCheckerAgent(BaseAgent):
    """
    健康检查智能体

    核心功能：
    - 检查所有组件健康状态
    - 监控数据库连接
    - 检查LLM服务可用性
    - 监控消息队列
    - 生成健康报告
    """

    def __init__(self, config: AgentConfig = None):
        if config is None:
            config = AgentConfig(
                name="health_checker",
                description="System health monitoring",
                provider="ollama",
                model="qwen2.5-7b",
                max_tokens=2048
            )
        super().__init__(config)

        # 组件健康状态存储
        self._components: Dict[str, ComponentHealth] = {}

        # 默认组件列表
        self._default_components = [
            ComponentHealth("mysql", ComponentType.DATABASE, HealthStatus.UNHEALTHY, 0, {}, 0),
            ComponentHealth("neo4j", ComponentType.DATABASE, HealthStatus.UNHEALTHY, 0, {}, 0),
            ComponentHealth("mongodb", ComponentType.DATABASE, HealthStatus.UNHEALTHY, 0, {}, 0),
            ComponentHealth("chromadb", ComponentType.DATABASE, HealthStatus.UNHEALTHY, 0, {}, 0),
            ComponentHealth("rocketmq", ComponentType.MESSAGE_QUEUE, HealthStatus.UNHEALTHY, 0, {}, 0),
            ComponentHealth("ollama", ComponentType.LLM, HealthStatus.UNHEALTHY, 0, {}, 0),
            ComponentHealth("openai", ComponentType.LLM, HealthStatus.UNHEALTHY, 0, {}, 0),
        ]

        # 初始化组件列表
        for component in self._default_components:
            self._components[component.name] = component

        self._last_full_check = 0
        self._check_interval = 60  # 秒

    def process(self, message: Message) -> Message:
        """处理消息 - 健康检查"""
        content = str(message.content).lower()

        if "check" in content:
            return self._handle_check_request(message)
        elif "status" in content:
            return self._handle_status_request(message)
        elif "list" in content:
            return self._handle_list_request(message)
        elif "reset" in content:
            return self._handle_reset_request(message)
        else:
            return self._handle_check_request(message)

    def _handle_check_request(self, message: Message) -> Message:
        """处理检查请求"""
        content = str(message.content)

        # 确定检查范围
        if "all" in content or "system" in content:
            return self._check_all_components()

        elif "database" in content:
            return self._check_databases()

        elif "llm" in content:
            return self._check_llm()

        elif "queue" in content or "rocketmq" in content:
            return self._check_message_queue()

        else:
            return self._check_all_components()

    def _handle_status_request(self, message: Message) -> Message:
        """处理状态请求"""
        # 获取所有组件状态
        status = self._get_overall_status()

        response_lines = ["=== System Health Status ===", ""]
        response_lines.append(f"Overall Status: {status['overall'].value.upper()}")
        response_lines.append(f"Checked: {time.ctime(status['last_check'])}")
        response_lines.append(f"Components: {status['total']} total, {status['healthy']} healthy")

        # 细分状态
        response_lines.append("")
        response_lines.append("Component Status:")

        for name, health in self._components.items():
            icon = {"healthy": "✓", "degraded": "⚠", "unhealthy": "✗"}[health.status.value]
            response_lines.append(f"  {icon} {name}: {health.status.value} ({health.latency_ms}ms)")

        return self._create_message(
            "\n".join(response_lines),
            MessageType.TEXT,
            overall_status=status["overall"].value,
            component_count=status["total"]
        )

    def _handle_list_request(self, message: Message) -> Message:
        """处理列表请求"""
        content = str(message.content).lower()

        if "database" in content:
            components = [c for c in self._components.values() if c.component_type == ComponentType.DATABASE]
        elif "llm" in content:
            components = [c for c in self._components.values() if c.component_type == ComponentType.LLM]
        elif "queue" in content:
            components = [c for c in self._components.values() if c.component_type == ComponentType.MESSAGE_QUEUE]
        else:
            components = list(self._components.values())

        response_lines = ["Registered Components:"]
        for c in components:
            response_lines.append(f"  - {c.name} ({c.component_type.value})")

        return self._create_message(
            "\n".join(response_lines),
            MessageType.TEXT,
            component_count=len(components)
        )

    def _handle_reset_request(self, message: Message) -> Message:
        """处理重置请求"""
        # 重置所有组件状态
        for name in self._components:
            self._components[name] = ComponentHealth(
                name=name,
                component_type=ComponentType.DATABASE if "db" in name else ComponentType.LLM,
                status=HealthStatus.UNHEALTHY,
                latency_ms=0,
                details={},
                last_check=0
            )

        self._last_full_check = 0

        return self._create_message(
            "Health checker reset. All components marked as unhealthy.",
            MessageType.TEXT,
            reset_components=len(self._components)
        )

    def _handle_general_request(self, message: Message) -> Message:
        """处理一般请求"""
        response = (
            "Health Checker available commands:\n"
            "- 'check all' - 检查所有组件\n"
            "- 'check database' - 检查数据库\n"
            "- 'check llm' - 检查LLM服务\n"
            "- 'check queue' - 检查消息队列\n"
            "- 'status' - 查看整体状态\n"
            "- 'list' - 列出所有组件"
        )
        return self._create_message(response)

    def _check_all_components(self) -> Message:
        """检查所有组件"""
        self._last_full_check = time.time()

        results = []
        for name, component in self._components.items():
            health = self._check_component(name, component.component_type)
            self._components[name] = health
            results.append(health)

        overall = self._calculate_overall_status(results)
        self._components["_overall"] = ComponentHealth(
            name="system",
            component_type=ComponentType.DATABASE,
            status=overall,
            latency_ms=0,
            details={},
            last_check=self._last_full_check
        )

        response = self._format_check_results(results, overall)

        return self._create_message(
            response,
            MessageType.TEXT,
            overall_status=overall.value,
            components_checked=len(results)
        )

    def _check_databases(self) -> Message:
        """检查数据库"""
        db_components = [c for c in self._components.values() if c.component_type == ComponentType.DATABASE]
        results = []

        for component in db_components:
            health = self._check_component(component.name, ComponentType.DATABASE)
            self._components[component.name] = health
            results.append(health)

        overall = self._calculate_overall_status(results)

        response = "Database Health Check:\n"
        for r in results:
            icon = {"healthy": "✓", "degraded": "⚠", "unhealthy": "✗"}[r.status.value]
            response += f"  {icon} {r.name}: {r.status.value} ({r.latency_ms}ms)\n"

        return self._create_message(
            response,
            MessageType.TEXT,
            overall_status=overall.value,
            databases_checked=len(results)
        )

    def _check_llm(self) -> Message:
        """检查LLM服务"""
        llm_components = [c for c in self._components.values() if c.component_type == ComponentType.LLM]
        results = []

        for component in llm_components:
            health = self._check_component(component.name, ComponentType.LLM)
            self._components[component.name] = health
            results.append(health)

        overall = self._calculate_overall_status(results)

        response = "LLM Service Health Check:\n"
        for r in results:
            icon = {"healthy": "✓", "degraded": "⚠", "unhealthy": "✗"}[r.status.value]
            response += f"  {icon} {r.name}: {r.status.value} ({r.latency_ms}ms)\n"

        return self._create_message(
            response,
            MessageType.TEXT,
            overall_status=overall.value,
            llms_checked=len(results)
        )

    def _check_message_queue(self) -> Message:
        """检查消息队列"""
        mq_components = [c for c in self._components.values() if c.component_type == ComponentType.MESSAGE_QUEUE]
        results = []

        for component in mq_components:
            health = self._check_component(component.name, ComponentType.MESSAGE_QUEUE)
            self._components[component.name] = health
            results.append(health)

        overall = self._calculate_overall_status(results)

        response = "Message Queue Health Check:\n"
        for r in results:
            icon = {"healthy": "✓", "degraded": "⚠", "unhealthy": "✗"}[r.status.value]
            response += f"  {icon} {r.name}: {r.status.value} ({r.latency_ms}ms)\n"

        return self._create_message(
            response,
            MessageType.TEXT,
            overall_status=overall.value,
            queues_checked=len(results)
        )

    def _check_component(self, name: str, component_type: ComponentType) -> ComponentHealth:
        """检查单个组件（实际网络/连接检查）"""
        start_time = time.time()

        services = {
            "mysql":      ("localhost", 3306, "MySQL"),
            "neo4j":      ("localhost", 7687, "Neo4j"),
            "mongodb":    ("localhost", 27017, "MongoDB"),
            "chromadb":   ("localhost", 8000, "ChromaDB"),
            "rocketmq":   ("localhost", 9876, "RocketMQ"),
        }

        try:
            details = {}
            status = HealthStatus.UNHEALTHY

            if name in services:
                host, port, label = services[name]
                ok, lat = self._try_tcp_connect(host, port)
                details = {"host": host, "port": port}
                if ok:
                    status = HealthStatus.HEALTHY
                else:
                    details["error"] = f"{label} ({host}:{port}) 连接失败"
            elif "ollama" in name:
                ok, lat, details = self._try_http_connect("http://localhost:11434/api/tags")
                status = HealthStatus.HEALTHY if ok else HealthStatus.UNHEALTHY
            elif "openai" in name:
                import os
                api_key = os.environ.get("OPENAI_API_KEY", "")
                if api_key:
                    ok, lat, details = self._try_http_connect(
                        "https://api.openai.com/v1/models",
                        headers={"Authorization": f"Bearer {api_key}"}
                    )
                else:
                    lat = 0
                    details = {"error": "OPENAI_API_KEY not set"}
                status = HealthStatus.HEALTHY if ok else HealthStatus.UNHEALTHY
            else:
                lat = 0
                details = {"error": f"Unknown component: {name}"}

            total_latency = lat or int((time.time() - start_time) * 1000)
            return ComponentHealth(
                name=name, component_type=component_type, status=status,
                latency_ms=total_latency, details=details, last_check=time.time()
            )
        except Exception as e:
            return ComponentHealth(
                name=name, component_type=component_type, status=HealthStatus.UNHEALTHY,
                latency_ms=int((time.time() - start_time) * 1000),
                details={"error": str(e)}, last_check=time.time()
            )

    @staticmethod
    def _try_tcp_connect(host: str, port: int, timeout: int = 3):
        """尝试TCP端口连接"""
        import socket, time
        start = time.time()
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        try:
            result = sock.connect_ex((host, port))
            elapsed = int((time.time() - start) * 1000)
            return result == 0, elapsed
        finally:
            sock.close()

    @staticmethod
    def _try_http_connect(url: str, headers: dict = None, timeout: int = 5):
        """尝试HTTP连接"""
        import urllib.request, json, time
        start = time.time()
        req = urllib.request.Request(url, headers=headers or {})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                elapsed = int((time.time() - start) * 1000)
                body = resp.read().decode()
                try:
                    details = json.loads(body)
                    if isinstance(details, dict):
                        pass
                    details["http_status"] = resp.status
                except (json.JSONDecodeError, TypeError):
                    details = {"http_status": resp.status}
                return True, elapsed, details
        except Exception as e:
            elapsed = int((time.time() - start) * 1000)
            return False, elapsed, {"error": str(e)}

    def _calculate_overall_status(self, results: List[ComponentHealth]) -> HealthStatus:
        """计算整体健康状态"""
        if not results:
            return HealthStatus.UNHEALTHY

        unhealthy_count = sum(1 for r in results if r.status == HealthStatus.UNHEALTHY)
        degraded_count = sum(1 for r in results if r.status == HealthStatus.DEGRADED)

        if unhealthy_count > 0:
            return HealthStatus.UNHEALTHY
        elif degraded_count > len(results) // 2:
            return HealthStatus.DEGRADED
        else:
            return HealthStatus.HEALTHY

    def _get_overall_status(self) -> Dict[str, Any]:
        """获取整体状态"""
        results = list(self._components.values())

        overall = self._calculate_overall_status(results)

        return {
            "overall": overall,
            "healthy": sum(1 for r in results if r.status == HealthStatus.HEALTHY),
            "degraded": sum(1 for r in results if r.status == HealthStatus.DEGRADED),
            "unhealthy": sum(1 for r in results if r.status == HealthStatus.UNHEALTHY),
            "total": len(results),
            "last_check": self._last_full_check
        }

    def _format_check_results(self, results: List[ComponentHealth], overall: HealthStatus) -> str:
        """格式化检查结果"""
        lines = ["=== Health Check Results ===", ""]
        lines.append(f"Overall Status: {overall.value.upper()}")
        lines.append(f"Checked: {time.ctime()}")

        # 按类型分组
        by_type = {}
        for r in results:
            if r.component_type not in by_type:
                by_type[r.component_type] = []
            by_type[r.component_type].append(r)

        for comp_type, comp_results in by_type.items():
            lines.append("")
            lines.append(f"{comp_type.value.upper()}:")
            for r in comp_results:
                icon = {"healthy": "✓", "degraded": "⚠", "unhealthy": "✗"}[r.status.value]
                lines.append(f"  {icon} {r.name}: {r.status.value} ({r.latency_ms}ms)")

        return "\n".join(lines)

    def get_component_health(self, name: str) -> Optional[ComponentHealth]:
        """获取组件健康状态"""
        return self._components.get(name)

    def get_overall_health(self) -> ComponentHealth:
        """获取整体健康状态"""
        return self._components.get("_overall")

    def register_component(self, name: str, component_type: ComponentType) -> bool:
        """注册组件"""
        if name in self._components:
            return False
        self._components[name] = ComponentHealth(
            name=name,
            component_type=component_type,
            status=HealthStatus.UNHEALTHY,
            latency_ms=0,
            details={},
            last_check=0
        )
        return True

    def deregister_component(self, name: str) -> bool:
        """注销组件"""
        if name in self._components and name != "_overall":
            del self._components[name]
            return True
        return False

    def reset(self) -> None:
        """重置健康检查器"""
        for name in self._components:
            if name != "_overall":
                self._components[name] = ComponentHealth(
                    name=name,
                    component_type=ComponentType.DATABASE,
                    status=HealthStatus.UNHEALTHY,
                    latency_ms=0,
                    details={},
                    last_check=0
                )
        self._last_full_check = 0
