"""
世界模拟架构模型 — Step 1 数据层

支持：
- 事实管理（带时间范围的世界状态）
- 事件时间线（含因果链）
- 叙事记录（文学表达）
- 世界规则（约束引擎）

@file: models/world_simulation.py
@date: 2026-04-29
"""

from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, TYPE_CHECKING

from sqlalchemy import Column, Index, Text, Integer, DateTime, Float, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import SQLModel, Field, Relationship

from .novel import new_uuid, utc_now

if TYPE_CHECKING:
    from .novel import Novel


# ─── Fact（事实）───

class FactType:
    ATTRIBUTE = "attribute"
    RELATION = "relation"
    POSSESSION = "possession"
    EVENT = "event"
    RULE = "rule"
    INFERENCE = "inference"


class FactSource:
    OBSERVED = "observed"
    INFERRED = "inferred"
    TOLD = "told"
    ASSUMED = "assumed"
    SIMULATED = "simulated"


class Fact(SQLModel, table=True):
    """事实 — 世界状态机的核心，带时间范围的可追溯状态断言"""
    __tablename__ = "facts"

    id: str = Field(default_factory=new_uuid, primary_key=True)
    novel_id: str = Field(foreign_key="novels.id", index=True)

    fact_type: str = Field(default=FactType.ATTRIBUTE, index=True)
    subject_id: str = Field(index=True)  # 实体ID（角色/物品/地点等）
    predicate: str = Field(index=True)  # 谓语（属性/关系类型）
    object_value: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSONB, default=dict),
    )
    object_entity_id: Optional[str] = Field(default=None, index=True)

    # 时间范围（支持时间旅行查询）
    valid_from: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True)),
    )
    valid_until: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True)),
    )

    # 置信度与来源
    confidence: float = Field(default=1.0, sa_column=Column(Float))
    source: str = Field(default=FactSource.INFERRED, index=True)

    # 上下文关联
    chapter_id: Optional[str] = Field(default=None, foreign_key="chapter_contents.id")
    scene_id: Optional[str] = Field(default=None)

    # 推理链（记录推理路径）
    inference_chain: List[str] = Field(
        default_factory=list,
        sa_column=Column(JSONB, default=list),
    )

    # 反事实标记
    is_counterfactual: bool = Field(default=False, sa_column=Column(Boolean))
    counterfactual_branch: Optional[str] = Field(default=None)

    # 扩展元数据（使用meta_info避免与SQLAlchemy metadata冲突）
    meta_info: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSONB, default=dict),
    )

    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True)),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True)),
    )
    created_by: str = Field(default="system")

    # 复合索引优化时间旅行查询
    __table_args__ = (
        Index("ix_facts_subject_predicate_time", "subject_id", "predicate", "valid_from", "valid_until"),
        Index("ix_facts_current", "subject_id", "predicate", "valid_until", postgresql_where="valid_until IS NULL"),
        Index("ix_facts_counterfactual", "counterfactual_branch", "is_counterfactual"),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "fact_id": self.id,
            "fact_type": self.fact_type,
            "subject_id": self.subject_id,
            "predicate": self.predicate,
            "object_value": self.object_value,
            "object_entity_id": self.object_entity_id,
            "valid_from": self.valid_from.isoformat() if self.valid_from else None,
            "valid_until": self.valid_until.isoformat() if self.valid_until else None,
            "confidence": self.confidence,
            "source": self.source,
            "is_counterfactual": self.is_counterfactual,
            "counterfactual_branch": self.counterfactual_branch,
            "inference_chain": self.inference_chain,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ─── Event（事件）───

class EventType:
    ACTION = "action"
    PERCEPTION = "perception"
    DECISION = "decision"
    CHANGE = "change"
    INTERACTION = "interaction"
    ENVIRONMENT = "environment"
    SYSTEM = "system"


class Event(SQLModel, table=True):
    """事件 — 时间线核心，带因果链的世界变化记录"""
    __tablename__ = "events"

    id: str = Field(default_factory=new_uuid, primary_key=True)
    novel_id: str = Field(foreign_key="novels.id", index=True)
    chapter_id: Optional[str] = Field(default=None, foreign_key="chapter_contents.id")
    scene_id: Optional[str] = Field(default=None)

    event_type: str = Field(default=EventType.ACTION, index=True)
    event_subtype: Optional[str] = Field(default=None)

    description: str = Field(default="", sa_column=Column(Text))
    structured_data: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSONB, default=dict),
    )

    # 参与实体
    actor_id: Optional[str] = Field(default=None, foreign_key="characters.id")
    target_id: Optional[str] = Field(default=None, foreign_key="characters.id")
    participants: List[str] = Field(
        default_factory=list,
        sa_column=Column(JSONB, default=list),
    )

    # 事件效果
    effects: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSONB, default=dict),
    )

    # 因果链
    caused_by: List[str] = Field(
        default_factory=list,
        sa_column=Column(JSONB, default=list),
    )
    causes: List[str] = Field(
        default_factory=list,
        sa_column=Column(JSONB, default=list),
    )
    causal_strength: float = Field(default=1.0, sa_column=Column(Float))

    # 时间信息
    timestamp: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True)),
    )
    simulation_step: int = Field(default=0, index=True)
    duration: int = Field(default=1)

    # 空间信息
    location_id: Optional[str] = Field(default=None, foreign_key="world_entities.id")

    # 叙事关联
    narrative_coverage: List[str] = Field(
        default_factory=list,
        sa_column=Column(JSONB, default=list),
    )

    # 元数据
    importance: float = Field(default=0.5, sa_column=Column(Float))
    is_significant: bool = Field(default=False, sa_column=Column(Boolean))
    tags: List[str] = Field(
        default_factory=list,
        sa_column=Column(JSONB, default=list),
    )

    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True)),
    )

    # 复合索引
    __table_args__ = (
        Index("ix_events_timeline", "novel_id", "simulation_step", "timestamp"),
        Index("ix_events_actor", "actor_id", "simulation_step"),
        Index("ix_events_significant", "novel_id", "is_significant", "importance"),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.id,
            "event_type": self.event_type,
            "description": self.description,
            "actor_id": self.actor_id,
            "target_id": self.target_id,
            "participants": self.participants,
            "simulation_step": self.simulation_step,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "caused_by": self.caused_by,
            "causes": self.causes,
            "causal_strength": self.causal_strength,
            "importance": self.importance,
            "is_significant": self.is_significant,
            "effects": self.effects,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ─── Narrative（叙事）───

class NarrativeType:
    SCENE = "scene"
    DIALOGUE = "dialogue"
    DESCRIPTION = "description"
    MONOLOGUE = "monologue"
    TRANSITION = "transition"
    SUMMARY = "summary"


class POVType:
    THIRD_LIMITED = "third_limited"
    THIRD_OMNISCIENT = "third_omniscient"
    FIRST_PERSON = "first_person"
    SECOND_PERSON = "second_person"


class Narrative(SQLModel, table=True):
    """叙事 — 模拟事件的文学表达，精确映射到模拟事件"""
    __tablename__ = "narratives"

    id: str = Field(default_factory=new_uuid, primary_key=True)
    novel_id: str = Field(foreign_key="novels.id", index=True)
    chapter_id: str = Field(foreign_key="chapter_contents.id", index=True)

    narrative_type: str = Field(default=NarrativeType.SCENE, index=True)
    content: str = Field(default="", sa_column=Column(Text))
    content_structured: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSONB, default=dict),
    )

    # 视角
    pov_character: Optional[str] = Field(default=None, foreign_key="characters.id")
    pov_type: str = Field(default=POVType.THIRD_LIMITED)

    # 风格
    style_profile: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSONB, default=dict),
    )

    # 与模拟的关联（核心：叙事必须映射到模拟）
    covers_events: List[str] = Field(
        default_factory=list,
        sa_column=Column(JSONB, default=list),
    )
    covers_steps: List[int] = Field(
        default_factory=list,
        sa_column=Column(JSONB, default=list),
    )
    covers_facts: List[str] = Field(
        default_factory=list,
        sa_column=Column(JSONB, default=list),
    )

    # 叙事功能
    plot_function: Optional[str] = Field(default=None)  # exposition, rising_action, climax, etc.
    emotional_arc: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSONB, default=dict),
    )

    # 质量评估
    quality_metrics: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSONB, default=dict),
    )

    # 版本控制
    version: int = Field(default=1)
    previous_version: Optional[str] = Field(default=None, foreign_key="narratives.id")

    # 元数据
    word_count: Optional[int] = Field(default=None)
    reading_time: Optional[int] = Field(default=None)
    tags: List[str] = Field(
        default_factory=list,
        sa_column=Column(JSONB, default=list),
    )

    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True)),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True)),
    )
    generated_by: str = Field(default="system")

    # 复合索引
    __table_args__ = (
        Index("ix_narratives_chapter", "chapter_id", "narrative_type"),
        Index("ix_narratives_pov", "pov_character", "narrative_type"),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "narrative_id": self.id,
            "narrative_type": self.narrative_type,
            "content": self.content,
            "pov_character": self.pov_character,
            "pov_type": self.pov_type,
            "covers_events": self.covers_events,
            "covers_steps": self.covers_steps,
            "plot_function": self.plot_function,
            "word_count": self.word_count,
            "version": self.version,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "generated_by": self.generated_by,
        }


# ─── WorldRule（世界规则）───

class RuleType:
    PHYSICAL = "physical"
    MAGICAL = "magical"
    SOCIAL = "social"
    CAUSAL = "causal"
    CONSTRAINT = "constraint"


class WorldRule(SQLModel, table=True):
    """世界规则 — 约束引擎，定义世界运行法则"""
    __tablename__ = "world_rules"

    id: str = Field(default_factory=new_uuid, primary_key=True)
    novel_id: str = Field(foreign_key="novels.id", index=True)

    rule_name: str = Field(index=True)
    rule_type: str = Field(default=RuleType.PHYSICAL, index=True)

    # 规则内容
    condition: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSONB, default=dict),
    )
    action: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSONB, default=dict),
    )
    priority: int = Field(default=100)  # 数字越小优先级越高

    # 规则属性
    is_active: bool = Field(default=True, sa_column=Column(Boolean))
    description: Optional[str] = Field(default=None, sa_column=Column(Text))

    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True)),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.id,
            "rule_name": self.rule_name,
            "rule_type": self.rule_type,
            "condition": self.condition,
            "action": self.action,
            "priority": self.priority,
            "is_active": self.is_active,
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
