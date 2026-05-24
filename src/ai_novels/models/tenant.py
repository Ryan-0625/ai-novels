"""
租户实体模型 — SQLModel
"""

from typing import List, Optional
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Column, String, Boolean, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import SQLModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Tenant(SQLModel, table=True):
    __tablename__ = "tenants"

    id: str = Field(
        default_factory=lambda: str(uuid4()),
        primary_key=True,
    )
    name: str = Field(index=True, max_length=255)
    tier: str = Field(default="free", max_length=32)
    features: List[str] = Field(
        default_factory=list,
        sa_column=Column(JSONB, default=list),
    )
    is_active: bool = Field(default=True)
    config_override: dict = Field(
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
