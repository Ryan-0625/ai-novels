"""
LLM Tier 系统 — 按任务复杂度路由到不同级别模型

Tier 分级:
- FAST:     轻量级模型，用于简单任务（分类、判断、提取）
- STANDARD: 标准模型，默认使用（生成、分析、推理）
- PREMIUM:  高质量模型，用于复杂任务（创意写作、深度推理）

@file: llm/tier.py
@date: 2026-04-29
"""

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class ModelTier(Enum):
    """模型级别"""

    FAST = "fast"          # 轻量级，低延迟，低成本
    STANDARD = "standard"  # 标准，平衡质量与成本
    PREMIUM = "premium"    # 高质量，高成本


@dataclass
class TierConfig:
    """级别配置"""

    tier: ModelTier
    provider: str
    model: str
    max_tokens: int = 4096
    temperature: float = 0.7
    timeout: int = 120
    cost_per_1k_input: float = 0.0
    cost_per_1k_output: float = 0.0
    context_window: int = 8192
    complexity_min: float = 0.0  # 适用复杂度下限
    complexity_max: float = 1.0  # 适用复杂度上限
    description: str = ""

    def matches_complexity(self, complexity: float) -> bool:
        """检查复杂度是否在适用范围内"""
        return self.complexity_min <= complexity <= self.complexity_max

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """估算成本 (USD)"""
        input_cost = (input_tokens / 1000) * self.cost_per_1k_input
        output_cost = (output_tokens / 1000) * self.cost_per_1k_output
        return round(input_cost + output_cost, 6)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tier": self.tier.value,
            "provider": self.provider,
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "cost_per_1k_input": self.cost_per_1k_input,
            "cost_per_1k_output": self.cost_per_1k_output,
            "context_window": self.context_window,
            "complexity_range": [self.complexity_min, self.complexity_max],
        }


class TaskComplexityEstimator:
    """任务复杂度估计器

    基于 prompt 的多维特征估计任务复杂度:
    - 长度: 长文本通常更复杂
    - 指令数量: 多步骤指令更复杂
    - 推理深度: 需要多步推理的更复杂
    - 创造性要求: 创意写作比提取更复杂
    """

    # 复杂度指标权重
    WEIGHTS = {
        "length": 0.15,
        "instructions": 0.25,
        "reasoning": 0.30,
        "creativity": 0.30,
    }

    # 推理关键词
    REASONING_KEYWORDS = [
        "分析", "推理", "推断", "推导", "证明", "解释为什么",
        "analyze", "reason", "infer", "deduce", "prove", "explain why",
        "比较", "对比", "评估", "权衡", "因果关系",
        "compare", "contrast", "evaluate", "trade-off", "cause and effect",
    ]

    # 创造性关键词
    CREATIVE_KEYWORDS = [
        "创作", "写", "生成", "构思", "设计", "想象",
        "create", "write", "generate", "compose", "design", "imagine",
        "故事", "小说", "诗歌", "剧本", "情节", "角色",
        "story", "novel", "poem", "script", "plot", "character",
    ]

    # 简单任务关键词（降低复杂度）
    SIMPLE_KEYWORDS = [
        "分类", "判断", "是/否", "提取", "总结",
        "classify", "judge", "yes/no", "extract", "summarize",
        "简短", "一句话", "简要",
        "brief", "one sentence", "short",
    ]

    def __init__(self, weights: Optional[Dict[str, float]] = None):
        self.weights = weights or self.WEIGHTS.copy()

    def _score_length(self, prompt: str) -> float:
        """基于长度评分 (0-1)"""
        length = len(prompt)
        if length < 100:
            return 0.1
        elif length < 500:
            return 0.3
        elif length < 2000:
            return 0.6
        else:
            return 1.0

    def _score_instructions(self, prompt: str) -> float:
        """基于指令数量评分 (0-1)"""
        # 计数步骤指示词
        step_patterns = [
            r"\d+\.", r"步骤", r"step", r"首先", r"然后", r"最后",
            r"first", r"then", r"finally", r"next", r"after",
        ]
        count = sum(len(re.findall(p, prompt, re.IGNORECASE)) for p in step_patterns)
        return min(1.0, count / 5)

    def _score_reasoning(self, prompt: str) -> float:
        """基于推理需求评分 (0-1)"""
        prompt_lower = prompt.lower()
        matches = sum(1 for kw in self.REASONING_KEYWORDS if kw.lower() in prompt_lower)
        return min(1.0, matches / 3)

    def _score_creativity(self, prompt: str) -> float:
        """基于创造性需求评分 (0-1)"""
        prompt_lower = prompt.lower()
        matches = sum(1 for kw in self.CREATIVE_KEYWORDS if kw.lower() in prompt_lower)
        # 简单任务关键词降低创造性分数
        simple_matches = sum(1 for kw in self.SIMPLE_KEYWORDS if kw.lower() in prompt_lower)
        score = max(0.0, min(1.0, matches / 3) - simple_matches * 0.1)
        return score

    def estimate(self, prompt: str) -> float:
        """估计任务复杂度 (0-1)"""
        scores = {
            "length": self._score_length(prompt),
            "instructions": self._score_instructions(prompt),
            "reasoning": self._score_reasoning(prompt),
            "creativity": self._score_creativity(prompt),
        }

        complexity = sum(scores[k] * self.weights[k] for k in scores)
        return round(min(1.0, max(0.0, complexity)), 3)

    def estimate_batch(self, prompts: List[str]) -> List[float]:
        """批量估计"""
        return [self.estimate(p) for p in prompts]


class TierRouter:
    """Tier 路由器 — 根据任务复杂度选择合适级别的模型"""

    # 默认级别配置示例
    DEFAULT_TIERS: Dict[ModelTier, TierConfig] = {
        ModelTier.FAST: TierConfig(
            tier=ModelTier.FAST,
            provider="ollama",
            model="qwen2.5:7b",
            max_tokens=2048,
            temperature=0.3,
            cost_per_1k_input=0.0,
            cost_per_1k_output=0.0,
            complexity_min=0.0,
            complexity_max=0.35,
            description="轻量级任务: 分类、判断、提取",
        ),
        ModelTier.STANDARD: TierConfig(
            tier=ModelTier.STANDARD,
            provider="ollama",
            model="qwen2.5:14b",
            max_tokens=4096,
            temperature=0.7,
            cost_per_1k_input=0.0,
            cost_per_1k_output=0.0,
            complexity_min=0.25,
            complexity_max=0.70,
            description="标准任务: 生成、分析、推理",
        ),
        ModelTier.PREMIUM: TierConfig(
            tier=ModelTier.PREMIUM,
            provider="openai",
            model="gpt-4o",
            max_tokens=8192,
            temperature=0.8,
            cost_per_1k_input=0.005,
            cost_per_1k_output=0.015,
            context_window=128000,
            complexity_min=0.60,
            complexity_max=1.0,
            description="复杂任务: 创意写作、深度推理",
        ),
    }

    def __init__(
        self,
        tiers: Optional[Dict[ModelTier, TierConfig]] = None,
        estimator: Optional[TaskComplexityEstimator] = None,
    ):
        self._tiers = tiers or self.DEFAULT_TIERS.copy()
        self._estimator = estimator or TaskComplexityEstimator()
        self._default_tier = ModelTier.STANDARD

    @property
    def tiers(self) -> Dict[ModelTier, TierConfig]:
        return self._tiers.copy()

    def get_tier(self, tier: ModelTier) -> Optional[TierConfig]:
        """获取指定级别的配置"""
        return self._tiers.get(tier)

    def set_tier(self, config: TierConfig) -> None:
        """设置级别配置"""
        self._tiers[config.tier] = config

    def route_by_complexity(self, complexity: float) -> TierConfig:
        """根据复杂度路由到合适的级别

        Args:
            complexity: 任务复杂度 (0-1)

        Returns:
            匹配的 TierConfig
        """
        # 寻找最佳匹配
        best_match: Optional[TierConfig] = None
        best_score = -1.0

        for tier_config in self._tiers.values():
            if tier_config.matches_complexity(complexity):
                # 选择覆盖范围最精确（最窄）的
                coverage = tier_config.complexity_max - tier_config.complexity_min
                score = 1.0 / (coverage + 0.01)  # 越窄分数越高
                if score > best_score:
                    best_score = score
                    best_match = tier_config

        if best_match:
            return best_match

        # 无精确匹配时，找最近边界
        if complexity < 0.3:
            return self._tiers.get(ModelTier.FAST, self._tiers[self._default_tier])
        elif complexity < 0.7:
            return self._tiers.get(ModelTier.STANDARD, self._tiers[self._default_tier])
        else:
            return self._tiers.get(ModelTier.PREMIUM, self._tiers[self._default_tier])

    def route(
        self,
        prompt: str,
        preferred_tier: Optional[ModelTier] = None,
    ) -> Tuple[TierConfig, float]:
        """路由：估计复杂度 → 选择级别

        Returns:
            (TierConfig, 估计复杂度)
        """
        if preferred_tier and preferred_tier in self._tiers:
            return self._tiers[preferred_tier], -1.0

        complexity = self._estimator.estimate(prompt)
        config = self.route_by_complexity(complexity)
        return config, complexity

    def route_batch(
        self,
        prompts: List[str],
    ) -> List[Tuple[TierConfig, float]]:
        """批量路由"""
        complexities = self._estimator.estimate_batch(prompts)
        return [(self.route_by_complexity(c), c) for c in complexities]

    def get_cost_estimate(
        self,
        prompt: str,
        expected_output_tokens: int = 500,
    ) -> Dict[str, Any]:
        """获取成本估算"""
        config, complexity = self.route(prompt)
        input_tokens = len(prompt) // 4  # 粗略估算
        cost = config.estimate_cost(input_tokens, expected_output_tokens)
        return {
            "tier": config.tier.value,
            "model": config.model,
            "provider": config.provider,
            "complexity": complexity,
            "estimated_input_tokens": input_tokens,
            "estimated_output_tokens": expected_output_tokens,
            "estimated_cost_usd": cost,
        }

    def to_dict(self) -> Dict[str, Any]:
        """序列化"""
        return {
            "tiers": {
                tier.value: config.to_dict()
                for tier, config in self._tiers.items()
            },
            "default_tier": self._default_tier.value,
        }
