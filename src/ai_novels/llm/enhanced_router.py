"""
增强版LLM路由模块

提供智能路由、流式支持、成本优化、负载均衡等功能
"""

import asyncio
import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import (
    Any,
    AsyncIterator,
    Callable,
    Dict,
    List,
    Optional,
    Protocol,
    TypeVar,
    Union,
)
from collections import deque
from datetime import datetime, timedelta
import random

from ..core.exceptions import LLMError, ErrorCode
from ..core.performance_monitor import PerformanceMonitor, timed
from ..utils.logger import get_logger

logger = get_logger(__name__)

T = TypeVar('T')


class RoutingStrategy(Enum):
    """路由策略"""
    ROUND_ROBIN = "round_robin"          # 轮询
    LEAST_LATENCY = "least_latency"      # 最低延迟
    COST_OPTIMIZED = "cost_optimized"    # 成本优化
    QUALITY_FIRST = "quality_first"      # 质量优先
    FALLBACK = "fallback"                # 故障转移


class ModelCapability(Enum):
    """模型能力"""
    CHAT = "chat"
    COMPLETION = "completion"
    EMBEDDING = "embedding"
    IMAGE_GENERATION = "image_generation"
    CODE = "code"
    REASONING = "reasoning"
    LONG_CONTEXT = "long_context"
    STREAMING = "streaming"


@dataclass
class ModelInfo:
    """模型信息"""
    name: str
    provider: str
    capabilities: List[ModelCapability] = field(default_factory=list)
    max_tokens: int = 4096
    cost_per_1k_input: float = 0.0
    cost_per_1k_output: float = 0.0
    avg_latency_ms: float = 0.0
    success_rate: float = 1.0
    weight: int = 1
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RoutingDecision:
    """路由决策结果"""
    model_name: str
    provider: str
    strategy: RoutingStrategy
    reason: str
    estimated_cost: float = 0.0
    estimated_latency_ms: float = 0.0


@dataclass
class StreamChunk:
    """流式响应块"""
    content: str
    is_finished: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


class LLMProvider(Protocol):
    """LLM提供商协议"""
    
    async def generate(
        self,
        prompt: str,
        model: str,
        **kwargs
    ) -> str:
        """生成文本"""
        ...
    
    async def generate_stream(
        self,
        prompt: str,
        model: str,
        **kwargs
    ) -> AsyncIterator[StreamChunk]:
        """流式生成文本"""
        ...
    
    async def get_embeddings(
        self,
        texts: List[str],
        model: str,
        **kwargs
    ) -> List[List[float]]:
        """获取文本嵌入"""
        ...


class ProviderHealth:
    """提供商健康状态"""
    
    def __init__(self, window_size: int = 100):
        self.window_size = window_size
        self.requests: deque = deque(maxlen=window_size)
        self.errors: deque = deque(maxlen=window_size)
        self.latencies: deque = deque(maxlen=window_size)
        self.last_success = datetime.now()
        self.consecutive_errors = 0
        self.circuit_open = False
        self.circuit_opened_at: Optional[datetime] = None
    
    def record_success(self, latency_ms: float):
        """记录成功请求"""
        self.requests.append(datetime.now())
        self.latencies.append(latency_ms)
        self.last_success = datetime.now()
        self.consecutive_errors = 0
    
    def record_error(self):
        """记录错误请求"""
        self.errors.append(datetime.now())
        self.consecutive_errors += 1
    
    def get_success_rate(self) -> float:
        """获取成功率"""
        if not self.requests:
            return 1.0
        recent_errors = len([e for e in self.errors 
                           if e > datetime.now() - timedelta(minutes=5)])
        recent_requests = len([r for r in self.requests 
                              if r > datetime.now() - timedelta(minutes=5)])
        if recent_requests == 0:
            return 1.0
        return 1.0 - (recent_errors / recent_requests)
    
    def get_avg_latency(self) -> float:
        """获取平均延迟"""
        if not self.latencies:
            return 0.0
        return sum(self.latencies) / len(self.latencies)
    
    def should_trip_circuit(self, threshold: int = 5) -> bool:
        """是否应该触发熔断"""
        return self.consecutive_errors >= threshold
    
    def check_circuit(self, timeout_seconds: int = 60) -> bool:
        """检查熔断器状态"""
        if not self.circuit_open:
            if self.should_trip_circuit():
                self.circuit_open = True
                self.circuit_opened_at = datetime.now()
                return True
            return False
        
        # 检查是否应该关闭熔断器
        if self.circuit_opened_at:
            elapsed = (datetime.now() - self.circuit_opened_at).total_seconds()
            if elapsed > timeout_seconds:
                self.circuit_open = False
                self.circuit_opened_at = None
                self.consecutive_errors = 0
                return False
        return True


class SmartLLMRouter:
    """
    智能LLM路由器
    
    特性:
    - 多策略路由(轮询、延迟优先、成本优化、质量优先)
    - 自动故障转移和熔断
    - 流式响应支持
    - 成本追踪和优化
    - 性能监控
    """
    
    def __init__(
        self,
        default_strategy: RoutingStrategy = RoutingStrategy.ROUND_ROBIN,
        monitor: Optional[PerformanceMonitor] = None
    ):
        self.models: Dict[str, ModelInfo] = {}
        self.providers: Dict[str, LLMProvider] = {}
        self.health: Dict[str, ProviderHealth] = {}
        self.default_strategy = default_strategy
        self.monitor = monitor or PerformanceMonitor()
        
        # 轮询计数器
        self._round_robin_index = 0
        
        # 成本追踪
        self._cost_stats: Dict[str, Dict[str, float]] = {}
        
        # 回调函数
        self._pre_request_hooks: List[Callable] = []
        self._post_request_hooks: List[Callable] = []
        
        logger.info("SmartLLMRouter initialized")
    
    def register_model(self, info: ModelInfo):
        """注册模型"""
        self.models[info.name] = info
        self.health[info.name] = ProviderHealth()
        self._cost_stats[info.name] = {
            "total_cost": 0.0,
            "total_tokens": 0,
            "request_count": 0
        }
        logger.info(f"Registered model: {info.name} ({info.provider})")
    
    def register_provider(self, name: str, provider: LLMProvider):
        """注册提供商"""
        self.providers[name] = provider
        logger.info(f"Registered provider: {name}")
    
    def add_pre_request_hook(self, hook: Callable):
        """添加请求前钩子"""
        self._pre_request_hooks.append(hook)
    
    def add_post_request_hook(self, hook: Callable):
        """添加请求后钩子"""
        self._post_request_hooks.append(hook)
    
    def _select_model(
        self,
        capability: Optional[ModelCapability] = None,
        strategy: Optional[RoutingStrategy] = None,
        preferred_models: Optional[List[str]] = None
    ) -> RoutingDecision:
        """选择模型"""
        strategy = strategy or self.default_strategy
        
        # 过滤可用模型
        available = [
            (name, info) for name, info in self.models.items()
            if info.enabled 
            and not self.health[name].circuit_open
            and (capability is None or capability in info.capabilities)
            and (preferred_models is None or name in preferred_models)
        ]
        
        if not available:
            # 尝试使用备用模型
            available = [
                (name, info) for name, info in self.models.items()
                if info.enabled and (preferred_models is None or name in preferred_models)
            ]
        
        if not available:
            raise LLMError(
                ErrorCode.MODEL_NOT_FOUND,
                "No available models for the request"
            )
        
        # 根据策略选择
        if strategy == RoutingStrategy.ROUND_ROBIN:
            selected = self._round_robin_select(available)
            reason = "Round-robin selection"
        elif strategy == RoutingStrategy.LEAST_LATENCY:
            selected = self._least_latency_select(available)
            reason = "Lowest latency"
        elif strategy == RoutingStrategy.COST_OPTIMIZED:
            selected = self._cost_optimized_select(available)
            reason = "Cost optimization"
        elif strategy == RoutingStrategy.QUALITY_FIRST:
            selected = self._quality_first_select(available)
            reason = "Quality priority"
        else:
            selected = available[0][1]
            reason = "Default selection"
        
        return RoutingDecision(
            model_name=selected.name,
            provider=selected.provider,
            strategy=strategy,
            reason=reason,
            estimated_cost=self._estimate_cost(selected),
            estimated_latency_ms=selected.avg_latency_ms
        )
    
    def _round_robin_select(self, available: List[tuple]) -> ModelInfo:
        """轮询选择"""
        if not available:
            raise ValueError("No available models")
        
        # 考虑权重
        weighted = []
        for name, info in available:
            weighted.extend([info] * info.weight)
        
        self._round_robin_index = (self._round_robin_index + 1) % len(weighted)
        return weighted[self._round_robin_index]
    
    def _least_latency_select(self, available: List[tuple]) -> ModelInfo:
        """选择延迟最低的模型"""
        return min(
            available,
            key=lambda x: self.health[x[0]].get_avg_latency() or x[1].avg_latency_ms
        )[1]
    
    def _cost_optimized_select(self, available: List[tuple]) -> ModelInfo:
        """选择成本最低的模型"""
        return min(available, key=lambda x: x[1].cost_per_1k_input + x[1].cost_per_1k_output)[1]
    
    def _quality_first_select(self, available: List[tuple]) -> ModelInfo:
        """选择质量最高的模型(基于成功率和延迟)"""
        def quality_score(item):
            name, info = item
            health = self.health[name]
            return (
                health.get_success_rate() * 0.5 +
                (1.0 / (1 + health.get_avg_latency() / 1000)) * 0.5
            )
        
        return max(available, key=quality_score)[1]
    
    def _estimate_cost(self, model: ModelInfo, input_tokens: int = 1000, output_tokens: int = 500) -> float:
        """估算成本"""
        input_cost = (input_tokens / 1000) * model.cost_per_1k_input
        output_cost = (output_tokens / 1000) * model.cost_per_1k_output
        return input_cost + output_cost
    
    def _update_cost_stats(self, model_name: str, input_tokens: int, output_tokens: int):
        """更新成本统计"""
        model = self.models.get(model_name)
        if not model:
            return
        
        cost = self._estimate_cost(model, input_tokens, output_tokens)
        stats = self._cost_stats[model_name]
        stats["total_cost"] += cost
        stats["total_tokens"] += input_tokens + output_tokens
        stats["request_count"] += 1
    
    @timed("llm_generate")
    async def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        capability: Optional[ModelCapability] = None,
        strategy: Optional[RoutingStrategy] = None,
        max_retries: int = 3,
        **kwargs
    ) -> Dict[str, Any]:
        """
        生成文本
        
        Args:
            prompt: 提示词
            model: 指定模型(可选)
            capability: 所需能力(可选)
            strategy: 路由策略(可选)
            max_retries: 最大重试次数
            **kwargs: 其他参数
        
        Returns:
            包含生成结果和元信息的字典
        """
        # 执行前置钩子
        for hook in self._pre_request_hooks:
            await asyncio.get_event_loop().run_in_executor(
                None, hook, prompt, kwargs
            )
        
        # 选择模型
        if model:
            if model not in self.models:
                raise LLMError(ErrorCode.MODEL_NOT_FOUND, f"Model {model} not found")
            model_info = self.models[model]
            decision = RoutingDecision(
                model_name=model,
                provider=model_info.provider,
                strategy=RoutingStrategy.FALLBACK,
                reason="User specified"
            )
        else:
            decision = self._select_model(capability, strategy)
        
        logger.info(f"Routing to {decision.model_name} using {decision.strategy.value}")
        
        # 获取提供商
        provider = self.providers.get(decision.provider)
        if not provider:
            raise LLMError(
                ErrorCode.PROVIDER_NOT_FOUND,
                f"Provider {decision.provider} not found"
            )
        
        # 执行请求(带重试)
        last_error = None
        for attempt in range(max_retries):
            try:
                start_time = time.time()
                
                result = await provider.generate(
                    prompt,
                    decision.model_name,
                    **kwargs
                )
                
                latency_ms = (time.time() - start_time) * 1000
                
                # 更新健康状态
                self.health[decision.model_name].record_success(latency_ms)
                
                # 更新成本统计
                input_tokens = kwargs.get("input_tokens", len(prompt) // 4)
                output_tokens = kwargs.get("output_tokens", len(result) // 4)
                self._update_cost_stats(decision.model_name, input_tokens, output_tokens)
                
                # 记录指标
                self.monitor.record_histogram("llm_latency_ms", latency_ms)
                self.monitor.record_counter("llm_requests_total", 1)
                
                response = {
                    "content": result,
                    "model": decision.model_name,
                    "provider": decision.provider,
                    "latency_ms": latency_ms,
                    "routing": {
                        "strategy": decision.strategy.value,
                        "reason": decision.reason
                    }
                }
                
                # 执行后置钩子
                for hook in self._post_request_hooks:
                    await asyncio.get_event_loop().run_in_executor(
                        None, hook, response
                    )
                
                return response
                
            except Exception as e:
                last_error = e
                self.health[decision.model_name].record_error()
                logger.warning(f"Attempt {attempt + 1} failed: {e}")
                
                if attempt < max_retries - 1:
                    # 尝试故障转移
                    decision = self._select_model(
                        capability, 
                        RoutingStrategy.FALLBACK,
                        [m for m in self.models.keys() if m != decision.model_name]
                    )
                    await asyncio.sleep(2 ** attempt)  # 指数退避
        
        # 所有重试都失败
        self.monitor.record_counter("llm_errors_total", 1)
        raise LLMError(
            ErrorCode.LLM_REQUEST_FAILED,
            f"All retries failed: {last_error}"
        )
    
    async def generate_stream(
        self,
        prompt: str,
        model: Optional[str] = None,
        capability: Optional[ModelCapability] = None,
        strategy: Optional[RoutingStrategy] = None,
        **kwargs
    ) -> AsyncIterator[StreamChunk]:
        """
        流式生成文本
        
        Args:
            prompt: 提示词
            model: 指定模型(可选)
            capability: 所需能力(可选)
            strategy: 路由策略(可选)
            **kwargs: 其他参数
        
        Yields:
            StreamChunk 流式响应块
        """
        # 选择模型
        if model:
            if model not in self.models:
                raise LLMError(ErrorCode.MODEL_NOT_FOUND, f"Model {model} not found")
            model_info = self.models[model]
            decision = RoutingDecision(
                model_name=model,
                provider=model_info.provider,
                strategy=RoutingStrategy.FALLBACK,
                reason="User specified"
            )
        else:
            decision = self._select_model(capability, strategy)
        
        # 检查模型是否支持流式
        if ModelCapability.STREAMING not in self.models[decision.model_name].capabilities:
            raise LLMError(
                ErrorCode.CAPABILITY_NOT_SUPPORTED,
                f"Model {decision.model_name} does not support streaming"
            )
        
        provider = self.providers.get(decision.provider)
        if not provider:
            raise LLMError(
                ErrorCode.PROVIDER_NOT_FOUND,
                f"Provider {decision.provider} not found"
            )
        
        start_time = time.time()
        total_content = ""
        
        try:
            async for chunk in provider.generate_stream(prompt, decision.model_name, **kwargs):
                total_content += chunk.content
                yield chunk
            
            latency_ms = (time.time() - start_time) * 1000
            self.health[decision.model_name].record_success(latency_ms)
            
            self.monitor.record_histogram("llm_stream_latency_ms", latency_ms)
            self.monitor.record_counter("llm_stream_requests_total", 1)
            
        except Exception as e:
            self.health[decision.model_name].record_error()
            self.monitor.record_counter("llm_stream_errors_total", 1)
            raise LLMError(
                ErrorCode.LLM_STREAMING_FAILED,
                f"Streaming failed: {e}"
            )
    
    def get_cost_report(self) -> Dict[str, Any]:
        """获取成本报告"""
        total_cost = sum(s["total_cost"] for s in self._cost_stats.values())
        total_tokens = sum(s["total_tokens"] for s in self._cost_stats.values())
        total_requests = sum(s["request_count"] for s in self._cost_stats.values())
        
        return {
            "total_cost_usd": round(total_cost, 4),
            "total_tokens": total_tokens,
            "total_requests": total_requests,
            "avg_cost_per_request": round(total_cost / total_requests, 6) if total_requests > 0 else 0,
            "by_model": {
                name: {
                    "cost_usd": round(stats["total_cost"], 4),
                    "tokens": stats["total_tokens"],
                    "requests": int(stats["request_count"])
                }
                for name, stats in self._cost_stats.items()
            }
        }
    
    def get_health_report(self) -> Dict[str, Any]:
        """获取健康报告"""
        return {
            name: {
                "success_rate": round(health.get_success_rate(), 4),
                "avg_latency_ms": round(health.get_avg_latency(), 2),
                "consecutive_errors": health.consecutive_errors,
                "circuit_open": health.circuit_open,
                "last_success": health.last_success.isoformat() if health.last_success else None
            }
            for name, health in self.health.items()
        }


# 便捷函数
async def generate_text(
    prompt: str,
    model: Optional[str] = None,
    **kwargs
) -> str:
    """便捷的文本生成函数"""
    from ..config.manager import get_config
    config = get_config()
    
    router = SmartLLMRouter()
    # 这里应该从配置加载模型和提供商
    
    result = await router.generate(prompt, model=model, **kwargs)
    return result["content"]


async def generate_stream_text(
    prompt: str,
    model: Optional[str] = None,
    **kwargs
) -> AsyncIterator[str]:
    """便捷的流式文本生成函数"""
    router = SmartLLMRouter()
    
    async for chunk in router.generate_stream(prompt, model=model, **kwargs):
        yield chunk.content
