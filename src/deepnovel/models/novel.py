"""
小说、角色、世界观实体模型 — SQLModel版本

从 src/deepnovel/model/entities.py 的 dataclass 迁移而来。
使用 PostgreSQL JSONB 存储动态字段，保持灵活性同时获得类型安全。

@file: models/novel.py
@date: 2026-04-29
"""

import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, TYPE_CHECKING

from sqlalchemy import Column, Index, String, Text, Integer, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import SQLModel, Field, Relationship

if TYPE_CHECKING:
    from .chapter import ChapterContent, ChapterOutline
    from .narrative import Conflict, NarrativeHook
    from .task import Task


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def new_uuid() -> str:
    return str(uuid.uuid4())


class Novel(SQLModel, table=True):
    """小说实体 — 所有内容的根节点"""
    __tablename__ = "novels"

    id: str = Field(default_factory=new_uuid, primary_key=True)
    title: str = Field(index=True)
    genre: str = Field(default="")
    tone: str = Field(default="")
    target_audience: str = Field(default="")
    synopsis: str = Field(default="", sa_column=Column(Text))
    word_count_target: int = Field(default=50000)
    word_count_current: int = Field(default=0)
    status: str = Field(default="draft", index=True)  # draft, writing, completed, archived

    # JSONB 存储动态配置
    settings: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSONB, default=dict),
    )
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

    # 关系
    characters: List["Character"] = Relationship(back_populates="novel")
    world_entities: List["WorldEntity"] = Relationship(back_populates="novel")
    outlines: List["OutlineNode"] = Relationship(back_populates="novel")
    chapters: List["ChapterContent"] = Relationship(back_populates="novel")
    conflicts: List["Conflict"] = Relationship(back_populates="novel")
    hooks: List["NarrativeHook"] = Relationship(back_populates="novel")
    tasks: List["Task"] = Relationship(back_populates="novel")

    class Config:
        json_schema_extra = {
            "example": {
                "title": "星辰之海",
                "genre": "科幻",
                "tone": "史诗",
                "status": "draft",
            }
        }


class Character(SQLModel, table=True):
    """角色实体 — 世界仿真核心"""
    __tablename__ = "characters"

    id: str = Field(default_factory=new_uuid, primary_key=True)
    novel_id: str = Field(foreign_key="novels.id", index=True)
    name: str = Field(index=True)
    aliases: List[str] = Field(
        default_factory=list,
        sa_column=Column(JSONB, default=list),
    )
    age_visual: int = Field(default=0)
    age_real: Optional[int] = Field(default=None)
    gender: str = Field(default="")
    archetype: str = Field(default="", index=True)
    core_drive: str = Field(default="")
    core_wound: str = Field(default="")
    voice_style: str = Field(default="")

    # JSONB 扩展档案
    profile: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSONB, default=dict),
    )
    # 角色心智状态 (Step1 CharacterMind)
    mental_state: Dict[str, Any] = Field(
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

    # 关系
    novel: Novel = Relationship(back_populates="characters")

    # 复合索引：按小说查询角色
    __table_args__ = (
        Index("ix_character_novel_name", "novel_id", "name"),
    )

    def to_dict(self) -> Dict[str, Any]:
        """向后兼容：转换为字典"""
        return {
            "char_id": self.id,
            "name": self.name,
            "aliases": self.aliases,
            "age_visual": self.age_visual,
            "age_real": self.age_real,
            "gender": self.gender,
            "archetype": self.archetype,
            "core_drive": self.core_drive,
            "core_wound": self.core_wound,
            "voice_style": self.voice_style,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "profile": self.profile,
        }


class WorldEntity(SQLModel, table=True):
    """世界观实体 — 魔法、地理、历史、派系、科技"""
    __tablename__ = "world_entities"

    id: str = Field(default_factory=new_uuid, primary_key=True)
    novel_id: str = Field(foreign_key="novels.id", index=True)
    name: str = Field(index=True)
    category: str = Field(index=True)  # magic, geography, history, faction, technology
    public_description: str = Field(default="", sa_column=Column(Text))
    secret_truth: str = Field(default="", sa_column=Column(Text))
    unspoken_tension: str = Field(default="", sa_column=Column(Text))
    tags: List[str] = Field(
        default_factory=list,
        sa_column=Column(JSONB, default=list),
    )

    # JSONB 因果关系网络 (Step1 CausalReasoning)
    causal_links: Dict[str, Any] = Field(
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

    # 关系
    novel: Novel = Relationship(back_populates="world_entities")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "world_id": self.id,
            "name": self.name,
            "category": self.category,
            "public_description": self.public_description,
            "secret_truth": self.secret_truth,
            "unspoken_tension": self.unspoken_tension,
            "tags": self.tags,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class OutlineNode(SQLModel, table=True):
    """大纲节点（卷/章/场景）"""
    __tablename__ = "outline_nodes"

    id: str = Field(default_factory=new_uuid, primary_key=True)
    novel_id: str = Field(foreign_key="novels.id", index=True)
    parent_id: Optional[str] = Field(default=None, foreign_key="outline_nodes.id", index=True)
    node_type: str = Field(index=True)  # volume, chapter, scene
    title: str = Field(default="")
    order_index: int = Field(default=0)
    content: Optional[str] = Field(default=None, sa_column=Column(Text))

    # JSONB 元数据
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

    # 关系
    novel: Novel = Relationship(back_populates="outlines")

    __table_args__ = (
        Index("ix_outline_novel_type_order", "novel_id", "node_type", "order_index"),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.id,
            "node_type": self.node_type,
            "title": self.title,
            "content": self.content,
            "metadata": self.metadata,
        }
