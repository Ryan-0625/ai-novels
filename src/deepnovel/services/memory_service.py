"""
记忆系统 Service — 编码/检索/巩固/遗忘

@file: services/memory_service.py
@date: 2026-04-29
"""

import math
import time
from datetime import datetime, timezone
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
from deepnovel.repositories import (
    EpisodicMemoryRepository,
    SemanticMemoryRepository,
    EmotionalMemoryRepository,
    ProceduralMemoryRepository,
)


class MemoryEncodingService:
    """记忆编码服务 — 将经历转化为长期记忆"""

    def __init__(
        self,
        episodic_repo: Optional[EpisodicMemoryRepository] = None,
        semantic_repo: Optional[SemanticMemoryRepository] = None,
        emotional_repo: Optional[EmotionalMemoryRepository] = None,
        procedural_repo: Optional[ProceduralMemoryRepository] = None,
    ):
        self._episodic = episodic_repo or EpisodicMemoryRepository()
        self._semantic = semantic_repo or SemanticMemoryRepository()
        self._emotional = emotional_repo or EmotionalMemoryRepository()
        self._procedural = procedural_repo or ProceduralMemoryRepository()

    def _calculate_importance(
        self,
        emotional_arousal: float,
        goal_relevance: float,
        novelty: float,
        outcome_impact: float = 0.0,
    ) -> float:
        """计算记忆重要性"""
        importance = (
            emotional_arousal * 0.3 +
            goal_relevance * 0.4 +
            novelty * 0.2 +
            abs(outcome_impact) * 0.1
        )
        return min(1.0, importance)

    def _calculate_initial_strength(
        self,
        importance: float,
        emotional_arousal: float,
        novelty: float,
    ) -> float:
        """计算初始记忆强度"""
        return min(1.0, importance * 0.5 + emotional_arousal * 0.3 + novelty * 0.2)

    def _calculate_decay_rate(
        self,
        importance: float,
        emotional_arousal: float,
    ) -> float:
        """计算衰减率（重要性和情感高的记忆衰减更慢）"""
        base_rate = 0.1
        importance_factor = 1.0 - importance * 0.5  # 重要性高 → 衰减慢
        emotion_factor = 1.0 - emotional_arousal * 0.3  # 情感强 → 衰减慢
        return base_rate * importance_factor * emotion_factor

    async def encode_episodic(
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
        sensory_cues: Optional[List[str]] = None,
        goal_relevance: float = 0.5,
        novelty: float = 0.5,
        outcome_impact: float = 0.0,
        is_flashbulb: bool = False,
    ) -> EpisodicMemory:
        """编码情节记忆"""
        importance = self._calculate_importance(
            emotional_arousal, goal_relevance, novelty, outcome_impact
        )
        initial_strength = self._calculate_initial_strength(
            importance, emotional_arousal, novelty
        )
        decay_rate = self._calculate_decay_rate(importance, emotional_arousal)

        memory = EpisodicMemory(
            character_id=character_id,
            event_id=event_id,
            scene_description=scene_description,
            emotional_valence=emotional_valence,
            emotional_arousal=emotional_arousal,
            emotional_tags=emotional_tags or [],
            strength=initial_strength,
            initial_strength=initial_strength,
            decay_rate=decay_rate,
            context_tags=context_tags or [],
            sensory_cues=sensory_cues or [],
            importance=importance,
            is_flashbulb=is_flashbulb,
            is_consolidated=importance > 0.8 or emotional_arousal > 0.8,
        )
        return await self._episodic.create(session, memory)

    async def encode_semantic(
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
    ) -> SemanticMemory:
        """编码语义记忆（知识）"""
        # 检查是否已有相似知识
        existing = await self._semantic.get_by_concept(session, character_id, concept_key)
        if existing:
            # 合并知识（加权平均）
            old_weight = existing.confidence * existing.evidence_count
            new_weight = confidence * 1
            total_weight = old_weight + new_weight
            existing.concept_value = concept_value
            existing.confidence = (old_weight * existing.confidence + new_weight * confidence) / total_weight
            existing.evidence_count += 1
            existing.updated_at = datetime.now(timezone.utc)
            if related_concepts:
                existing.related_concepts.update(related_concepts)
            return await self._semantic.update(session, existing)

        knowledge = SemanticMemory(
            character_id=character_id,
            concept_key=concept_key,
            concept_value=concept_value,
            knowledge_type=knowledge_type,
            confidence=confidence,
            source_type=source_type,
            source_event_id=source_event_id,
            related_concepts=related_concepts or {},
        )
        return await self._semantic.create(session, knowledge)

    async def encode_emotional(
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
    ) -> EmotionalMemory:
        """编码情感记忆"""
        em = EmotionalMemory(
            character_id=character_id,
            trigger_type=trigger_type,
            trigger_pattern=trigger_pattern,
            triggered_emotion=triggered_emotion,
            intensity=intensity,
            reaction_type=reaction_type,
            source_episodic_id=source_episodic_id,
            conditioning_strength=conditioning_strength,
        )
        return await self._emotional.create(session, em)

    async def encode_procedural(
        self,
        session: AsyncSession,
        character_id: str,
        skill_name: str,
        skill_description: str,
        *,
        skill_category: str = SkillCategory.COGNITIVE,
        prerequisites: Optional[Dict[str, Any]] = None,
        execution_context: Optional[Dict[str, Any]] = None,
    ) -> ProceduralMemory:
        """编码程序记忆（技能）"""
        skill = ProceduralMemory(
            character_id=character_id,
            skill_name=skill_name,
            skill_description=skill_description,
            skill_category=skill_category,
            prerequisites=prerequisites or {},
            execution_context=execution_context or {},
        )
        return await self._procedural.create(session, skill)


class MemoryRetrievalService:
    """记忆检索服务 — 从长期记忆提取信息"""

    def __init__(
        self,
        episodic_repo: Optional[EpisodicMemoryRepository] = None,
        semantic_repo: Optional[SemanticMemoryRepository] = None,
        emotional_repo: Optional[EmotionalMemoryRepository] = None,
        procedural_repo: Optional[ProceduralMemoryRepository] = None,
    ):
        self._episodic = episodic_repo or EpisodicMemoryRepository()
        self._semantic = semantic_repo or SemanticMemoryRepository()
        self._emotional = emotional_repo or EmotionalMemoryRepository()
        self._procedural = procedural_repo or ProceduralMemoryRepository()

    async def recall_episodic(
        self,
        session: AsyncSession,
        character_id: str,
        strategy: str = "adaptive",
        *,
        query_tags: Optional[List[str]] = None,
        target_emotion: Optional[str] = None,
        time_window: Optional[int] = None,
        top_k: int = 5,
    ) -> List[EpisodicMemory]:
        """回忆情节记忆（多策略）

        Args:
            strategy: "adaptive" | "semantic" | "emotional" | "temporal" | "context"
        """
        if strategy == "emotional" and target_emotion:
            # 情感匹配
            memories = await self._episodic.get_by_character(session, character_id, limit=top_k * 2)
            filtered = [m for m in memories if target_emotion in m.emotional_tags]
            return sorted(filtered, key=lambda m: m.strength, reverse=True)[:top_k]

        elif strategy == "temporal" and time_window:
            # 时间邻近
            return await self._episodic.get_recent(session, character_id, time_window)

        elif strategy == "context" and query_tags:
            # 情境匹配
            return await self._episodic.get_by_context_tags(session, character_id, query_tags)

        else:  # adaptive / semantic
            # 默认：按强度排序返回
            return await self._episodic.get_by_character(session, character_id, limit=top_k)

    async def recall_semantic(
        self,
        session: AsyncSession,
        character_id: str,
        concept_key: Optional[str] = None,
        *,
        top_k: int = 5,
    ) -> List[SemanticMemory]:
        """回忆语义记忆"""
        if concept_key:
            memory = await self._semantic.get_by_concept(session, character_id, concept_key)
            return [memory] if memory else []
        return await self._semantic.get_by_character(session, character_id)

    async def recall_by_emotion(
        self,
        session: AsyncSession,
        character_id: str,
        emotion: str,
        *,
        top_k: int = 5,
    ) -> List[EpisodicMemory]:
        """按情感回忆（情感一致性效应）"""
        return await self._emotional.get_by_emotion(session, character_id, emotion)

    async def recall_skills(
        self,
        session: AsyncSession,
        character_id: str,
        category: Optional[str] = None,
        *,
        automatic_only: bool = False,
    ) -> List[ProceduralMemory]:
        """回忆技能"""
        if automatic_only:
            return await self._procedural.get_automatic_skills(session, character_id)
        return await self._procedural.get_by_character(session, character_id, category)

    async def get_skill(
        self,
        session: AsyncSession,
        character_id: str,
        skill_name: str,
    ) -> Optional[ProceduralMemory]:
        """获取特定技能"""
        return await self._procedural.get_by_skill_name(session, character_id, skill_name)


class MemoryConsolidationService:
    """记忆巩固服务 — 强化和整合记忆"""

    def __init__(
        self,
        episodic_repo: Optional[EpisodicMemoryRepository] = None,
        semantic_repo: Optional[SemanticMemoryRepository] = None,
        procedural_repo: Optional[ProceduralMemoryRepository] = None,
    ):
        self._episodic = episodic_repo or EpisodicMemoryRepository()
        self._semantic = semantic_repo or SemanticMemoryRepository()
        self._procedural = procedural_repo or ProceduralMemoryRepository()

    async def rehearse(
        self,
        session: AsyncSession,
        memory_id: str,
        rehearsal_type: str = "active",
    ) -> Optional[float]:
        """复述记忆（增强强度）

        Returns:
            更新后的记忆强度
        """
        memory = await self._episodic.get_by_id(session, memory_id)
        if not memory:
            return None

        memory.rehearsal_count += 1
        memory.last_rehearsed = datetime.now(timezone.utc)

        # 根据复述类型增强
        boosts = {"active": 0.15, "emotional": 0.25, "passive": 0.1}
        boost = boosts.get(rehearsal_type, 0.1)

        memory.strength = min(1.0, memory.strength + boost)

        # 检查是否巩固
        if memory.rehearsal_count >= 3 and not memory.is_consolidated:
            memory.is_consolidated = True
            memory.decay_rate *= 0.7  # 巩固后衰减更慢

        await self._episodic.update(session, memory)
        return memory.strength

    async def consolidate_episodic_to_semantic(
        self,
        session: AsyncSession,
        character_id: str,
        pattern_name: str,
        pattern_description: str,
        *,
        confidence: float = 0.7,
    ) -> SemanticMemory:
        """将情节记忆模式提取为语义记忆"""
        return await self._semantic.create(
            session,
            SemanticMemory(
                character_id=character_id,
                concept_key=pattern_name,
                concept_value=pattern_description,
                knowledge_type=KnowledgeType.BELIEF,
                confidence=confidence,
                source_type=SourceType.INFERRED,
            ),
        )

    async def strengthen_skill(
        self,
        session: AsyncSession,
        skill_id: str,
        practice_amount: float = 0.1,
    ) -> Optional[ProceduralMemory]:
        """通过练习增强技能"""
        skill = await self._procedural.get_by_id(session, skill_id)
        if not skill:
            return None

        skill.proficiency = min(1.0, skill.proficiency + practice_amount)
        skill.practice_count += 1

        # 自动化阈值
        if skill.proficiency >= 0.8 and skill.practice_count >= 20:
            skill.is_automatic = True
            skill.attention_required = max(0.1, skill.attention_required - 0.2)

        return await self._procedural.update(session, skill)


class MemoryForgettingService:
    """记忆遗忘服务 — 主动优化记忆系统"""

    def __init__(
        self,
        episodic_repo: Optional[EpisodicMemoryRepository] = None,
    ):
        self._episodic = episodic_repo or EpisodicMemoryRepository()

    def _calculate_current_strength(
        self,
        memory: EpisodicMemory,
        current_time: datetime,
    ) -> float:
        """计算当前记忆强度（考虑时间衰减）"""
        time_diff = (current_time - memory.encoded_at).total_seconds() / 86400  # 天数
        time_decay = math.exp(-memory.decay_rate * time_diff)

        # 复述增益
        rehearsal_boost = 1 + memory.rehearsal_count * 0.2

        # 情感增益
        emotional_boost = 1 + memory.emotional_arousal * 0.5

        # 巩固保护
        consolidation_boost = 2.0 if memory.is_consolidated else 1.0

        current_strength = (
            memory.initial_strength *
            time_decay *
            rehearsal_boost *
            emotional_boost *
            consolidation_boost
        )
        return min(1.0, current_strength)

    def _should_protect(self, memory: EpisodicMemory) -> bool:
        """判断是否应该保护记忆不被遗忘"""
        if memory.is_flashbulb:
            return True
        if memory.access_count > 10:
            return True
        if memory.importance > 0.9:
            return True
        return False

    async def apply_forgetting(
        self,
        session: AsyncSession,
        character_id: str,
        threshold: float = 0.1,
    ) -> List[str]:
        """应用遗忘机制

        Returns:
            被遗忘的记忆ID列表
        """
        now = datetime.now(timezone.utc)
        memories = await self._episodic.get_by_character(
            session, character_id, limit=1000
        )

        forgotten = []
        for memory in memories:
            current_strength = self._calculate_current_strength(memory, now)

            # 更新数据库中的强度
            memory.strength = current_strength
            await self._episodic.update(session, memory)

            # 判断是否遗忘
            if current_strength < threshold and not self._should_protect(memory):
                await self._episodic.delete(session, memory)
                forgotten.append(memory.id)

        return forgotten


class MemoryManager:
    """记忆管理器 — 统一入口，整合编码/检索/巩固/遗忘"""

    def __init__(
        self,
        encoding: Optional[MemoryEncodingService] = None,
        retrieval: Optional[MemoryRetrievalService] = None,
        consolidation: Optional[MemoryConsolidationService] = None,
        forgetting: Optional[MemoryForgettingService] = None,
    ):
        self.encoding = encoding or MemoryEncodingService()
        self.retrieval = retrieval or MemoryRetrievalService()
        self.consolidation = consolidation or MemoryConsolidationService()
        self.forgetting = forgetting or MemoryForgettingService()

    async def record_experience(
        self,
        session: AsyncSession,
        character_id: str,
        scene_description: str,
        **kwargs,
    ) -> EpisodicMemory:
        """记录经历（便捷方法）"""
        return await self.encoding.encode_episodic(
            session, character_id, scene_description, **kwargs
        )

    async def learn_fact(
        self,
        session: AsyncSession,
        character_id: str,
        concept_key: str,
        concept_value: str,
        **kwargs,
    ) -> SemanticMemory:
        """学习知识（便捷方法）"""
        return await self.encoding.encode_semantic(
            session, character_id, concept_key, concept_value, **kwargs
        )

    async def recall(
        self,
        session: AsyncSession,
        character_id: str,
        strategy: str = "adaptive",
        **kwargs,
    ) -> List[EpisodicMemory]:
        """回忆情节记忆（便捷方法）"""
        return await self.retrieval.recall_episodic(
            session, character_id, strategy, **kwargs
        )

    async def rehearse_memory(
        self,
        session: AsyncSession,
        memory_id: str,
        rehearsal_type: str = "active",
    ) -> Optional[float]:
        """复述记忆（便捷方法）"""
        return await self.consolidation.rehearse(session, memory_id, rehearsal_type)

    async def run_forgetting(
        self,
        session: AsyncSession,
        character_id: str,
        threshold: float = 0.1,
    ) -> List[str]:
        """运行遗忘机制（便捷方法）"""
        return await self.forgetting.apply_forgetting(
            session, character_id, threshold
        )
