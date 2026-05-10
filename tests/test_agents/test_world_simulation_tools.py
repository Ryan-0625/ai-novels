"""
世界模拟 Agent 工具单元测试

使用 mock 测试工具业务逻辑。
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from deepnovel.agents.tools import (
    WorldStateTool,
    CharacterMindTool,
    CausalReasoningTool,
    NarrativeRecordTool,
)
from deepnovel.models import Fact, Event, Narrative, NarrativeType, Character
from deepnovel.repositories import CharacterRepository
from deepnovel.services import WorldStateService, EventService, NarrativeService
from deepnovel.services.world_rule_service import WorldRuleService


class TestWorldStateTool:
    """WorldStateTool 测试"""

    @pytest.fixture
    def mock_session(self):
        return AsyncMock()

    @pytest.fixture
    def tool(self):
        mock_world = MagicMock(spec=WorldStateService)
        mock_events = MagicMock(spec=EventService)
        mock_rules = MagicMock(spec=WorldRuleService)
        return WorldStateTool(
            world_service=mock_world,
            event_service=mock_events,
            rule_service=mock_rules,
        )

    @pytest.mark.asyncio
    async def test_query_state(self, mock_session, tool):
        """query_state 必须返回当前状态"""
        fact = Fact(subject_id="char-1", predicate="location", object_value={"value": "仙灵岛"})
        tool._world.get_current_state.return_value = fact

        result = await tool.query_state(mock_session, "char-1", "location")

        assert result["subject_id"] == "char-1"
        assert result["predicate"] == "location"

    @pytest.mark.asyncio
    async def test_query_state_not_found(self, mock_session, tool):
        """query_state 未找到时必须返回 None"""
        tool._world.get_current_state.return_value = None

        result = await tool.query_state(mock_session, "char-1", "location")

        assert result is None

    @pytest.mark.asyncio
    async def test_set_state(self, mock_session, tool):
        """set_state 必须设置状态并传播效果"""
        fact = Fact(
            novel_id="novel-1",
            subject_id="char-1",
            predicate="location",
            object_value={"value": "蜀山"},
        )
        tool._world.set_fact.return_value = fact
        tool._rules.find_applicable_rules.return_value = []

        result = await tool.set_state(
            mock_session,
            novel_id="novel-1",
            subject_id="char-1",
            predicate="location",
            value={"value": "蜀山"},
        )

        assert result["subject_id"] == "char-1"
        assert result["object_value"] == {"value": "蜀山"}
        assert "propagated" in result

    @pytest.mark.asyncio
    async def test_batch_set_state(self, mock_session, tool):
        """batch_set_state 必须批量设置状态"""
        fact = Fact(
            novel_id="novel-1",
            subject_id="char-1",
            predicate="location",
            object_value={"value": "蜀山"},
        )
        tool._world.set_fact.return_value = fact
        tool._world.get_current_state.return_value = fact
        tool._rules.find_applicable_rules.return_value = []

        changes = [
            {"subject_id": "char-1", "predicate": "location", "value": {"value": "蜀山"}},
        ]
        result = await tool.batch_set_state(mock_session, "novel-1", changes)

        assert len(result) == 1
        assert result[0]["subject_id"] == "char-1"

    @pytest.mark.asyncio
    async def test_create_branch(self, mock_session, tool):
        """create_branch 必须创建反事实分支"""
        tool._world.create_counterfactual_branch.return_value = "cf_main_abc123"

        result = await tool.create_branch(
            mock_session,
            novel_id="novel-1",
            base_branch="main",
            changes=[{"subject_id": "char-1", "predicate": "location", "new_value": {"value": "蜀山"}}],
        )

        assert result.startswith("cf_main_")

    @pytest.mark.asyncio
    async def test_compare_branches(self, mock_session, tool):
        """compare_branches 必须比较分支差异"""
        fact_a = Fact(subject_id="char-1", predicate="location", object_value={"value": "余杭镇"})
        fact_b = Fact(subject_id="char-1", predicate="location", object_value={"value": "蜀山"})
        tool._world.get_branch_facts.side_effect = [
            [fact_a],
            [fact_b],
        ]

        result = await tool.compare_branches(mock_session, "branch-a", "branch-b")

        assert result["difference_count"] == 1
        assert result["differences"][0]["branch_a"] == {"value": "余杭镇"}
        assert result["differences"][0]["branch_b"] == {"value": "蜀山"}


class TestCharacterMindTool:
    """CharacterMindTool 测试"""

    @pytest.fixture
    def mock_session(self):
        return AsyncMock()

    @pytest.fixture
    def tool(self):
        mock_repo = MagicMock(spec=CharacterRepository)
        mock_world = MagicMock(spec=WorldStateService)
        return CharacterMindTool(
            character_repo=mock_repo,
            world_service=mock_world,
        )

    @pytest.mark.asyncio
    async def test_get_mind(self, mock_session, tool):
        """get_mind 必须返回角色心智状态"""
        character = Character(
            id="char-1",
            name="李逍遥",
            mental_state={"current_emotion": {"joy": 0.8}},
            profile={"personality": {"extraversion": 0.9}},
        )
        tool._character_repo.get_by_id.return_value = character

        result = await tool.get_mind(mock_session, "char-1")

        assert result["name"] == "李逍遥"
        assert result["mental_state"]["current_emotion"]["joy"] == 0.8

    @pytest.mark.asyncio
    async def test_retrieve_memories_temporal(self, mock_session, tool):
        """retrieve_memories temporal 必须按时间排序"""
        character = Character(
            id="char-1",
            mental_state={
                "episodic_memory": [
                    {"timestamp": 100, "content": "最早的记忆"},
                    {"timestamp": 300, "content": "最近的记忆"},
                    {"timestamp": 200, "content": "中间的记忆"},
                ]
            },
        )
        tool._character_repo.get_by_id.return_value = character

        result = await tool.retrieve_memories(
            mock_session, "char-1", "查询", retrieval_type="temporal", top_k=2
        )

        assert len(result) == 2
        assert result[0]["timestamp"] == 300  # 最近优先

    @pytest.mark.asyncio
    async def test_retrieve_memories_emotional(self, mock_session, tool):
        """retrieve_memories emotional 必须按情感强度排序"""
        character = Character(
            id="char-1",
            mental_state={
                "episodic_memory": [
                    {"content": "弱情感", "emotion_intensity": 0.2},
                    {"content": "强情感", "emotion_intensity": 0.9},
                ]
            },
        )
        tool._character_repo.get_by_id.return_value = character

        result = await tool.retrieve_memories(
            mock_session, "char-1", "查询", retrieval_type="emotional", top_k=1
        )

        assert len(result) == 1
        assert result[0]["emotion_intensity"] == 0.9

    @pytest.mark.asyncio
    async def test_update_belief(self, mock_session, tool):
        """update_belief 必须更新信念"""
        character = Character(
            id="char-1",
            mental_state={"beliefs": {"about_others": {"赵灵儿": {"value": 0.5, "evidence": []}}}},
        )
        tool._character_repo.get_by_id.return_value = character
        tool._character_repo.update.return_value = character

        result = await tool.update_belief(
            mock_session,
            "char-1",
            "about_others",
            "赵灵儿",
            {"value": 0.9, "confidence": 0.8, "source": "event-1"},
        )

        assert result["value"] > 0.5  # 信念应该增加
        assert "event-1" in result["evidence"]

    @pytest.mark.asyncio
    async def test_compute_emotion(self, mock_session, tool):
        """compute_emotion 必须计算情感反应"""
        character = Character(
            id="char-1",
            mental_state={
                "current_emotion": {"joy": 0.5, "fear": 0.2},
                "emotional_baseline": {"joy": 0.6, "fear": 0.3},
                "emotional_regulation": 0.5,
            },
            profile={"personality": {"extraversion": 0.8, "neuroticism": 0.4}},
        )
        tool._character_repo.get_by_id.return_value = character
        tool._character_repo.update.return_value = character

        result = await tool.compute_emotion(
            mock_session,
            "char-1",
            {"desirability": 0.8, "controllability": 0.6, "importance": 0.7},
        )

        assert "joy" in result
        assert 0 <= result["joy"] <= 1

    @pytest.mark.asyncio
    async def test_check_consistency(self, mock_session, tool):
        """check_consistency 必须检查行动一致性"""
        character = Character(
            id="char-1",
            name="李逍遥",
            archetype="hero",
            profile={"values": ["正义", "勇敢"], "personality": {"extraversion": 0.8}},
        )
        tool._character_repo.get_by_id.return_value = character

        result = await tool.check_consistency(mock_session, "char-1", "保护村民")

        assert result["consistent"] is True
        assert result["consistency_score"] >= 0.5


class TestCausalReasoningTool:
    """CausalReasoningTool 测试"""

    @pytest.fixture
    def mock_session(self):
        return AsyncMock()

    @pytest.fixture
    def tool(self):
        mock_events = MagicMock(spec=EventService)
        mock_events._repo = MagicMock()
        mock_events._repo.get_by_id = AsyncMock()
        mock_world = MagicMock(spec=WorldStateService)
        return CausalReasoningTool(
            event_service=mock_events,
            world_service=mock_world,
        )

    @pytest.mark.asyncio
    async def test_trace_causes(self, mock_session, tool):
        """trace_causes 必须追溯原因链"""
        event = Event(id="event-c", novel_id="n1", description="结果事件")
        cause = Event(id="event-b", novel_id="n1", description="原因事件", causes=["event-c"])
        tool._events._repo.get_by_id.return_value = event
        tool._events.trace_causes.return_value = [cause]

        result = await tool.trace_causes(mock_session, "event-c", depth=3)

        assert result["event_id"] == "event-c"
        assert result["cause_count"] == 1
        assert result["causes"][0]["description"] == "原因事件"

    @pytest.mark.asyncio
    async def test_predict_consequences(self, mock_session, tool):
        """predict_consequences 必须预测后果"""
        event = Event(id="event-a", novel_id="n1", description="初始事件", event_type="action")
        consequence = Event(id="event-b", novel_id="n1", description="后果事件")
        tool._events._repo.get_by_id.return_value = event
        tool._events.predict_consequences.return_value = [consequence]

        result = await tool.predict_consequences(mock_session, "event-a", steps=3)

        assert result["event_id"] == "event-a"
        assert result["prediction_count"] >= 1

    @pytest.mark.asyncio
    async def test_generate_explanation(self, mock_session, tool):
        """generate_explanation 必须生成解释"""
        event = Event(id="event-a", novel_id="n1", description="李逍遥闯入仙灵岛")
        cause = Event(id="event-b", novel_id="n1", description="李逍遥寻找仙药")
        tool._events._repo.get_by_id.return_value = event
        tool._events.trace_causes.return_value = [cause]
        tool._events.predict_consequences.return_value = []

        result = await tool.generate_explanation(
            mock_session, "event-a", audience="reader", depth="simple"
        )

        assert "explanation" in result
        assert "李逍遥闯入仙灵岛" in result["explanation"]
        assert result["cause_count"] == 1

    @pytest.mark.asyncio
    async def test_analyze_what_if(self, mock_session, tool):
        """analyze_what_if 必须执行反事实分析"""
        event = Event(id="event-1", novel_id="n1", description="李逍遥去仙灵岛")
        tool._events._repo.get_by_id.return_value = event
        tool._world.create_counterfactual_branch.return_value = "cf_main_test123"
        tool._world.get_branch_facts.return_value = [
            Fact(subject_id="char-1", predicate="location", object_value={"value": "蜀山"})
        ]
        tool._world.get_current_state.return_value = Fact(
            subject_id="char-1", predicate="location", object_value={"value": "余杭镇"}
        )

        result = await tool.analyze_what_if(
            mock_session,
            novel_id="n1",
            event_id="event-1",
            modification={"subject_id": "char-1", "predicate": "location", "new_value": {"value": "蜀山"}},
        )

        assert result["branch_id"] == "cf_main_test123"
        assert len(result["key_differences"]) == 1


class TestNarrativeRecordTool:
    """NarrativeRecordTool 测试"""

    @pytest.fixture
    def mock_session(self):
        return AsyncMock()

    @pytest.fixture
    def tool(self):
        mock_narrative = MagicMock(spec=NarrativeService)
        mock_events = MagicMock(spec=EventService)
        mock_events._repo = MagicMock()
        mock_events._repo.get_by_id = AsyncMock()
        mock_chars = MagicMock(spec=CharacterRepository)
        mock_chars.get_by_id = AsyncMock(return_value=None)
        return NarrativeRecordTool(
            narrative_service=mock_narrative,
            event_service=mock_events,
            character_repo=mock_chars,
        )

    @pytest.mark.asyncio
    async def test_record_scene(self, mock_session, tool):
        """record_scene 必须创建场景叙事"""
        event = Event(id="event-1", novel_id="n1", description="事件发生")
        narrative = Narrative(
            id="narrative-1",
            novel_id="n1",
            chapter_id="ch-1",
            content="场景内容",
            narrative_type=NarrativeType.SCENE,
            covers_events=["event-1"],
        )
        tool._events._repo.get_by_id.return_value = event
        tool._narrative.create_narrative.return_value = narrative
        tool._narrative.check_event_coverage.return_value = {
            "covered": ["event-1"],
            "missing": [],
            "coverage_rate": 1.0,
        }

        result = await tool.record_scene(
            mock_session,
            novel_id="n1",
            chapter_id="ch-1",
            content="场景内容",
            events=["event-1"],
        )

        assert result["content"] == "场景内容"
        assert result["event_coverage"]["coverage_rate"] == 1.0

    @pytest.mark.asyncio
    async def test_record_multi_pov_scene(self, mock_session, tool):
        """record_multi_pov_scene 必须创建多视角叙事"""
        narrative = Narrative(
            id="narrative-1",
            novel_id="n1",
            chapter_id="ch-1",
            content="合并内容",
            narrative_type=NarrativeType.SCENE,
        )
        tool._narrative.create_narrative.return_value = narrative
        tool._narrative.check_event_coverage.return_value = {
            "covered": ["event-1"],
            "missing": [],
            "coverage_rate": 1.0,
        }

        contents = {
            "char-1": "李逍遥的视角",
            "char-2": "赵灵儿的视角",
        }
        result = await tool.record_multi_pov_scene(
            mock_session,
            novel_id="n1",
            chapter_id="ch-1",
            contents=contents,
            events=["event-1"],
            transition_style="sequential",
        )

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_check_style_consistency(self, mock_session, tool):
        """check_style_consistency 必须检查风格一致性"""
        narratives = [
            Narrative(
                id="n1",
                chapter_id="ch-1",
                pov_type="third_limited",
                style_profile={"tone": "melancholic", "pace": "slow"},
                plot_function="exposition",
                content="内容1",
            ),
            Narrative(
                id="n2",
                chapter_id="ch-1",
                pov_type="third_limited",
                style_profile={"tone": "melancholic", "pace": "slow"},
                plot_function="rising_action",
                content="内容2",
            ),
        ]
        tool._narrative.get_chapter_narratives.return_value = narratives

        result = await tool.check_style_consistency(mock_session, "ch-1")

        assert "metrics" in result
        assert "overall" in result
        assert result["is_consistent"] is True

    @pytest.mark.asyncio
    async def test_check_style_consistency_inconsistent(self, mock_session, tool):
        """check_style_consistency 不一致时必须返回建议"""
        narratives = [
            Narrative(
                id="n1",
                chapter_id="ch-1",
                pov_type="third_limited",
                style_profile={"tone": "melancholic"},
                content="内容1",
            ),
            Narrative(
                id="n2",
                chapter_id="ch-1",
                pov_type="first_person",  # 视角不一致
                style_profile={"tone": "cheerful"},  # 基调不一致
                content="内容2",
            ),
        ]
        tool._narrative.get_chapter_narratives.return_value = narratives

        result = await tool.check_style_consistency(mock_session, "ch-1", tolerance=0.9)

        assert result["is_consistent"] is False
        assert len(result["suggestions"]) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
