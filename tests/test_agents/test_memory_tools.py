"""
记忆系统 Agent 工具单元测试

使用 mock 测试工具业务逻辑。
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from deepnovel.agents.tools import (
    MemoryEncodingTool,
    MemoryRetrievalTool,
    MemoryConsolidationTool,
)
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
from deepnovel.services import (
    MemoryEncodingService,
    MemoryRetrievalService,
    MemoryConsolidationService,
)


class TestMemoryEncodingTool:
    """MemoryEncodingTool 测试"""

    @pytest.fixture
    def mock_session(self):
        return AsyncMock()

    @pytest.fixture
    def tool(self):
        mock_service = MagicMock(spec=MemoryEncodingService)
        return MemoryEncodingTool(encoding_service=mock_service)

    @pytest.mark.asyncio
    async def test_encode_experience(self, mock_session, tool):
        """encode_experience 必须编码经历为情节记忆"""
        mem = EpisodicMemory(
            character_id="char-1",
            scene_description="闯入仙灵岛",
            emotional_arousal=0.8,
            importance=0.9,
        )
        tool._encoding.encode_episodic.return_value = mem

        result = await tool.encode_experience(
            mock_session,
            character_id="char-1",
            scene_description="闯入仙灵岛",
            emotional_arousal=0.8,
            goal_relevance=0.9,
        )

        assert result["scene_description"] == "闯入仙灵岛"
        assert result["importance"] == 0.9
        tool._encoding.encode_episodic.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_learn_knowledge(self, mock_session, tool):
        """learn_knowledge 必须编码语义记忆"""
        mem = SemanticMemory(
            character_id="char-1",
            concept_key="魔法体系",
            concept_value="五行相生相克",
            confidence=0.8,
        )
        tool._encoding.encode_semantic.return_value = mem

        result = await tool.learn_knowledge(
            mock_session,
            character_id="char-1",
            concept_key="魔法体系",
            concept_value="五行相生相克",
        )

        assert result["concept_key"] == "魔法体系"
        assert result["confidence"] == 0.8

    @pytest.mark.asyncio
    async def test_associate_emotion(self, mock_session, tool):
        """associate_emotion 必须编码情感记忆"""
        mem = EmotionalMemory(
            character_id="char-1",
            trigger_type=TriggerType.SITUATION_PATTERN,
            trigger_pattern="看到蛇",
            triggered_emotion="恐惧",
            intensity=0.8,
        )
        tool._encoding.encode_emotional.return_value = mem

        result = await tool.associate_emotion(
            mock_session,
            character_id="char-1",
            trigger_type=TriggerType.SITUATION_PATTERN,
            trigger_pattern="看到蛇",
            triggered_emotion="恐惧",
            intensity=0.8,
        )

        assert result["triggered_emotion"] == "恐惧"
        assert result["intensity"] == 0.8

    @pytest.mark.asyncio
    async def test_learn_skill(self, mock_session, tool):
        """learn_skill 必须编码程序记忆"""
        mem = ProceduralMemory(
            character_id="char-1",
            skill_name="御剑术",
            skill_description="御剑飞行",
            skill_category=SkillCategory.MAGIC,
        )
        tool._encoding.encode_procedural.return_value = mem

        result = await tool.learn_skill(
            mock_session,
            character_id="char-1",
            skill_name="御剑术",
            skill_description="御剑飞行",
            skill_category=SkillCategory.MAGIC,
        )

        assert result["skill_name"] == "御剑术"
        assert result["skill_category"] == SkillCategory.MAGIC


class TestMemoryRetrievalTool:
    """MemoryRetrievalTool 测试"""

    @pytest.fixture
    def mock_session(self):
        return AsyncMock()

    @pytest.fixture
    def tool(self):
        mock_service = MagicMock(spec=MemoryRetrievalService)
        return MemoryRetrievalTool(retrieval_service=mock_service)

    @pytest.mark.asyncio
    async def test_recall_experiences(self, mock_session, tool):
        """recall_experiences 必须返回情节记忆列表"""
        mem1 = EpisodicMemory(character_id="char-1", scene_description="记忆1", strength=0.9)
        mem2 = EpisodicMemory(character_id="char-1", scene_description="记忆2", strength=0.5)
        tool._retrieval.recall_episodic.return_value = [mem1, mem2]

        result = await tool.recall_experiences(
            mock_session, "char-1", strategy="adaptive", top_k=2
        )

        assert len(result) == 2
        assert result[0]["scene_description"] == "记忆1"

    @pytest.mark.asyncio
    async def test_recall_experiences_emotional(self, mock_session, tool):
        """recall_experiences emotional 策略必须按情感过滤"""
        mem = EpisodicMemory(
            character_id="char-1",
            scene_description="快乐记忆",
            emotional_tags=["喜悦"],
        )
        tool._retrieval.recall_episodic.return_value = [mem]

        result = await tool.recall_experiences(
            mock_session,
            "char-1",
            strategy="emotional",
            target_emotion="喜悦",
            top_k=1,
        )

        assert len(result) == 1
        assert "喜悦" in result[0]["emotional_tags"]

    @pytest.mark.asyncio
    async def test_recall_knowledge(self, mock_session, tool):
        """recall_knowledge 必须返回知识列表"""
        mem = SemanticMemory(
            character_id="char-1",
            concept_key="魔法体系",
            concept_value="五行相生相克",
        )
        tool._retrieval.recall_semantic.return_value = [mem]

        result = await tool.recall_knowledge(
            mock_session, "char-1", concept_key="魔法体系"
        )

        assert len(result) == 1
        assert result[0]["concept_value"] == "五行相生相克"

    @pytest.mark.asyncio
    async def test_recall_skills(self, mock_session, tool):
        """recall_skills 必须返回技能列表"""
        mem = ProceduralMemory(
            character_id="char-1", skill_name="御剑术", proficiency=0.9
        )
        tool._retrieval.recall_skills.return_value = [mem]

        result = await tool.recall_skills(mock_session, "char-1")

        assert len(result) == 1
        assert result[0]["skill_name"] == "御剑术"

    @pytest.mark.asyncio
    async def test_recall_skills_automatic(self, mock_session, tool):
        """recall_skills automatic_only 必须只返回自动化技能"""
        mem = ProceduralMemory(
            character_id="char-1",
            skill_name="基础剑法",
            is_automatic=True,
        )
        tool._retrieval.recall_skills.return_value = [mem]

        result = await tool.recall_skills(
            mock_session, "char-1", automatic_only=True
        )

        assert len(result) == 1
        assert result[0]["is_automatic"] is True

    @pytest.mark.asyncio
    async def test_recall_emotional_patterns(self, mock_session, tool):
        """recall_emotional_patterns 必须返回情感记忆列表"""
        mem = EmotionalMemory(
            character_id="char-1",
            triggered_emotion="恐惧",
            conditioning_strength=0.8,
        )
        tool._retrieval.recall_by_emotion.return_value = [mem]

        result = await tool.recall_emotional_patterns(
            mock_session, "char-1", "恐惧"
        )

        assert len(result) == 1
        assert result[0]["triggered_emotion"] == "恐惧"


class TestMemoryConsolidationTool:
    """MemoryConsolidationTool 测试"""

    @pytest.fixture
    def mock_session(self):
        return AsyncMock()

    @pytest.fixture
    def tool(self):
        mock_consolidation = MagicMock(spec=MemoryConsolidationService)
        mock_encoding = MagicMock(spec=MemoryEncodingService)
        return MemoryConsolidationTool(
            consolidation_service=mock_consolidation,
            encoding_service=mock_encoding,
        )

    @pytest.mark.asyncio
    async def test_rehearse(self, mock_session, tool):
        """rehearse 必须增强记忆强度"""
        tool._consolidation.rehearse.return_value = 0.75

        result = await tool.rehearse(
            mock_session, "mem-1", rehearsal_type="active"
        )

        assert result["memory_id"] == "mem-1"
        assert result["new_strength"] == 0.75

    @pytest.mark.asyncio
    async def test_rehearse_not_found(self, mock_session, tool):
        """rehearse 记忆不存在时必须返回 None"""
        tool._consolidation.rehearse.return_value = None

        result = await tool.rehearse(mock_session, "not-exist")

        assert result is None

    @pytest.mark.asyncio
    async def test_extract_pattern(self, mock_session, tool):
        """extract_pattern 必须提取语义记忆"""
        mem = SemanticMemory(
            character_id="char-1",
            concept_key="战斗模式",
            concept_value="先防御后反击",
        )
        tool._consolidation.consolidate_episodic_to_semantic.return_value = mem

        result = await tool.extract_pattern(
            mock_session, "char-1", "战斗模式", "先防御后反击"
        )

        assert result["concept_key"] == "战斗模式"
        assert result["concept_value"] == "先防御后反击"

    @pytest.mark.asyncio
    async def test_practice_skill(self, mock_session, tool):
        """practice_skill 必须增强技能"""
        skill = ProceduralMemory(
            character_id="char-1",
            skill_name="御剑术",
            proficiency=0.7,
        )
        tool._consolidation.strengthen_skill.return_value = skill

        result = await tool.practice_skill(
            mock_session, "skill-1", practice_amount=0.1
        )

        assert result["skill_name"] == "御剑术"
        assert result["proficiency"] == 0.7

    @pytest.mark.asyncio
    async def test_practice_skill_not_found(self, mock_session, tool):
        """practice_skill 技能不存在时必须返回 None"""
        tool._consolidation.strengthen_skill.return_value = None

        result = await tool.practice_skill(mock_session, "not-exist")

        assert result is None

    @pytest.mark.asyncio
    async def test_consolidate_from_experience(self, mock_session, tool):
        """consolidate_from_experience 必须完成完整巩固流程"""
        episodic = EpisodicMemory(
            character_id="char-1",
            scene_description="经历描述",
            importance=0.8,
        )
        semantic = SemanticMemory(
            character_id="char-1",
            concept_key="模式名",
            concept_value="从经历提取的模式：经历描述",
        )
        tool._encoding.encode_episodic.return_value = episodic
        tool._consolidation.consolidate_episodic_to_semantic.return_value = semantic

        result = await tool.consolidate_from_experience(
            mock_session,
            character_id="char-1",
            experience_description="经历描述",
            pattern_name="模式名",
        )

        assert "episodic" in result
        assert "semantic" in result
        assert result["episodic"]["scene_description"] == "经历描述"
        assert result["semantic"]["concept_key"] == "模式名"
        tool._encoding.encode_episodic.assert_awaited_once()
        tool._consolidation.consolidate_episodic_to_semantic.assert_awaited_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
