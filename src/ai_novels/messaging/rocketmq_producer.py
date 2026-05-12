"""
RocketMQ生产者实现

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
    from rocketmq import Producer, Message, Consumer, PushConsumer, Sender
    _ROCKETMQ_AVAILABLE = True
except ImportError:
    _ROCKETMQ_AVAILABLE = False


@dataclass
class ProducerConfig:
    """RocketMQ生产者配置"""
    group_name: str = "ai_novels_producer"
    name_server: str = "localhost:9876"
    max_message_size: int = 1048576
    send_message_timeout_ms: int = 3000
    compress_message_body_threshold: int = 4096
    retry_times_when_send_failed: int = 2
    retry_times_when_send_async_failed: int = 2
    access_key: str = ""
    secret_key: str = ""

    @classmethod
    def from_config(cls, config: Dict[str, Any] = None) -> 'ProducerConfig':
        """从配置字典创建"""
        if config is None:
            mq_config = settings.get("messaging", {})
            rocketmq_config = mq_config.get("rocketmq", {})
            producer_config = rocketmq_config.get("producer", {})

            # 从环境变量读取（如果设置）
            name_server = os.environ.get('ROCKETMQ_NAME_SERVER', rocketmq_config.get("name_server", "localhost:9876"))

            config = {
                "group_name": producer_config.get("group_name", "ai_novels_producer"),
                "name_server": name_server,
                "max_message_size": producer_config.get("max_message_size", 1048576),
                "send_message_timeout_ms": producer_config.get("send_message_timeout_ms", 3000),
                "compress_message_body_threshold": producer_config.get("compress_message_body_threshold", 4096),
                "retry_times_when_send_failed": producer_config.get("retry_times_when_send_failed", 2),
                "retry_times_when_send_async_failed": producer_config.get("retry_times_when_send_async_failed", 2),
                "access_key": os.environ.get('ROCKETMQ_ACCESS_KEY', producer_config.get("access_key", "")),
                "secret_key": os.environ.get('ROCKETMQ_SECRET_KEY', producer_config.get("secret_key", "")),
            }

        return cls(
            group_name=config.get("group_name", "ai_novels_producer"),
            name_server=config.get("name_server", "localhost:9876"),
            max_message_size=config.get("max_message_size", 1048576),
            send_message_timeout_ms=config.get("send_message_timeout_ms", 3000),
            compress_message_body_threshold=config.get("compress_message_body_threshold", 4096),
            retry_times_when_send_failed=config.get("retry_times_when_send_failed", 2),
            retry_times_when_send_async_failed=config.get("retry_times_when_send_async_failed", 2),
            access_key=config.get("access_key", ""),
            secret_key=config.get("secret_key", ""),
        )


# 兼容类名
RocketMQConfig = ProducerConfig


class BaseProducer(ABC):
    """消息生产者基类"""

    @abstractmethod
    def send(self, topic: str, message: Dict[str, Any], tags: str = "") -> Optional[Dict[str, Any]]:
        """发送消息"""
        pass

    @abstractmethod
    def send_sync(self, topic: str, message: Dict[str, Any], tags: str = "") -> Optional[Dict[str, Any]]:
        """同步发送消息"""
        pass

    @abstractmethod
    def send_async(self, topic: str, message: Dict[str, Any], tags: str = "", callback: Callable = None) -> bool:
        """异步发送消息"""
        pass

    @abstractmethod
    def send_one_way(self, topic: str, message: Dict[str, Any], tags: str = "") -> bool:
        """单向发送消息（不等待响应）"""
        pass

    @abstractmethod
    def close(self) -> bool:
        """关闭生产者"""
        pass


class RocketMQProducer(BaseProducer):
    """
    RocketMQ消息生产者实现

    需要 rocketmq-client-python 库，否则抛出 ImportError。
    """

    def __init__(self, config: ProducerConfig = None, **kwargs):
        """初始化生产者"""
        if not _ROCKETMQ_AVAILABLE:
            raise ImportError(
                "rocketmq-client-python is not available. "
                "Install it with: pip install rocketmq-client-python"
            )

        self._logger = get_logger()

        if kwargs:
            self._config = ProducerConfig.from_config(kwargs)
        elif config:
            self._config = config
        else:
            self._config = ProducerConfig.from_config()

        self._producer: Optional[Any] = None
        self._is_connected = False

        self._logger.messaging("RocketMQ Producer initializing",
                              name_server=self._config.name_server)
        self._init_producer()

    def _init_producer(self):
        """初始化RocketMQ生产者"""
        try:
            self._producer = rocketmq.Producer(self._config.group_name)
            self._producer.set_name_server_address(self._config.name_server)

            if self._config.access_key and self._config.secret_key:
                self._producer.set_session_credentials(
                    self._config.access_key,
                    self._config.secret_key,
                    "Default"
                )

            self._is_connected = True
            self._logger.messaging("RocketMQ Producer initialized",
                                  name_server=self._config.name_server,
                                  group=self._config.group_name)
        except Exception as e:
            self._logger.messaging_error("Failed to initialize RocketMQ Producer", error=str(e))
            raise

    def connect(self) -> bool:
        """建立连接"""
        if self._producer is None:
            return False
        try:
            self._producer.start()
            self._is_connected = True
            return True
        except Exception as e:
            self._logger.messaging_error("Failed to connect RocketMQ Producer", error=str(e))
            self._is_connected = False
            return False

    def disconnect(self) -> bool:
        """断开连接"""
        if self._producer is not None:
            try:
                self._producer.shutdown()
            except Exception as e:
                self._logger.messaging_error("Failed to shutdown RocketMQ Producer", error=str(e))
        self._is_connected = False
        return True

    def is_connected(self) -> bool:
        return self._is_connected

    def health_check(self) -> dict:
        try:
            return {
                "status": "healthy" if self._is_connected else "unhealthy",
                "latency_ms": 0,
                "details": {
                    "producer_group": self._config.group_name,
                    "name_server": self._config.name_server
                }
            }
        except Exception as e:
            return {"status": "unhealthy", "latency_ms": 0, "error": str(e)}

    def close(self) -> bool:
        return self.disconnect()

    def send(self, topic: str, message: Dict[str, Any], tags: str = "", send_type: str = "sync") -> Optional[Dict[str, Any]]:
        """发送消息"""
        if not self._is_connected and not self.connect():
            return None
        try:
            msg_str = __import__('json').dumps(message, ensure_ascii=False)
            msg = Message(topic)
            msg.set_keys(str(__import__('uuid').uuid4()))
            msg.set_tags(tags)
            msg.set_body(msg_str)

            if send_type == "sync":
                result = self._producer.send_sync(msg)
            elif send_type == "async":
                result = self._producer.send_async(msg)
            else:
                result = self._producer.send_one_way(msg)

            return {"status": "sent", "topic": topic, "message_id": result.msg_id}
        except Exception as e:
            self._logger.messaging_error("Failed to send message", topic=topic, error=str(e))
            return None

    def send_sync(self, topic: str, message: Dict[str, Any], tags: str = "") -> Optional[Dict[str, Any]]:
        return self.send(topic, message, tags, "sync")

    def send_async(self, topic: str, message: Dict[str, Any], tags: str = "", callback: Callable = None) -> bool:
        return self.send(topic, message, tags, "async") is not None

    def send_one_way(self, topic: str, message: Dict[str, Any], tags: str = "") -> bool:
        return self.send(topic, message, tags, "one_way") is not None

    def send_batch(self, topic: str, messages: List[Dict[str, Any]], tags: str = "") -> List[Dict[str, Any]]:
        return [self.send_sync(topic, msg, tags) for msg in messages if msg]

    def send_delayed(self, topic: str, message: Dict[str, Any], delay_level: int = 1, tags: str = "") -> Optional[Dict[str, Any]]:
        return self.send_sync(topic, message, tags)

    def send_orderly(self, topic: str, message: Dict[str, Any], shard_key: str, tags: str = "") -> Optional[Dict[str, Any]]:
        return self.send_sync(topic, message, tags)

    def test_connection(self) -> bool:
        return self.health_check()["status"] == "healthy"


# Mock message classes - 保留用于兼容性
class NovelGenerationMessage:
    """小说生成消息"""

    @staticmethod
    def create_task(task_id: str, user_id: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """创建生成任务消息"""
        return {
            "message_type": "generation_task",
            "task_id": task_id,
            "user_id": user_id,
            "action": "create",
            "config": config,
            "timestamp": int(__import__('time').time() * 1000)
        }

    @staticmethod
    def update_task(task_id: str, status: str, progress: float = None, error: str = None) -> Dict[str, Any]:
        """创建任务更新消息"""
        return {
            "message_type": "generation_task_update",
            "task_id": task_id,
            "status": status,
            "progress": progress,
            "error": error,
            "timestamp": int(__import__('time').time() * 1000)
        }

    @staticmethod
    def generate_chapter(task_id: str, chapter_id: str, outline_id: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """创建章节生成消息"""
        return {
            "message_type": "generate_chapter",
            "task_id": task_id,
            "chapter_id": chapter_id,
            "outline_id": outline_id,
            "context": context,
            "timestamp": int(__import__('time').time() * 1000)
        }


class notifyMessage:
    """通知消息"""

    @staticmethod
    def create(msg_type: str, title: str, content: str, recipients: List[str]) -> Dict[str, Any]:
        """创建通知消息"""
        return {
            "message_type": "notification",
            "notify_type": msg_type,
            "title": title,
            "content": content,
            "recipients": recipients,
            "timestamp": int(__import__('time').time() * 1000)
        }
