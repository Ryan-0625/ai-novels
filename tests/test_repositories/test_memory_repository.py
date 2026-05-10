"""
记忆系统 Repository 单元测试

使用 mock AsyncSession 测试业务逻辑。
"""

from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from deepnovel.models import (
    EpisodicMemory,
    SemanticMemory,
    EmotionalMemory,
    ProceduralMemory,
    KnowledgeType,
    SourceType,
    TriggerType,
    ReactionType,
    SkillCategory,
)
from deepnovel.repositories import (
    EpisodicMemoryRepository,
    SemanticMemoryRepository,
    EmotionalMemoryRepository,
    ProceduralMemoryRepository,
)


class TestEpisodicMemoryRepository:
    """EpisodicMemoryRepository 测试"""

    @pytest.fixture
    def mock_session(self):
        return AsyncMock()

    @pytest.fixture
    def repo(self):
        return EpisodicMemoryRepository()

    @pytest.mark.asyncio
    async def test_get_by_character(self, mock_session, repo):
        """get_by_character 必须返回角色的情节记忆（按强度排序）"""
        mem1 = EpisodicMemory(character_id="char-1", scene_description="强记忆", strength=0.9)
        mem2 = EpisodicMemory(character_id="char-1", scene_description="弱记忆", strength=0.3)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mem1, mem2]
        mock_session.execute.return_value = mock_result

        result = await repo.get_by_character(mock_session, "char-1")

        assert len(result) == 2
        assert result[0].strength == 0.9
        assert result[1].strength == 0.3

    @pytest.mark.asyncio
    async def test_get_by_character_pagination(self, mock_session, repo):
        """get_by_character 必须支持分页"""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        result = await repo.get_by_character(mock_session, "char-1", offset=10, limit=5)

        assert result == []
        stmt = mock_session.execute.call_args[0][0]
        assert ":param_1" in str(stmt) or "10" in str(stmt)

    @pytest.mark.asyncio
    async def test_get_by_emotion_range(self, mock_session, repo):
        """get_by_emotion_range 必须按情感范围过滤"""
        mem = EpisodicMemory(
            character_id="char-1",
            scene_description="快乐记忆",
            emotional_valence=0.8,
            emotional_arousal=0.7,
        )
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mem]
        mock_session.execute.return_value = mock_result

        result = await repo.get_by_emotion_range(
            mock_session, "char-1", min_valence=0.5, max_valence=1.0
        )

        assert len(result) == 1
        assert result[0].emotional_valence == 0.8

    @pytest.mark.asyncio
    async def test_get_by_context_tags(self, mock_session, repo):
        """get_by_context_tags 必须按情境标签查询"""
        mem = EpisodicMemory(
            character_id="char-1",
            scene_description="战斗记忆",
            context_tags=["战斗", "仙灵岛"],
        )
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mem]
        mock_session.execute.return_value = mock_result

        result = await repo.get_by_context_tags(mock_session, "char-1", ["战斗"])

        assert len(result) == 1
        assert "战斗" in result[0].context_tags

    @pytest.mark.asyncio
    async def test_get_recent(self, mock_session, repo):
        """get_recent 必须返回最近记忆"""
        now = datetime.now(timezone.utc)
        mem = EpisodicMemory(
            character_id="char-1",
            scene_description="最近记忆",
            experienced_at=now,
        )
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mem]
        mock_session.execute.return_value = mock_result

        result = await repo.get_recent(mock_session, "char-1", time_window_seconds=3600)

        assert len(result) == 1
        assert result[0].scene_description == "最近记忆"

    @pytest.mark.asyncio
    async def test_increment_access(self, mock_session, repo):
        """increment_access 必须增加访问计数"""
        mem = EpisodicMemory(id="mem-1", character_id="char-1", access_count=0)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mem
        mock_session.execute.return_value = mock_result

        result = await repo.increment_access(mock_session, "mem-1")

        assert result is not None
        assert result.access_count == 1
        assert result.last_accessed is not None


class TestSemanticMemoryRepository:
    """SemanticMemoryRepository 测试"""

    @pytest.fixture
    def mock_session(self):
        return AsyncMock()

    @pytest.fixture
    def repo(self):
        return SemanticMemoryRepository()

    @pytest.mark.asyncio
    async def test_get_by_character(self, mock_session, repo):
        """get_by_character 必须返回角色的语义记忆（按置信度排序）"""
        mem1 = SemanticMemory(
            character_id="char-1", concept_key="魔法体系", confidence=0.95
        )
        mem2 = SemanticMemory(
            character_id="char-1", concept_key="门派关系", confidence=0.7
        )
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mem1, mem2]
        mock_session.execute.return_value = mock_result

        result = await repo.get_by_character(mock_session, "char-1")

        assert len(result) == 2
        assert result[0].confidence == 0.95

    @pytest.mark.asyncio
    async def test_get_by_character_with_type(self, mock_session, repo):
        """get_by_character 带 knowledge_type 时必须过滤"""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        result = await repo.get_by_character(
            mock_session, "char-1", knowledge_type=KnowledgeType.WORLD_FACT
        )

        assert result == []
        stmt = mock_session.execute.call_args[0][0]
        assert ":knowledge_type_1" in str(stmt) or "world_fact" in str(stmt)

    @pytest.mark.asyncio
    async def test_get_by_concept(self, mock_session, repo):
        """get_by_concept 必须按概念键查询"""
        mem = SemanticMemory(
            character_id="char-1",
            concept_key="魔法体系",
            concept_value="五行相生相克",
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mem
        mock_session.execute.return_value = mock_result

        result = await repo.get_by_concept(mock_session, "char-1", "魔法体系")

        assert result is not None
        assert result.concept_value == "五行相生相克"

    @pytest.mark.asyncio
    async def test_get_by_concept_not_found(self, mock_session, repo):
        """get_by_concept 未找到时必须返回 None"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await repo.get_by_concept(mock_session, "char-1", "不存在")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_high_confidence(self, mock_session, repo):
        """get_high_confidence 必须返回高置信度知识"""
        mem = SemanticMemory(
            character_id="char-1", concept_key="重要知识", confidence=0.9
        )
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mem]
        mock_session.execute.return_value = mock_result

        result = await repo.get_high_confidence(mock_session, "char-1", min_confidence=0.8)

        assert len(result) == 1
        assert result[0].confidence >= 0.8


class TestEmotionalMemoryRepository:
    """EmotionalMemoryRepository 测试"""

    @pytest.fixture
    def mock_session(self):
        return AsyncMock()

    @pytest.fixture
    def repo(self):
        return EmotionalMemoryRepository()

    @pytest.mark.asyncio
    async def test_get_by_character(self, mock_session, repo):
        """get_by_character 必须返回角色的情感记忆"""
        mem = EmotionalMemory(
            character_id="char-1",
            trigger_type=TriggerType.SITUATION_PATTERN,
            triggered_emotion="恐惧",
        )
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mem]
        mock_session.execute.return_value = mock_result

        result = await repo.get_by_character(mock_session, "char-1")

        assert len(result) == 1
        assert result[0].triggered_emotion == "恐惧"

    @pytest.mark.asyncio
    async def test_get_by_trigger(self, mock_session, repo):
        """get_by_trigger 必须按触发器查询"""
        mem = EmotionalMemory(
            character_id="char-1",
            trigger_type=TriggerType.PERSON_PRESENCE,
            trigger_pattern="看到敌人",
            triggered_emotion="愤怒",
        )
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mem]
        mock_session.execute.return_value = mock_result

        result = await repo.get_by_trigger(
            mock_session, "char-1", TriggerType.PERSON_PRESENCE, "看到敌人"
        )

        assert len(result) == 1
        assert result[0].trigger_pattern == "看到敌人"

    @pytest.mark.asyncio
    async def test_get_by_emotion(self, mock_session, repo):
        """get_by_emotion 必须按情感类型查询"""
        mem = EmotionalMemory(
            character_id="char-1",
            triggered_emotion="喜悦",
            conditioning_strength=0.8,
        )
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mem]
        mock_session.execute.return_value = mock_result

        result = await repo.get_by_emotion(mock_session, "char-1", "喜悦")

        assert len(result) == 1
        assert result[0].conditioning_strength == 0.8


class TestProceduralMemoryRepository:
    """ProceduralMemoryRepository 测试"""

    @pytest.fixture
    def mock_session(self):
        return AsyncMock()

    @pytest.fixture
    def repo(self):
        return ProceduralMemoryRepository()

    @pytest.mark.asyncio
    async def test_get_by_character(self, mock_session, repo):
        """get_by_character 必须返回角色的技能（按熟练度排序）"""
        mem1 = ProceduralMemory(
            character_id="char-1", skill_name="御剑术", proficiency=0.9
        )
        mem2 = ProceduralMemory(
            character_id="char-1", skill_name="炼丹术", proficiency=0.5
        )
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mem1, mem2]
        mock_session.execute.return_value = mock_result

        result = await repo.get_by_character(mock_session, "char-1")

        assert len(result) == 2
        assert result[0].skill_name == "御剑术"

    @pytest.mark.asyncio
    async def test_get_by_character_with_category(self, mock_session, repo):
        """get_by_character 带 category 时必须过滤"""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        result = await repo.get_by_character(
            mock_session, "char-1", category=SkillCategory.MAGIC
        )

        assert result == []

    @pytest.mark.asyncio
    async def test_get_by_skill_name(self, mock_session, repo):
        """get_by_skill_name 必须按技能名称查询"""
        mem = ProceduralMemory(
            character_id="char-1", skill_name="御剑术", proficiency=0.9
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mem
        mock_session.execute.return_value = mock_result

        result = await repo.get_by_skill_name(mock_session, "char-1", "御剑术")

        assert result is not None
        assert result.proficiency == 0.9

    @pytest.mark.asyncio
    async def test_get_automatic_skills(self, mock_session, repo):
        """get_automatic_skills 必须返回已自动化的技能"""
        mem = ProceduralMemory(
            character_id="char-1",
            skill_name="基础剑法",
            is_automatic=True,
            proficiency=0.95,
        )
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mem]
        mock_session.execute.return_value = mock_result

        result = await repo.get_automatic_skills(mock_session, "char-1")

        assert len(result) == 1
        assert result[0].is_automatic is True


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
