"""
用户实体模型 — SQLModel
"""

from typing import List, Optional
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import SQLModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: str = Field(
        default_factory=lambda: str(uuid4()),
        primary_key=True,
    )
    tenant_id: str = Field(
        sa_column=Column(String(64), ForeignKey("tenants.id"), nullable=False, index=True),
    )
    username: str = Field(index=True, max_length=255)
    email: str = Field(default="", max_length=255)
    hashed_password: str = Field(default="", max_length=255)
    roles: List[str] = Field(
        default_factory=lambda: ["viewer"],
        sa_column=Column(JSONB, default=list),
    )
    is_active: bool = Field(default=True)
    last_login_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    preferences: dict = Field(
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
