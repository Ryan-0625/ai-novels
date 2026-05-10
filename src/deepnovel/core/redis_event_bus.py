"""
Redis Streams 持久化事件总线

替代内存EventBus，提供：
- 事件持久化（进程重启不丢失）
- 多消费者消费组
- 跨服务事件传递

@file: core/redis_event_bus.py
@date: 2026-04-29
"""

import asyncio
import json
import uuid
from typing import Any, Callable, Dict, List, Optional

import redis.asyncio as redis

from .event_bus import Event, EventPriority, EventType


def _get_redis_url() -> str:
    """从 AppConfig 获取 Redis URL（延迟导入避免循环依赖）"""
    from deepnovel.config.app_config import get_config

    return get_config().redis.url


class RedisEventBus:
    """Redis Streams 持久化事件总线

    接口兼容旧版 EventBus，支持渐进式迁移。
    """

    STREAM_KEY = "deepnovel:events"
    CONSUMER_GROUP = "deepnovel:consumers"

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self._handlers: Dict[str, List[Callable]] = {}
        self._running = False
        self._listen_task: Optional[asyncio.Task] = None

    @classmethod
    async def from_url(cls, url: str = "redis://localhost:6379") -> "RedisEventBus":
        """从URL创建EventBus实例"""
        client = redis.from_url(url, decode_responses=True)
        return cls(client)

    @classmethod
    async def from_config(cls) -> "RedisEventBus":
        """从AppConfig创建EventBus实例"""
        return await cls.from_url(_get_redis_url())

    async def publish(self, event: Event) -> str:
        """发布事件到Redis Stream"""
        payload = json.dumps(event.to_dict(), default=str)
        event_id = await self.redis.xadd(
            self.STREAM_KEY,
            fields={"data": payload},
            maxlen=100000,
            approximate=True,
        )
        return event_id

    async def publish_dict(
        self,
        event_type: str,
        payload: Dict[str, Any],
        source: str = "unknown",
        priority: EventPriority = EventPriority.NORMAL,
    ) -> str:
        """便捷方法：从字典创建并发布事件"""
        event = Event(
            type=event_type,
            payload=payload,
            source=source,
            priority=priority,
        )
        return await self.publish(event)

    def subscribe(self, event_type: str, handler: Callable):
        """订阅事件（内存注册，异步消费）"""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    async def start(self):
        """启动事件消费循环"""
        if self._running:
            return
        self._running = True

        # 确保消费组存在
        try:
            await self.redis.xgroup_create(
                self.STREAM_KEY,
                self.CONSUMER_GROUP,
                id="0",
                mkstream=True,
            )
        except redis.ResponseError as e:
            if "already exists" not in str(e).lower():
                raise

        self._listen_task = asyncio.create_task(self._consume_loop())

    async def stop(self):
        """停止事件消费循环"""
        self._running = False
        if self._listen_task:
            self._listen_task.cancel()
            try:
                await self._listen_task
            except asyncio.CancelledError:
                pass

    async def _consume_loop(self):
        """消费循环 — 从Redis Stream读取事件并分发"""
        consumer_name = f"consumer-{uuid.uuid4().hex[:8]}"

        while self._running:
            try:
                messages = await self.redis.xreadgroup(
                    groupname=self.CONSUMER_GROUP,
                    consumername=consumer_name,
                    streams={self.STREAM_KEY: ">"},
                    count=10,
                    block=5000,
                )

                for stream_name, entries in messages:
                    for entry_id, fields in entries:
                        await self._process_entry(entry_id, fields)

            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(1)

    async def _process_entry(self, entry_id: str, fields: Dict[str, str]):
        """处理单条Stream条目"""
        try:
            data = json.loads(fields.get("data", "{}"))
            event_type = data.get("type", "")

            # 创建Event对象
            event = Event(
                type=event_type,
                payload=data.get("payload", {}),
                source=data.get("source", "unknown"),
                event_id=data.get("event_id", entry_id),
                correlation_id=data.get("correlation_id"),
            )

            # 分发到注册的处理器
            handlers = self._handlers.get(event_type, [])
            for handler in handlers:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(event)
                    else:
                        handler(event)
                except Exception:
                    pass

            # 确认消息已处理
            await self.redis.xack(self.STREAM_KEY, self.CONSUMER_GROUP, entry_id)

        except json.JSONDecodeError:
            pass

    async def get_pending_count(self) -> int:
        """获取待处理事件数量"""
        info = await self.redis.xpending(self.STREAM_KEY, self.CONSUMER_GROUP)
        return info.get("pending", 0) if info else 0

    async def get_stream_info(self) -> Dict[str, Any]:
        """获取Stream统计信息"""
        info = await self.redis.xinfo_stream(self.STREAM_KEY)
        return {
            "length": info.get("length", 0),
            "radix-tree-keys": info.get("radix-tree-keys", 0),
            "groups": info.get("groups", 0),
            "last-generated-id": info.get("last-generated-id", ""),
        }
