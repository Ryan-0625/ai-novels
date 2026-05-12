"""
系统健康检查服务

@file: services/health_service.py
@date: 2026-03-18
@version: 1.0
@description: 统一的系统健康检查服务，检测所有组件状态
"""

import time
import os
import traceback
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

from ..database.mysql_client import MySQLClient
from ..database.neo4j_client import Neo4jClient
from ..database.mongodb_client import MongoDBClient
from ..database.chromadb_client import ChromaDBClient
from ..messaging.rocketmq_producer import RocketMQProducer, RocketMQConfig
from ..messaging.rocketmq_consumer import RocketMQConsumer, ConsumerConfig
from ..llm.router import get_llm_router, LLMRouter
from ..utils import get_logger


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
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "type": self.component_type.value,
            "status": self.status.value,
            "latency_ms": self.latency_ms,
            "details": self.details,
            "last_check": self.last_check,
            "error": self.error
        }


class HealthService:
    """
    系统健康检查服务

    检测组件:
    - MySQL
    - Neo4j
    - MongoDB
    - ChromaDB
    - RocketMQ (Producer & Consumer)
    - Ollama (LLM)
    """

    def __init__(self):
        """初始化健康检查服务"""
        self._logger = get_logger()
        self._components: Dict[str, ComponentHealth] = {}
        self._clients: Dict[str, Any] = {}
        self._last_full_check = 0
        self._check_interval = 60  # 秒
        self._timeout = 120  # 秒 - 增加超时时间，避免 Ollama 误判

        # 初始化组件列表
        self._init_components()

    def _init_components(self):
        """初始化组件列表"""
        # 数据库组件
        self._components["mysql"] = ComponentHealth(
            name="mysql",
            component_type=ComponentType.DATABASE,
            status=HealthStatus.UNHEALTHY,
            latency_ms=0,
            details={},
            last_check=0
        )
        self._components["neo4j"] = ComponentHealth(
            name="neo4j",
            component_type=ComponentType.DATABASE,
            status=HealthStatus.UNHEALTHY,
            latency_ms=0,
            details={},
            last_check=0
        )
        self._components["mongodb"] = ComponentHealth(
            name="mongodb",
            component_type=ComponentType.DATABASE,
            status=HealthStatus.UNHEALTHY,
            latency_ms=0,
            details={},
            last_check=0
        )
        self._components["chromadb"] = ComponentHealth(
            name="chromadb",
            component_type=ComponentType.DATABASE,
            status=HealthStatus.UNHEALTHY,
            latency_ms=0,
            details={},
            last_check=0
        )

        # 消息队列组件
        self._components["rocketmq_producer"] = ComponentHealth(
            name="rocketmq_producer",
            component_type=ComponentType.MESSAGE_QUEUE,
            status=HealthStatus.UNHEALTHY,
            latency_ms=0,
            details={},
            last_check=0
        )
        self._components["rocketmq_consumer"] = ComponentHealth(
            name="rocketmq_consumer",
            component_type=ComponentType.MESSAGE_QUEUE,
            status=HealthStatus.UNHEALTHY,
            latency_ms=0,
            details={},
            last_check=0
        )

        # LLM组件
        self._components["ollama"] = ComponentHealth(
            name="ollama",
            component_type=ComponentType.LLM,
            status=HealthStatus.UNHEALTHY,
            latency_ms=0,
            details={},
            last_check=0
        )

    def _get_mysql_client(self) -> MySQLClient:
        """获取MySQL客户端"""
        if "mysql" not in self._clients:
            from ai_novels.config.manager import settings
            db_config = settings.get_database("mysql")
            self._clients["mysql"] = MySQLClient(config=db_config)
        return self._clients["mysql"]

    def _get_neo4j_client(self) -> Neo4jClient:
        """获取Neo4j客户端"""
        if "neo4j" not in self._clients:
            from ai_novels.config.manager import settings
            db_config = settings.get_database("neo4j")
            self._clients["neo4j"] = Neo4jClient(config=db_config)
        return self._clients["neo4j"]

    def _get_mongodb_client(self) -> MongoDBClient:
        """获取MongoDB客户端"""
        if "mongodb" not in self._clients:
            from ai_novels.config.manager import settings
            db_config = settings.get_database("mongodb")
            self._clients["mongodb"] = MongoDBClient(config=db_config)
        return self._clients["mongodb"]

    def _get_chromadb_client(self) -> ChromaDBClient:
        """获取ChromaDB客户端"""
        if "chromadb" not in self._clients:
            from ai_novels.config.manager import settings
            db_config = settings.get_database("chromadb")
            self._clients["chromadb"] = ChromaDBClient(config=db_config)
            # 初始化时建立连接
            if not self._clients["chromadb"].connect():
                pass  # 连接失败会在health_check中处理
        return self._clients["chromadb"]

    def _get_producer(self) -> Optional[RocketMQProducer]:
        """获取RocketMQ生产者"""
        if "producer" not in self._clients:
            try:
                from ai_novels.config.manager import settings
                msg_config = settings.get("messaging", {})
                rocketmq_config = msg_config.get("rocketmq", {})
                name_server = rocketmq_config.get("name_server", os.environ.get("ROCKETMQ_NS", "localhost:19876"))

                config = RocketMQConfig(
                    name_server=name_server,
                    group_name="ai_novels_health_check"
                )
                producer = RocketMQProducer(config)
                if producer.connect():
                    self._clients["producer"] = producer
            except Exception:
                pass
        return self._clients.get("producer")

    def _get_consumer(self) -> Optional[RocketMQConsumer]:
        """获取RocketMQ消费者"""
        if "consumer" not in self._clients:
            try:
                from ai_novels.config.manager import settings
                msg_config = settings.get("messaging", {})
                rocketmq_config = msg_config.get("rocketmq", {})
                name_server = rocketmq_config.get("name_server", os.environ.get("ROCKETMQ_NS", "localhost:19876"))

                config = ConsumerConfig(
                    name_server=name_server,
                    consumer_group="ai_novels_health_check"
                )
                consumer = RocketMQConsumer(config)
                if consumer.connect():
                    self._clients["consumer"] = consumer
            except Exception:
                pass
        return self._clients.get("consumer")

    def _check_mysql(self) -> ComponentHealth:
        """检查MySQL"""
        start_time = time.time()
        try:
            self._logger.database_debug("Health check: MySQL")
            client = self._get_mysql_client()
            health = client.health_check()
            latency_ms = int((time.time() - start_time) * 1000)

            self._logger.database(f"Health check: MySQL {'healthy' if health.get('status') == 'healthy' else 'unhealthy'} [{latency_ms}ms]")
            return ComponentHealth(
                name="mysql",
                component_type=ComponentType.DATABASE,
                status=HealthStatus.HEALTHY if health.get("status") == "healthy" else HealthStatus.UNHEALTHY,
                latency_ms=latency_ms,
                details=health.get("details", {}),
                last_check=time.time(),
                error=health.get("error") if health.get("status") != "healthy" else None
            )
        except Exception as e:
            return ComponentHealth(
                name="mysql",
                component_type=ComponentType.DATABASE,
                status=HealthStatus.UNHEALTHY,
                latency_ms=int((time.time() - start_time) * 1000),
                details={"error": str(e), "traceback": traceback.format_exc()},
                last_check=time.time(),
                error=f"MySQL check failed: {str(e)}"
            )

    def _check_neo4j(self) -> ComponentHealth:
        """检查Neo4j"""
        start_time = time.time()
        try:
            self._logger.database_debug("Health check: Neo4j")
            client = self._get_neo4j_client()
            health = client.health_check()
            latency_ms = int((time.time() - start_time) * 1000)

            self._logger.database(f"Health check: Neo4j {'healthy' if health.get('status') == 'healthy' else 'unhealthy'} [{latency_ms}ms]")
            return ComponentHealth(
                name="neo4j",
                component_type=ComponentType.DATABASE,
                status=HealthStatus.HEALTHY if health.get("status") == "healthy" else HealthStatus.UNHEALTHY,
                latency_ms=latency_ms,
                details=health.get("details", {}),
                last_check=time.time(),
                error=health.get("error") if health.get("status") != "healthy" else None
            )
        except Exception as e:
            return ComponentHealth(
                name="neo4j",
                component_type=ComponentType.DATABASE,
                status=HealthStatus.UNHEALTHY,
                latency_ms=int((time.time() - start_time) * 1000),
                details={"error": str(e), "traceback": traceback.format_exc()},
                last_check=time.time(),
                error=f"Neo4j check failed: {str(e)}"
            )

    def _check_mongodb(self) -> ComponentHealth:
        """检查MongoDB"""
        start_time = time.time()
        try:
            self._logger.database_debug("Health check: MongoDB")
            client = self._get_mongodb_client()
            health = client.health_check()
            latency_ms = int((time.time() - start_time) * 1000)

            self._logger.database(f"Health check: MongoDB {'healthy' if health.get('status') == 'healthy' else 'unhealthy'} [{latency_ms}ms]")
            return ComponentHealth(
                name="mongodb",
                component_type=ComponentType.DATABASE,
                status=HealthStatus.HEALTHY if health.get("status") == "healthy" else HealthStatus.UNHEALTHY,
                latency_ms=latency_ms,
                details=health.get("details", {}),
                last_check=time.time(),
                error=health.get("error") if health.get("status") != "healthy" else None
            )
        except Exception as e:
            return ComponentHealth(
                name="mongodb",
                component_type=ComponentType.DATABASE,
                status=HealthStatus.UNHEALTHY,
                latency_ms=int((time.time() - start_time) * 1000),
                details={"error": str(e), "traceback": traceback.format_exc()},
                last_check=time.time(),
                error=f"MongoDB check failed: {str(e)}"
            )

    def _check_chromadb(self) -> ComponentHealth:
        """检查ChromaDB（带自动重连）"""
        start_time = time.time()
        try:
            self._logger.database_debug("Health check: ChromaDB")
            client = self._get_chromadb_client()

            # 使用带自动重连的健康检查方法
            health = client.health_check_with_reconnect(max_retries=2)
            latency_ms = int((time.time() - start_time) * 1000)

            self._logger.database(f"Health check: ChromaDB {'healthy' if health.get('status') == 'healthy' else 'unhealthy'} [{latency_ms}ms]")
            return ComponentHealth(
                name="chromadb",
                component_type=ComponentType.DATABASE,
                status=HealthStatus.HEALTHY if health.get("status") == "healthy" else HealthStatus.UNHEALTHY,
                latency_ms=latency_ms,
                details=health.get("details", {}),
                last_check=time.time(),
                error=health.get("error") if health.get("status") != "healthy" else None
            )
        except Exception as e:
            return ComponentHealth(
                name="chromadb",
                component_type=ComponentType.DATABASE,
                status=HealthStatus.UNHEALTHY,
                latency_ms=int((time.time() - start_time) * 1000),
                details={
                    "error": str(e),
                    "traceback": traceback.format_exc()
                },
                last_check=time.time(),
                error=f"ChromaDB check failed: {str(e)}"
            )

    def _check_rocketmq_producer(self) -> ComponentHealth:
        """检查RocketMQ生产者"""
        start_time = time.time()
        try:
            producer = self._get_producer()
            if producer is None:
                return ComponentHealth(
                    name="rocketmq_producer",
                    component_type=ComponentType.MESSAGE_QUEUE,
                    status=HealthStatus.UNHEALTHY,
                    latency_ms=int((time.time() - start_time) * 1000),
                    details={},
                    last_check=time.time(),
                    error="Producer not initialized"
                )

            health = producer.health_check()
            latency_ms = int((time.time() - start_time) * 1000)

            return ComponentHealth(
                name="rocketmq_producer",
                component_type=ComponentType.MESSAGE_QUEUE,
                status=HealthStatus.HEALTHY if health.get("status") == "healthy" else HealthStatus.UNHEALTHY,
                latency_ms=latency_ms,
                details=health.get("details", {}),
                last_check=time.time(),
                error=None
            )
        except Exception as e:
            return ComponentHealth(
                name="rocketmq_producer",
                component_type=ComponentType.MESSAGE_QUEUE,
                status=HealthStatus.UNHEALTHY,
                latency_ms=int((time.time() - start_time) * 1000),
                details={"error": str(e), "traceback": traceback.format_exc()},
                last_check=time.time(),
                error=f"RocketMQ Producer check failed: {str(e)}"
            )

    def _check_rocketmq_consumer(self) -> ComponentHealth:
        """检查RocketMQ消费者"""
        start_time = time.time()
        try:
            consumer = self._get_consumer()
            if consumer is None:
                return ComponentHealth(
                    name="rocketmq_consumer",
                    component_type=ComponentType.MESSAGE_QUEUE,
                    status=HealthStatus.UNHEALTHY,
                    latency_ms=int((time.time() - start_time) * 1000),
                    details={},
                    last_check=time.time(),
                    error="Consumer not initialized"
                )

            health = consumer.health_check()
            latency_ms = int((time.time() - start_time) * 1000)

            return ComponentHealth(
                name="rocketmq_consumer",
                component_type=ComponentType.MESSAGE_QUEUE,
                status=HealthStatus.HEALTHY if health.get("status") == "healthy" else HealthStatus.UNHEALTHY,
                latency_ms=latency_ms,
                details=health.get("details", {}),
                last_check=time.time(),
                error=None
            )
        except Exception as e:
            return ComponentHealth(
                name="rocketmq_consumer",
                component_type=ComponentType.MESSAGE_QUEUE,
                status=HealthStatus.UNHEALTHY,
                latency_ms=int((time.time() - start_time) * 1000),
                details={"error": str(e), "traceback": traceback.format_exc()},
                last_check=time.time(),
                error=f"RocketMQ Consumer check failed: {str(e)}"
            )

    def _check_ollama(self) -> ComponentHealth:
        """检查Ollama LLM服务"""
        start_time = time.time()
        try:
            from ai_novels.config.manager import settings
            # Router's initialize() does self._config.get("llm", {}) then iterates items()
            # So we need to wrap the llm config under "llm" key
            llm_config = {"llm": settings.get("llm", {})}

            # Force reinitialize to ensure fresh config is loaded
            router = get_llm_router(llm_config, force_init=True)

            # DEBUG: Log router info
            import logging
            logging.info(f"Ollama health check - Router clients: {list(router._load_balancer._clients.keys())}")
            logging.info(f"Ollama health check - Router config keys: {list(llm_config.get('llm', {}).keys())}")

            # 获取客户端并检查健康状态
            # 使用 load_balancer.get_client_by_name 直接按名称获取，不检查健康状态
            client = router._load_balancer.get_client_by_name("ollama")
            if client is None:
                # Try get_client (which filters by health)
                client = router.get_client("ollama")
            if client is None:
                self._logger.llm_error("Ollama client not found")
                return ComponentHealth(
                    name="ollama",
                    component_type=ComponentType.LLM,
                    status=HealthStatus.UNHEALTHY,
                    latency_ms=int((time.time() - start_time) * 1000),
                    details={"error": "Ollama client not found"},
                    last_check=time.time(),
                    error="Ollama client not found"
                )

            # 执行健康检查
            self._logger.llm_debug("Health check: Ollama")
            health = client.health_check()
            latency_ms = int((time.time() - start_time) * 1000)

            self._logger.llm(f"Health check: Ollama {'healthy' if health.get('status') == 'healthy' else 'unhealthy'} [{latency_ms}ms]")

            # 收集详细信息
            details = health.get("details", {}).copy() if health.get("details") else {}
            details["model"] = health.get("model", "qwen2.5-7b")
            details["provider"] = health.get("provider", "ollama")

            return ComponentHealth(
                name="ollama",
                component_type=ComponentType.LLM,
                status=HealthStatus.HEALTHY if health.get("status") == "healthy" else HealthStatus.UNHEALTHY,
                latency_ms=latency_ms,
                details=details,
                last_check=time.time(),
                error=health.get("error") if health.get("status") != "healthy" else None
            )
        except Exception as e:
            import traceback
            return ComponentHealth(
                name="ollama",
                component_type=ComponentType.LLM,
                status=HealthStatus.UNHEALTHY,
                latency_ms=int((time.time() - start_time) * 1000),
                details={"error": str(e), "traceback": traceback.format_exc()},
                last_check=time.time(),
                error=f"Ollama check failed: {str(e)}"
            )

    def _execute_check(self, component_name: str) -> ComponentHealth:
        """执行单个组件的健康检查"""
        check_map = {
            "mysql": self._check_mysql,
            "neo4j": self._check_neo4j,
            "mongodb": self._check_mongodb,
            "chromadb": self._check_chromadb,
            "rocketmq_producer": self._check_rocketmq_producer,
            "rocketmq_consumer": self._check_rocketmq_consumer,
            "ollama": self._check_ollama,
        }

        check_func = check_map.get(component_name)
        if check_func:
            return check_func()
        return ComponentHealth(
            name=component_name,
            component_type=ComponentType.DATABASE,
            status=HealthStatus.UNHEALTHY,
            latency_ms=0,
            details={},
            last_check=time.time(),
            error=f"No check function for {component_name}"
        )

    def check_all(self) -> Dict[str, Any]:
        """
        检查所有组件健康状态

        Returns:
            Dict: 健康检查结果
        """
        self._logger.system("Starting system health check")
        # 如果距离上次检查时间较短，返回缓存结果
        if time.time() - self._last_full_check < self._check_interval:
            self._logger.system("Health check: returning cached results")
            return self._get_result()

        # 并发执行健康检查
        components_to_check = list(self._components.keys())
        self._logger.system(f"Health check: checking {len(components_to_check)} components")
        results = {}

        with ThreadPoolExecutor(max_workers=7) as executor:
            future_to_component = {
                executor.submit(self._execute_check, name): name
                for name in components_to_check
            }

            for future in future_to_component:
                component_name = future_to_component[future]
                try:
                    health = future.result(timeout=self._timeout)
                    self._components[component_name] = health
                    results[component_name] = health
                except FuturesTimeoutError:
                    self._components[component_name] = ComponentHealth(
                        name=component_name,
                        component_type=ComponentType.DATABASE,
                        status=HealthStatus.UNHEALTHY,
                        latency_ms=0,
                        details={},
                        last_check=time.time(),
                        error="Check timeout"
                    )
                    results[component_name] = self._components[component_name]
                except Exception as e:
                    self._components[component_name] = ComponentHealth(
                        name=component_name,
                        component_type=ComponentType.DATABASE,
                        status=HealthStatus.UNHEALTHY,
                        latency_ms=0,
                        details={},
                        last_check=time.time(),
                        error=str(e)
                    )
                    results[component_name] = self._components[component_name]

        self._last_full_check = time.time()

        overall = self._get_overall_status()
        self._logger.system(f"Health check completed: overall status={overall.value}")
        return self._get_result()

    def check_single(self, component_name: str) -> ComponentHealth:
        """
        检查单个组件

        Args:
            component_name: 组件名称

        Returns:
            ComponentHealth: 健康状态
        """
        health = self._execute_check(component_name)
        self._components[component_name] = health
        return health

    def _get_overall_status(self) -> HealthStatus:
        """计算整体健康状态"""
        unhealthy_count = sum(
            1 for c in self._components.values()
            if c.status == HealthStatus.UNHEALTHY
        )
        degraded_count = sum(
            1 for c in self._components.values()
            if c.status == HealthStatus.DEGRADED
        )

        if unhealthy_count > 0:
            return HealthStatus.UNHEALTHY
        elif degraded_count > len(self._components) // 2:
            return HealthStatus.DEGRADED
        else:
            return HealthStatus.HEALTHY

    def _get_result(self) -> Dict[str, Any]:
        """获取检查结果"""
        overall = self._get_overall_status()

        return {
            "overall_status": overall.value,
            "overall_status_code": 200 if overall == HealthStatus.HEALTHY else (503 if overall == HealthStatus.UNHEALTHY else 200),
            "components": {name: health.to_dict() for name, health in self._components.items()},
            "last_check": self._last_full_check,
            "component_count": len(self._components),
            "healthy_count": sum(1 for c in self._components.values() if c.status == HealthStatus.HEALTHY),
            "degraded_count": sum(1 for c in self._components.values() if c.status == HealthStatus.DEGRADED),
            "unhealthy_count": sum(1 for c in self._components.values() if c.status == HealthStatus.UNHEALTHY)
        }

    def get_overall_health(self) -> ComponentHealth:
        """获取整体健康状态"""
        return ComponentHealth(
            name="system",
            component_type=ComponentType.DATABASE,
            status=self._get_overall_status(),
            latency_ms=0,
            details={},
            last_check=self._last_full_check
        )

    def get_component_health(self, name: str) -> Optional[ComponentHealth]:
        """获取组件健康状态"""
        return self._components.get(name)

    def reset(self) -> None:
        """重置健康检查服务"""
        for name in self._components:
            self._components[name] = ComponentHealth(
                name=name,
                component_type=ComponentType.DATABASE,
                status=HealthStatus.UNHEALTHY,
                latency_ms=0,
                details={},
                last_check=0
            )
        self._last_full_check = 0

    def get_dependencies(self) -> Dict[str, List[str]]:
        """
        获取组件依赖关系

        Returns:
            Dict: 组件依赖关系
        """
        return {
            "ollama": [],  # LLM服务是基础依赖
            "mysql": [],
            "neo4j": [],
            "mongodb": [],
            "chromadb": [],
            "rocketmq_producer": [],  # 消息队列是可选依赖
            "rocketmq_consumer": [],
        }


# 全局单例
_health_service: Optional[HealthService] = None


def get_health_service() -> HealthService:
    """获取全局健康检查服务实例"""
    global _health_service
    if _health_service is None:
        _health_service = HealthService()
    return _health_service


def check_system_health() -> Dict[str, Any]:
    """检查系统健康状态（便捷函数）"""
    service = get_health_service()
    return service.check_all()
