"""
记忆系统 Agent 工具

Agent 可直接调用的记忆系统工具集：
- MemoryEncodingTool: 记忆编码
- MemoryRetrievalTool: 记忆检索
- MemoryConsolidationTool: 记忆巩固

@file: agents/tools/memory_tools.py
@date: 2026-04-29
"""

from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from deepnovel.models import (
    EpisodicMemory,
    SemanticMemory,
    EmotionalMemory,
    ProceduralMemory,
    KnowledgeType,
    SourceType,
    TriggerType,
    ReactionType,
    SkillCategory,
)
from deepnovel.services import (
    MemoryEncodingService,
    MemoryRetrievalService,
    MemoryConsolidationService,
    MemoryManager,
)


class MemoryEncodingTool:
    """记忆编码工具 — 将经历转化为长期记忆"""

    def __init__(
        self,
        encoding_service: Optional[MemoryEncodingService] = None,
    ):
        self._encoding = encoding_service or MemoryEncodingService()

    async def encode_experience(
        self,
        session: AsyncSession,
        character_id: str,
        scene_description: str,
        *,
        event_id: Optional[str] = None,
        emotional_valence: float = 0.0,
        emotional_arousal: float = 0.5,
        emotional_tags: Optional[List[str]] = None,
        context_tags: Optional[List[str]] = None,
        goal_relevance: float = 0.5,
        novelty: float = 0.5,
        outcome_impact: float = 0.0,
        is_flashbulb: bool = False,
    ) -> Dict[str, Any]:
        """编码经历为情节记忆

        Returns:
            记忆字典
        """
        memory = await self._encoding.encode_episodic(
            session,
            character_id,
            scene_description,
            event_id=event_id,
            emotional_valence=emotional_valence,
            emotional_arousal=emotional_arousal,
            emotional_tags=emotional_tags,
            context_tags=context_tags,
            goal_relevance=goal_relevance,
            novelty=novelty,
            outcome_impact=outcome_impact,
            is_flashbulb=is_flashbulb,
        )
        return memory.to_dict()

    async def learn_knowledge(
        self,
        session: AsyncSession,
        character_id: str,
        concept_key: str,
        concept_value: str,
        *,
        knowledge_type: str = KnowledgeType.WORLD_FACT,
        confidence: float = 0.8,
        source_type: str = SourceType.DIRECT_EXPERIENCE,
        source_event_id: Optional[str] = None,
        related_concepts: Optional[Dict[str, float]] = None,
    ) -> Dict[str, Any]:
        """学习知识（语义记忆）

        Returns:
            知识字典
        """
        memory = await self._encoding.encode_semantic(
            session,
            character_id,
            concept_key,
            concept_value,
            knowledge_type=knowledge_type,
            confidence=confidence,
            source_type=source_type,
            source_event_id=source_event_id,
            related_concepts=related_concepts,
        )
        return memory.to_dict()

    async def associate_emotion(
        self,
        session: AsyncSession,
        character_id: str,
        trigger_type: str,
        trigger_pattern: str,
        triggered_emotion: str,
        intensity: float,
        *,
        reaction_type: str = ReactionType.CONDITIONED,
        source_episodic_id: Optional[str] = None,
        conditioning_strength: float = 0.5,
    ) -> Dict[str, Any]:
        """建立情感关联（情感记忆）

        Returns:
            情感记忆字典
        """
        memory = await self._encoding.encode_emotional(
            session,
            character_id,
            trigger_type,
            trigger_pattern,
            triggered_emotion,
            intensity,
            reaction_type=reaction_type,
            source_episodic_id=source_episodic_id,
            conditioning_strength=conditioning_strength,
        )
        return memory.to_dict()

    async def learn_skill(
        self,
        session: AsyncSession,
        character_id: str,
        skill_name: str,
        skill_description: str,
        *,
        skill_category: str = SkillCategory.COGNITIVE,
        prerequisites: Optional[Dict[str, Any]] = None,
        execution_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """学习技能（程序记忆）

        Returns:
            技能记忆字典
        """
        memory = await self._encoding.encode_procedural(
            session,
            character_id,
            skill_name,
            skill_description,
            skill_category=skill_category,
            prerequisites=prerequisites,
            execution_context=execution_context,
        )
        return memory.to_dict()


class MemoryRetrievalTool:
    """记忆检索工具 — 从长期记忆提取信息"""

    def __init__(
        self,
        retrieval_service: Optional[MemoryRetrievalService] = None,
    ):
        self._retrieval = retrieval_service or MemoryRetrievalService()

    async def recall_experiences(
        self,
        session: AsyncSession,
        character_id: str,
        strategy: str = "adaptive",
        *,
        query_tags: Optional[List[str]] = None,
        target_emotion: Optional[str] = None,
        time_window: Optional[int] = None,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """回忆经历（情节记忆）

        Args:
            strategy: "adaptive" | "semantic" | "emotional" | "temporal" | "context"

        Returns:
            记忆字典列表
        """
        memories = await self._retrieval.recall_episodic(
            session,
            character_id,
            strategy,
            query_tags=query_tags,
            target_emotion=target_emotion,
            time_window=time_window,
            top_k=top_k,
        )
        return [m.to_dict() for m in memories]

    async def recall_knowledge(
        self,
        session: AsyncSession,
        character_id: str,
        concept_key: Optional[str] = None,
        *,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """回忆知识（语义记忆）"""
        memories = await self._retrieval.recall_semantic(
            session, character_id, concept_key, top_k=top_k
        )
        return [m.to_dict() for m in memories]

    async def recall_skills(
        self,
        session: AsyncSession,
        character_id: str,
        category: Optional[str] = None,
        *,
        automatic_only: bool = False,
    ) -> List[Dict[str, Any]]:
        """回忆技能（程序记忆）"""
        memories = await self._retrieval.recall_skills(
            session, character_id, category, automatic_only=automatic_only
        )
        return [m.to_dict() for m in memories]

    async def recall_emotional_patterns(
        self,
        session: AsyncSession,
        character_id: str,
        emotion: str,
        *,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """回忆情感模式（情感记忆）"""
        memories = await self._retrieval.recall_by_emotion(
            session, character_id, emotion, top_k=top_k
        )
        return [m.to_dict() for m in memories]


class MemoryConsolidationTool:
    """记忆巩固工具 — 强化和整合记忆"""

    def __init__(
        self,
        consolidation_service: Optional[MemoryConsolidationService] = None,
        encoding_service: Optional[MemoryEncodingService] = None,
    ):
        self._consolidation = consolidation_service or MemoryConsolidationService()
        self._encoding = encoding_service or MemoryEncodingService()

    async def rehearse(
        self,
        session: AsyncSession,
        memory_id: str,
        rehearsal_type: str = "active",
    ) -> Optional[Dict[str, Any]]:
        """复述记忆（增强强度）

        Returns:
            {"memory_id": str, "new_strength": float} 或 None
        """
        new_strength = await self._consolidation.rehearse(
            session, memory_id, rehearsal_type
        )
        if new_strength is None:
            return None
        return {"memory_id": memory_id, "new_strength": new_strength}

    async def extract_pattern(
        self,
        session: AsyncSession,
        character_id: str,
        pattern_name: str,
        pattern_description: str,
        *,
        confidence: float = 0.7,
    ) -> Dict[str, Any]:
        """从情节记忆中提取模式到语义记忆"""
        memory = await self._consolidation.consolidate_episodic_to_semantic(
            session,
            character_id,
            pattern_name,
            pattern_description,
            confidence=confidence,
        )
        return memory.to_dict()

    async def practice_skill(
        self,
        session: AsyncSession,
        skill_id: str,
        practice_amount: float = 0.1,
    ) -> Optional[Dict[str, Any]]:
        """练习技能（增强熟练度）

        Returns:
            更新后的技能字典或 None
        """
        skill = await self._consolidation.strengthen_skill(
            session, skill_id, practice_amount
        )
        if skill is None:
            return None
        return skill.to_dict()

    async def consolidate_from_experience(
        self,
        session: AsyncSession,
        character_id: str,
        experience_description: str,
        pattern_name: str,
        *,
        emotional_arousal: float = 0.5,
        goal_relevance: float = 0.5,
        novelty: float = 0.5,
    ) -> Dict[str, Any]:
        """完整巩固流程：编码经历 → 提取模式

        1. 编码经历为情节记忆
        2. 自动提取模式到语义记忆

        Returns:
            {"episodic": dict, "semantic": dict}
        """
        episodic = await self._encoding.encode_episodic(
            session,
            character_id,
            experience_description,
            emotional_arousal=emotional_arousal,
            goal_relevance=goal_relevance,
            novelty=novelty,
        )

        semantic = await self._consolidation.consolidate_episodic_to_semantic(
            session,
            character_id,
            pattern_name,
            f"从经历提取的模式：{experience_description}",
            confidence=episodic.importance * episodic.confidence
            if hasattr(episodic, "confidence")
            else episodic.importance,
        )

        return {
            "episodic": episodic.to_dict(),
            "semantic": semantic.to_dict(),
        }
