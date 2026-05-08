"""
RocketMQ消费者实现

支持真实环境和测试环境的双模式：
- 真实环境：使用rocketmq-client-python库连接真实的RocketMQ服务器
- 测试环境：使用Mock实现，无需外部依赖
"""

from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass
from abc import ABC, abstractmethod
import os

from ..config.manager import settings
from ..utils import get_logger

# 尝试导入真实的RocketMQ客户端
try:
    import rocketmq
    from rocketmq import Consumer, PushConsumer
    _ROCKETMQ_AVAILABLE = True
except ImportError:
    _ROCKETMQ_AVAILABLE = False


@dataclass
class ConsumerConfig:
    """RocketMQ消费者配置"""
    name_server: str = "localhost:9876"
    consumer_group: str = "ai_novels_consumer"
    access_key: str = ""
    secret_key: str = ""
    topic: str = "ai_novels_task_execution"
    tags: str = "*"
    batch_size: int = 16
    max_concurrency: int = 10
    offset_reset: str = "latest"
    retry_times: int = 3
    subscription_type: str = "Broadcasting"  # Broadcasting or Ordering

    @classmethod
    def from_config(cls, config: Dict[str, Any] = None) -> 'ConsumerConfig':
        """从配置字典创建"""
        if config is None:
            config = {}

        mq_config = settings.get("messaging", {})
        rocketmq_config = mq_config.get("rocketmq", {})

        # 从环境变量读取（如果设置）
        name_server = os.environ.get('ROCKETMQ_NAME_SERVER', rocketmq_config.get("name_server", "localhost:9876"))

        return cls(
            name_server=config.get("name_server") or name_server,
            consumer_group=config.get("consumer_group") or mq_config.get("consumer_group", "ai_novels_consumer"),
            access_key=config.get("access_key") or os.environ.get('ROCKETMQ_ACCESS_KEY', ""),
            secret_key=config.get("secret_key") or os.environ.get('ROCKETMQ_SECRET_KEY', ""),
            topic=config.get("topic") or mq_config.get("topic", "ai_novels_task_execution"),
            tags=config.get("tags", "*"),
            batch_size=config.get("batch_size", 16),
            max_concurrency=config.get("max_concurrency", 10),
            offset_reset=config.get("offset_reset", "latest"),
            retry_times=config.get("retry_times", 3),
            subscription_type=config.get("subscription_type", "Broadcasting")
        )


class MessageHandler(ABC):
    """消息处理器基类"""

    @abstractmethod
    def handle(self, message: Dict[str, Any]) -> bool:
        """处理消息"""
        pass

    @abstractmethod
    def get_topics(self) -> List[str]:
        """获取监听的主题列表"""
        pass


class BaseConsumer(ABC):
    """消息消费者基类"""

    @abstractmethod
    def subscribe(self, handler: MessageHandler) -> bool:
        """订阅消息"""
        pass

    @abstractmethod
    def start(self) -> bool:
        """启动消费者"""
        pass

    @abstractmethod
    def stop(self) -> bool:
        """停止消费者"""
        pass

    @abstractmethod
    def is_running(self) -> bool:
        """检查是否正在运行"""
        pass


class RocketMQConsumer(BaseConsumer):
    """
    RocketMQ消息消费者实现

    需要 rocketmq-client-python 库，否则抛出 ImportError。
    """

    def __init__(self, config: ConsumerConfig = None, **kwargs):
        """初始化消费者"""
        if not _ROCKETMQ_AVAILABLE:
            raise ImportError(
                "rocketmq-client-python is not available. "
                "Install it with: pip install rocketmq-client-python"
            )

        if config is None:
            if kwargs:
                config = ConsumerConfig.from_config(kwargs)
            else:
                config = ConsumerConfig.from_config()
        self._config = config
        self._consumer: Optional[Any] = None
        self._handlers: Dict[str, List[MessageHandler]] = {}
        self._running = False
        self._is_connected = False

        self._logger = get_logger()
        self._logger.messaging("RocketMQ Consumer initializing",
                              topic=self._config.topic,
                              group=self._config.consumer_group)

        self._init_consumer()

    def _init_consumer(self):
        """初始化RocketMQ消费者"""
        try:
            self._consumer = rocketmq.PushConsumer(self._config.consumer_group)
            self._consumer.set_name_server_address(self._config.name_server)
            self._consumer.set_thread_count(self._config.max_concurrency)
            self._consumer.set_batch_size(self._config.batch_size)

            if self._config.access_key and self._config.secret_key:
                self._consumer.set_session_credentials(
                    self._config.access_key,
                    self._config.secret_key,
                    "Default"
                )

            self._consumer.subscribe(self._config.topic, self._config.tags, self._on_message)
            self._is_connected = True
            self._logger.messaging("RocketMQ Consumer initialized",
                                  topic=self._config.topic,
                                  group=self._config.consumer_group)
        except Exception as e:
            self._logger.messaging_error("Failed to initialize RocketMQ Consumer", error=str(e))
            raise

    def _on_message(self, msg: Any) -> int:
        """处理收到的消息"""
        try:
            body = msg.body if hasattr(msg, 'body') else str(msg)
            message = __import__('json').loads(body)

            topics = [msg.topic] if hasattr(msg, 'topic') else []
            notified = False
            for topic in topics:
                if topic in self._handlers:
                    for handler in self._handlers[topic]:
                        try:
                            handler.handle(message)
                            notified = True
                        except Exception as e:
                            self._logger.messaging_error("Handler error", topic=topic, error=str(e))
            return 0 if notified else -1
        except Exception as e:
            self._logger.messaging_error("Message processing error", error=str(e))
            return -1

    def connect(self) -> bool:
        """建立连接"""
        if self._consumer is None:
            return False
        try:
            self._is_connected = True
            return True
        except Exception as e:
            self._logger.messaging_error("Failed to connect RocketMQ Consumer", error=str(e))
            self._is_connected = False
            return False

    def disconnect(self) -> bool:
        """断开连接"""
        if self._consumer is not None:
            try:
                self._consumer.shutdown()
            except Exception as e:
                self._logger.messaging_error("Failed to shutdown RocketMQ Consumer", error=str(e))
        self._is_connected = False
        return True

    def is_connected(self) -> bool:
        return getattr(self, '_is_connected', False)

    def health_check(self) -> dict:
        handler_count = sum(len(h) for h in self._handlers.values())
        return {
            "status": "healthy" if self.is_connected() else "unhealthy",
            "latency_ms": 0,
            "details": {
                "consumer_group": self._config.consumer_group,
                "topic": self._config.topic,
                "handler_count": handler_count,
                "is_running": self._running
            }
        }

    def subscribe(self, handler: MessageHandler) -> bool:
        topics = handler.get_topics()
        for topic in topics:
            if topic not in self._handlers:
                self._handlers[topic] = []
            if handler not in self._handlers[topic]:
                self._handlers[topic].append(handler)
        if self._consumer is not None:
            try:
                for topic in topics:
                    self._consumer.subscribe(topic, "*", self._on_message)
            except Exception as e:
                self._logger.messaging_error("Failed to subscribe topics", error=str(e))
                return False
        return True

    def start(self) -> bool:
        if self._running:
            return True
        if not self.is_connected() and not self.connect():
            return False
        self._running = True
        return True

    def stop(self) -> bool:
        self._running = False
        return self.disconnect()

    def is_running(self) -> bool:
        return self._running

    def test_connection(self) -> bool:
        return self.health_check()["status"] == "healthy"


# Mock message handlers
class NovelGenerationHandler(MessageHandler):
    """小说生成消息处理器"""

    def __init__(self):
        self._topics = ["novel_generation", "generation_task_update"]

    def get_topics(self) -> List[str]:
        return self._topics

    def handle(self, message: Dict[str, Any]) -> bool:
        """处理小说生成消息"""
        self._logger = get_logger()
        self._logger.messaging("NovelGenerationHandler processing message",
                              message_type=message.get("message_type"))
        return True


class NotifyMessageHandler(MessageHandler):
    """通知消息处理器"""

    def __init__(self):
        self._topics = ["notifications", "notify"]

    def get_topics(self) -> List[str]:
        return self._topics

    def handle(self, message: Dict[str, Any]) -> bool:
        """处理通知消息"""
        self._logger = get_logger()
        self._logger.messaging("NotifyMessageHandler processing message",
                              title=message.get("title"))
        return True


class TaskStatusHandler(MessageHandler):
    """任务状态处理器"""

    def __init__(self):
        self._topics = ["task_status", "stage_update"]

    def get_topics(self) -> List[str]:
        return self._topics

    def handle(self, message: Dict[str, Any]) -> bool:
        """处理任务状态消息"""
        self._logger = get_logger()
        self._logger.messaging("TaskStatusHandler processing message",
                              status=message.get("status"))
        return True


# 消费者管理器
class ConsumerManager:
    """消费者管理器"""

    def __init__(self):
        self._consumers: Dict[str, BaseConsumer] = {}
        self._handlers: Dict[str, List[MessageHandler]] = {}

    def add_consumer(self, name: str, consumer: BaseConsumer) -> bool:
        self._consumers[name] = consumer
        return True

    def register_handler(self, name: str, handler: MessageHandler) -> bool:
        if name in self._consumers:
            return self._consumers[name].subscribe(handler)
        return False

    def start_all(self) -> bool:
        success = True
        for consumer in self._consumers.values():
            if not consumer.start():
                success = False
        return success

    def stop_all(self) -> bool:
        success = True
        for consumer in self._consumers.values():
            if not consumer.stop():
                success = False
        return success

    def get_status(self) -> Dict[str, Any]:
        return {
            name: {
                "is_running": consumer.is_running(),
                "is_connected": consumer.is_connected()
            }
            for name, consumer in self._consumers.items()
        }
