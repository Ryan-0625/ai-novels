"""
RocketMQ Producer 测试

需要 mock rocketmq-client-python 依赖，因为 CI 环境通常未安装。
"""

import pytest
import sys
import os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from ai_novels.messaging.rocketmq_producer import (
    ProducerConfig, RocketMQProducer, BaseProducer,
    NovelGenerationMessage, notifyMessage
)


@pytest.fixture(autouse=True)
def _patch_rocketmq():
    """自动 mock rocketmq 外部依赖"""
    with patch('ai_novels.messaging.rocketmq_producer._ROCKETMQ_AVAILABLE', True):
        with patch('ai_novels.messaging.rocketmq_producer.Message', create=True):
            with patch('ai_novels.messaging.rocketmq_producer.rocketmq', create=True) as mock_rmq:
                mock_producer = MagicMock()
                mock_rmq.Producer.return_value = mock_producer
                yield_mock = mock_producer.send_sync
                yield_mock.return_value = MagicMock(msg_id="mock-id")
                yield


class TestProducerConfig:
    """ProducerConfig 配置类测试"""

    def test_default_config(self):
        """测试默认配置"""
        config = ProducerConfig()
        assert config.group_name == "ai_novels_producer"
        assert config.name_server == "localhost:9876"
        assert config.max_message_size == 1048576
        assert config.send_message_timeout_ms == 3000

    def test_custom_config(self):
        """测试自定义配置"""
        config = ProducerConfig(
            group_name="custom_producer",
            name_server="192.168.1.1:9876",
            max_message_size=2048576,
            send_message_timeout_ms=5000,
        )
        assert config.group_name == "custom_producer"
        assert config.name_server == "192.168.1.1:9876"
        assert config.max_message_size == 2048576
        assert config.send_message_timeout_ms == 5000


class TestRocketMQProducerInit:
    """测试RocketMQ生产者初始化"""

    def test_init_with_default_config(self):
        """测试默认初始化"""
        producer = RocketMQProducer()
        assert producer._config.group_name == "ai_novels_producer"

    def test_init_with_config_object(self):
        """测试使用配置对象初始化"""
        config = ProducerConfig(
            group_name="test-group",
            name_server="test:9876"
        )
        producer = RocketMQProducer(config=config)
        assert producer._config.group_name == "test-group"

    def test_init_with_kwargs(self):
        """测试使用kwargs初始化"""
        producer = RocketMQProducer(
            group_name="kwarg_group",
            name_server="kwarg:9876"
        )
        assert producer._config.group_name == "kwarg_group"
        assert producer._config.name_server == "kwarg:9876"


class TestRocketMQProducerConnection:
    """测试RocketMQ生产者连接管理"""

    def test_connect(self):
        """测试连接"""
        producer = RocketMQProducer()
        result = producer.connect()
        assert result is True
        assert producer.is_connected() is True

    def test_disconnect(self):
        """测试断开连接"""
        producer = RocketMQProducer()
        result = producer.disconnect()
        assert result is True
        assert producer.is_connected() is False

    def test_health_check(self):
        """测试健康检查"""
        producer = RocketMQProducer()
        health = producer.health_check()
        assert "status" in health
        assert health["status"] == "healthy" or health["status"] == "unhealthy"

    def test_test_connection(self):
        """测试连接测试"""
        producer = RocketMQProducer()
        assert isinstance(producer.test_connection(), bool)


class TestRocketMQProducerSend:
    """测试RocketMQ生产者发送功能"""

    def test_send_sync(self):
        """测试同步发送"""
        producer = RocketMQProducer()
        producer.connect()
        result = producer.send_sync("test-topic", {"key": "value"})
        assert result is not None
        assert result["status"] == "sent"

    def test_send_one_way(self):
        """测试单向发送"""
        producer = RocketMQProducer()
        producer.connect()
        result = producer.send_one_way("test-topic", {"key": "value"})
        assert isinstance(result, bool)

    def test_send_batch(self):
        """测试批量发送"""
        producer = RocketMQProducer()
        producer.connect()
        messages = [
            {"id": 1, "data": "msg1"},
            {"id": 2, "data": "msg2"},
        ]
        results = producer.send_batch("test-topic", messages)
        assert len(results) == 2
        assert all(r is not None for r in results)


class TestProducerMessageHelper:
    """测试消息辅助类"""

    def test_novel_generation_create_task(self):
        msg = NovelGenerationMessage.create_task(
            task_id="task-1",
            user_id="user-1",
            config={"genre": "fantasy"}
        )
        assert msg["message_type"] == "generation_task"
        assert msg["task_id"] == "task-1"
        assert msg["config"]["genre"] == "fantasy"

    def test_novel_generation_update_task(self):
        msg = NovelGenerationMessage.update_task(
            task_id="task-1",
            status="running",
            progress=0.5,
        )
        assert msg["message_type"] == "generation_task_update"
        assert msg["status"] == "running"
        assert msg["progress"] == 0.5

    def test_novel_generation_generate_chapter(self):
        msg = NovelGenerationMessage.generate_chapter(
            task_id="task-1",
            chapter_id="ch-1",
            outline_id="outline-1",
            context={"style": "narrative"}
        )
        assert msg["message_type"] == "generate_chapter"
        assert msg["chapter_id"] == "ch-1"

    def test_notify_message(self):
        msg = notifyMessage.create(
            msg_type="info",
            title="测试通知",
            content="这是一条测试通知",
            recipients=["user-1"]
        )
        assert msg["message_type"] == "notification"
        assert msg["title"] == "测试通知"

    def test_base_producer_abstract(self):
        """测试BaseProducer是抽象类"""
        with pytest.raises(TypeError):
            BaseProducer()
