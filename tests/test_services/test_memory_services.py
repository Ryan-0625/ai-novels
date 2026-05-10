"""
记忆系统 Service 单元测试

使用 mock AsyncSession 和 mock Repository 测试业务逻辑。
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
from deepnovel.services import (
    MemoryEncodingService,
    MemoryRetrievalService,
    MemoryConsolidationService,
    MemoryForgettingService,
    MemoryManager,
)


class TestMemoryEncodingService:
    """MemoryEncodingService 测试"""

    @pytest.fixture
    def mock_session(self):
        return AsyncMock()

    @pytest.fixture
    def mock_repos(self):
        return {
            "episodic": MagicMock(spec=EpisodicMemoryRepository),
            "semantic": MagicMock(spec=SemanticMemoryRepository),
            "emotional": MagicMock(spec=EmotionalMemoryRepository),
            "procedural": MagicMock(spec=ProceduralMemoryRepository),
        }

    @pytest.fixture
    def service(self, mock_repos):
        return MemoryEncodingService(
            episodic_repo=mock_repos["episodic"],
            semantic_repo=mock_repos["semantic"],
            emotional_repo=mock_repos["emotional"],
            procedural_repo=mock_repos["procedural"],
        )

    @pytest.mark.asyncio
    async def test_encode_episodic(self, mock_session, mock_repos, service):
        """encode_episodic 必须创建情节记忆"""
        mem = EpisodicMemory(
            character_id="char-1",
            scene_description="闯入仙灵岛",
            emotional_arousal=0.8,
            importance=0.9,
        )
        mock_repos["episodic"].create.return_value = mem

        result = await service.encode_episodic(
            mock_session,
            character_id="char-1",
            scene_description="闯入仙灵岛",
            emotional_arousal=0.8,
            goal_relevance=0.9,
            novelty=0.7,
        )

        assert result.scene_description == "闯入仙灵岛"
        assert result.importance > 0.5
        mock_repos["episodic"].create.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_encode_episodic_flashbulb(self, mock_session, mock_repos, service):
        """encode_episodic flashbulb 记忆必须自动巩固"""
        mem = EpisodicMemory(
            character_id="char-1",
            scene_description="重大事件",
            emotional_arousal=0.9,
            is_flashbulb=True,
        )
        mock_repos["episodic"].create.return_value = mem

        result = await service.encode_episodic(
            mock_session,
            character_id="char-1",
            scene_description="重大事件",
            emotional_arousal=0.9,
            is_flashbulb=True,
        )

        assert result.is_flashbulb is True

    @pytest.mark.asyncio
    async def test_calculate_importance(self, service):
        """_calculate_importance 必须正确计算重要性"""
        importance = service._calculate_importance(
            emotional_arousal=0.8,
            goal_relevance=0.9,
            novelty=0.7,
            outcome_impact=0.5,
        )
        assert 0 <= importance <= 1.0
        assert importance > 0.5  # 高情感+高目标相关性 → 高重要性

    @pytest.mark.asyncio
    async def test_encode_semantic_new(self, mock_session, mock_repos, service):
        """encode_semantic 新知识时必须创建"""
        mem = SemanticMemory(
            character_id="char-1",
            concept_key="魔法体系",
            concept_value="五行相生相克",
            confidence=0.8,
        )
        mock_repos["semantic"].get_by_concept.return_value = None
        mock_repos["semantic"].create.return_value = mem

        result = await service.encode_semantic(
            mock_session,
            character_id="char-1",
            concept_key="魔法体系",
            concept_value="五行相生相克",
        )

        assert result.concept_key == "魔法体系"
        mock_repos["semantic"].create.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_encode_semantic_merge(self, mock_session, mock_repos, service):
        """encode_semantic 已有知识时必须合并"""
        existing = SemanticMemory(
            character_id="char-1",
            concept_key="魔法体系",
            concept_value="旧值",
            confidence=0.6,
            evidence_count=2,
        )
        mock_repos["semantic"].get_by_concept.return_value = existing
        mock_repos["semantic"].update.return_value = existing

        result = await service.encode_semantic(
            mock_session,
            character_id="char-1",
            concept_key="魔法体系",
            concept_value="新值",
            confidence=0.9,
        )

        assert result.evidence_count == 3  # 证据计数增加
        mock_repos["semantic"].update.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_encode_emotional(self, mock_session, mock_repos, service):
        """encode_emotional 必须创建情感记忆"""
        mem = EmotionalMemory(
            character_id="char-1",
            trigger_type=TriggerType.SITUATION_PATTERN,
            trigger_pattern="看到蛇",
            triggered_emotion="恐惧",
            intensity=0.8,
        )
        mock_repos["emotional"].create.return_value = mem

        result = await service.encode_emotional(
            mock_session,
            character_id="char-1",
            trigger_type=TriggerType.SITUATION_PATTERN,
            trigger_pattern="看到蛇",
            triggered_emotion="恐惧",
            intensity=0.8,
        )

        assert result.triggered_emotion == "恐惧"
        assert result.intensity == 0.8

    @pytest.mark.asyncio
    async def test_encode_procedural(self, mock_session, mock_repos, service):
        """encode_procedural 必须创建程序记忆"""
        mem = ProceduralMemory(
            character_id="char-1",
            skill_name="御剑术",
            skill_description="御剑飞行",
            skill_category=SkillCategory.MAGIC,
        )
        mock_repos["procedural"].create.return_value = mem

        result = await service.encode_procedural(
            mock_session,
            character_id="char-1",
            skill_name="御剑术",
            skill_description="御剑飞行",
            skill_category=SkillCategory.MAGIC,
        )

        assert result.skill_name == "御剑术"
        assert result.skill_category == SkillCategory.MAGIC


class TestMemoryRetrievalService:
    """MemoryRetrievalService 测试"""

    @pytest.fixture
    def mock_session(self):
        return AsyncMock()

    @pytest.fixture
    def mock_repos(self):
        return {
            "episodic": MagicMock(spec=EpisodicMemoryRepository),
            "semantic": MagicMock(spec=SemanticMemoryRepository),
            "emotional": MagicMock(spec=EmotionalMemoryRepository),
            "procedural": MagicMock(spec=ProceduralMemoryRepository),
        }

    @pytest.fixture
    def service(self, mock_repos):
        return MemoryRetrievalService(
            episodic_repo=mock_repos["episodic"],
            semantic_repo=mock_repos["semantic"],
            emotional_repo=mock_repos["emotional"],
            procedural_repo=mock_repos["procedural"],
        )

    @pytest.mark.asyncio
    async def test_recall_episodic_adaptive(self, mock_session, mock_repos, service):
        """recall_episodic adaptive 策略必须返回按强度排序的记忆"""
        mem1 = EpisodicMemory(character_id="char-1", scene_description="强记忆", strength=0.9)
        mem2 = EpisodicMemory(character_id="char-1", scene_description="弱记忆", strength=0.3)
        mock_repos["episodic"].get_by_character.return_value = [mem1, mem2]

        result = await service.recall_episodic(mock_session, "char-1", top_k=2)

        assert len(result) == 2
        assert result[0].strength == 0.9

    @pytest.mark.asyncio
    async def test_recall_episodic_emotional(self, mock_session, mock_repos, service):
        """recall_episodic emotional 策略必须按情感标签过滤"""
        mem = EpisodicMemory(
            character_id="char-1",
            scene_description="快乐记忆",
            emotional_tags=["喜悦", "兴奋"],
            strength=0.8,
        )
        mock_repos["episodic"].get_by_character.return_value = [mem]

        result = await service.recall_episodic(
            mock_session, "char-1", strategy="emotional", target_emotion="喜悦", top_k=1
        )

        assert len(result) == 1
        assert "喜悦" in result[0].emotional_tags

    @pytest.mark.asyncio
    async def test_recall_episodic_temporal(self, mock_session, mock_repos, service):
        """recall_episodic temporal 策略必须按时间窗口返回"""
        mem = EpisodicMemory(character_id="char-1", scene_description="最近记忆")
        mock_repos["episodic"].get_recent.return_value = [mem]

        result = await service.recall_episodic(
            mock_session, "char-1", strategy="temporal", time_window=3600, top_k=1
        )

        assert len(result) == 1
        mock_repos["episodic"].get_recent.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_recall_semantic_by_key(self, mock_session, mock_repos, service):
        """recall_semantic 带 concept_key 时必须返回特定知识"""
        mem = SemanticMemory(
            character_id="char-1",
            concept_key="魔法体系",
            concept_value="五行相生相克",
        )
        mock_repos["semantic"].get_by_concept.return_value = mem

        result = await service.recall_semantic(
            mock_session, "char-1", concept_key="魔法体系"
        )

        assert len(result) == 1
        assert result[0].concept_value == "五行相生相克"

    @pytest.mark.asyncio
    async def test_recall_skills(self, mock_session, mock_repos, service):
        """recall_skills 必须返回技能列表"""
        mem = ProceduralMemory(
            character_id="char-1", skill_name="御剑术", proficiency=0.9
        )
        mock_repos["procedural"].get_by_character.return_value = [mem]

        result = await service.recall_skills(mock_session, "char-1")

        assert len(result) == 1
        assert result[0].skill_name == "御剑术"

    @pytest.mark.asyncio
    async def test_recall_skills_automatic_only(self, mock_session, mock_repos, service):
        """recall_skills automatic_only 必须只返回自动化技能"""
        mem = ProceduralMemory(
            character_id="char-1", skill_name="基础剑法", is_automatic=True
        )
        mock_repos["procedural"].get_automatic_skills.return_value = [mem]

        result = await service.recall_skills(
            mock_session, "char-1", automatic_only=True
        )

        assert len(result) == 1
        assert result[0].is_automatic is True


class TestMemoryConsolidationService:
    """MemoryConsolidationService 测试"""

    @pytest.fixture
    def mock_session(self):
        return AsyncMock()

    @pytest.fixture
    def mock_repos(self):
        return {
            "episodic": MagicMock(spec=EpisodicMemoryRepository),
            "semantic": MagicMock(spec=SemanticMemoryRepository),
            "procedural": MagicMock(spec=ProceduralMemoryRepository),
        }

    @pytest.fixture
    def service(self, mock_repos):
        return MemoryConsolidationService(
            episodic_repo=mock_repos["episodic"],
            semantic_repo=mock_repos["semantic"],
            procedural_repo=mock_repos["procedural"],
        )

    @pytest.mark.asyncio
    async def test_rehearse(self, mock_session, mock_repos, service):
        """rehearse 必须增强记忆强度"""
        mem = EpisodicMemory(
            id="mem-1",
            character_id="char-1",
            scene_description="重要记忆",
            strength=0.5,
            rehearsal_count=0,
        )
        mock_repos["episodic"].get_by_id.return_value = mem
        mock_repos["episodic"].update.return_value = mem

        result = await service.rehearse(mock_session, "mem-1", rehearsal_type="active")

        assert result > 0.5  # 强度应该增加
        assert mem.rehearsal_count == 1
        assert mem.last_rehearsed is not None

    @pytest.mark.asyncio
    async def test_rehearse_consolidation(self, mock_session, mock_repos, service):
        """rehearse 多次后必须巩固记忆"""
        mem = EpisodicMemory(
            id="mem-1",
            character_id="char-1",
            strength=0.5,
            rehearsal_count=2,
            is_consolidated=False,
        )
        mock_repos["episodic"].get_by_id.return_value = mem
        mock_repos["episodic"].update.return_value = mem

        result = await service.rehearse(mock_session, "mem-1")

        assert mem.is_consolidated is True  # 第3次复述后巩固
        assert mem.decay_rate < 0.1  # 巩固后衰减更慢

    @pytest.mark.asyncio
    async def test_rehearse_not_found(self, mock_session, mock_repos, service):
        """rehearse 记忆不存在时必须返回 None"""
        mock_repos["episodic"].get_by_id.return_value = None

        result = await service.rehearse(mock_session, "not-exist")

        assert result is None

    @pytest.mark.asyncio
    async def test_consolidate_episodic_to_semantic(self, mock_session, mock_repos, service):
        """consolidate_episodic_to_semantic 必须提取语义记忆"""
        mem = SemanticMemory(
            character_id="char-1",
            concept_key="战斗模式",
            concept_value="遇到强敌时先防御",
            knowledge_type=KnowledgeType.BELIEF,
        )
        mock_repos["semantic"].create.return_value = mem

        result = await service.consolidate_episodic_to_semantic(
            mock_session, "char-1", "战斗模式", "遇到强敌时先防御"
        )

        assert result.concept_key == "战斗模式"
        assert result.knowledge_type == KnowledgeType.BELIEF

    @pytest.mark.asyncio
    async def test_strengthen_skill(self, mock_session, mock_repos, service):
        """strengthen_skill 必须增强技能熟练度"""
        skill = ProceduralMemory(
            id="skill-1",
            character_id="char-1",
            skill_name="御剑术",
            proficiency=0.5,
            practice_count=10,
        )
        mock_repos["procedural"].get_by_id.return_value = skill
        mock_repos["procedural"].update.return_value = skill

        result = await service.strengthen_skill(mock_session, "skill-1", practice_amount=0.2)

        assert result.proficiency > 0.5
        assert result.practice_count == 11

    @pytest.mark.asyncio
    async def test_strengthen_skill_automation(self, mock_session, mock_repos, service):
        """strengthen_skill 达到阈值后必须自动化"""
        skill = ProceduralMemory(
            id="skill-1",
            character_id="char-1",
            skill_name="基础剑法",
            proficiency=0.75,
            practice_count=19,
            is_automatic=False,
            attention_required=0.5,
        )
        mock_repos["procedural"].get_by_id.return_value = skill
        mock_repos["procedural"].update.return_value = skill

        result = await service.strengthen_skill(mock_session, "skill-1", practice_amount=0.1)

        assert result.proficiency >= 0.8
        assert result.practice_count >= 20
        assert result.is_automatic is True
        assert result.attention_required < 0.5


class TestMemoryForgettingService:
    """MemoryForgettingService 测试"""

    @pytest.fixture
    def mock_session(self):
        return AsyncMock()

    @pytest.fixture
    def mock_repo(self):
        return MagicMock(spec=EpisodicMemoryRepository)

    @pytest.fixture
    def service(self, mock_repo):
        return MemoryForgettingService(episodic_repo=mock_repo)

    @pytest.mark.asyncio
    async def test_apply_forgetting_weak_memory(self, mock_session, mock_repo, service):
        """apply_forgetting 必须遗忘弱记忆"""
        weak_mem = EpisodicMemory(
            id="weak-mem",
            character_id="char-1",
            scene_description="弱记忆",
            initial_strength=0.2,
            decay_rate=0.5,
            encoded_at=datetime.now(timezone.utc) - timedelta(days=30),
            is_flashbulb=False,
            access_count=0,
            importance=0.2,
        )
        mock_repo.get_by_character.return_value = [weak_mem]
        mock_repo.update.return_value = weak_mem

        result = await service.apply_forgetting(mock_session, "char-1", threshold=0.3)

        assert "weak-mem" in result
        mock_repo.delete.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_apply_forgetting_protect_flashbulb(self, mock_session, mock_repo, service):
        """apply_forgetting 必须保护闪光灯记忆"""
        flashbulb = EpisodicMemory(
            id="flashbulb-mem",
            character_id="char-1",
            scene_description="重大事件",
            initial_strength=0.2,
            decay_rate=0.5,
            encoded_at=datetime.now(timezone.utc) - timedelta(days=30),
            is_flashbulb=True,
            access_count=0,
            importance=0.2,
        )
        mock_repo.get_by_character.return_value = [flashbulb]
        mock_repo.update.return_value = flashbulb

        result = await service.apply_forgetting(mock_session, "char-1", threshold=0.3)

        assert "flashbulb-mem" not in result  # 不应该被遗忘
        mock_repo.delete.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_apply_forgetting_protect_high_access(self, mock_session, mock_repo, service):
        """apply_forgetting 必须保护高频访问记忆"""
        popular = EpisodicMemory(
            id="popular-mem",
            character_id="char-1",
            scene_description="常用记忆",
            initial_strength=0.2,
            decay_rate=0.5,
            encoded_at=datetime.now(timezone.utc) - timedelta(days=30),
            access_count=15,
            importance=0.2,
        )
        mock_repo.get_by_character.return_value = [popular]
        mock_repo.update.return_value = popular

        result = await service.apply_forgetting(mock_session, "char-1", threshold=0.3)

        assert "popular-mem" not in result
        mock_repo.delete.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_calculate_current_strength(self, service):
        """_calculate_current_strength 必须考虑所有因素"""
        mem = EpisodicMemory(
            character_id="char-1",
            scene_description="测试记忆",
            initial_strength=1.0,
            decay_rate=0.1,
            encoded_at=datetime.now(timezone.utc) - timedelta(days=10),
            rehearsal_count=2,
            emotional_arousal=0.8,
            is_consolidated=True,
        )

        strength = service._calculate_current_strength(
            mem, datetime.now(timezone.utc)
        )

        assert 0 <= strength <= 1.0
        # 高初始强度 + 复述 + 高情感 + 巩固 → 强度应该较高
        assert strength > 0.3

    @pytest.mark.asyncio
    async def test_should_protect(self, service):
        """_should_protect 必须正确判断保护条件"""
        flashbulb = EpisodicMemory(is_flashbulb=True)
        popular = EpisodicMemory(access_count=15)
        important = EpisodicMemory(importance=0.95)
        normal = EpisodicMemory(is_flashbulb=False, access_count=5, importance=0.5)

        assert service._should_protect(flashbulb) is True
        assert service._should_protect(popular) is True
        assert service._should_protect(important) is True
        assert service._should_protect(normal) is False


class TestMemoryManager:
    """MemoryManager 测试"""

    @pytest.fixture
    def mock_session(self):
        return AsyncMock()

    @pytest.fixture
    def mock_services(self):
        return {
            "encoding": MagicMock(spec=MemoryEncodingService),
            "retrieval": MagicMock(spec=MemoryRetrievalService),
            "consolidation": MagicMock(spec=MemoryConsolidationService),
            "forgetting": MagicMock(spec=MemoryForgettingService),
        }

    @pytest.fixture
    def manager(self, mock_services):
        return MemoryManager(
            encoding=mock_services["encoding"],
            retrieval=mock_services["retrieval"],
            consolidation=mock_services["consolidation"],
            forgetting=mock_services["forgetting"],
        )

    @pytest.mark.asyncio
    async def test_record_experience(self, mock_session, mock_services, manager):
        """record_experience 必须委托给 encoding.encode_episodic"""
        mem = EpisodicMemory(character_id="char-1", scene_description="经历")
        mock_services["encoding"].encode_episodic.return_value = mem

        result = await manager.record_experience(
            mock_session, "char-1", "经历描述"
        )

        assert result.scene_description == "经历"
        mock_services["encoding"].encode_episodic.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_learn_fact(self, mock_session, mock_services, manager):
        """learn_fact 必须委托给 encoding.encode_semantic"""
        mem = SemanticMemory(
            character_id="char-1", concept_key="key", concept_value="value"
        )
        mock_services["encoding"].encode_semantic.return_value = mem

        result = await manager.learn_fact(
            mock_session, "char-1", "key", "value"
        )

        assert result.concept_key == "key"
        mock_services["encoding"].encode_semantic.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_recall(self, mock_session, mock_services, manager):
        """recall 必须委托给 retrieval.recall_episodic"""
        mem = EpisodicMemory(character_id="char-1", scene_description="记忆")
        mock_services["retrieval"].recall_episodic.return_value = [mem]

        result = await manager.recall(mock_session, "char-1", strategy="adaptive")

        assert len(result) == 1
        mock_services["retrieval"].recall_episodic.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_rehearse_memory(self, mock_session, mock_services, manager):
        """rehearse_memory 必须委托给 consolidation.rehearse"""
        mock_services["consolidation"].rehearse.return_value = 0.8

        result = await manager.rehearse_memory(mock_session, "mem-1")

        assert result == 0.8
        mock_services["consolidation"].rehearse.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_run_forgetting(self, mock_session, mock_services, manager):
        """run_forgetting 必须委托给 forgetting.apply_forgetting"""
        mock_services["forgetting"].apply_forgetting.return_value = ["forgotten-mem"]

        result = await manager.run_forgetting(mock_session, "char-1")

        assert result == ["forgotten-mem"]
        mock_services["forgetting"].apply_forgetting.assert_awaited_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
