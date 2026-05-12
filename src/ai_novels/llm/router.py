"""
LLM 路由实现

@file: llm/router.py
@date: 2026-03-12
@author: AI-Novels Team
@version: 1.0
@description: LLM路由管理，支持多种provider、负载均衡、失败降级
"""

import os
import random
import time
from typing import Any, Dict, List, Optional
from enum import Enum
from abc import ABC

from .base import BaseLLMClient, EmbeddingClient
from .adapters.ollama import OllamaClient
from .adapters.qwen import QwenClient
from .adapters.openai import OpenAIClient
from .adapters.gemini import GeminiClient
from .adapters.minimax import MinimaxClient

from ai_novels.utils import log_error, get_logger


class Provider(Enum):
    """LLM提供商枚举"""
    OLLAMA = "ollama"
    QWEN = "qwen"
    OPENAI = "openai"
    GEMINI = "gemini"
    MINIMAX = "minimax"
    DEEPSEEK = "deepseek"


class LoadBalanceStrategy(Enum):
    """负载均衡策略"""
    ROUND_ROBIN = "round_robin"
    RANDOM = "random"
    LEAST_CONNECTIONS = "least_connections"


class LLMLoadBalancer:
    """
    LLM负载均衡器

    实现多种负载均衡策略
    """

    def __init__(self, strategy: LoadBalanceStrategy = LoadBalanceStrategy.ROUND_ROBIN):
        """
        初始化负载均衡器

        Args:
            strategy: 负载均衡策略
        """
        self._strategy = strategy
        self._clients: Dict[str, BaseLLMClient] = {}
        self._healthy_clients: List[str] = []
        self._round_robin_index = 0
        self._connections: Dict[str, int] = {}

    def add_client(self, name: str, client: BaseLLMClient) -> bool:
        """
        添加客户端

        Args:
            name: 客户端名称
            client: LLM客户端实例

        Returns:
            是否成功
        """
        try:
            self._clients[name] = client
            self._connections[name] = 0
            return True
        except Exception:
            return False

    def remove_client(self, name: str) -> bool:
        """
        移除客户端

        Args:
            name: 客户端名称

        Returns:
            是否成功
        """
        try:
            if name in self._clients:
                del self._clients[name]
            if name in self._connections:
                del self._connections[name]
            return True
        except Exception:
            return False

    def update_healthy_clients(self) -> List[str]:
        """
        更新健康客户端列表

        Returns:
            健康客户端名称列表
        """
        self._healthy_clients = []
        for name, client in self._clients.items():
            health = client.health_check()
            if health.get("status") == "healthy":
                self._healthy_clients.append(name)
        return self._healthy_clients

    def get_client(self, prefer: str = None) -> Optional[BaseLLMClient]:
        """
        获取客户端（根据负载均衡策略）

        Args:
            prefer: 优先选择的客户端名称

        Returns:
            LLM客户端实例
        """
        # 更新健康列表
        self.update_healthy_clients()

        if not self._healthy_clients:
            return None

        # 如果有首选且健康，返回首选
        if prefer and prefer in self._healthy_clients:
            return self._clients[prefer]

        # 根据策略选择
        if self._strategy == LoadBalanceStrategy.RANDOM:
            name = random.choice(self._healthy_clients)
            return self._clients.get(name)

        elif self._strategy == LoadBalanceStrategy.ROUND_ROBIN:
            name = self._healthy_clients[self._round_robin_index % len(self._healthy_clients)]
            self._round_robin_index = (self._round_robin_index + 1) % len(self._healthy_clients)
            return self._clients.get(name)

        elif self._strategy == LoadBalanceStrategy.LEAST_CONNECTIONS:
            if not self._connections:
                name = random.choice(self._healthy_clients)
                return self._clients.get(name)
            name = min(self._connections, key=self._connections.get)
            return self._clients.get(name)

        return None

    def get_client_by_name(self, name: str) -> Optional[BaseLLMClient]:
        """
        根据名称获取客户端

        Args:
            name: 客户端名称

        Returns:
            LLM客户端实例
        """
        return self._clients.get(name)

    def increment_connection(self, name: str) -> None:
        """增加连接数"""
        if name in self._connections:
            self._connections[name] += 1

    def decrement_connection(self, name: str) -> None:
        """减少连接数"""
        if name in self._connections and self._connections[name] > 0:
            self._connections[name] -= 1


class LLMRouter:
    """
    LLM路由管理器

    统一管理多个LLM提供商，支持：
    - provider匹配
    - 负载均衡
    - 失败降级
    - 健康检查
    """

    # 提供商映射
    PROVIDER_MAP = {
        Provider.OLLAMA: OllamaClient,
        Provider.QWEN: QwenClient,
        Provider.OPENAI: OpenAIClient,
        Provider.GEMINI: GeminiClient,
        Provider.MINIMAX: MinimaxClient,
        Provider.DEEPSEEK: OpenAIClient,  # DeepSeek 使用 OpenAI 兼容 API
    }

    def __init__(
        self,
        config: Dict[str, Any] = None,
        load_balance_strategy: LoadBalanceStrategy = LoadBalanceStrategy.ROUND_ROBIN
    ):
        """
        初始化LLM路由

        Args:
            config: 路由配置
            load_balance_strategy: 负载均衡策略
        """
        self._config = config or {}
        self._load_balancer = LLMLoadBalancer(load_balance_strategy)
        self._default_provider: str = "ollama"
        self._health_check_interval: int = 60  # 秒
        self._last_health_check: float = 0
        self._initialized = False

    def initialize(self) -> bool:
        """
        初始化路由

        Returns:
            是否成功
        """
        try:
            llm_config = self._config.get("llm", {})

            # 设置默认provider
            self._default_provider = llm_config.get("default", "ollama")

            # 已知的非provider配置项，跳过这些键
            SKIP_KEYS = {"default", "provider", "model", "embedding", "performance", "fallback", "version", "description"}

            # 初始化all providers
            for provider_name, provider_config in llm_config.items():
                if provider_name in SKIP_KEYS:
                    continue
                self._init_provider(provider_name, provider_config)

            # 健康检查
            self._update_healthy_providers()

            self._initialized = True
            return True

        except Exception as e:
            log_error(f"Failed to initialize LLMRouter: {e}")
            self._initialized = False
            return False

    def _init_provider(self, name: str, config: Dict[str, Any]) -> bool:
        """
        初始化单个provider

        Args:
            name: provider名称
            config: 配置

        Returns:
            是否成功
        """
        try:
            provider = config.get("provider", "ollama")
            model = config.get("model", "default")

            # 创建客户端配置
            client_config = {
                "provider": provider,
                "model": model,
                "api_key": config.get("api_key"),
                "base_url": config.get("base_url"),
                "temperature": config.get("temperature", 0.7),
                "max_tokens": config.get("max_tokens", 8192),
                "timeout": config.get("timeout", 30)
            }

            # 获取客户端类
            client_class = self.PROVIDER_MAP.get(
                Provider(provider.lower()),
                OllamaClient
            )
            client = client_class(client_config)

            # 添加到负载均衡器
            self._load_balancer.add_client(name, client)
            return True

        except Exception as e:
            log_error(f"Failed to init provider {name}: {e}")
            return False

    def _update_healthy_providers(self) -> List[str]:
        """
        更新健康provider列表

        Returns:
            健康provider列表
        """
        return self._load_balancer.update_healthy_clients()

    def _should_health_check(self) -> bool:
        """
        判断是否需要进行健康检查

        Returns:
            是否需要
        """
        current_time = time.time()
        if current_time - self._last_health_check > self._health_check_interval:
            return True
        return False

    def _health_check_if_needed(self) -> None:
        """
        如需要则执行健康检查
        """
        if self._should_health_check():
            self._update_healthy_providers()
            self._last_health_check = time.time()

    def generate(
        self,
        prompt: str,
        provider: str = None,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> Optional[str]:
        """
        生成文本（支持失败降级）

        Args:
            prompt: 提示词
            provider: provider名称，None则使用默认
            system_prompt: 系统提示
            **kwargs: 其他参数

        Returns:
            生成的文本
        """
        # 健康检查
        self._health_check_if_needed()

        # 获取目标provider列表（优先级：指定provider -> 默认provider -> 所有健康provider）
        target_providers = []

        if provider:
            target_providers.append(provider)

        if self._default_provider and self._default_provider not in target_providers:
            target_providers.append(self._default_provider)

        # 获取所有健康provider作为降级候选
        all_healthy = self._load_balancer.update_healthy_clients()
        for p in all_healthy:
            if p not in target_providers:
                target_providers.append(p)

        # 尝试每个provider
        last_error = None
        for provider_name in target_providers:
            client = self._load_balancer.get_client_by_name(provider_name)
            if client is None:
                continue

            try:
                start_time = time.time()
                self._load_balancer.increment_connection(provider_name)
                result = client.generate(prompt, system_prompt, **kwargs)
                self._load_balancer.decrement_connection(provider_name)
                elapsed_ms = int((time.time() - start_time) * 1000)
                # 记录 LLM 调用日志
                try:
                    get_logger().llm_call(
                        provider=provider_name,
                        model=getattr(client, 'model', 'unknown'),
                        prompt_tokens=len(prompt),
                        completion_tokens=len(result) if result else 0,
                        duration_ms=elapsed_ms,
                    )
                except Exception:
                    pass
                return result
            except Exception as e:
                self._load_balancer.decrement_connection(provider_name)
                last_error = e
                log_error(f"Provider {provider_name} failed: {e}")

        # 所有provider都失败
        if last_error:
            raise last_error
        return None

    def generate_json(
        self,
        prompt: str,
        response_schema: Dict[str, Any],
        provider: str = None,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> Optional[Dict[str, Any]]:
        """
        生成JSON格式文本

        Args:
            prompt: 提示词
            response_schema: 响应JSON Schema
            provider: provider名称
            system_prompt: 系统提示
            **kwargs: 其他参数

        Returns:
            JSON格式的响应
        """
        # 健康检查
        self._health_check_if_needed()

        # 获取client
        client = self._load_balancer.get_client(provider)
        if client is None:
            return None

        try:
            start_time = time.time()
            self._load_balancer.increment_connection(provider or "")
            # 尝试调用generate_json，如果客户端不支持则使用默认实现
            result = getattr(client, 'generate_json', None)
            if result is not None:
                result = result(prompt, response_schema, system_prompt, **kwargs)
            else:
                # 使用默认的generate_json实现（解析generate的输出）
                import json
                full_prompt = f"请生成符合以下Schema的JSON：\n{json.dumps(response_schema, ensure_ascii=False)}\n\n{prompt}"
                text_result = client.generate(full_prompt, system_prompt, **kwargs)
                # 尝试从文本中提取JSON
                clean_result = text_result
                if "```json" in text_result:
                    clean_result = text_result.split("```json")[1].split("```")[0].strip()
                result = json.loads(clean_result)
            self._load_balancer.decrement_connection(provider or "")
            elapsed_ms = int((time.time() - start_time) * 1000)
            # 记录 LLM 调用日志
            try:
                get_logger().llm_call(
                    provider=provider or self._default_provider,
                    model=getattr(client, 'model', 'unknown'),
                    prompt_tokens=len(prompt),
                    completion_tokens=len(str(result)) if result else 0,
                    duration_ms=elapsed_ms,
                )
            except Exception:
                pass
            return result
        except Exception as e:
            self._load_balancer.decrement_connection(provider or "")
            log_error(f"Generate JSON error: {e}")
            return None

    def embed(self, text: str, provider: str = None) -> Optional[List[float]]:
        """
        生成文本嵌入

        Args:
            text: 输入文本
            provider: provider名称

        Returns:
            嵌入向量
        """
        client = self._load_balancer.get_client(provider)
        if client is None:
            return None

        if isinstance(client, EmbeddingClient):
            return client.embed(text)
        return None

    def health_check(self) -> Dict[str, Any]:
        """
        健康检查

        Returns:
            健康检查结果
        """
        self._update_healthy_providers()

        providers_status = {}
        for name, client in self._load_balancer._clients.items():
            health = client.health_check()
            providers_status[name] = {
                "status": health.get("status"),
                "latency_ms": health.get("latency_ms"),
                "model": health.get("model")
            }

        return {
            "default_provider": self._default_provider,
            "healthy_providers": self._load_balancer._healthy_providers,
            "total_providers": len(self._load_balancer._clients),
            "providers_status": providers_status
        }

    def reload(self) -> bool:
        """
        重新加载配置

        Returns:
            是否成功
        """
        self._load_balancer._clients.clear()
        return self.initialize()

    def is_initialized(self) -> bool:
        """
        检查是否已初始化

        Returns:
            是否已初始化
        """
        return self._initialized

    def get_client(self, provider: str = None) -> Optional[BaseLLMClient]:
        """
        获取客户端

        Args:
            provider: provider名称

        Returns:
            客户端实例
        """
        return self._load_balancer.get_client(provider)


# 全局路由实例
_global_router: Optional[LLMRouter] = None


def get_llm_router(config: Dict[str, Any] = None, force_init: bool = False) -> LLMRouter:
    """
    获取全局LLM路由实例

    Args:
        config: 路由配置
        force_init: 是否强制重新初始化（忽略已有实例）

    Returns:
        LLMRouter实例
    """
    global _global_router
    if _global_router is None or force_init:
        _global_router = LLMRouter(config)
        _global_router.initialize()
    return _global_router


def generate_text(
    prompt: str,
    provider: str = None,
    system_prompt: Optional[str] = None,
    **kwargs
) -> Optional[str]:
    """
    全局文本生成函数

    Args:
        prompt: 提示词
        provider: provider名称
        system_prompt: 系统提示
        **kwargs: 其他参数

    Returns:
        生成的文本
    """
    router = get_llm_router()
    return router.generate(prompt, provider, system_prompt, **kwargs)


def generate_json_text(
    prompt: str,
    response_schema: Dict[str, Any],
    provider: str = None,
    system_prompt: Optional[str] = None,
    **kwargs
) -> Optional[Dict[str, Any]]:
    """
    全局JSON文本生成函数

    Args:
        prompt: 提示词
        response_schema: 响应JSON Schema
        provider: provider名称
        system_prompt: 系统提示
        **kwargs: 其他参数

    Returns:
        JSON格式的响应
    """
    router = get_llm_router()
    return router.generate_json(prompt, response_schema, provider, system_prompt, **kwargs)
