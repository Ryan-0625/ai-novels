"""
事件服务 — 时间线与因果链管理

@file: services/event_service.py
@date: 2026-04-29
"""

from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from deepnovel.models import Event
from deepnovel.repositories import EventRepository


class EventService:
    """事件服务 — 管理时间线、因果链、重大事件

    核心能力：
    1. 事件创建与关联
    2. 因果链追溯与预测
    3. 重大事件识别
    4. 时间线查询
    """

    def __init__(self, repository: Optional[EventRepository] = None):
        self._repo = repository or EventRepository()

    async def create_event(
        self,
        session: AsyncSession,
        novel_id: str,
        description: str,
        *,
        event_type: str = "action",
        event_subtype: Optional[str] = None,
        actor_id: Optional[str] = None,
        target_id: Optional[str] = None,
        participants: Optional[List[str]] = None,
        chapter_id: Optional[str] = None,
        simulation_step: int = 0,
        caused_by: Optional[List[str]] = None,
        effects: Optional[Dict[str, Any]] = None,
        importance: float = 0.5,
        is_significant: bool = False,
        location_id: Optional[str] = None,
        structured_data: Optional[Dict[str, Any]] = None,
    ) -> Event:
        """创建事件"""
        event = Event(
            novel_id=novel_id,
            description=description,
            event_type=event_type,
            event_subtype=event_subtype,
            actor_id=actor_id,
            target_id=target_id,
            participants=participants or [],
            chapter_id=chapter_id,
            simulation_step=simulation_step,
            caused_by=caused_by or [],
            effects=effects or {},
            importance=importance,
            is_significant=is_significant,
            location_id=location_id,
            structured_data=structured_data or {},
        )
        return await self._repo.create(session, event)

    async def link_causation(
        self,
        session: AsyncSession,
        cause_event_id: str,
        effect_event_id: str,
        causal_strength: float = 1.0,
    ) -> bool:
        """建立因果关系（双向链接）"""
        cause = await self._repo.get_by_id(session, cause_event_id)
        effect = await self._repo.get_by_id(session, effect_event_id)

        if not cause or not effect:
            return False

        # 双向链接
        if effect_event_id not in cause.causes:
            cause.causes.append(effect_event_id)
        if cause_event_id not in effect.caused_by:
            effect.caused_by.append(cause_event_id)

        effect.causal_strength = causal_strength

        await self._repo.update(session, cause)
        await self._repo.update(session, effect)
        return True

    async def get_timeline(
        self,
        session: AsyncSession,
        novel_id: str,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> List[Event]:
        """获取小说时间线（按模拟步排序）"""
        return await self._repo.get_by_novel(session, novel_id, offset=offset, limit=limit)

    async def get_significant_events(
        self,
        session: AsyncSession,
        novel_id: str,
        min_importance: float = 0.7,
    ) -> List[Event]:
        """获取重大事件（转折点）"""
        return await self._repo.get_significant_events(session, novel_id, min_importance)

    async def trace_causes(
        self,
        session: AsyncSession,
        event_id: str,
        depth: int = 3,
    ) -> List[Event]:
        """追溯原因链"""
        return await self._repo.get_causal_chain(session, event_id, direction="backward", depth=depth)

    async def predict_consequences(
        self,
        session: AsyncSession,
        event_id: str,
        depth: int = 3,
    ) -> List[Event]:
        """预测后果链"""
        return await self._repo.get_causal_chain(session, event_id, direction="forward", depth=depth)

    async def get_actor_timeline(
        self,
        session: AsyncSession,
        actor_id: str,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> List[Event]:
        """获取角色的行动时间线"""
        return await self._repo.get_by_actor(session, actor_id, offset=offset, limit=limit)
