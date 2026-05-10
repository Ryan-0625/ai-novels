"""
事件总线系统 - 实现组件间解耦通信

提供发布-订阅模式的事件驱动架构，支持同步/异步事件处理、
事件过滤、优先级队列和持久化事件。
"""

import asyncio
import json
import time
import uuid
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from enum import Enum, auto
from typing import (
    Any,
    Callable,
    Coroutine,
    Dict,
    Generic,
    List,
    Optional,
    Set,
    TypeVar,
    Union,
)
from weakref import WeakMethod

from ..utils.logger import get_logger

logger = get_logger()


class EventPriority(Enum):
    """事件优先级"""
    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3


class EventType(Enum):
    """系统事件类型"""
    # Agent 相关
    AGENT_STARTED = "agent.started"
    AGENT_COMPLETED = "agent.completed"
    AGENT_FAILED = "agent.failed"
    AGENT_MESSAGE = "agent.message"
    
    # 任务相关
    TASK_CREATED = "task.created"
    TASK_STARTED = "task.started"
    TASK_PROGRESS = "task.progress"
    TASK_COMPLETED = "task.completed"
    TASK_FAILED = "task.failed"
    TASK_CANCELLED = "task.cancelled"
    
    # LLM 相关
    LLM_REQUEST = "llm.request"
    LLM_RESPONSE = "llm.response"
    LLM_ERROR = "llm.error"
    LLM_STREAM_CHUNK = "llm.stream.chunk"
    
    # 数据库相关
    DB_CONNECTION_OPENED = "db.connection.opened"
    DB_CONNECTION_CLOSED = "db.connection.closed"
    DB_QUERY_EXECUTED = "db.query.executed"
    DB_ERROR = "db.error"
    
    # 系统相关
    SYSTEM_STARTUP = "system.startup"
    SYSTEM_SHUTDOWN = "system.shutdown"
    SYSTEM_ERROR = "system.error"
    CONFIG_RELOADED = "config.reloaded"
    
    # 自定义
    CUSTOM = "custom"


@dataclass
class Event:
    """事件对象"""
    type: Union[EventType, str]
    payload: Dict[str, Any] = field(default_factory=dict)
    source: str = "unknown"
    timestamp: float = field(default_factory=time.time)
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    correlation_id: Optional[str] = None
    priority: EventPriority = EventPriority.NORMAL
    
    def __post_init__(self):
        if isinstance(self.type, EventType):
            self.type = self.type.value
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "event_id": self.event_id,
            "type": self.type,
            "source": self.source,
            "timestamp": self.timestamp,
            "correlation_id": self.correlation_id,
            "priority": self.priority.value,
            "payload": self.payload,
        }
    
    def to_json(self) -> str:
        """转换为 JSON 字符串"""
        return json.dumps(self.to_dict(), default=str)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Event":
        """从字典创建事件"""
        return cls(
            type=data["type"],
            payload=data.get("payload", {}),
            source=data.get("source", "unknown"),
            timestamp=data.get("timestamp", time.time()),
            event_id=data.get("event_id", str(uuid.uuid4())),
            correlation_id=data.get("correlation_id"),
            priority=EventPriority(data.get("priority", 2)),
        )


T = TypeVar("T")


class EventHandler(ABC, Generic[T]):
    """事件处理器抽象基类"""
    
    @abstractmethod
    async def handle(self, event: Event) -> T:
        """处理事件"""
        pass
    
    @property
    @abstractmethod
    def event_types(self) -> List[Union[EventType, str]]:
        """订阅的事件类型"""
        pass


class EventFilter(ABC):
    """事件过滤器抽象基类"""
    
    @abstractmethod
    def matches(self, event: Event) -> bool:
        """检查事件是否匹配过滤条件"""
        pass


class SourceFilter(EventFilter):
    """按事件源过滤"""
    
    def __init__(self, sources: Union[str, List[str]]):
        self.sources = {sources} if isinstance(sources, str) else set(sources)
    
    def matches(self, event: Event) -> bool:
        return event.source in self.sources


class PayloadFilter(EventFilter):
    """按 payload 字段过滤"""
    
    def __init__(self, **conditions: Any):
        self.conditions = conditions
    
    def matches(self, event: Event) -> bool:
        return all(
            event.payload.get(key) == value
            for key, value in self.conditions.items()
        )


class CompositeFilter(EventFilter):
    """组合过滤器（AND 逻辑）"""
    
    def __init__(self, *filters: EventFilter):
        self.filters = filters
    
    def matches(self, event: Event) -> bool:
        return all(f.matches(event) for f in self.filters)


HandlerType = Union[
    Callable[[Event], None],
    Callable[[Event], Coroutine[Any, Any, None]],
    EventHandler,
]


class EventBus:
    """
    事件总线（优化版）
    
    实现发布-订阅模式，支持：
    - 同步/异步事件处理
    - 事件优先级队列
    - 事件过滤
    - 一次性订阅
    - 通配符订阅
    - 批量事件处理（NEW）
    - 事件统计（NEW）
    """
    
    def __init__(
        self,
        enable_batch: bool = True,
        batch_size: int = 100,
        batch_interval: float = 0.05,  # 50ms
        enable_stats: bool = True
    ):
        # 处理器映射: event_type -> [(handler, filter, once)]
        self._handlers: Dict[str, List[tuple]] = defaultdict(list)
        # 异步任务集合
        self._tasks: Set[asyncio.Task] = set()
        # 事件历史（用于回放）
        self._history: List[Event] = []
        self._history_size = 1000
        # 运行状态
        self._running = False
        # 事件队列（用于优先级处理）
        self._queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        # 处理锁
        self._lock = asyncio.Lock()
        
        # 批量事件处理配置
        self._enable_batch = enable_batch
        self._batch_size = batch_size
        self._batch_interval = batch_interval
        self._batch_queue: List[Event] = []
        self._batch_lock = asyncio.Lock()
        self._batch_task: Optional[asyncio.Task] = None
        self._batch_stop = False
        
        # 事件统计
        self._enable_stats = enable_stats
        self._stats = {
            'published': 0,
            'processed': 0,
            'batched': 0,
            'errors': 0,
            'handlers_called': 0
        }
        self._stats_lock = asyncio.Lock()
    
    def subscribe(
        self,
        event_type: Union[EventType, str, List[Union[EventType, str]]],
        handler: HandlerType,
        event_filter: Optional[EventFilter] = None,
        once: bool = False,
    ) -> Callable[[], None]:
        """
        订阅事件
        
        Args:
            event_type: 事件类型或类型列表
            handler: 事件处理器
            event_filter: 可选的事件过滤器
            once: 是否只处理一次
            
        Returns:
            取消订阅函数
        """
        types = self._normalize_types(event_type)
        
        for et in types:
            self._handlers[et].append((handler, event_filter, once))
            logger.system(f"Handler subscribed to {et}")
        
        def unsubscribe():
            for et in types:
                self._handlers[et] = [
                    (h, f, o) for h, f, o in self._handlers[et]
                    if h != handler
                ]
                logger.system(f"Handler unsubscribed from {et}")
        
        return unsubscribe
    
    def on(
        self,
        event_type: Union[EventType, str, List[Union[EventType, str]]],
        event_filter: Optional[EventFilter] = None,
    ) -> Callable[[HandlerType], HandlerType]:
        """
        装饰器方式订阅事件
        
        Example:
            @event_bus.on(EventType.TASK_COMPLETED)
            async def handle_task(event: Event):
                print(f"Task completed: {event.payload}")
        """
        def decorator(handler: HandlerType) -> HandlerType:
            self.subscribe(event_type, handler, event_filter)
            return handler
        return decorator
    
    def once(
        self,
        event_type: Union[EventType, str, List[Union[EventType, str]]],
        event_filter: Optional[EventFilter] = None,
    ) -> Callable[[HandlerType], HandlerType]:
        """装饰器方式一次性订阅"""
        def decorator(handler: HandlerType) -> HandlerType:
            self.subscribe(event_type, handler, event_filter, once=True)
            return handler
        return decorator
    
    async def publish(self, event: Event, wait: bool = False, batch: bool = False) -> None:
        """
        发布事件（支持批量处理）
        
        Args:
            event: 要发布的事件
            wait: 是否等待所有处理器完成
            batch: 是否使用批量处理（高吞吐量场景）
        """
        # 更新统计
        if self._enable_stats:
            async with self._stats_lock:
                self._stats['published'] += 1
        
        # 批量处理模式
        if batch and self._enable_batch:
            await self._add_to_batch(event)
            return
        
        # 立即处理
        await self._process_event(event, wait)
    
    async def _add_to_batch(self, event: Event):
        """添加事件到批处理队列"""
        async with self._batch_lock:
            self._batch_queue.append(event)
            
            # 启动批处理任务
            if self._batch_task is None or self._batch_task.done():
                self._batch_task = asyncio.create_task(self._batch_processor())
            
            # 如果队列已满，立即刷新
            if len(self._batch_queue) >= self._batch_size:
                await self._flush_batch()
    
    async def _batch_processor(self):
        """批处理后台任务"""
        while not self._batch_stop:
            await asyncio.sleep(self._batch_interval)
            async with self._batch_lock:
                if self._batch_queue:
                    await self._flush_batch()
    
    async def _flush_batch(self):
        """刷新批处理队列"""
        if not self._batch_queue:
            return
        
        # 复制队列并清空
        batch = self._batch_queue[:]
        self._batch_queue.clear()
        
        # 批量处理事件
        tasks = []
        for event in batch:
            tasks.append(self._process_event(event, wait=False))
        
        await asyncio.gather(*tasks, return_exceptions=True)
        
        if self._enable_stats:
            async with self._stats_lock:
                self._stats['batched'] += len(batch)
    
    async def _process_event(self, event: Event, wait: bool = False):
        """处理单个事件"""
        # 记录历史
        self._history.append(event)
        if len(self._history) > self._history_size:
            self._history.pop(0)
        
        # 获取匹配的处理器
        handlers = self._get_matching_handlers(event)
        
        if not handlers:
            logger.system(f"No handlers for event {event.type}")
            return
        
        # 执行处理器
        tasks = []
        for handler, once in handlers:
            task = self._execute_handler(handler, event)
            if isinstance(task, asyncio.Task):
                tasks.append(task)
        
        if self._enable_stats:
            async with self._stats_lock:
                self._stats['handlers_called'] += len(handlers)
        
        if wait and tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        
        if self._enable_stats:
            async with self._stats_lock:
                self._stats['processed'] += 1
    
    async def publish_type(
        self,
        event_type: Union[EventType, str],
        payload: Dict[str, Any] = None,
        source: str = "unknown",
        correlation_id: Optional[str] = None,
        priority: EventPriority = EventPriority.NORMAL,
        wait: bool = False,
        batch: bool = False,
    ) -> None:
        """便捷方法：按类型发布事件"""
        event = Event(
            type=event_type,
            payload=payload or {},
            source=source,
            correlation_id=correlation_id,
            priority=priority,
        )
        await self.publish(event, wait, batch)
    
    async def publish_batch(self, events: List[Event], wait: bool = False) -> int:
        """
        批量发布事件
        
        Args:
            events: 事件列表
            wait: 是否等待所有处理器完成
            
        Returns:
            发布的事件数量
        """
        tasks = []
        for event in events:
            tasks.append(self._process_event(event, wait=False))
        
        if wait:
            await asyncio.gather(*tasks, return_exceptions=True)
        
        if self._enable_stats:
            async with self._stats_lock:
                self._stats['batched'] += len(events)
        
        return len(events)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取事件统计信息"""
        if not self._enable_stats:
            return {'enabled': False}
        
        return {
            'enabled': True,
            'published': self._stats['published'],
            'processed': self._stats['processed'],
            'batched': self._stats['batched'],
            'errors': self._stats['errors'],
            'handlers_called': self._stats['handlers_called'],
            'batch_queue_size': len(self._batch_queue),
            'handlers_count': sum(len(h) for h in self._handlers.values()),
            'history_size': len(self._history)
        }
    
    def reset_stats(self):
        """重置统计信息"""
        if self._enable_stats:
            self._stats = {
                'published': 0,
                'processed': 0,
                'batched': 0,
                'errors': 0,
                'handlers_called': 0
            }
    
    def _get_matching_handlers(
        self, event: Event
    ) -> List[tuple]:
        """获取匹配的事件处理器"""
        handlers = []
        
        # 精确匹配
        if event.type in self._handlers:
            for handler, event_filter, once in self._handlers[event.type]:
                if event_filter is None or event_filter.matches(event):
                    handlers.append((handler, once))
        
        # 通配符匹配 (e.g., "task.*" matches "task.created")
        for pattern, handler_list in self._handlers.items():
            if pattern.endswith(".*") and event.type.startswith(pattern[:-1]):
                for handler, event_filter, once in handler_list:
                    if event_filter is None or event_filter.matches(event):
                        handlers.append((handler, once))
        
        # 移除一次性处理器
        for handler, once in handlers:
            if once:
                self._handlers[event.type] = [
                    (h, f, o) for h, f, o in self._handlers[event.type]
                    if h != handler
                ]
        
        return handlers
    
    def _execute_handler(
        self, handler: HandlerType, event: Event
    ) -> Optional[asyncio.Task]:
        """执行处理器"""
        try:
            if isinstance(handler, EventHandler):
                coro = handler.handle(event)
            elif asyncio.iscoroutinefunction(handler):
                coro = handler(event)
            else:
                # 同步处理器在线程中执行
                import threading
                thread = threading.Thread(target=handler, args=(event,))
                thread.start()
                return None
            
            # 创建任务并跟踪
            task = asyncio.create_task(coro)
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)
            return task
            
        except Exception as e:
            logger.system(f"Error executing handler for {event.type}: {e}")
            return None
    
    def _normalize_types(
        self, event_type: Union[EventType, str, List[Union[EventType, str]]]
    ) -> List[str]:
        """标准化事件类型"""
        if isinstance(event_type, list):
            return [
                et.value if isinstance(et, EventType) else et
                for et in event_type
            ]
        elif isinstance(event_type, EventType):
            return [event_type.value]
        else:
            return [event_type]
    
    def get_history(
        self,
        event_type: Optional[Union[EventType, str]] = None,
        limit: int = 100,
    ) -> List[Event]:
        """获取事件历史"""
        history = self._history
        
        if event_type:
            type_str = event_type.value if isinstance(event_type, EventType) else event_type
            history = [e for e in history if e.type == type_str]
        
        return history[-limit:]
    
    def clear_history(self) -> None:
        """清空事件历史"""
        self._history.clear()
    
    async def replay(
        self,
        event_type: Optional[Union[EventType, str]] = None,
        handler: Optional[HandlerType] = None,
    ) -> int:
        """
        回放历史事件
        
        Returns:
            回放的事件数量
        """
        events = self.get_history(event_type)
        
        for event in events:
            if handler:
                self._execute_handler(handler, event)
            else:
                await self.publish(event)
        
        return len(events)
    
    async def shutdown(self) -> None:
        """关闭事件总线"""
        logger.info("Shutting down event bus...")
        
        # 等待所有任务完成
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        
        self._handlers.clear()
        self.clear_history()
        
        logger.info("Event bus shutdown complete")


class PersistentEventBus(EventBus):
    """持久化事件总线 - 将事件持久化存储"""
    
    def __init__(
        self, 
        storage_path: Optional[str] = None,
        enable_batch: bool = True,
        batch_size: int = 100,
        batch_interval: float = 0.05,
        enable_stats: bool = True
    ):
        super().__init__(
            enable_batch=enable_batch,
            batch_size=batch_size,
            batch_interval=batch_interval,
            enable_stats=enable_stats
        )
        self.storage_path = storage_path
        self._persistent_events: List[Event] = []
    
    async def publish(self, event: Event, wait: bool = False) -> None:
        """发布并持久化事件"""
        # 持久化
        self._persistent_events.append(event)
        
        if self.storage_path and len(self._persistent_events) >= 100:
            await self._flush()
        
        # 正常发布
        await super().publish(event, wait)
    
    async def _flush(self) -> None:
        """将事件刷新到存储"""
        if not self.storage_path or not self._persistent_events:
            return
        
        try:
            import aiofiles
            lines = [e.to_json() + "\n" for e in self._persistent_events]
            
            async with aiofiles.open(self.storage_path, "a") as f:
                await f.writelines(lines)
            
            self._persistent_events.clear()
            logger.debug(f"Flushed {len(lines)} events to storage")
            
        except Exception as e:
            logger.error(f"Failed to flush events: {e}")
    
    async def load(self) -> List[Event]:
        """从存储加载事件"""
        if not self.storage_path:
            return []
        
        events = []
        try:
            import aiofiles
            
            async with aiofiles.open(self.storage_path, "r") as f:
                async for line in f:
                    line = line.strip()
                    if line:
                        data = json.loads(line)
                        events.append(Event.from_dict(data))
                        
        except FileNotFoundError:
            pass
        except Exception as e:
            logger.error(f"Failed to load events: {e}")
        
        return events
    
    async def shutdown(self) -> None:
        """关闭并刷新剩余事件"""
        await self._flush()
        await super().shutdown()


# 全局事件总线实例
event_bus = EventBus()


# 便捷函数
def subscribe(
    event_type: Union[EventType, str, List[Union[EventType, str]]],
    handler: HandlerType,
    event_filter: Optional[EventFilter] = None,
    once: bool = False,
) -> Callable[[], None]:
    """订阅全局事件总线"""
    return event_bus.subscribe(event_type, handler, event_filter, once)


def on(
    event_type: Union[EventType, str, List[Union[EventType, str]]],
    event_filter: Optional[EventFilter] = None,
) -> Callable[[HandlerType], HandlerType]:
    """装饰器方式订阅全局事件总线"""
    return event_bus.on(event_type, event_filter)


async def publish(event: Event, wait: bool = False) -> None:
    """发布到全局事件总线"""
    await event_bus.publish(event, wait)


async def publish_type(
    event_type: Union[EventType, str],
    payload: Dict[str, Any] = None,
    source: str = "unknown",
    **kwargs,
) -> None:
    """便捷发布到全局事件总线"""
    await event_bus.publish_type(event_type, payload, source, **kwargs)
