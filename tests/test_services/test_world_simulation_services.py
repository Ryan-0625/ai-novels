"""
世界模拟 Service 单元测试

使用 mock AsyncSession 和 mock Repository 测试业务逻辑。
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from deepnovel.models import Fact, FactSource, Event, Narrative, NarrativeType, POVType, WorldRule, RuleType
from deepnovel.repositories import FactRepository, EventRepository, NarrativeRepository, WorldRuleRepository
from deepnovel.services import WorldStateService, EventService, NarrativeService, WorldRuleService


class TestWorldStateService:
    """WorldStateService 测试"""

    @pytest.fixture
    def mock_session(self):
        return AsyncMock()

    @pytest.fixture
    def mock_repo(self):
        repo = MagicMock(spec=FactRepository)
        return repo

    @pytest.fixture
    def service(self, mock_repo):
        return WorldStateService(repository=mock_repo)

    @pytest.mark.asyncio
    async def test_set_fact(self, mock_session, mock_repo, service):
        """set_fact 必须创建事实并标记旧事实为历史"""
        mock_repo.invalidate_fact.return_value = True
        mock_repo.create.return_value = Fact(
            novel_id="novel-1",
            subject_id="char-1",
            predicate="location",
            object_value={"value": "仙灵岛"},
        )

        result = await service.set_fact(
            mock_session,
            novel_id="novel-1",
            subject_id="char-1",
            predicate="location",
            value={"value": "仙灵岛"},
        )

        assert result.subject_id == "char-1"
        assert result.predicate == "location"
        mock_repo.invalidate_fact.assert_awaited_once_with(mock_session, "char-1", "location")
        mock_repo.create.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_current_state(self, mock_session, mock_repo, service):
        """get_current_state 必须返回当前有效事实"""
        fact = Fact(subject_id="char-1", predicate="location", valid_until=None)
        mock_repo.get_current_fact.return_value = fact

        result = await service.get_current_state(mock_session, "char-1", "location")

        assert result == fact
        mock_repo.get_current_fact.assert_awaited_once_with(mock_session, "char-1", "location")

    @pytest.mark.asyncio
    async def test_get_state_at_time(self, mock_session, mock_repo, service):
        """get_state_at_time 必须支持时间旅行查询"""
        now = datetime.now(timezone.utc)
        fact = Fact(subject_id="char-1", predicate="location")
        mock_repo.get_facts_at_time.return_value = fact

        result = await service.get_state_at_time(mock_session, "char-1", "location", now)

        assert result == fact

    @pytest.mark.asyncio
    async def test_create_counterfactual_branch(self, mock_session, mock_repo, service):
        """create_counterfactual_branch 必须创建反事实分支"""
        mock_repo.invalidate_fact.return_value = True
        mock_repo.create.return_value = Fact(
            novel_id="novel-1",
            subject_id="char-1",
            predicate="location",
            object_value={"value": "蜀山"},
        )
        mock_repo.get_current_fact.return_value = Fact(
            novel_id="novel-1",
            subject_id="char-1",
            predicate="location",
            is_counterfactual=False,
        )

        branch_id = await service.create_counterfactual_branch(
            mock_session,
            novel_id="novel-1",
            base_branch="main",
            changes=[{"subject_id": "char-1", "predicate": "location", "new_value": {"value": "蜀山"}}],
        )

        assert branch_id.startswith("cf_main_")


class TestEventService:
    """EventService 测试"""

    @pytest.fixture
    def mock_session(self):
        return AsyncMock()

    @pytest.fixture
    def mock_repo(self):
        repo = MagicMock(spec=EventRepository)
        return repo

    @pytest.fixture
    def service(self, mock_repo):
        return EventService(repository=mock_repo)

    @pytest.mark.asyncio
    async def test_create_event(self, mock_session, mock_repo, service):
        """create_event 必须创建事件"""
        mock_repo.create.return_value = Event(
            novel_id="novel-1",
            description="李逍遥闯入仙灵岛",
            event_type="action",
        )

        result = await service.create_event(
            mock_session,
            novel_id="novel-1",
            description="李逍遥闯入仙灵岛",
            actor_id="char-1",
        )

        assert result.description == "李逍遥闯入仙灵岛"
        mock_repo.create.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_link_causation(self, mock_session, mock_repo, service):
        """link_causation 必须建立双向因果链接"""
        cause = Event(id="event-a", novel_id="n1", causes=[])
        effect = Event(id="event-b", novel_id="n1", caused_by=[])
        mock_repo.get_by_id.side_effect = [cause, effect]

        result = await service.link_causation(mock_session, "event-a", "event-b", 0.9)

        assert result is True
        assert "event-b" in cause.causes
        assert "event-a" in effect.caused_by
        assert effect.causal_strength == 0.9

    @pytest.mark.asyncio
    async def test_link_causation_not_found(self, mock_session, mock_repo, service):
        """link_causation 事件不存在时必须返回 False"""
        mock_repo.get_by_id.return_value = None

        result = await service.link_causation(mock_session, "event-a", "event-b")

        assert result is False

    @pytest.mark.asyncio
    async def test_trace_causes(self, mock_session, mock_repo, service):
        """trace_causes 必须追溯原因链"""
        mock_repo.get_causal_chain.return_value = [Event(id="event-b")]

        result = await service.trace_causes(mock_session, "event-c", depth=3)

        assert len(result) == 1
        mock_repo.get_causal_chain.assert_awaited_once_with(
            mock_session, "event-c", direction="backward", depth=3
        )


class TestNarrativeService:
    """NarrativeService 测试"""

    @pytest.fixture
    def mock_session(self):
        return AsyncMock()

    @pytest.fixture
    def mock_repo(self):
        repo = MagicMock(spec=NarrativeRepository)
        return repo

    @pytest.fixture
    def service(self, mock_repo):
        return NarrativeService(repository=mock_repo)

    @pytest.mark.asyncio
    async def test_create_narrative(self, mock_session, mock_repo, service):
        """create_narrative 必须创建叙事"""
        mock_repo.create.return_value = Narrative(
            novel_id="novel-1",
            chapter_id="ch-1",
            content="仙灵岛上，李逍遥遇见了赵灵儿...",
            narrative_type=NarrativeType.SCENE,
        )

        result = await service.create_narrative(
            mock_session,
            novel_id="novel-1",
            chapter_id="ch-1",
            content="仙灵岛上，李逍遥遇见了赵灵儿...",
            pov_character="char-1",
        )

        assert result.content == "仙灵岛上，李逍遥遇见了赵灵儿..."
        # 验证 service 在调用 create 时正确计算了 word_count
        created_narrative = mock_repo.create.call_args[0][1]
        assert created_narrative.word_count == len("仙灵岛上，李逍遥遇见了赵灵儿...")

    @pytest.mark.asyncio
    async def test_create_new_version(self, mock_session, mock_repo, service):
        """create_new_version 必须创建新版本"""
        old = Narrative(
            id="narrative-1",
            novel_id="novel-1",
            chapter_id="ch-1",
            content="旧内容",
            version=1,
        )
        mock_repo.get_by_id.return_value = old
        mock_repo.create.return_value = Narrative(
            novel_id="novel-1",
            chapter_id="ch-1",
            content="新内容",
            version=2,
            previous_version="narrative-1",
        )

        result = await service.create_new_version(mock_session, "narrative-1", "新内容")

        assert result.version == 2
        assert result.previous_version == "narrative-1"

    @pytest.mark.asyncio
    async def test_check_event_coverage(self, mock_session, mock_repo, service):
        """check_event_coverage 必须计算事件覆盖率"""
        narrative = Narrative(
            id="narrative-1",
            covers_events=["event-1", "event-2"],
        )
        mock_repo.get_by_id.return_value = narrative

        result = await service.check_event_coverage(
            mock_session, "narrative-1", ["event-1", "event-2", "event-3"]
        )

        assert result["coverage_rate"] == 2 / 3
        assert "event-3" in result["missing"]


class TestWorldRuleService:
    """WorldRuleService 测试"""

    @pytest.fixture
    def mock_session(self):
        return AsyncMock()

    @pytest.fixture
    def mock_repo(self):
        repo = MagicMock(spec=WorldRuleRepository)
        return repo

    @pytest.fixture
    def service(self, mock_repo):
        return WorldRuleService(repository=mock_repo)

    @pytest.mark.asyncio
    async def test_create_rule(self, mock_session, mock_repo, service):
        """create_rule 必须创建规则"""
        mock_repo.create.return_value = WorldRule(
            novel_id="novel-1",
            rule_name="死亡规则",
            rule_type=RuleType.PHYSICAL,
            condition={"predicate": "health", "operator": "<=", "value": 0},
            action={"set_fact": {"predicate": "status", "value": "dead"}},
            priority=10,
        )

        result = await service.create_rule(
            mock_session,
            novel_id="novel-1",
            rule_name="死亡规则",
            rule_type=RuleType.PHYSICAL,
            condition={"predicate": "health", "operator": "<=", "value": 0},
            action={"set_fact": {"predicate": "status", "value": "dead"}},
            priority=10,
        )

        assert result.rule_name == "死亡规则"
        assert result.priority == 10

    @pytest.mark.asyncio
    async def test_deactivate_rule(self, mock_session, mock_repo, service):
        """deactivate_rule 必须停用规则"""
        rule = WorldRule(id="rule-1", is_active=True)
        mock_repo.get_by_id.return_value = rule
        mock_repo.update.return_value = rule

        result = await service.deactivate_rule(mock_session, "rule-1")

        assert result.is_active is False

    @pytest.mark.asyncio
    async def test_match_condition(self, service):
        """_match_condition 必须正确匹配条件"""
        condition = {"predicate": "health", "value": {"operator": "<=", "value": 0}}
        context = {"predicate": "health", "value": -10}

        assert service._match_condition(condition, context) is True

        context2 = {"predicate": "health", "value": 10}
        assert service._match_condition(condition, context2) is False

    @pytest.mark.asyncio
    async def test_evaluate_rules(self, mock_session, mock_repo, service):
        """evaluate_rules 必须返回匹配的动作"""
        rule = WorldRule(
            id="rule-1",
            rule_name="死亡规则",
            condition={"predicate": "health"},
            action={"set_fact": {"predicate": "status", "value": "dead"}},
            priority=10,
        )
        mock_repo.get_applicable_rules.return_value = [rule]

        result = await service.evaluate_rules(
            mock_session, "novel-1", "health", {"predicate": "health"}
        )

        assert len(result) == 1
        assert result[0]["rule_name"] == "死亡规则"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
