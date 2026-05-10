"""
任务实体模型 — 小说生成任务

@file: models/task.py
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


class TaskStatus:
    """任务状态常量"""
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Task(SQLModel, table=True):
    """任务实体 — 追踪小说生成任务的完整生命周期"""
    __tablename__ = "tasks"

    id: str = Field(default_factory=new_uuid, primary_key=True)
    novel_id: Optional[str] = Field(default=None, foreign_key="novels.id", index=True)
    name: str = Field(default="")
    task_type: str = Field(default="", index=True)  # generate_novel, generate_chapter, etc.
    status: str = Field(default=TaskStatus.PENDING, index=True)
    progress: int = Field(default=0)  # 0-100

    # 输入配置
    config: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSONB, default=dict),
    )
    # 执行结果
    result: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSONB, default=dict),
    )
    # 错误信息
    error: Optional[str] = Field(default=None, sa_column=Column(Text))

    # 执行日志 (结构化)
    logs: List[Dict[str, Any]] = Field(
        default_factory=list,
        sa_column=Column(JSONB, default=list),
    )

    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True)),
    )
    started_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True)),
    )
    completed_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True)),
    )

    # 关系
    novel: Optional["Novel"] = Relationship(back_populates="tasks")
