"""Initial schema: all tables including multi-tenant support

Revision ID: 001_initial_schema
Revises:
Create Date: 2026-05-24
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

# revision identifiers, used by Alembic.
revision: str = "001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ──────────────────────────────────────────────────────────
    # 1. 租户表 (新)
    # ──────────────────────────────────────────────────────────
    op.create_table(
        "tenants",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False, index=True),
        sa.Column("tier", sa.String(32), server_default="free"),
        sa.Column("features", JSONB, server_default="[]"),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("config_override", JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )

    # ──────────────────────────────────────────────────────────
    # 2. 用户表 (新)
    # ──────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(64),
                  sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("username", sa.String(255), nullable=False, index=True),
        sa.Column("email", sa.String(255), server_default=""),
        sa.Column("hashed_password", sa.String(255), server_default=""),
        sa.Column("roles", JSONB, server_default='["viewer"]'),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("preferences", JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )

    # ──────────────────────────────────────────────────────────
    # 3. 小说表
    # ──────────────────────────────────────────────────────────
    op.create_table(
        "novels",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("title", sa.String(255), nullable=False, index=True),
        sa.Column("genre", sa.String(64), server_default=""),
        sa.Column("tone", sa.String(64), server_default=""),
        sa.Column("target_audience", sa.String(64), server_default=""),
        sa.Column("synopsis", sa.Text, server_default=""),
        sa.Column("word_count_target", sa.Integer, server_default="50000"),
        sa.Column("word_count_current", sa.Integer, server_default="0"),
        sa.Column("status", sa.String(32), server_default="draft", index=True),
        sa.Column("tenant_id", sa.String(64),
                  sa.ForeignKey("tenants.id"), nullable=True, index=True),
        sa.Column("settings", JSONB, server_default="{}"),
        sa.Column("meta_info", JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )

    # ──────────────────────────────────────────────────────────
    # 4. 角色表
    # ──────────────────────────────────────────────────────────
    op.create_table(
        "characters",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("novel_id", sa.String(64),
                  sa.ForeignKey("novels.id"), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False, index=True),
        sa.Column("aliases", JSONB, server_default="[]"),
        sa.Column("age_visual", sa.Integer, server_default="0"),
        sa.Column("age_real", sa.Integer, nullable=True),
        sa.Column("gender", sa.String(32), server_default=""),
        sa.Column("archetype", sa.String(64), server_default="", index=True),
        sa.Column("core_drive", sa.Text, server_default=""),
        sa.Column("core_wound", sa.Text, server_default=""),
        sa.Column("voice_style", sa.Text, server_default=""),
        sa.Column("tenant_id", sa.String(64),
                  sa.ForeignKey("tenants.id"), nullable=True, index=True),
        sa.Column("profile", JSONB, server_default="{}"),
        sa.Column("mental_state", JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_character_novel_name", "characters", ["novel_id", "name"])

    # ──────────────────────────────────────────────────────────
    # 5. 世界观实体表
    # ──────────────────────────────────────────────────────────
    op.create_table(
        "world_entities",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("novel_id", sa.String(64),
                  sa.ForeignKey("novels.id"), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False, index=True),
        sa.Column("category", sa.String(64), nullable=False, index=True),
        sa.Column("public_description", sa.Text, server_default=""),
        sa.Column("secret_truth", sa.Text, server_default=""),
        sa.Column("unspoken_tension", sa.Text, server_default=""),
        sa.Column("tags", JSONB, server_default="[]"),
        sa.Column("tenant_id", sa.String(64),
                  sa.ForeignKey("tenants.id"), nullable=True, index=True),
        sa.Column("causal_links", JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )

    # ──────────────────────────────────────────────────────────
    # 6. 大纲节点表
    # ──────────────────────────────────────────────────────────
    op.create_table(
        "outline_nodes",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("novel_id", sa.String(64),
                  sa.ForeignKey("novels.id"), nullable=False, index=True),
        sa.Column("parent_id", sa.String(64),
                  sa.ForeignKey("outline_nodes.id"), nullable=True, index=True),
        sa.Column("node_type", sa.String(32), nullable=False, index=True),
        sa.Column("title", sa.String(255), server_default=""),
        sa.Column("order_index", sa.Integer, server_default="0"),
        sa.Column("content", sa.Text, nullable=True),
        sa.Column("tenant_id", sa.String(64),
                  sa.ForeignKey("tenants.id"), nullable=True, index=True),
        sa.Column("meta_info", JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_outline_novel_type_order", "outline_nodes",
                    ["novel_id", "node_type", "order_index"])

    # ──────────────────────────────────────────────────────────
    # 7. 章节大纲表
    # ──────────────────────────────────────────────────────────
    op.create_table(
        "chapter_outlines",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("novel_id", sa.String(64),
                  sa.ForeignKey("novels.id"), nullable=False, index=True),
        sa.Column("chapter_number", sa.Integer, server_default="0", index=True),
        sa.Column("title", sa.String(255), server_default=""),
        sa.Column("main_event", sa.Text, server_default=""),
        sa.Column("pacing", sa.Integer, server_default="5"),
        sa.Column("required_beats", JSONB, server_default="[]"),
        sa.Column("emotional_trajectory", JSONB, server_default="{}"),
        sa.Column("hooks", JSONB, server_default="[]"),
        sa.Column("characters", JSONB, server_default="[]"),
        sa.Column("tenant_id", sa.String(64),
                  sa.ForeignKey("tenants.id"), nullable=True, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )

    # ──────────────────────────────────────────────────────────
    # 8. 章节内容表
    # ──────────────────────────────────────────────────────────
    op.create_table(
        "chapter_contents",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("novel_id", sa.String(64),
                  sa.ForeignKey("novels.id"), nullable=False, index=True),
        sa.Column("chapter_number", sa.Integer, server_default="0", index=True),
        sa.Column("title", sa.String(255), server_default=""),
        sa.Column("content", sa.Text, server_default=""),
        sa.Column("word_count", sa.Integer, server_default="0"),
        sa.Column("status", sa.String(32), server_default="draft", index=True),
        sa.Column("tenant_id", sa.String(64),
                  sa.ForeignKey("tenants.id"), nullable=True, index=True),
        sa.Column("meta_info", JSONB, server_default="{}"),
        sa.Column("versions", JSONB, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )

    # ──────────────────────────────────────────────────────────
    # 9. 冲突表
    # ──────────────────────────────────────────────────────────
    op.create_table(
        "conflicts",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("novel_id", sa.String(64),
                  sa.ForeignKey("novels.id"), nullable=False, index=True),
        sa.Column("title", sa.String(255), server_default=""),
        sa.Column("type", sa.String(32), server_default="", index=True),
        sa.Column("intensity", sa.Integer, server_default="5"),
        sa.Column("status", sa.String(32), server_default="active", index=True),
        sa.Column("involved_characters", JSONB, server_default="[]"),
        sa.Column("escalate_count", sa.Integer, server_default="0"),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )

    # ──────────────────────────────────────────────────────────
    # 10. 叙事钩子表
    # ──────────────────────────────────────────────────────────
    op.create_table(
        "narrative_hooks",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("novel_id", sa.String(64),
                  sa.ForeignKey("novels.id"), nullable=False, index=True),
        sa.Column("title", sa.String(255), server_default=""),
        sa.Column("type", sa.String(32), server_default="", index=True),
        sa.Column("intensity", sa.Integer, server_default="5"),
        sa.Column("status", sa.String(32), server_default="open", index=True),
        sa.Column("chapters_mentioned", JSONB, server_default="[]"),
        sa.Column("resolved_in_chapter", sa.Integer, nullable=True),
        sa.Column("associated_characters", JSONB, server_default="[]"),
        sa.Column("associated_world_entities", JSONB, server_default="[]"),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )

    # ──────────────────────────────────────────────────────────
    # 11. 任务表
    # ──────────────────────────────────────────────────────────
    op.create_table(
        "tasks",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("novel_id", sa.String(64),
                  sa.ForeignKey("novels.id"), nullable=True, index=True),
        sa.Column("name", sa.String(255), server_default=""),
        sa.Column("task_type", sa.String(64), server_default="", index=True),
        sa.Column("status", sa.String(32), server_default="pending", index=True),
        sa.Column("progress", sa.Float, server_default="0.0"),
        sa.Column("user_id", sa.String(64), server_default="default", index=True),
        sa.Column("tenant_id", sa.String(64),
                  sa.ForeignKey("tenants.id"), nullable=True, index=True),
        sa.Column("genre", sa.String(64), server_default=""),
        sa.Column("title", sa.String(255), server_default=""),
        sa.Column("description", sa.Text, server_default=""),
        sa.Column("chapters", sa.Integer, server_default="5"),
        sa.Column("word_count_per_chapter", sa.Integer, server_default="2000"),
        sa.Column("style", sa.String(64), server_default="light"),
        sa.Column("target_audience", sa.String(64), server_default="general"),
        sa.Column("language", sa.String(16), server_default="zh-CN"),
        sa.Column("current_stage", sa.String(64), server_default="initializing"),
        sa.Column("config", JSONB, server_default="{}"),
        sa.Column("result", JSONB, server_default="{}"),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("logs", JSONB, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
    )

    # ──────────────────────────────────────────────────────────
    # 12. 插入默认租户 (兼容旧数据)
    # ──────────────────────────────────────────────────────────
    op.execute("""
        INSERT INTO tenants (id, name, tier, is_active, created_at, updated_at)
        VALUES ('default', '默认租户', 'free', true, NOW(), NOW())
    """)


def downgrade() -> None:
    """Drop all tables in reverse order (respect FK constraints)."""
    op.drop_table("tasks")
    op.drop_table("narrative_hooks")
    op.drop_table("conflicts")
    op.drop_table("chapter_contents")
    op.drop_table("chapter_outlines")
    op.drop_table("outline_nodes")
    op.drop_index("ix_outline_novel_type_order", table_name="outline_nodes")
    op.drop_table("world_entities")
    op.drop_table("characters")
    op.drop_index("ix_character_novel_name", table_name="characters")
    op.drop_table("novels")
    op.drop_table("users")
    op.drop_table("tenants")
