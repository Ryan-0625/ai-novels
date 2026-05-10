"""
世界模拟 Repository — Fact / Event / Narrative / WorldRule

@file: repositories/world_simulation_repository.py
@date: 2026-04-29
"""

from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from deepnovel.models import Fact, Event, Narrative, WorldRule

from .base import BaseRepository


class FactRepository(BaseRepository[Fact]):
    """事实 Repository — 支持时间旅行查询"""

    def __init__(self):
        super().__init__(Fact)

    async def get_by_novel(
        self,
        session: AsyncSession,
        novel_id: str,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> List[Fact]:
        """获取小说下所有事实"""
        stmt = (
            select(Fact)
            .where(Fact.novel_id == novel_id)
            .offset(offset)
            .limit(limit)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_subject(
        self,
        session: AsyncSession,
        subject_id: str,
        predicate: Optional[str] = None,
    ) -> List[Fact]:
        """获取指定主语的所有事实"""
        stmt = select(Fact).where(Fact.subject_id == subject_id)
        if predicate:
            stmt = stmt.where(Fact.predicate == predicate)
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def get_current_fact(
        self,
        session: AsyncSession,
        subject_id: str,
        predicate: str,
    ) -> Optional[Fact]:
        """获取当前有效的事实（valid_until IS NULL）"""
        stmt = (
            select(Fact)
            .where(Fact.subject_id == subject_id)
            .where(Fact.predicate == predicate)
            .where(Fact.valid_until.is_(None))
            .where(Fact.is_counterfactual.is_(False))
            .order_by(desc(Fact.valid_from))
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_facts_at_time(
        self,
        session: AsyncSession,
        subject_id: str,
        predicate: str,
        timestamp: datetime,
    ) -> Optional[Fact]:
        """时间旅行查询 — 获取指定时间点有效的事实"""
        stmt = (
            select(Fact)
            .where(Fact.subject_id == subject_id)
            .where(Fact.predicate == predicate)
            .where(Fact.valid_from <= timestamp)
            .where(
                or_(
                    Fact.valid_until.is_(None),
                    Fact.valid_until > timestamp,
                )
            )
            .where(Fact.is_counterfactual.is_(False))
            .order_by(desc(Fact.valid_from))
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def invalidate_fact(
        self,
        session: AsyncSession,
        subject_id: str,
        predicate: str,
        invalidation_time: Optional[datetime] = None,
    ) -> bool:
        """标记旧事实为历史（设置 valid_until）"""
        now = invalidation_time or datetime.now(timezone.utc)
        stmt = (
            select(Fact)
            .where(Fact.subject_id == subject_id)
            .where(Fact.predicate == predicate)
            .where(Fact.valid_until.is_(None))
            .where(Fact.is_counterfactual.is_(False))
        )
        result = await session.execute(stmt)
        fact = result.scalar_one_or_none()
        if fact:
            fact.valid_until = now
            session.add(fact)
            await session.flush()
            return True
        return False

    async def get_by_counterfactual_branch(
        self,
        session: AsyncSession,
        branch_id: str,
    ) -> List[Fact]:
        """获取反事实分支的所有事实"""
        stmt = (
            select(Fact)
            .where(Fact.counterfactual_branch == branch_id)
            .where(Fact.is_counterfactual.is_(True))
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())


class EventRepository(BaseRepository[Event]):
    """事件 Repository — 时间线与因果链"""

    def __init__(self):
        super().__init__(Event)

    async def get_by_novel(
        self,
        session: AsyncSession,
        novel_id: str,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> List[Event]:
        """获取小说下所有事件（按模拟步排序）"""
        stmt = (
            select(Event)
            .where(Event.novel_id == novel_id)
            .order_by(Event.simulation_step)
            .offset(offset)
            .limit(limit)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_chapter(
        self,
        session: AsyncSession,
        chapter_id: str,
        event_type: Optional[str] = None,
    ) -> List[Event]:
        """获取章节关联事件"""
        stmt = select(Event).where(Event.chapter_id == chapter_id)
        if event_type:
            stmt = stmt.where(Event.event_type == event_type)
        stmt = stmt.order_by(Event.simulation_step)
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_actor(
        self,
        session: AsyncSession,
        actor_id: str,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> List[Event]:
        """获取指定行动者的事件"""
        stmt = (
            select(Event)
            .where(Event.actor_id == actor_id)
            .order_by(Event.simulation_step)
            .offset(offset)
            .limit(limit)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def get_significant_events(
        self,
        session: AsyncSession,
        novel_id: str,
        min_importance: float = 0.7,
    ) -> List[Event]:
        """获取重大事件（转折点）"""
        stmt = (
            select(Event)
            .where(Event.novel_id == novel_id)
            .where(Event.is_significant.is_(True))
            .where(Event.importance >= min_importance)
            .order_by(Event.simulation_step)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def get_causal_chain(
        self,
        session: AsyncSession,
        event_id: str,
        direction: str = "backward",
        depth: int = 3,
    ) -> List[Event]:
        """获取因果链（前因或后果）

        Args:
            direction: "backward" 追溯原因, "forward" 预测后果
            depth: 追溯深度
        """
        chain = []
        visited = {event_id}
        current_ids = [event_id]

        for _ in range(depth):
            if not current_ids:
                break
            next_ids = []
            for eid in current_ids:
                event = await self.get_by_id(session, eid)
                if not event:
                    continue
                related_ids = event.caused_by if direction == "backward" else event.causes
                for rid in related_ids:
                    if rid not in visited:
                        visited.add(rid)
                        next_ids.append(rid)
                        related_event = await self.get_by_id(session, rid)
                        if related_event:
                            chain.append(related_event)
            current_ids = next_ids

        return chain


class NarrativeRepository(BaseRepository[Narrative]):
    """叙事 Repository — 文学表达层"""

    def __init__(self):
        super().__init__(Narrative)

    async def get_by_chapter(
        self,
        session: AsyncSession,
        chapter_id: str,
        narrative_type: Optional[str] = None,
    ) -> List[Narrative]:
        """获取章节的所有叙事"""
        stmt = select(Narrative).where(Narrative.chapter_id == chapter_id)
        if narrative_type:
            stmt = stmt.where(Narrative.narrative_type == narrative_type)
        stmt = stmt.order_by(Narrative.created_at)
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_pov(
        self,
        session: AsyncSession,
        character_id: str,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> List[Narrative]:
        """获取指定视角角色的叙事"""
        stmt = (
            select(Narrative)
            .where(Narrative.pov_character == character_id)
            .order_by(Narrative.created_at)
            .offset(offset)
            .limit(limit)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_event_coverage(
        self,
        session: AsyncSession,
        event_id: str,
    ) -> List[Narrative]:
        """获取覆盖指定事件的所有叙事"""
        stmt = (
            select(Narrative)
            .where(Narrative.covers_events.contains([event_id]))
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def get_latest_version(
        self,
        session: AsyncSession,
        narrative_id: str,
    ) -> Optional[Narrative]:
        """获取叙事的最新版本"""
        current = await self.get_by_id(session, narrative_id)
        if not current:
            return None

        # 沿着 previous_version 链找到最新版本
        visited = {current.id}
        latest = current
        while latest.previous_version and latest.previous_version not in visited:
            visited.add(latest.previous_version)
            next_version = await self.get_by_id(session, latest.previous_version)
            if next_version and next_version.version > latest.version:
                latest = next_version
            else:
                break
        return latest


class WorldRuleRepository(BaseRepository[WorldRule]):
    """世界规则 Repository — 约束引擎"""

    def __init__(self):
        super().__init__(WorldRule)

    async def get_by_novel(
        self,
        session: AsyncSession,
        novel_id: str,
        active_only: bool = True,
    ) -> List[WorldRule]:
        """获取小说的世界规则"""
        stmt = select(WorldRule).where(WorldRule.novel_id == novel_id)
        if active_only:
            stmt = stmt.where(WorldRule.is_active.is_(True))
        stmt = stmt.order_by(WorldRule.priority)
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_type(
        self,
        session: AsyncSession,
        novel_id: str,
        rule_type: str,
    ) -> List[WorldRule]:
        """按规则类型获取"""
        stmt = (
            select(WorldRule)
            .where(WorldRule.novel_id == novel_id)
            .where(WorldRule.rule_type == rule_type)
            .where(WorldRule.is_active.is_(True))
            .order_by(WorldRule.priority)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def get_applicable_rules(
        self,
        session: AsyncSession,
        novel_id: str,
        predicate: str,
    ) -> List[WorldRule]:
        """获取可能适用于指定谓语的规则"""
        stmt = (
            select(WorldRule)
            .where(WorldRule.novel_id == novel_id)
            .where(WorldRule.is_active.is_(True))
            .where(WorldRule.condition["predicate"].as_string() == predicate)
            .order_by(WorldRule.priority)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())
