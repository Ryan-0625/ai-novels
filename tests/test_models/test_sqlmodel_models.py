"""
SQLModel 实体模型测试

验证从 dataclass 到 SQLModel 的迁移:
- 模型定义正确性
- 向后兼容 to_dict()
- JSONB 字段支持
- 关系定义
"""

import pytest
from datetime import datetime
from sqlmodel import SQLModel

# 确保模型注册到metadata
from deepnovel.models import (
    Novel, Character, WorldEntity,
    ChapterOutline, ChapterContent,
    Conflict, NarrativeHook,
    Task, TaskStatus,
)


class TestModelRegistration:
    """模型注册测试"""

    def test_all_models_registered(self):
        """所有模型必须注册到SQLModel.metadata"""
        tables = SQLModel.metadata.tables
        expected = [
            "novels", "characters", "world_entities",
            "outline_nodes", "chapter_outlines", "chapter_contents",
            "conflicts", "narrative_hooks", "tasks",
        ]
        for table in expected:
            assert table in tables, f"Table {table} not registered in metadata"

    def test_novel_table_columns(self):
        """novels表必须包含正确列"""
        cols = SQLModel.metadata.tables["novels"].columns
        required = ["id", "title", "genre", "status", "created_at", "updated_at"]
        for col in required:
            assert col in cols, f"Column {col} missing from novels table"

    def test_character_table_columns(self):
        """characters表必须包含正确列"""
        cols = SQLModel.metadata.tables["characters"].columns
        required = ["id", "novel_id", "name", "archetype", "profile", "mental_state"]
        for col in required:
            assert col in cols, f"Column {col} missing from characters table"

    def test_jsonb_columns_exist(self):
        """JSONB列必须正确定义"""
        from sqlalchemy.dialects.postgresql import JSONB
        char_table = SQLModel.metadata.tables["characters"]
        assert isinstance(char_table.c.profile.type, JSONB), "profile column should be JSONB"
        assert isinstance(char_table.c.mental_state.type, JSONB), "mental_state column should be JSONB"


class TestNovelModel:
    """Novel模型测试"""

    def test_novel_creation(self):
        """必须能创建Novel实例"""
        novel = Novel(title="测试小说", genre="科幻")
        assert novel.title == "测试小说"
        assert novel.genre == "科幻"
        assert novel.status == "draft"
        assert novel.word_count_target == 50000
        assert novel.id is not None  # UUID自动生成
        assert novel.created_at is not None

    def test_novel_settings_jsonb(self):
        """settings字段必须支持JSONB"""
        novel = Novel(
            title="测试",
            settings={"language": "zh", "style": "verbose"},
        )
        assert novel.settings["language"] == "zh"

    def test_novel_to_dict(self):
        """必须支持向后兼容的to_dict()"""
        novel = Novel(title="测试小说", genre="科幻")
        d = novel.model_dump()
        assert d["title"] == "测试小说"
        assert d["genre"] == "科幻"
        assert "id" in d


class TestCharacterModel:
    """Character模型测试"""

    def test_character_creation(self):
        """必须能创建Character实例"""
        char = Character(
            name="张三",
            archetype="英雄",
            age_visual=25,
            gender="男",
        )
        assert char.name == "张三"
        assert char.archetype == "英雄"
        assert char.aliases == []

    def test_character_profile_jsonb(self):
        """profile字段必须支持复杂JSON"""
        char = Character(
            name="李四",
            profile={
                "appearance": "高大",
                "background": {"birthplace": "北京", "family": "商人"},
            },
        )
        assert char.profile["appearance"] == "高大"
        assert char.profile["background"]["birthplace"] == "北京"

    def test_character_to_dict_backward_compat(self):
        """to_dict() 必须兼容旧格式"""
        char = Character(
            name="王五",
            archetype="导师",
            aliases=["老王", "大师"],
        )
        d = char.to_dict()
        assert d["name"] == "王五"
        assert d["archetype"] == "导师"
        assert d["aliases"] == ["老王", "大师"]
        assert "char_id" in d  # 旧字段名兼容
        assert d["char_id"] == char.id

    def test_character_mental_state(self):
        """mental_state字段用于CharacterMind"""
        char = Character(
            name="赵六",
            mental_state={
                "mood": "angry",
                "stress_level": 8,
                "relationships": {"张三": "rival"},
            },
        )
        assert char.mental_state["mood"] == "angry"


class TestWorldEntityModel:
    """WorldEntity模型测试"""

    def test_world_entity_creation(self):
        """必须能创建WorldEntity实例"""
        we = WorldEntity(
            name="魔法学院",
            category="magic",
            public_description="一所古老的魔法学校",
        )
        assert we.name == "魔法学院"
        assert we.category == "magic"

    def test_world_entity_causal_links(self):
        """causal_links字段支持因果关系网络"""
        we = WorldEntity(
            name="龙族",
            category="faction",
            causal_links={
                "causes": ["魔法枯竭"],
                "caused_by": ["古代战争"],
                "influences": {"humans": "hostile"},
            },
        )
        assert "魔法枯竭" in we.causal_links["causes"]

    def test_world_entity_to_dict(self):
        """to_dict() 兼容旧格式"""
        we = WorldEntity(name="遗迹", category="geography")
        d = we.to_dict()
        assert d["name"] == "遗迹"
        assert "world_id" in d
        assert d["world_id"] == we.id


class TestNarrativeModel:
    """冲突与钩子模型测试"""

    def test_conflict_creation(self):
        """必须能创建Conflict实例"""
        conflict = Conflict(
            title="家族恩怨",
            type="character",
            intensity=8,
        )
        assert conflict.title == "家族恩怨"
        assert conflict.status == "active"

    def test_conflict_to_dict(self):
        """to_dict() 输出正确格式"""
        c = Conflict(title="权力斗争", type="external")
        d = c.to_dict()
        assert d["title"] == "权力斗争"
        assert "conflict_id" in d

    def test_hook_creation(self):
        """必须能创建NarrativeHook实例"""
        hook = NarrativeHook(
            title="神秘信使",
            type="mystery",
            intensity=7,
        )
        assert hook.status == "open"

    def test_hook_to_dict(self):
        """to_dict() 输出正确格式"""
        h = NarrativeHook(title="失踪的王子", type="mystery")
        d = h.to_dict()
        assert d["title"] == "失踪的王子"
        assert "hook_id" in d


class TestTaskModel:
    """任务模型测试"""

    def test_task_status_constants(self):
        """任务状态常量必须定义正确"""
        assert TaskStatus.PENDING == "pending"
        assert TaskStatus.RUNNING == "running"
        assert TaskStatus.COMPLETED == "completed"
        assert TaskStatus.FAILED == "failed"

    def test_task_creation(self):
        """必须能创建Task实例"""
        task = Task(name="生成第一章", task_type="generate_chapter")
        assert task.status == TaskStatus.PENDING
        assert task.progress == 0
        assert task.config == {}

    def test_task_logs_jsonb(self):
        """logs字段必须支持结构化日志"""
        task = Task(
            name="测试任务",
            logs=[
                {"timestamp": "2024-01-01T00:00:00Z", "level": "INFO", "message": "开始"},
                {"timestamp": "2024-01-01T00:01:00Z", "level": "DEBUG", "message": "处理中"},
            ],
        )
        assert len(task.logs) == 2
        assert task.logs[0]["level"] == "INFO"


class TestIndexes:
    """数据库索引测试"""

    def test_character_compound_index(self):
        """characters表必须有复合索引"""
        indexes = SQLModel.metadata.tables["characters"].indexes
        index_names = [idx.name for idx in indexes]
        assert "ix_character_novel_name" in index_names

    def test_novel_status_index(self):
        """novels.status必须有索引"""
        assert SQLModel.metadata.tables["novels"].c.status.index is True

    def test_task_status_index(self):
        """tasks.status必须有索引"""
        assert SQLModel.metadata.tables["tasks"].c.status.index is True


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
