"""
RocketMQ Consumer 测试

需要 mock rocketmq-client-python 依赖，因为 CI 环境通常未安装。
"""

import pytest
import json
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

from deepnovel.messaging.rocketmq_consumer import (
    RocketMQConsumer,
    MessageHandler,
    ConsumerConfig,
    BaseConsumer
)


# ============================================================================
# 测试辅助
# ============================================================================

class MockMessageHandler(MessageHandler):
    """Mock消息处理器"""

    def __init__(self, topics: list = None):
        self._topics = topics or ["test-topic"]
        self.received_messages = []

    def get_topics(self) -> list:
        return self._topics

    def handle(self, message: dict) -> bool:
        self.received_messages.append(message)
        return True


# ============================================================================
# ConsumerConfig 测试
# ============================================================================

class TestConsumerConfig:
    """ConsumerConfig配置类测试"""

    def test_default_config(self):
        config = ConsumerConfig()
        assert config.name_server == "localhost:9876"
        assert config.consumer_group == "ai_novels_consumer"
        assert config.topic == "ai_novels_task_execution"
        assert config.tags == "*"
        assert config.batch_size == 16
        assert config.max_concurrency == 10
        assert config.offset_reset == "latest"

    def test_custom_config(self):
        config = ConsumerConfig(
            name_server="192.168.1.1:9876",
            consumer_group="custom-group",
            topic="custom-topic",
            tags="tag1",
            batch_size=32,
            max_concurrency=5,
        )
        assert config.name_server == "192.168.1.1:9876"
        assert config.consumer_group == "custom-group"
        assert config.topic == "custom-topic"
        assert config.tags == "tag1"
        assert config.batch_size == 32
        assert config.max_concurrency == 5


# ============================================================================
# RocketMQConsumer 测试（所有测试使用 mock 依赖）
# ============================================================================

@pytest.fixture(autouse=True)
def _patch_rocketmq():
    """自动 mock rocketmq 外部依赖"""
    with patch('deepnovel.messaging.rocketmq_consumer._ROCKETMQ_AVAILABLE', True):
        with patch('deepnovel.messaging.rocketmq_consumer.rocketmq', create=True) as mock_rmq:
            mock_rmq.PushConsumer.return_value = MagicMock()
            yield


class TestRocketMQConsumerInit:
    """测试RocketMQ消费者初始化"""

    def test_consumer_init_with_config(self):
        """测试使用配置对象初始化"""
        config = ConsumerConfig(
            name_server="localhost:9876",
            consumer_group="test-group",
            topic="test-topic"
        )

        consumer = RocketMQConsumer(config)
        assert consumer._config == config
        assert consumer._running is False
        assert consumer._handlers == {}

    def test_consumer_init_with_kwargs(self):
        """测试使用kwargs初始化"""
        consumer = RocketMQConsumer(
            name_server="localhost:9876",
            consumer_group="test-group",
            topic="test-topic"
        )
        assert consumer._config.name_server == "localhost:9876"
        assert consumer._config.consumer_group == "test-group"
        assert consumer._config.topic == "test-topic"

    def test_consumer_init_default(self):
        """测试默认初始化"""
        consumer = RocketMQConsumer()
        assert consumer._config is not None
        assert consumer._config.consumer_group == "ai_novels_consumer"


class TestRocketMQConsumerConnection:
    """测试RocketMQ消费者连接管理"""

    def test_connect(self):
        """测试连接"""
        consumer = RocketMQConsumer()
        result = consumer.connect()

        assert result is True
        assert consumer.is_connected() is True

    def test_disconnect(self):
        """测试断开连接"""
        consumer = RocketMQConsumer()
        consumer.connect()

        result = consumer.disconnect()

        assert result is True
        assert consumer.is_connected() is False

    def test_disconnect_not_connected(self):
        """测试断开未连接的consumer"""
        consumer = RocketMQConsumer()

        result = consumer.disconnect()

        assert result is True


class TestRocketMQConsumerHealthCheck:
    """测试RocketMQ消费者健康检查"""

    def test_health_check_connected(self):
        """测试已连接状态的健康检查"""
        consumer = RocketMQConsumer()
        consumer.connect()

        health = consumer.health_check()

        assert health["status"] == "healthy"
        assert "details" in health
        assert health["details"]["consumer_group"] == "ai_novels_consumer"

    def test_health_check_disconnected(self):
        """测试断开连接后的健康检查"""
        consumer = RocketMQConsumer()
        consumer.disconnect()

        health = consumer.health_check()

        assert health["status"] == "unhealthy"

    def test_test_connection(self):
        """测试test_connection方法"""
        consumer = RocketMQConsumer()

        # 初始化成功后即处于连接状态
        assert consumer.test_connection() is True

        # 断开后返回False
        consumer.disconnect()
        assert consumer.test_connection() is False


class TestRocketMQConsumerSubscription:
    """测试RocketMQ消费者订阅"""

    def test_subscribe_handler(self):
        """测试订阅处理器"""
        consumer = RocketMQConsumer()
        handler = MockMessageHandler(topics=["topic1"])

        result = consumer.subscribe(handler)

        assert result is True
        assert "topic1" in consumer._handlers
        assert handler in consumer._handlers["topic1"]

    def test_subscribe_multiple_handlers_same_topic(self):
        """测试多个处理器订阅同一topic"""
        consumer = RocketMQConsumer()
        handler1 = MockMessageHandler(topics=["topic1"])
        handler2 = MockMessageHandler(topics=["topic1"])

        consumer.subscribe(handler1)
        consumer.subscribe(handler2)

        assert len(consumer._handlers["topic1"]) == 2

    def test_subscribe_multiple_topics(self):
        """测试订阅多个topics"""
        consumer = RocketMQConsumer()
        handler = MockMessageHandler(topics=["topic1", "topic2", "topic3"])

        consumer.subscribe(handler)

        assert "topic1" in consumer._handlers
        assert "topic2" in consumer._handlers
        assert "topic3" in consumer._handlers


class TestRocketMQConsumerLifecycle:
    """测试RocketMQ消费者生命周期"""

    def test_start_stop(self):
        """测试启动和停止"""
        consumer = RocketMQConsumer()
        handler = MockMessageHandler()
        consumer.subscribe(handler)

        # 启动
        result_start = consumer.start()
        assert result_start is True
        assert consumer.is_running() is True

        # 停止
        result_stop = consumer.stop()
        assert result_stop is True
        assert consumer.is_running() is False

    def test_start_already_running(self):
        """测试重复启动"""
        consumer = RocketMQConsumer()
        handler = MockMessageHandler()
        consumer.subscribe(handler)

        consumer.start()
        result = consumer.start()  # 再次启动

        assert result is True  # 应该返回True（幂等）

    def test_start_without_connection(self):
        """测试启动时自动连接"""
        consumer = RocketMQConsumer()
        handler = MockMessageHandler()
        consumer.subscribe(handler)

        # 未连接时启动应该自动连接
        result = consumer.start()

        assert result is True
        assert consumer.is_connected() is True
        assert consumer.is_running() is True


class TestRocketMQConsumerMessageProcessing:
    """测试RocketMQ消费者消息处理"""

    def test_on_message(self):
        """测试消息处理"""
        consumer = RocketMQConsumer()
        handler = MockMessageHandler(topics=["test-topic"])
        consumer.subscribe(handler)

        # 模拟消息
        mock_msg = MagicMock()
        mock_msg.body = json.dumps({"data": "test"}).encode('utf-8')
        mock_msg.topic = "test-topic"
        mock_msg.keys = "test-key"

        result = consumer._on_message(mock_msg)

        assert result == 0  # 0表示成功
        assert len(handler.received_messages) == 1

    def test_on_message_no_handler(self):
        """测试无处理器时的消息处理"""
        consumer = RocketMQConsumer()
        mock_msg = MagicMock()
        mock_msg.body = json.dumps({"data": "test"}).encode('utf-8')
        mock_msg.topic = "test-topic"
        mock_msg.keys = "test-key"

        result = consumer._on_message(mock_msg)
        assert result == -1  # -1表示无处理器处理

    def test_on_message_invalid_json(self):
        """测试无效JSON的处理"""
        consumer = RocketMQConsumer()
        handler = MockMessageHandler(topics=["test-topic"])
        consumer.subscribe(handler)

        mock_msg = MagicMock()
        mock_msg.body = b"invalid json"
        mock_msg.topic = "test-topic"

        result = consumer._on_message(mock_msg)

        assert result == -1  # JSON解析失败

    def test_on_message_handler_exception(self):
        """测试处理器异常"""
        consumer = RocketMQConsumer()

        # 创建一个会抛出异常的处理器
        error_handler = MockMessageHandler(topics=["test-topic"])
        original_handle = error_handler.handle
        error_handler.handle = lambda msg: (_ for _ in ()).throw(Exception("处理失败"))

        consumer.subscribe(error_handler)

        mock_msg = MagicMock()
        mock_msg.body = json.dumps({"data": "test"}).encode('utf-8')
        mock_msg.topic = "test-topic"
        mock_msg.keys = "test-key"

        result = consumer._on_message(mock_msg)

        assert result == -1  # 处理器异常


class TestBaseConsumerAbstract:
    """测试基类抽象方法"""

    def test_base_consumer_is_abstract(self):
        """测试BaseConsumer是抽象类"""
        with pytest.raises(TypeError):
            BaseConsumer()

    def test_base_consumer_subclass_must_implement(self):
        """测试子类必须实现抽象方法"""

        class IncompleteConsumer(BaseConsumer):
            pass

        with pytest.raises(TypeError):
            IncompleteConsumer()
