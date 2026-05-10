"""
世界状态服务 — 世界模拟核心业务逻辑

@file: services/world_state_service.py
@date: 2026-04-29
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from deepnovel.models import Fact, FactSource
from deepnovel.repositories import FactRepository


class WorldStateService:
    """世界状态服务 — 管理事实、实体状态、时间旅行查询

    核心能力：
    1. 原子性事实设置（自动处理时间范围）
    2. 实体完整状态查询（支持时间点）
    3. 事实传播效果（连锁反应）
    4. 反事实分支管理（假设分析）
    """

    def __init__(self, repository: Optional[FactRepository] = None):
        self._repo = repository or FactRepository()

    async def set_fact(
        self,
        session: AsyncSession,
        novel_id: str,
        subject_id: str,
        predicate: str,
        value: Dict[str, Any],
        *,
        fact_type: str = "attribute",
        confidence: float = 1.0,
        source: str = FactSource.INFERRED,
        chapter_id: Optional[str] = None,
        inference_chain: Optional[List[str]] = None,
        object_entity_id: Optional[str] = None,
    ) -> Fact:
        """设置事实（原子操作）

        流程：
        1. 标记旧事实为历史（设置 valid_until）
        2. 插入新事实（设置 valid_from）
        """
        # 1. 标记旧事实为历史
        await self._repo.invalidate_fact(session, subject_id, predicate)

        # 2. 创建新事实
        fact = Fact(
            novel_id=novel_id,
            subject_id=subject_id,
            predicate=predicate,
            object_value=value,
            fact_type=fact_type,
            confidence=confidence,
            source=source,
            chapter_id=chapter_id,
            inference_chain=inference_chain or [],
            object_entity_id=object_entity_id,
            valid_from=datetime.now(timezone.utc),
            valid_until=None,
        )

        return await self._repo.create(session, fact)

    async def get_current_state(
        self,
        session: AsyncSession,
        subject_id: str,
        predicate: str,
    ) -> Optional[Fact]:
        """获取当前有效事实"""
        return await self._repo.get_current_fact(session, subject_id, predicate)

    async def get_state_at_time(
        self,
        session: AsyncSession,
        subject_id: str,
        predicate: str,
        timestamp: datetime,
    ) -> Optional[Fact]:
        """时间旅行查询 — 获取指定时间点的事实"""
        return await self._repo.get_facts_at_time(session, subject_id, predicate, timestamp)

    async def get_entity_facts(
        self,
        session: AsyncSession,
        subject_id: str,
        predicate: Optional[str] = None,
    ) -> List[Fact]:
        """获取实体的所有事实"""
        return await self._repo.get_by_subject(session, subject_id, predicate)

    async def get_novel_facts(
        self,
        session: AsyncSession,
        novel_id: str,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> List[Fact]:
        """获取小说下所有事实"""
        return await self._repo.get_by_novel(session, novel_id, offset=offset, limit=limit)

    async def create_counterfactual_branch(
        self,
        session: AsyncSession,
        novel_id: str,
        base_branch: str,
        changes: List[Dict[str, Any]],
        name: str = "假设分析",
    ) -> str:
        """创建反事实分支

        Args:
            changes: 假设变化列表，每项包含 subject_id, predicate, new_value

        Returns:
            分支ID
        """
        import uuid

        branch_id = f"cf_{base_branch}_{uuid.uuid4().hex[:8]}"

        for change in changes:
            await self.set_fact(
                session,
                novel_id=novel_id,
                subject_id=change["subject_id"],
                predicate=change["predicate"],
                value=change["new_value"],
                source="counterfactual",
                inference_chain=[f"branch:{branch_id}"],
            )
            # 标记为反事实
            fact = await self._repo.get_current_fact(
                session, change["subject_id"], change["predicate"]
            )
            if fact:
                fact.is_counterfactual = True
                fact.counterfactual_branch = branch_id
                await self._repo.update(session, fact)

        return branch_id

    async def get_branch_facts(
        self,
        session: AsyncSession,
        branch_id: str,
    ) -> List[Fact]:
        """获取反事实分支的所有事实"""
        return await self._repo.get_by_counterfactual_branch(session, branch_id)
