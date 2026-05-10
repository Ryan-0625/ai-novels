"""
叙事服务 — 文学表达层管理

@file: services/narrative_service.py
@date: 2026-04-29
"""

from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from deepnovel.models import Narrative, NarrativeType, POVType
from deepnovel.repositories import NarrativeRepository


class NarrativeService:
    """叙事服务 — 管理文学表达与模拟事件的映射

    核心能力：
    1. 叙事创建与版本控制
    2. 多视角叙事管理
    3. 事件覆盖追踪
    4. 风格一致性检查
    """

    def __init__(self, repository: Optional[NarrativeRepository] = None):
        self._repo = repository or NarrativeRepository()

    async def create_narrative(
        self,
        session: AsyncSession,
        novel_id: str,
        chapter_id: str,
        content: str,
        *,
        narrative_type: str = NarrativeType.SCENE,
        pov_character: Optional[str] = None,
        pov_type: str = POVType.THIRD_LIMITED,
        style_profile: Optional[Dict[str, Any]] = None,
        covers_events: Optional[List[str]] = None,
        covers_steps: Optional[List[int]] = None,
        covers_facts: Optional[List[str]] = None,
        plot_function: Optional[str] = None,
        emotional_arc: Optional[Dict[str, Any]] = None,
        word_count: Optional[int] = None,
        generated_by: str = "system",
    ) -> Narrative:
        """创建叙事"""
        narrative = Narrative(
            novel_id=novel_id,
            chapter_id=chapter_id,
            content=content,
            narrative_type=narrative_type,
            pov_character=pov_character,
            pov_type=pov_type,
            style_profile=style_profile or {},
            covers_events=covers_events or [],
            covers_steps=covers_steps or [],
            covers_facts=covers_facts or [],
            plot_function=plot_function,
            emotional_arc=emotional_arc or {},
            word_count=word_count or len(content),
            generated_by=generated_by,
        )
        return await self._repo.create(session, narrative)

    async def create_new_version(
        self,
        session: AsyncSession,
        narrative_id: str,
        new_content: str,
        generated_by: str = "system",
    ) -> Optional[Narrative]:
        """创建叙事新版本

        保留旧版本链接，创建新版本记录。
        """
        old = await self._repo.get_by_id(session, narrative_id)
        if not old:
            return None

        narrative = Narrative(
            novel_id=old.novel_id,
            chapter_id=old.chapter_id,
            content=new_content,
            narrative_type=old.narrative_type,
            pov_character=old.pov_character,
            pov_type=old.pov_type,
            style_profile=old.style_profile,
            covers_events=old.covers_events,
            covers_steps=old.covers_steps,
            covers_facts=old.covers_facts,
            plot_function=old.plot_function,
            emotional_arc=old.emotional_arc,
            word_count=len(new_content),
            version=old.version + 1,
            previous_version=old.id,
            generated_by=generated_by,
        )
        return await self._repo.create(session, narrative)

    async def get_chapter_narratives(
        self,
        session: AsyncSession,
        chapter_id: str,
        narrative_type: Optional[str] = None,
    ) -> List[Narrative]:
        """获取章节的所有叙事"""
        return await self._repo.get_by_chapter(session, chapter_id, narrative_type)

    async def get_pov_narratives(
        self,
        session: AsyncSession,
        character_id: str,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> List[Narrative]:
        """获取指定视角的所有叙事"""
        return await self._repo.get_by_pov(session, character_id, offset=offset, limit=limit)

    async def get_event_narratives(
        self,
        session: AsyncSession,
        event_id: str,
    ) -> List[Narrative]:
        """获取覆盖指定事件的所有叙事"""
        return await self._repo.get_by_event_coverage(session, event_id)

    async def check_event_coverage(
        self,
        session: AsyncSession,
        narrative_id: str,
        expected_events: List[str],
    ) -> Dict[str, Any]:
        """检查叙事是否覆盖所有预期事件

        Returns:
            {"covered": [...], "missing": [...], "coverage_rate": float}
        """
        narrative = await self._repo.get_by_id(session, narrative_id)
        if not narrative:
            return {"covered": [], "missing": expected_events, "coverage_rate": 0.0}

        covered = [eid for eid in expected_events if eid in narrative.covers_events]
        missing = [eid for eid in expected_events if eid not in narrative.covers_events]
        rate = len(covered) / len(expected_events) if expected_events else 1.0

        return {
            "covered": covered,
            "missing": missing,
            "coverage_rate": rate,
        }
