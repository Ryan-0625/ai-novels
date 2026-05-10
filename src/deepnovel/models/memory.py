"""
记忆系统模型 — Step 2 三级阶梯架构

长期记忆模型：
- EpisodicMemory: 情节记忆（个人经历）
- SemanticMemory: 语义记忆（知识概念）
- EmotionalMemory: 情感记忆（情绪关联）
- ProceduralMemory: 程序记忆（技能习惯）

@file: models/memory.py
@date: 2026-04-29
"""

from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, TYPE_CHECKING

from sqlalchemy import Column, Index, Text, Integer, ForeignKey, DateTime, Float, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import SQLModel, Field, Relationship

from .novel import new_uuid, utc_now

if TYPE_CHECKING:
    from .novel import Character


# ─── EpisodicMemory（情节记忆）───

class EpisodicMemory(SQLModel, table=True):
    """情节记忆 — 个人经历，带情感标记和情境编码"""
    __tablename__ = "episodic_memories"

    id: str = Field(default_factory=new_uuid, primary_key=True)
    character_id: str = Field(foreign_key="characters.id", index=True)
    event_id: Optional[str] = Field(default=None, foreign_key="events.id", index=True)

    # 记忆内容
    scene_description: str = Field(default="", sa_column=Column(Text))

    # 时间编码
    experienced_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True)),
    )
    encoded_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True)),
    )

    # 情感标记（决定记忆强度）
    emotional_valence: float = Field(default=0.0, sa_column=Column(Float))  # -1 到 +1
    emotional_arousal: float = Field(default=0.5, sa_column=Column(Float))  # 0 到 1
    emotional_tags: List[str] = Field(
        default_factory=list,
        sa_column=Column(JSONB, default=list),
    )

    # 记忆强度（决定可提取性）
    strength: float = Field(default=0.5, sa_column=Column(Float))
    initial_strength: float = Field(default=0.5, sa_column=Column(Float))
    decay_rate: float = Field(default=0.1, sa_column=Column(Float))

    # 巩固状态
    rehearsal_count: int = Field(default=0)
    last_rehearsed: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True)),
    )
    is_consolidated: bool = Field(default=False, sa_column=Column(Boolean))

    # 情境编码（提取线索）
    context_tags: List[str] = Field(
        default_factory=list,
        sa_column=Column(JSONB, default=list),
    )
    sensory_cues: List[str] = Field(
        default_factory=list,
        sa_column=Column(JSONB, default=list),
    )

    # 元数据
    importance: float = Field(default=0.5, sa_column=Column(Float))
    is_flashbulb: bool = Field(default=False, sa_column=Column(Boolean))

    # 访问统计
    access_count: int = Field(default=0)
    last_accessed: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True)),
    )

    # 复合索引
    __table_args__ = (
        Index("ix_episodic_character_strength", "character_id", "strength"),
        Index("ix_episodic_emotion", "character_id", "emotional_valence", "emotional_arousal"),
        Index("ix_episodic_time", "character_id", "experienced_at"),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "memory_id": self.id,
            "character_id": self.character_id,
            "event_id": self.event_id,
            "scene_description": self.scene_description,
            "emotional_valence": self.emotional_valence,
            "emotional_arousal": self.emotional_arousal,
            "emotional_tags": self.emotional_tags,
            "strength": self.strength,
            "importance": self.importance,
            "is_consolidated": self.is_consolidated,
            "rehearsal_count": self.rehearsal_count,
            "context_tags": self.context_tags,
            "is_flashbulb": self.is_flashbulb,
        }


# ─── SemanticMemory（语义记忆）───

class KnowledgeType:
    WORLD_FACT = "world_fact"
    SOCIAL_NORM = "social_norm"
    PERSONAL_TRAIT = "personal_trait"
    RELATIONSHIP = "relationship"
    SKILL = "skill"
    BELIEF = "belief"


class SourceType:
    DIRECT_EXPERIENCE = "direct_experience"
    TOLD_BY_TRUSTED = "told_by_trusted"
    TOLD_BY_UNTRUSTED = "told_by_untrusted"
    INFERRED = "inferred"
    ASSUMED = "assumed"


class SemanticMemory(SQLModel, table=True):
    """语义记忆 — 知识概念，带置信度和证据链"""
    __tablename__ = "semantic_memories"

    id: str = Field(default_factory=new_uuid, primary_key=True)
    character_id: str = Field(foreign_key="characters.id", index=True)

    # 知识内容
    concept_key: str = Field(index=True)
    concept_value: str = Field(default="", sa_column=Column(Text))
    knowledge_type: str = Field(default=KnowledgeType.WORLD_FACT, index=True)

    # 置信度
    confidence: float = Field(default=0.8, sa_column=Column(Float))
    evidence_count: int = Field(default=1)

    # 来源
    source_type: str = Field(default=SourceType.DIRECT_EXPERIENCE)
    source_event_id: Optional[str] = Field(default=None, foreign_key="events.id")

    # 关联网络
    related_concepts: Dict[str, float] = Field(
        default_factory=dict,
        sa_column=Column(JSONB, default=dict),
    )

    # 使用统计
    access_count: int = Field(default=0)
    last_accessed: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True)),
    )

    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True)),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True)),
    )

    # 复合索引
    __table_args__ = (
        Index("ix_semantic_character_type", "character_id", "knowledge_type"),
        Index("ix_semantic_concept", "character_id", "concept_key"),
        Index("ix_semantic_confidence", "character_id", "confidence"),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "memory_id": self.id,
            "character_id": self.character_id,
            "concept_key": self.concept_key,
            "concept_value": self.concept_value,
            "knowledge_type": self.knowledge_type,
            "confidence": self.confidence,
            "evidence_count": self.evidence_count,
            "source_type": self.source_type,
            "related_concepts": self.related_concepts,
        }


# ─── EmotionalMemory（情感记忆）───

class TriggerType:
    SITUATION_PATTERN = "situation_pattern"
    PERSON_PRESENCE = "person_presence"
    LOCATION_RETURN = "location_return"
    SENSORY_CUE = "sensory_cue"
    ANNIVERSARY = "anniversary"


class ReactionType:
    AUTOMATIC = "automatic"
    CONDITIONED = "conditioned"
    LEARNED = "learned"
    EMPATHETIC = "empathetic"


class EmotionalMemory(SQLModel, table=True):
    """情感记忆 — 触发器与情感反应的条件化关联"""
    __tablename__ = "emotional_memories"

    id: str = Field(default_factory=new_uuid, primary_key=True)
    character_id: str = Field(foreign_key="characters.id", index=True)

    # 触发器
    trigger_type: str = Field(default=TriggerType.SITUATION_PATTERN, index=True)
    trigger_pattern: str = Field(default="", sa_column=Column(Text))

    # 情感反应
    triggered_emotion: str = Field(index=True)
    intensity: float = Field(default=0.5, sa_column=Column(Float))
    reaction_type: str = Field(default=ReactionType.CONDITIONED)

    # 关联记忆
    source_episodic_id: Optional[str] = Field(
        default=None, foreign_key="episodic_memories.id"
    )

    # 条件化程度
    conditioning_strength: float = Field(default=0.5, sa_column=Column(Float))
    extinction_count: int = Field(default=0)

    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True)),
    )

    # 复合索引
    __table_args__ = (
        Index("ix_emotional_character_trigger", "character_id", "trigger_type"),
        Index("ix_emotional_character_emotion", "character_id", "triggered_emotion"),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "memory_id": self.id,
            "character_id": self.character_id,
            "trigger_type": self.trigger_type,
            "trigger_pattern": self.trigger_pattern,
            "triggered_emotion": self.triggered_emotion,
            "intensity": self.intensity,
            "reaction_type": self.reaction_type,
            "conditioning_strength": self.conditioning_strength,
            "extinction_count": self.extinction_count,
        }


# ─── ProceduralMemory（程序记忆）───

class SkillCategory:
    COMBAT = "combat"
    MAGIC = "magic"
    SOCIAL = "social"
    CRAFT = "craft"
    MOVEMENT = "movement"
    COGNITIVE = "cognitive"


class ProceduralMemory(SQLModel, table=True):
    """程序记忆 — 技能和习惯，带熟练度和自动化程度"""
    __tablename__ = "procedural_memories"

    id: str = Field(default_factory=new_uuid, primary_key=True)
    character_id: str = Field(foreign_key="characters.id", index=True)

    # 技能内容
    skill_name: str = Field(index=True)
    skill_description: Optional[str] = Field(default=None, sa_column=Column(Text))
    skill_category: str = Field(default=SkillCategory.COGNITIVE, index=True)

    # 熟练度
    proficiency: float = Field(default=0.0, sa_column=Column(Float))
    practice_count: int = Field(default=0)

    # 执行条件
    prerequisites: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSONB, default=dict),
    )
    execution_context: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSONB, default=dict),
    )

    # 自动化程度
    is_automatic: bool = Field(default=False, sa_column=Column(Boolean))
    attention_required: float = Field(default=0.5, sa_column=Column(Float))

    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True)),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True)),
    )

    # 复合索引
    __table_args__ = (
        Index("ix_procedural_character_category", "character_id", "skill_category"),
        Index("ix_procedural_character_proficiency", "character_id", "proficiency"),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "memory_id": self.id,
            "character_id": self.character_id,
            "skill_name": self.skill_name,
            "skill_category": self.skill_category,
            "proficiency": self.proficiency,
            "practice_count": self.practice_count,
            "is_automatic": self.is_automatic,
            "attention_required": self.attention_required,
        }
