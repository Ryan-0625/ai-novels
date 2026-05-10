"""
LLM Tier 系统单元测试
"""

import pytest

from deepnovel.llm.tier import (
    ModelTier,
    TierConfig,
    TaskComplexityEstimator,
    TierRouter,
)


class TestTierConfig:
    """TierConfig 测试"""

    def test_init(self):
        config = TierConfig(
            tier=ModelTier.STANDARD,
            provider="openai",
            model="gpt-4o",
        )
        assert config.tier == ModelTier.STANDARD
        assert config.provider == "openai"
        assert config.complexity_min == 0.0
        assert config.complexity_max == 1.0

    def test_matches_complexity(self):
        config = TierConfig(
            tier=ModelTier.FAST,
            provider="test",
            model="m",
            complexity_min=0.0,
            complexity_max=0.35,
        )
        assert config.matches_complexity(0.2) is True
        assert config.matches_complexity(0.5) is False

    def test_estimate_cost(self):
        config = TierConfig(
            tier=ModelTier.PREMIUM,
            provider="openai",
            model="gpt-4o",
            cost_per_1k_input=0.005,
            cost_per_1k_output=0.015,
        )
        cost = config.estimate_cost(input_tokens=2000, output_tokens=500)
        # input: 2 * 0.005 = 0.01, output: 0.5 * 0.015 = 0.0075
        assert cost == pytest.approx(0.0175, rel=1e-4)

    def test_to_dict(self):
        config = TierConfig(tier=ModelTier.FAST, provider="test", model="m")
        d = config.to_dict()
        assert d["tier"] == "fast"
        assert d["provider"] == "test"


class TestTaskComplexityEstimator:
    """TaskComplexityEstimator 测试"""

    @pytest.fixture
    def estimator(self):
        return TaskComplexityEstimator()

    def test_simple_prompt(self, estimator):
        """简单 prompt 复杂度低"""
        prompt = "分类这句话的情感。"
        score = estimator.estimate(prompt)
        assert score < 0.4

    def test_complex_prompt(self, estimator):
        """复杂 prompt 复杂度高"""
        prompt = (
            "创作一个关于修仙的完整故事，包括主角背景、修炼体系、"
            "主要冲突、高潮和结局。要求情节曲折，角色丰满，"
            "世界观详细。分析主角的心理变化、成长弧线和因果关系。"
            "首先设计世界观，然后构思角色，最后编写情节。"
            "想象一个宏大的仙侠世界。"
        )
        score = estimator.estimate(prompt)
        assert score > 0.5

    def test_reasoning_prompt(self, estimator):
        """推理任务复杂度中等偏高"""
        prompt = "分析以下因果关系，推断最可能的结果。"
        score = estimator.estimate(prompt)
        assert score > 0.3

    def test_length_scoring(self, estimator):
        """长度评分"""
        short_score = estimator._score_length("短")
        long_score = estimator._score_length("长" * 3000)
        assert short_score < long_score

    def test_instruction_scoring(self, estimator):
        """指令数量评分"""
        no_steps = estimator._score_instructions("回答问题")
        many_steps = estimator._score_instructions(
            "1. 首先分析 2. 然后比较 3. 最后总结"
        )
        assert no_steps < many_steps

    def test_batch_estimate(self, estimator):
        """批量估计"""
        prompts = [
            "简单",
            "创作一个完整故事，分析因果关系，推理主角行为动机。"
        ]
        scores = estimator.estimate_batch(prompts)
        assert len(scores) == 2
        assert scores[0] < scores[1]


class TestTierRouter:
    """TierRouter 测试"""

    @pytest.fixture
    def router(self):
        return TierRouter()

    def test_init_default_tiers(self, router):
        """默认初始化包含3个级别"""
        assert len(router.tiers) == 3
        assert ModelTier.FAST in router.tiers
        assert ModelTier.STANDARD in router.tiers
        assert ModelTier.PREMIUM in router.tiers

    def test_get_tier(self, router):
        config = router.get_tier(ModelTier.FAST)
        assert config is not None
        assert config.tier == ModelTier.FAST

    def test_set_tier(self, router):
        new_config = TierConfig(
            tier=ModelTier.FAST,
            provider="new",
            model="new-model",
        )
        router.set_tier(new_config)
        assert router.get_tier(ModelTier.FAST).provider == "new"

    def test_route_by_complexity_low(self, router):
        """低复杂度 → FAST"""
        config = router.route_by_complexity(0.2)
        assert config.tier == ModelTier.FAST

    def test_route_by_complexity_medium(self, router):
        """中等复杂度 → STANDARD"""
        config = router.route_by_complexity(0.5)
        assert config.tier == ModelTier.STANDARD

    def test_route_by_complexity_high(self, router):
        """高复杂度 → PREMIUM"""
        config = router.route_by_complexity(0.9)
        assert config.tier == ModelTier.PREMIUM

    def test_route_simple_prompt(self, router):
        """简单 prompt 路由到 FAST"""
        config, complexity = router.route("分类这句话。")
        assert config.tier == ModelTier.FAST
        assert complexity >= 0

    def test_route_complex_prompt(self, router):
        """复杂 prompt 路由到 PREMIUM"""
        config, complexity = router.route(
            "创作一个关于修仙的完整故事，分析角色心理，设计修炼体系。"
            "首先构思世界观，然后推导因果关系，评估情节合理性。"
            "想象一个宏大的仙侠世界。"
        )
        assert complexity > 0.5
        assert config.tier == ModelTier.PREMIUM

    def test_route_preferred_tier(self, router):
        """指定级别优先"""
        config, _ = router.route("任何内容", preferred_tier=ModelTier.PREMIUM)
        assert config.tier == ModelTier.PREMIUM

    def test_route_batch(self, router):
        """批量路由"""
        prompts = [
            "分类",
            "创作一个完整故事，分析因果关系，推理主角行为动机。"
        ]
        results = router.route_batch(prompts)
        assert len(results) == 2
        assert results[0][0].tier != results[1][0].tier

    def test_cost_estimate(self, router):
        """成本估算"""
        estimate = router.get_cost_estimate("测试 prompt", expected_output_tokens=200)
        assert "tier" in estimate
        assert "estimated_cost_usd" in estimate
        assert "complexity" in estimate

    def test_to_dict(self, router):
        d = router.to_dict()
        assert "tiers" in d
        assert "default_tier" in d


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
