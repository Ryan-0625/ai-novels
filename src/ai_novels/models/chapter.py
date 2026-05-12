"""
章节实体模型 — SQLModel版本

@file: models/chapter.py
@date: 2026-04-29
"""

from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, TYPE_CHECKING

from sqlalchemy import Column, Text, Integer, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import SQLModel, Field, Relationship

from .novel import new_uuid, utc_now

if TYPE_CHECKING:
    from .novel import Novel


class ChapterOutline(SQLModel, table=True):
    """章节大纲 — 写作前的规划"""
    __tablename__ = "chapter_outlines"

    id: str = Field(default_factory=new_uuid, primary_key=True)
    novel_id: str = Field(foreign_key="novels.id", index=True)
    chapter_number: int = Field(default=0, index=True)
    title: str = Field(default="")
    main_event: str = Field(default="", sa_column=Column(Text))
    pacing: int = Field(default=5)  # 1-10

    # JSONB 数组/对象
    required_beats: List[str] = Field(
        default_factory=list,
        sa_column=Column(JSONB, default=list),
    )
    emotional_trajectory: Dict[str, str] = Field(
        default_factory=dict,
        sa_column=Column(JSONB, default=dict),
    )
    hooks: List[str] = Field(
        default_factory=list,
        sa_column=Column(JSONB, default=list),
    )
    characters: List[str] = Field(
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

    # 关系（ChapterOutline是独立规划表，不建立双向关系避免冲突）
    novel: Optional["Novel"] = Relationship()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "outline_id": self.id,
            "chapter_number": self.chapter_number,
            "title": self.title,
            "main_event": self.main_event,
            "pacing": self.pacing,
            "required_beats": self.required_beats,
            "emotional_trajectory": self.emotional_trajectory,
            "hooks": self.hooks,
            "characters": self.characters,
        }


class ChapterContent(SQLModel, table=True):
    """章节正文 — 实际生成的内容"""
    __tablename__ = "chapter_contents"

    id: str = Field(default_factory=new_uuid, primary_key=True)
    novel_id: str = Field(foreign_key="novels.id", index=True)
    chapter_number: int = Field(default=0, index=True)
    title: str = Field(default="")
    content: str = Field(default="", sa_column=Column(Text))
    word_count: int = Field(default=0)
    status: str = Field(default="draft", index=True)  # draft, reviewed, published

    # JSONB 元数据
    meta_info: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSONB, default=dict),
    )
    # 版本历史
    versions: List[Dict[str, Any]] = Field(
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

    # 关系
    novel: Optional["Novel"] = Relationship(back_populates="chapters")
