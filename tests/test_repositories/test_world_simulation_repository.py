"""
世界模拟 Repository 单元测试

使用 mock AsyncSession 测试业务逻辑。
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from deepnovel.models import (
    Fact,
    FactType,
    FactSource,
    Event,
    EventType,
    Narrative,
    NarrativeType,
    POVType,
    WorldRule,
    RuleType,
)
from deepnovel.repositories import (
    FactRepository,
    EventRepository,
    NarrativeRepository,
    WorldRuleRepository,
)


class TestFactRepository:
    """FactRepository 测试"""

    @pytest.fixture
    def mock_session(self):
        return AsyncMock()

    @pytest.fixture
    def repo(self):
        return FactRepository()

    @pytest.mark.asyncio
    async def test_get_by_subject(self, mock_session, repo):
        """get_by_subject 必须返回指定主语的事实"""
        fact = Fact(subject_id="char-1", predicate="location")
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [fact]
        mock_session.execute.return_value = mock_result

        result = await repo.get_by_subject(mock_session, "char-1")

        assert len(result) == 1
        assert result[0].subject_id == "char-1"

    @pytest.mark.asyncio
    async def test_get_by_subject_with_predicate(self, mock_session, repo):
        """get_by_subject 带 predicate 时必须过滤"""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        result = await repo.get_by_subject(mock_session, "char-1", predicate="location")

        assert result == []
        # 验证查询中同时过滤了 subject_id 和 predicate（SQLAlchemy 使用参数化查询）
        stmt = mock_session.execute.call_args[0][0]
        assert ":predicate_1" in str(stmt)

    @pytest.mark.asyncio
    async def test_get_current_fact(self, mock_session, repo):
        """get_current_fact 必须返回当前有效事实"""
        fact = Fact(subject_id="char-1", predicate="location", valid_until=None)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = fact
        mock_session.execute.return_value = mock_result

        result = await repo.get_current_fact(mock_session, "char-1", "location")

        assert result == fact
        assert result.valid_until is None

    @pytest.mark.asyncio
    async def test_get_facts_at_time(self, mock_session, repo):
        """get_facts_at_time 必须支持时间旅行查询"""
        now = datetime.now(timezone.utc)
        fact = Fact(subject_id="char-1", predicate="location", valid_from=now)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = fact
        mock_session.execute.return_value = mock_result

        result = await repo.get_facts_at_time(mock_session, "char-1", "location", now)

        assert result == fact

    @pytest.mark.asyncio
    async def test_invalidate_fact(self, mock_session, repo):
        """invalidate_fact 必须标记旧事实为历史"""
        fact = Fact(subject_id="char-1", predicate="location", valid_until=None)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = fact
        mock_session.execute.return_value = mock_result

        result = await repo.invalidate_fact(mock_session, "char-1", "location")

        assert result is True
        assert fact.valid_until is not None
        mock_session.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_invalidate_fact_not_found(self, mock_session, repo):
        """invalidate_fact 未找到时必须返回 False"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await repo.invalidate_fact(mock_session, "char-1", "location")

        assert result is False

    @pytest.mark.asyncio
    async def test_get_by_counterfactual_branch(self, mock_session, repo):
        """get_by_counterfactual_branch 必须返回反事实分支事实"""
        fact = Fact(
            subject_id="char-1",
            predicate="location",
            is_counterfactual=True,
            counterfactual_branch="branch-1",
        )
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [fact]
        mock_session.execute.return_value = mock_result

        result = await repo.get_by_counterfactual_branch(mock_session, "branch-1")

        assert len(result) == 1
        assert result[0].counterfactual_branch == "branch-1"


class TestEventRepository:
    """EventRepository 测试"""

    @pytest.fixture
    def mock_session(self):
        return AsyncMock()

    @pytest.fixture
    def repo(self):
        return EventRepository()

    @pytest.mark.asyncio
    async def test_get_by_novel(self, mock_session, repo):
        """get_by_novel 必须按模拟步排序"""
        event1 = Event(novel_id="novel-1", simulation_step=1)
        event2 = Event(novel_id="novel-1", simulation_step=2)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [event1, event2]
        mock_session.execute.return_value = mock_result

        result = await repo.get_by_novel(mock_session, "novel-1")

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_get_by_actor(self, mock_session, repo):
        """get_by_actor 必须返回行动者事件"""
        event = Event(novel_id="novel-1", actor_id="char-1")
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [event]
        mock_session.execute.return_value = mock_result

        result = await repo.get_by_actor(mock_session, "char-1")

        assert len(result) == 1
        assert result[0].actor_id == "char-1"

    @pytest.mark.asyncio
    async def test_get_significant_events(self, mock_session, repo):
        """get_significant_events 必须过滤重大事件"""
        event = Event(
            novel_id="novel-1",
            is_significant=True,
            importance=0.9,
            simulation_step=5,
        )
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [event]
        mock_session.execute.return_value = mock_result

        result = await repo.get_significant_events(mock_session, "novel-1")

        assert len(result) == 1
        assert result[0].is_significant is True

    @pytest.mark.asyncio
    async def test_get_causal_chain_backward(self, mock_session, repo):
        """get_causal_chain backward 必须追溯原因"""
        event_c = Event(id="event-c", novel_id="n1", caused_by=["event-b"])
        event_b = Event(id="event-b", novel_id="n1", caused_by=["event-a"])
        event_a = Event(id="event-a", novel_id="n1", caused_by=[])

        def side_effect(session, eid):
            return {"event-a": event_a, "event-b": event_b, "event-c": event_c}.get(eid)

        repo.get_by_id = AsyncMock(side_effect=side_effect)

        result = await repo.get_causal_chain(mock_session, "event-c", direction="backward", depth=3)

        assert len(result) == 2
        assert event_b in result
        assert event_a in result

    @pytest.mark.asyncio
    async def test_get_causal_chain_forward(self, mock_session, repo):
        """get_causal_chain forward 必须追踪后果"""
        event_a = Event(id="event-a", novel_id="n1", causes=["event-b"])
        event_b = Event(id="event-b", novel_id="n1", causes=["event-c"])
        event_c = Event(id="event-c", novel_id="n1", causes=[])

        def side_effect(session, eid):
            return {"event-a": event_a, "event-b": event_b, "event-c": event_c}.get(eid)

        repo.get_by_id = AsyncMock(side_effect=side_effect)

        result = await repo.get_causal_chain(mock_session, "event-a", direction="forward", depth=3)

        assert len(result) == 2
        assert event_b in result
        assert event_c in result


class TestNarrativeRepository:
    """NarrativeRepository 测试"""

    @pytest.fixture
    def mock_session(self):
        return AsyncMock()

    @pytest.fixture
    def repo(self):
        return NarrativeRepository()

    @pytest.mark.asyncio
    async def test_get_by_chapter(self, mock_session, repo):
        """get_by_chapter 必须返回章节叙事"""
        narrative = Narrative(chapter_id="ch-1", narrative_type=NarrativeType.SCENE)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [narrative]
        mock_session.execute.return_value = mock_result

        result = await repo.get_by_chapter(mock_session, "ch-1")

        assert len(result) == 1
        assert result[0].chapter_id == "ch-1"

    @pytest.mark.asyncio
    async def test_get_by_pov(self, mock_session, repo):
        """get_by_pov 必须返回指定视角叙事"""
        narrative = Narrative(
            chapter_id="ch-1",
            pov_character="char-1",
            pov_type=POVType.THIRD_LIMITED,
        )
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [narrative]
        mock_session.execute.return_value = mock_result

        result = await repo.get_by_pov(mock_session, "char-1")

        assert len(result) == 1
        assert result[0].pov_character == "char-1"

    @pytest.mark.asyncio
    async def test_get_by_event_coverage(self, mock_session, repo):
        """get_by_event_coverage 必须返回覆盖事件的叙事"""
        narrative = Narrative(chapter_id="ch-1", covers_events=["event-1", "event-2"])
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [narrative]
        mock_session.execute.return_value = mock_result

        result = await repo.get_by_event_coverage(mock_session, "event-1")

        assert len(result) == 1
        assert "event-1" in result[0].covers_events


class TestWorldRuleRepository:
    """WorldRuleRepository 测试"""

    @pytest.fixture
    def mock_session(self):
        return AsyncMock()

    @pytest.fixture
    def repo(self):
        return WorldRuleRepository()

    @pytest.mark.asyncio
    async def test_get_by_novel(self, mock_session, repo):
        """get_by_novel 必须返回小说的活跃规则"""
        rule = WorldRule(
            novel_id="novel-1",
            rule_name="死亡规则",
            rule_type=RuleType.PHYSICAL,
            is_active=True,
            priority=10,
        )
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [rule]
        mock_session.execute.return_value = mock_result

        result = await repo.get_by_novel(mock_session, "novel-1")

        assert len(result) == 1
        assert result[0].rule_name == "死亡规则"

    @pytest.mark.asyncio
    async def test_get_by_type(self, mock_session, repo):
        """get_by_type 必须按类型过滤"""
        rule = WorldRule(
            novel_id="novel-1",
            rule_name="魔法规则",
            rule_type=RuleType.MAGICAL,
        )
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [rule]
        mock_session.execute.return_value = mock_result

        result = await repo.get_by_type(mock_session, "novel-1", RuleType.MAGICAL)

        assert len(result) == 1
        assert result[0].rule_type == RuleType.MAGICAL

    @pytest.mark.asyncio
    async def test_get_applicable_rules(self, mock_session, repo):
        """get_applicable_rules 必须返回适用的规则"""
        rule = WorldRule(
            novel_id="novel-1",
            rule_name="健康规则",
            condition={"predicate": "health"},
            priority=5,
        )
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [rule]
        mock_session.execute.return_value = mock_result

        result = await repo.get_applicable_rules(mock_session, "novel-1", "health")

        assert len(result) == 1
        assert result[0].condition["predicate"] == "health"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
