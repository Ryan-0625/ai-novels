"""
Event Bus 单元测试 - Phase 1 Core层
真实环境测试，不使用Mock
"""

import asyncio
import pytest
from typing import List

# 添加项目路径
import sys
sys.path.insert(0, "e:/VScode(study)/Project/AI-Novels/src")

from ai_novels.core.event_bus import (
    Event,
    EventBus,
    EventType,
    EventPriority,
    SourceFilter,
    PayloadFilter,
)


class TestEvent:
    """测试 Event 类"""
    
    def test_event_init_with_enum_type(self):
        """测试使用 EventType 枚举初始化 Event"""
        event = Event(
            type=EventType.TASK_CREATED,
            payload={"task_id": "123"},
            source="test"
        )
        
        assert event.type == "task.created"  # __post_init__ 转换
        assert event.payload == {"task_id": "123"}
        assert event.source == "test"
        assert event.event_id is not None
        assert event.timestamp > 0
        
    def test_event_init_with_string_type(self):
        """测试使用字符串类型初始化 Event"""
        event = Event(
            type="custom.event",
            payload={"data": "test"},
            source="test_source"
        )
        
        assert event.type == "custom.event"
        assert event.payload == {"data": "test"}
        assert event.source == "test_source"
        
    def test_event_post_init_converts_enum(self):
        """测试 __post_init__ 正确转换枚举为字符串"""
        event = Event(type=EventType.AGENT_STARTED)
        assert isinstance(event.type, str)
        assert event.type == "agent.started"
        
    def test_event_to_dict(self):
        """测试 Event 转换为字典"""
        event = Event(
            type=EventType.TASK_COMPLETED,
            payload={"result": "success"},
            source="agent",
            priority=EventPriority.HIGH
        )
        
        data = event.to_dict()
        
        assert data["type"] == "task.completed"
        assert data["payload"] == {"result": "success"}
        assert data["source"] == "agent"
        assert data["priority"] == 1  # HIGH = 1
        assert "event_id" in data
        assert "timestamp" in data
        
    def test_event_to_json(self):
        """测试 Event 转换为 JSON"""
        event = Event(type=EventType.SYSTEM_STARTUP)
        json_str = event.to_json()
        
        assert isinstance(json_str, str)
        assert "system.startup" in json_str
        assert "event_id" in json_str
        
    def test_event_from_dict(self):
        """测试从字典创建 Event"""
        data = {
            "type": "test.event",
            "payload": {"key": "value"},
            "source": "test",
            "timestamp": 1234567890.0,
            "event_id": "test-id-123",
            "priority": 2  # NORMAL
        }
        
        event = Event.from_dict(data)
        
        assert event.type == "test.event"
        assert event.payload == {"key": "value"}
        assert event.source == "test"
        assert event.event_id == "test-id-123"
        assert event.priority == EventPriority.NORMAL


class TestEventBus:
    """测试 EventBus 类"""
    
    @pytest.fixture
    def event_bus(self):
        """提供干净的 EventBus 实例"""
        return EventBus()
    
    @pytest.fixture
    def sample_event(self):
        """提供示例事件"""
        return Event(
            type=EventType.TASK_CREATED,
            payload={"task_id": "test-123"},
            source="test"
        )
    
    def test_event_bus_init(self, event_bus):
        """测试 EventBus 初始化"""
        assert event_bus._handlers == {}
        assert event_bus._history == []
        assert event_bus._running == False
        assert len(event_bus._tasks) == 0
        
    @pytest.mark.asyncio
    async def test_subscribe_and_publish_sync(self, event_bus, sample_event):
        """测试订阅和发布（同步处理器）"""
        received_events: List[Event] = []
        
        def handler(event: Event):
            received_events.append(event)
        
        # 订阅
        unsubscribe = event_bus.subscribe(EventType.TASK_CREATED, handler)
        
        # 发布事件
        await event_bus.publish(sample_event)
        
        # 给同步处理器一点时间执行
        await asyncio.sleep(0.1)
        
        # 验证
        assert len(received_events) == 1
        assert received_events[0].type == "task.created"
        assert received_events[0].payload["task_id"] == "test-123"
        
        # 取消订阅
        unsubscribe()
        
    @pytest.mark.asyncio
    async def test_subscribe_and_publish_async(self, event_bus, sample_event):
        """测试订阅和发布（异步处理器）"""
        received_events: List[Event] = []
        
        async def async_handler(event: Event):
            received_events.append(event)
        
        # 订阅
        event_bus.subscribe(EventType.TASK_CREATED, async_handler)
        
        # 发布事件并等待
        await event_bus.publish(sample_event, wait=True)
        
        # 验证
        assert len(received_events) == 1
        assert received_events[0].type == "task.created"
        
    @pytest.mark.asyncio
    async def test_unsubscribe(self, event_bus, sample_event):
        """测试取消订阅"""
        received_events: List[Event] = []
        
        def handler(event: Event):
            received_events.append(event)
        
        # 订阅并获取取消函数
        unsubscribe = event_bus.subscribe(EventType.TASK_CREATED, handler)
        
        # 发布一次
        await event_bus.publish(sample_event)
        await asyncio.sleep(0.1)
        assert len(received_events) == 1
        
        # 取消订阅
        unsubscribe()
        
        # 再次发布
        await event_bus.publish(sample_event)
        await asyncio.sleep(0.1)
        
        # 应该没有新事件
        assert len(received_events) == 1
        
    @pytest.mark.asyncio
    async def test_subscribe_multiple_handlers(self, event_bus, sample_event):
        """测试多个处理器订阅同一事件"""
        handler1_calls = []
        handler2_calls = []
        
        def handler1(event: Event):
            handler1_calls.append(event)
            
        def handler2(event: Event):
            handler2_calls.append(event)
        
        event_bus.subscribe(EventType.TASK_CREATED, handler1)
        event_bus.subscribe(EventType.TASK_CREATED, handler2)
        
        await event_bus.publish(sample_event)
        await asyncio.sleep(0.1)
        
        assert len(handler1_calls) == 1
        assert len(handler2_calls) == 1
        
    @pytest.mark.asyncio
    async def test_subscribe_multiple_event_types(self, event_bus):
        """测试订阅多个事件类型"""
        received_types = []
        
        def handler(event: Event):
            received_types.append(event.type)
        
        # 订阅多个类型
        event_bus.subscribe([EventType.TASK_CREATED, EventType.TASK_COMPLETED], handler)
        
        # 发布不同类型的事件
        await event_bus.publish(Event(type=EventType.TASK_CREATED, source="test"))
        await event_bus.publish(Event(type=EventType.TASK_COMPLETED, source="test"))
        await event_bus.publish(Event(type=EventType.AGENT_STARTED, source="test"))
        await asyncio.sleep(0.1)
        
        # 应该只收到订阅的类型
        assert len(received_types) == 2
        assert "task.created" in received_types
        assert "task.completed" in received_types
        assert "agent.started" not in received_types
        
    @pytest.mark.asyncio
    async def test_once_subscription(self, event_bus, sample_event):
        """测试一次性订阅"""
        received_events = []
        
        def handler(event: Event):
            received_events.append(event)
        
        # 一次性订阅
        event_bus.subscribe(EventType.TASK_CREATED, handler, once=True)
        
        # 发布两次
        await event_bus.publish(sample_event)
        await event_bus.publish(sample_event)
        await asyncio.sleep(0.1)
        
        # 应该只收到一次
        assert len(received_events) == 1
        
    @pytest.mark.asyncio
    async def test_publish_with_wait(self, event_bus):
        """测试发布并等待处理器完成"""
        execution_order = []
        
        async def async_handler(event: Event):
            await asyncio.sleep(0.05)  # 模拟异步操作
            execution_order.append("handler")
        
        event_bus.subscribe(EventType.TASK_CREATED, async_handler)
        
        execution_order.append("before_publish")
        await event_bus.publish(
            Event(type=EventType.TASK_CREATED, source="test"),
            wait=True
        )
        execution_order.append("after_publish")
        
        # 验证执行顺序
        assert execution_order == ["before_publish", "handler", "after_publish"]
        
    def test_get_history(self, event_bus):
        """测试获取事件历史"""
        # 创建一些事件
        event1 = Event(type=EventType.TASK_CREATED, source="test")
        event2 = Event(type=EventType.TASK_COMPLETED, source="test")
        event3 = Event(type=EventType.AGENT_STARTED, source="test")
        
        # 手动添加到历史（模拟发布）
        event_bus._history.append(event1)
        event_bus._history.append(event2)
        event_bus._history.append(event3)
        
        # 获取全部历史
        all_history = event_bus.get_history()
        assert len(all_history) == 3
        
        # 按类型过滤
        task_history = event_bus.get_history(EventType.TASK_CREATED)
        assert len(task_history) == 1
        assert task_history[0].type == "task.created"
        
        # 限制数量
        limited_history = event_bus.get_history(limit=2)
        assert len(limited_history) == 2
        
    def test_clear_history(self, event_bus):
        """测试清空事件历史"""
        event_bus._history.append(Event(type=EventType.TASK_CREATED, source="test"))
        assert len(event_bus._history) == 1
        
        event_bus.clear_history()
        assert len(event_bus._history) == 0
        
    @pytest.mark.asyncio
    async def test_publish_type_convenience(self, event_bus):
        """测试 publish_type 便捷方法"""
        received_events = []
        
        def handler(event: Event):
            received_events.append(event)
        
        event_bus.subscribe(EventType.TASK_PROGRESS, handler)
        
        await event_bus.publish_type(
            event_type=EventType.TASK_PROGRESS,
            payload={"progress": 50},
            source="test_agent"
        )
        await asyncio.sleep(0.1)
        
        assert len(received_events) == 1
        assert received_events[0].type == "task.progress"
        assert received_events[0].payload["progress"] == 50
        assert received_events[0].source == "test_agent"
        
    @pytest.mark.asyncio
    async def test_no_handlers_for_event(self, event_bus):
        """测试没有处理器的事件发布"""
        # 发布一个没有订阅者的事件
        event = Event(type=EventType.LLM_ERROR, source="test")
        
        # 应该正常完成，不抛出异常
        await event_bus.publish(event)
        
        # 历史记录中应该有该事件
        assert len(event_bus._history) == 1


class TestEventFilters:
    """测试事件过滤器"""
    
    def test_source_filter_matches(self):
        """测试 SourceFilter 匹配"""
        filter_ = SourceFilter(["agent1", "agent2"])
        
        event_match = Event(type=EventType.TASK_CREATED, source="agent1")
        event_no_match = Event(type=EventType.TASK_CREATED, source="agent3")
        
        assert filter_.matches(event_match) == True
        assert filter_.matches(event_no_match) == False
        
    def test_source_filter_single_source(self):
        """测试 SourceFilter 单源匹配"""
        filter_ = SourceFilter("agent1")
        
        event = Event(type=EventType.TASK_CREATED, source="agent1")
        assert filter_.matches(event) == True
        
    def test_payload_filter_matches(self):
        """测试 PayloadFilter 匹配"""
        filter_ = PayloadFilter(task_id="123", status="running")
        
        event_match = Event(
            type=EventType.TASK_PROGRESS,
            payload={"task_id": "123", "status": "running", "progress": 50}
        )
        event_no_match = Event(
            type=EventType.TASK_PROGRESS,
            payload={"task_id": "456", "status": "running"}
        )
        
        assert filter_.matches(event_match) == True
        assert filter_.matches(event_no_match) == False
        
    def test_payload_filter_partial_match(self):
        """测试 PayloadFilter 部分匹配"""
        filter_ = PayloadFilter(status="completed")
        
        event = Event(
            type=EventType.TASK_COMPLETED,
            payload={"task_id": "123", "status": "completed", "result": "success"}
        )
        
        assert filter_.matches(event) == True


class TestGlobalEventBus:
    """测试全局事件总线实例"""
    
    @pytest.mark.asyncio
    async def test_global_event_bus_exists(self):
        """测试全局 event_bus 实例存在"""
        from ai_novels.core.event_bus import event_bus as global_bus
        
        assert global_bus is not None
        assert isinstance(global_bus, EventBus)
        
    @pytest.mark.asyncio
    async def test_global_subscribe_and_publish(self):
        """测试全局事件总线订阅和发布"""
        from ai_novels.core.event_bus import (
            event_bus as global_bus,
            subscribe,
            publish_type,
        )
        
        received = []
        
        def handler(event: Event):
            received.append(event)
        
        # 使用全局 subscribe 函数
        unsubscribe = subscribe(EventType.SYSTEM_STARTUP, handler)
        
        # 使用全局 publish_type 函数
        await publish_type(EventType.SYSTEM_STARTUP, source="test")
        await asyncio.sleep(0.1)
        
        assert len(received) == 1
        assert received[0].type == "system.startup"
        
        # 清理
        unsubscribe()
