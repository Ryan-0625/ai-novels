"""
LLM Router实现

@file: core/llm_router.py
@date: 2026-03-12
@author: AI-Novels Team
@version: 1.0
@description: LLM路由与管理，支持多种LLM提供商
"""

import os
import time
import importlib
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from enum import Enum

from ..config.manager import ConfigManager, settings
from ..llm.cache import get_llm_cache
from ai_novels.utils import log_error, log_info


class LLMProvider(Enum):
    """LLM提供商枚举"""
    OPENAI = "openai"
    OLLAMA = "ollama"
    QWEN = "qwen"
    GEMINI = "gemini"
    MINIMAX = "minimax"
    LOCAL = "local"


@dataclass
class LLMConfig:
    """LLM配置"""
    provider: str
    model: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 8192
    timeout: int = 120  # 增加超时时间到120秒
    retry_times: int = 3
    stream: bool = False


class BaseLLMClient(ABC):
    """LLM客户端基类"""

    def __init__(self, config: LLMConfig):
        self.config = config
        self._name = config.provider

    @property
    def name(self) -> str:
        """获取提供商名称"""
        return self._name

    @abstractmethod
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> str:
        """生成文本"""
        pass

    @abstractmethod
    def generate_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> Callable:
        """流式生成文本"""
        pass

    @abstractmethod
    def embed(self, text: str) -> List[float]:
        """生成文本嵌入"""
        pass

    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        pass

    def generate_json(
        self,
        prompt: str,
        response_schema: Dict[str, Any],
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> Optional[Dict[str, Any]]:
        """
        生成JSON格式文本（默认实现，使用generate后解析JSON）

        Args:
            prompt: 提示词
            response_schema: JSON Schema定义
            system_prompt: 系统提示
            **kwargs: 其他参数

        Returns:
            JSON格式的响应（解析后的字典）
        """
        # 构建带JSON schema的提示
        import json
        schema_str = json.dumps(response_schema, indent=2, ensure_ascii=False)
        json_prompt = f"""请根据以下要求生成JSON格式的响应：

要求：
1. 输出必须是有效的JSON格式
2. JSON结构必须符合下面的Schema：
{schema_str}
3. 直接输出JSON，不要添加任何其他文本

用户请求：
{prompt}

JSON响应："""

        try:
            result = self.generate(json_prompt, system_prompt, **kwargs)
            # 尝试解析JSON
            # 提取JSON部分（可能被包裹在```json ... ```中）
            clean_result = result
            if "```json" in result:
                clean_result = result.split("```json")[1].split("```")[0].strip()
            elif "```" in result:
                clean_result = result.split("```")[1].split("```")[0].strip()

            return json.loads(clean_result)
        except Exception as e:
            self._logger and self._logger.llm_error("Failed to generate JSON", error=str(e))
            return None


class OpenAIClient(BaseLLMClient):
    """OpenAI客户端"""

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        try:
            from openai import OpenAI
            self._client = OpenAI(
                api_key=config.api_key or os.environ.get("OPENAI_API_KEY"),
                base_url=config.base_url,
                timeout=config.timeout
            )
        except ImportError:
            raise ImportError("Please install openai: pip install openai")

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = self._client.chat.completions.create(
            model=self.config.model,
            messages=messages,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
            **kwargs
        )
        return response.choices[0].message.content

    def generate_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> Callable:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        def stream_generator():
            response = self._client.chat.completions.create(
                model=self.config.model,
                messages=messages,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
                stream=True,
                **kwargs
            )
            for chunk in response:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        return stream_generator

    def embed(self, text: str) -> List[float]:
        response = self._client.embeddings.create(
            model=self.config.model.replace("chat", "embedding"),
            input=text
        )
        return response.data[0].embedding

    def health_check(self) -> Dict[str, Any]:
        try:
            start = time.time()
            self._client.chat.completions.create(
                model=self.config.model,
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=1
            )
            return {
                "status": "healthy",
                "latency_ms": int((time.time() - start) * 1000)
            }
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}


class OllamaClient(BaseLLMClient):
    """Ollama客户端"""

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        try:
            from ollama import Client
            self._client = Client(
                host=config.base_url or "http://localhost:11434",
                timeout=config.timeout
            )
        except ImportError:
            raise ImportError("Please install ollama: pip install ollama")

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> str:
        # Qwen2.5模型对system prompt不敏感，只使用user prompt
        # 将system prompt合并到user prompt中
        if system_prompt:
            # 合并system prompt和user prompt
            combined_prompt = f"SYSTEM INSTRUCTION:\n{system_prompt}\n\nUSER REQUEST:\n{prompt}"
        else:
            combined_prompt = prompt

        # keep_alive=1800 让模型在内存中保持30分钟，避免后续Agent冷加载
        response = self._client.chat(
            model=self.config.model,
            messages=[
                {
                    "role": "user",
                    "content": combined_prompt
                }
            ],
            options={
                "temperature": self.config.temperature,
                "num_predict": self.config.max_tokens
            },
            keep_alive=1800,
            **kwargs
        )
        return response["message"]["content"]

    def generate_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> Callable:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        def stream_generator():
            response = self._client.chat(
                model=self.config.model,
                messages=messages,
                options={
                    "temperature": self.config.temperature,
                    "num_predict": self.config.max_tokens
                },
                stream=True,
                keep_alive=1800,
                **kwargs
            )
            for chunk in response:
                if chunk["message"]["content"]:
                    yield chunk["message"]["content"]

        return stream_generator

    def embed(self, text: str) -> List[float]:
        response = self._client.embeddings(
            model=self.config.model,
            prompt=text
        )
        return response["embedding"]

    def health_check(self) -> Dict[str, Any]:
        try:
            start = time.time()
            self._client.generate(model=self.config.model, prompt="hi")
            return {
                "status": "healthy",
                "latency_ms": int((time.time() - start) * 1000)
            }
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}


class QwenClient(BaseLLMClient):
    """通义千问客户端"""

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        try:
            from dashscope import Generation
            self._client = Generation
        except ImportError:
            raise ImportError("Please install dashscope: pip install dashscope")

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = self._client.call(
            model=self.config.model,
            messages=messages,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
            **kwargs
        )
        return response.output.choices[0].message.content

    def generate_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> Callable:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        def stream_generator():
            response = self._client.call(
                model=self.config.model,
                messages=messages,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
                stream=True,
                **kwargs
            )
            for chunk in response:
                if chunk.output.choices:
                    yield chunk.output.choices[0].message.content

        return stream_generator

    def embed(self, text: str) -> List[float]:
        # 通义千问使用文本嵌入模型
        from dashscope import Embeddings
        response = Embeddings.call(
            model="text-embedding-v1",
            input=text
        )
        return response.output.embeddings[0].embedding

    def health_check(self) -> Dict[str, Any]:
        try:
            start = time.time()
            self._client.call(
                model=self.config.model,
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=1
            )
            return {
                "status": "healthy",
                "latency_ms": int((time.time() - start) * 1000)
            }
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}


class GeminiClient(BaseLLMClient):
    """Gemini客户端"""

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        try:
            import google.generativeai as genai
            genai.configure(api_key=config.api_key)
            self._client = genai.GenerativeModel(self.config.model)
        except ImportError:
            raise ImportError("Please install google-generativeai: pip install google-generativeai")

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> str:
        if system_prompt:
            self._client.start_chat(system_instruction=system_prompt)
        response = self._client.generate_content(
            prompt,
            generation_config={
                "temperature": self.config.temperature,
                "max_output_tokens": self.config.max_tokens
            },
            **kwargs
        )
        return response.text

    def generate_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> Callable:
        if system_prompt:
            self._client.start_chat(system_instruction=system_prompt)

        def stream_generator():
            response = self._client.generate_content(
                prompt,
                generation_config={
                    "temperature": self.config.temperature,
                    "max_output_tokens": self.config.max_tokens
                },
                stream=True,
                **kwargs
            )
            for chunk in response:
                yield chunk.text

        return stream_generator

    def embed(self, text: str) -> List[float]:
        import google.generativeai as genai
        response = genai.embed_content(
            model="models/text-embedding-004",
            content=text
        )
        return response["embedding"]

    def health_check(self) -> Dict[str, Any]:
        try:
            start = time.time()
            self._client.generate_content("hi")
            return {
                "status": "healthy",
                "latency_ms": int((time.time() - start) * 1000)
            }
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}


class MinimaxClient(BaseLLMClient):
    """MiniMax客户端"""

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        try:
            from minimax import MinimaxClient
            self._client = MinimaxClient(
                api_key=config.api_key,
                group_id=config.base_url
            )
        except ImportError:
            raise ImportError("Please install minimax: pip install minimax")

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> str:
        response = self._client.chat.completions.create(
            model=self.config.model,
            messages=[
                {"role": "system", "content": system_prompt} if system_prompt else None,
                {"role": "user", "content": prompt}
            ],
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
            **kwargs
        )
        return response.choices[0].message.content

    def generate_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> Callable:
        def stream_generator():
            response = self._client.chat.completions.create(
                model=self.config.model,
                messages=[
                    {"role": "system", "content": system_prompt} if system_prompt else None,
                    {"role": "user", "content": prompt}
                ],
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
                stream=True,
                **kwargs
            )
            for chunk in response:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        return stream_generator

    def embed(self, text: str) -> List[float]:
        response = self._client.embeddings.create(
            model="embo-01",
            input=text
        )
        return response.data[0].embedding

    def health_check(self) -> Dict[str, Any]:
        try:
            start = time.time()
            self._client.chat.completions.create(
                model=self.config.model,
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=1
            )
            return {
                "status": "healthy",
                "latency_ms": int((time.time() - start) * 1000)
            }
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}


class LLMRouter:
    """
    LLM路由管理器

    统一管理多个LLM提供商，支持故障转移和负载均衡
    """

    # 提供商映射
    PROVIDER_MAP = {
        LLMProvider.OPENAI: OpenAIClient,
        LLMProvider.OLLAMA: OllamaClient,
        LLMProvider.QWEN: QwenClient,
        LLMProvider.GEMINI: GeminiClient,
        LLMProvider.MINIMAX: MinimaxClient,
        LLMProvider.LOCAL: OllamaClient
    }

    def __init__(self, config_manager: ConfigManager = None):
        """
        初始化LLM路由

        Args:
            config_manager: 配置管理器
        """
        self._config_manager = config_manager or settings._manager
        self._clients: Dict[str, BaseLLMClient] = {}
        self._default_provider: Optional[str] = None
        self._healthy_providers: List[str] = []
        self._initialized = False
        self._cache = get_llm_cache()

    def initialize(self) -> bool:
        """
        初始化路由

        Returns:
            是否成功
        """
        try:
            config = self._config_manager.to_dict() if self._config_manager else {}
            llm_config = config.get("llm", {})

            # 初始化默认提供商
            self._default_provider = llm_config.get("default", "ollama")

            # 已知的非provider配置项，跳过这些键
            SKIP_KEYS = {"default", "provider", "model", "embedding", "performance", "fallback", "version", "description"}

            # 初始化所有配置的提供商
            for provider_name, provider_config in llm_config.items():
                if provider_name in SKIP_KEYS:
                    continue
                if not isinstance(provider_config, dict):
                    continue
                self._init_provider(provider_name, provider_config)

            # 降级: 如果无任何provider注册，创建默认Ollama客户端
            if not self._clients:
                log_info("No LLM providers configured, creating default Ollama client")
                self._init_provider("ollama", {
                    "provider": "ollama",
                    "model": "qwen2.5-7b",
                    "base_url": "http://localhost:11434",
                    "temperature": 0.7,
                    "max_tokens": 8192,
                    "timeout": 600
                })

            # 从 agents.json 读取 agent_router.default_timeout 并应用
            agents_config = config.get("agents", {})
            agent_router = agents_config.get("agent_router", {})
            default_timeout = agent_router.get("default_timeout", 600)
            self.set_timeout(default_timeout)

            # 健康检查
            self._update_healthy_providers()

            self._initialized = True
            return True

        except Exception as e:
            log_error(f"Failed to initialize LLMRouter: {e}")
            self._initialized = False
            return False

    def set_timeout(self, timeout: int):
        """
        设置所有客户端的超时时间

        Args:
            timeout: 超时时间（秒）
        """
        for name, client in self._clients.items():
            client.config.timeout = timeout
            # 对于Ollama Client，需要重新创建底层_client以应用新的timeout
            if isinstance(client, OllamaClient):
                try:
                    from ollama import Client
                    client._client = Client(
                        host=client.config.base_url or "http://localhost:11434",
                        timeout=timeout
                    )
                    log_info(f"OllamaClient {name} timeout updated to {timeout}s")
                except Exception as e:
                    log_error(f"Failed to update timeout for OllamaClient {name}: {e}")
        log_info(f"LLMRouter timeout set to {timeout}s")

    def _init_provider(self, name: str, config: Dict[str, Any]) -> bool:
        """
        初始化单个提供商

        Args:
            name: 提供商名称
            config: 配置

        Returns:
            是否成功
        """
        try:
            provider = config.get("provider", "ollama")
            model = config.get("model", "default")

            llm_config = LLMConfig(
                provider=provider,
                model=model,
                api_key=config.get("api_key"),
                base_url=config.get("base_url"),
                temperature=config.get("temperature", 0.7),
                max_tokens=config.get("max_tokens", 8192),
                timeout=config.get("timeout", 120)
            )

            client_class = self.PROVIDER_MAP.get(
                LLMProvider(provider),
                OllamaClient
            )
            client = client_class(llm_config)

            self._clients[name] = client
            return True

        except Exception as e:
            log_error(f"Failed to init provider {name}: {e}")
            return False

    def _update_healthy_providers(self):
        """更新健康提供商列表"""
        self._healthy_providers = []
        for name, client in self._clients.items():
            health = client.health_check()
            if health.get("status") == "healthy":
                self._healthy_providers.append(name)

    def get_client(self, provider: str = None) -> Optional[BaseLLMClient]:
        """
        获取客户端

        Args:
            provider: 提供商名称，None则使用默认

        Returns:
            客户端实例
        """
        if provider is None:
            provider = self._default_provider

        if provider in self._clients:
            return self._clients[provider]

        if provider in self._healthy_providers:
            return self._clients.get(provider)

        return None

    def generate(
        self,
        prompt: str,
        provider: str = None,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> Optional[str]:
        """
        生成文本（带缓存）

        Args:
            prompt: 提示词
            provider: 提供商名称
            system_prompt: 系统提示
            **kwargs: 其他参数

        Returns:
            生成的文本
        """
        client = self.get_client(provider)
        if client is None:
            return None

        # 生成缓存键
        cache_key = self._cache.generate_key(
            prompt=prompt,
            provider=provider or self._default_provider,
            model=client.config.model,
            system_prompt=system_prompt,
            temperature=kwargs.get("temperature", client.config.temperature),
            max_tokens=kwargs.get("max_tokens", client.config.max_tokens)
        )

        # 检查缓存
        cached_result = self._cache.get(cache_key)
        if cached_result is not None:
            return cached_result

        try:
            # Filter out temperature and max_tokens
            filtered_kwargs = {k: v for k, v in kwargs.items() if k not in ["temperature", "max_tokens", "timeout"]}
            result = client.generate(prompt, system_prompt, **filtered_kwargs)
            # 设置缓存
            self._cache.set(cache_key, result)
            return result
        except Exception as e:
            log_error(f"Generate error: {e}")
            return None

    def generate_stream(
        self,
        prompt: str,
        provider: str = None,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> Optional[Callable]:
        """
        流式生成文本

        Args:
            prompt: 提示词
            provider: 提供商名称
            system_prompt: 系统提示
            **kwargs: 其他参数

        Returns:
            流生成器
        """
        client = self.get_client(provider)
        if client is None:
            return None

        try:
            return client.generate_stream(prompt, system_prompt, **kwargs)
        except Exception as e:
            log_error(f"Generate stream error: {e}")
            return None

    def embed(self, text: str, provider: str = None) -> Optional[List[float]]:
        """
        生成文本嵌入

        Args:
            text: 文本
            provider: 提供商名称

        Returns:
            嵌入向量
        """
        client = self.get_client(provider)
        if client is None:
            return None

        try:
            return client.embed(text)
        except Exception as e:
            log_error(f"Embed error: {e}")
            return None

    def health_check(self) -> Dict[str, Any]:
        """
        健康检查

        Returns:
            健康检查结果
        """
        self._update_healthy_providers()
        return {
            "default_provider": self._default_provider,
            "healthy_providers": self._healthy_providers,
            "total_providers": len(self._clients)
        }

    def reload(self) -> bool:
        """
        重新加载配置

        Returns:
            是否成功
        """
        self._clients.clear()
        return self.initialize()

    def is_initialized(self) -> bool:
        """
        检查是否已初始化

        Returns:
            是否已初始化
        """
        return self._initialized


# 全局LLM路由实例
_router: Optional[LLMRouter] = None


def get_llm_router(config_manager: ConfigManager = None) -> LLMRouter:
    """
    获取全局LLM路由实例

    Args:
        config_manager: 配置管理器

    Returns:
        LLMRouter实例
    """
    global _router
    if _router is None:
        from ..utils import get_logger
        logger = get_logger()
        _router = LLMRouter(config_manager)
        logger.llm_debug("Initializing LLM Router")
        _router.initialize()
        logger.llm(f"LLM Router initialized with default provider: {_router._default_provider}, providers: {list(_router._clients.keys())}")
    return _router


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
        provider: 提供商名称
        system_prompt: 系统提示
        **kwargs: 其他参数

    Returns:
        生成的文本
    """
    router = get_llm_router()
    return router.generate(prompt, provider, system_prompt, **kwargs)


def embed_text(text: str, provider: str = None) -> Optional[List[float]]:
    """
    全局文本嵌入函数

    Args:
        text: 文本
        provider: 提供商名称

    Returns:
        嵌入向量
    """
    router = get_llm_router()
    return router.embed(text, provider)
