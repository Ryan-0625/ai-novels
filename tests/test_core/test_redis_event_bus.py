"""
Redis Streams 事件总线测试

测试范围:
- 事件发布与消费
- 消费组管理
- 向后兼容（Event类型）
"""

import asyncio

import pytest
import redis.asyncio as redis

from deepnovel.core.event_bus import Event, EventPriority, EventType
from deepnovel.core.redis_event_bus import RedisEventBus


class TestRedisEventBusUnit:
    """RedisEventBus单元测试（无需Redis连接）"""

    def test_event_to_dict_backward_compat(self):
        """Event.to_dict() 必须兼容旧格式"""
        event = Event(
            type=EventType.TASK_CREATED,
            payload={"task_id": "123", "name": "test"},
            source="test_source",
        )
        d = event.to_dict()
        assert d["type"] == "task.created"
        assert d["payload"]["task_id"] == "123"
        assert d["source"] == "test_source"
        assert "event_id" in d
        assert "timestamp" in d

    def test_event_priority_enum(self):
        """EventPriority 枚举值必须正确"""
        assert EventPriority.CRITICAL.value == 0
        assert EventPriority.HIGH.value == 1
        assert EventPriority.NORMAL.value == 2
        assert EventPriority.LOW.value == 3

    def test_event_type_values(self):
        """EventType 字符串值必须正确"""
        assert EventType.TASK_CREATED.value == "task.created"
        assert EventType.AGENT_STARTED.value == "agent.started"
        assert EventType.LLM_REQUEST.value == "llm.request"


class TestRedisEventBusIntegration:
    """RedisEventBus集成测试（需要Redis连接）"""

    @pytest.fixture
    async def event_bus(self):
        """创建并清理EventBus实例"""
        client = None
        try:
            client = redis.from_url("redis://localhost:6379", decode_responses=True)
            await client.ping()
            bus = RedisEventBus(client)
            yield bus
            await bus.stop()
            # 清理测试数据
            await bus.redis.delete(RedisEventBus.STREAM_KEY)
            await client.aclose()
        except (redis.ConnectionError, OSError):
            if client:
                await client.aclose()
            pytest.skip("Redis not available")

    @pytest.mark.asyncio
    async def test_publish_event(self, event_bus):
        """必须能发布事件"""
        event = Event(
            type=EventType.TASK_CREATED,
            payload={"task_id": "t1", "name": "generate_chapter"},
        )
        event_id = await event_bus.publish(event)
        assert event_id is not None
        assert "-" in event_id  # Redis Stream ID format

    @pytest.mark.asyncio
    async def test_publish_dict(self, event_bus):
        """publish_dict 便捷方法必须工作"""
        event_id = await event_bus.publish_dict(
            event_type="task.created",
            payload={"task_id": "t2"},
            source="test",
        )
        assert event_id is not None

    @pytest.mark.asyncio
    async def test_subscribe_and_consume(self, event_bus):
        """订阅和消费必须工作"""
        received = []

        async def handler(event: Event):
            received.append(event.payload.get("task_id"))

        event_bus.subscribe("task.created", handler)
        await event_bus.start()

        # 发布事件
        await event_bus.publish_dict(
            event_type="task.created",
            payload={"task_id": "t3"},
        )

        # 等待消费
        await asyncio.sleep(0.5)

        assert "t3" in received

    @pytest.mark.asyncio
    async def test_stream_info(self, event_bus):
        """Stream统计信息必须可获取"""
        await event_bus.publish_dict("test.event", {"data": "test"})
        info = await event_bus.get_stream_info()
        assert "length" in info
        assert info["length"] >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
