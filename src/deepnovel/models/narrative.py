"""
叙事元素模型 — 冲突与钩子

@file: models/narrative.py
@date: 2026-04-29
"""

from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, TYPE_CHECKING

from sqlalchemy import Column, Integer, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import SQLModel, Field, Relationship

from .novel import new_uuid, utc_now

if TYPE_CHECKING:
    from .novel import Novel


class Conflict(SQLModel, table=True):
    """冲突实体 — 推动情节发展的核心动力"""
    __tablename__ = "conflicts"

    id: str = Field(default_factory=new_uuid, primary_key=True)
    novel_id: str = Field(foreign_key="novels.id", index=True)
    title: str = Field(default="")
    type: str = Field(default="", index=True)  # character, external, internal, moral
    intensity: int = Field(default=5)  # 1-10
    status: str = Field(default="active", index=True)  # active, resolved, escalated

    # JSONB 关联数据
    involved_characters: List[str] = Field(
        default_factory=list,
        sa_column=Column(JSONB, default=list),
    )
    escalate_count: int = Field(default=0)

    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True)),
    )
    resolved_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True)),
    )

    # 关系
    novel: Optional["Novel"] = Relationship(back_populates="conflicts")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "conflict_id": self.id,
            "title": self.title,
            "type": self.type,
            "intensity": self.intensity,
            "status": self.status,
            "involved_characters": self.involved_characters,
            "escalate_count": self.escalate_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
        }


class NarrativeHook(SQLModel, table=True):
    """叙事钩子 — 悬念与读者粘性"""
    __tablename__ = "narrative_hooks"

    id: str = Field(default_factory=new_uuid, primary_key=True)
    novel_id: str = Field(foreign_key="novels.id", index=True)
    title: str = Field(default="")
    type: str = Field(default="", index=True)  # mystery, threat, cliffhanger, emotional_debt
    intensity: int = Field(default=5)  # 1-10
    status: str = Field(default="open", index=True)  # open, active, resolved, ignored

    # JSONB 关联数据
    chapters_mentioned: List[int] = Field(
        default_factory=list,
        sa_column=Column(JSONB, default=list),
    )
    resolved_in_chapter: Optional[int] = Field(default=None)
    associated_characters: List[str] = Field(
        default_factory=list,
        sa_column=Column(JSONB, default=list),
    )
    associated_world_entities: List[str] = Field(
        default_factory=list,
        sa_column=Column(JSONB, default=list),
    )

    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True)),
    )
    resolved_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True)),
    )

    # 关系
    novel: Optional["Novel"] = Relationship(back_populates="hooks")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hook_id": self.id,
            "title": self.title,
            "type": self.type,
            "intensity": self.intensity,
            "status": self.status,
            "chapters_mentioned": self.chapters_mentioned,
            "resolved_in_chapter": self.resolved_in_chapter,
            "associated_characters": self.associated_characters,
            "associated_world_entities": self.associated_world_entities,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
