"""
OpenAI 适配器

@file: llm/adapters/openai.py
@date: 2026-03-12
@author: AI-Novels Team
@version: 1.0
@description: OpenAI API客户端适配器，支持gpt-4o/gpt-4-turbo
"""

import os
from typing import Any, Dict, List, Optional

from ..base import BaseLLMClient, EmbeddingClient


class OpenAIClient(BaseLLMClient, EmbeddingClient):
    """
    OpenAI LLM客户端适配器

    支持的模型:
    - gpt-4o
    - gpt-4-turbo
    - gpt-4
    - gpt-3.5-turbo
    """

    def __init__(self, config: Dict[str, Any]):
        """
        初始化OpenAI客户端

        Args:
            config: OpenAI配置
                - api_key: OpenAI API密钥
                - model: 模型名称 (默认: gpt-4o)
                - base_url: API地址 (默认: https://api.openai.com/v1)
                - timeout: 请求超时秒数 (默认: 30)
        """
        super().__init__(config)
        try:
            from openai import OpenAI
            self._client = OpenAI(
                api_key=config.get("api_key") or os.environ.get("OPENAI_API_KEY"),
                base_url=config.get("base_url", "https://api.openai.com/v1"),
                timeout=config.get("timeout", 30)
            )
        except ImportError:
            raise ImportError("Please install openai: pip install openai")

        self._model = config.get("model", "gpt-4o")
        self._temperature = config.get("temperature", 0.7)
        self._max_tokens = config.get("max_tokens", 8192)

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        生成文本

        Args:
            prompt: 用户提示
            system_prompt: 系统提示
            **kwargs: 其他参数 (temperature, max_tokens等)

        Returns:
            生成的文本
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=kwargs.get("temperature", self._temperature),
            max_tokens=kwargs.get("max_tokens", self._max_tokens)
        )
        return response.choices[0].message.content

    def generate_json(
        self,
        prompt: str,
        response_schema: Dict[str, Any],
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        生成JSON格式文本（使用OpenAI的函数调用或response_format）

        Args:
            prompt: 用户提示
            response_schema: 响应JSON Schema定义
            system_prompt: 系统提示
            **kwargs: 其他参数

        Returns:
            JSON格式的响应
        """
        import json

        schema_str = json.dumps(response_schema, indent=2)
        json_prompt = f"""你应该始终以JSON格式响应，并且必须符合以下JSON Schema:

{schema_str}

请仔细阅读Schema定义，确保你的响应：
1. 是有效的JSON格式
2. 包含Schema中定义的所有必需字段
3. 字段类型与Schema定义一致

用户提示:
{prompt}

如果你理解了，请以符合Schema的JSON格式响应。"""

        content = self.generate(json_prompt, system_prompt, **kwargs)

        # 尝试解析JSON
        try:
            # 查找JSON对象
            start = content.find('{')
            end = content.rfind('}') + 1
            if start != -1 and end > start:
                json_str = content[start:end]
                return json.loads(json_str)
            return json.loads(content)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse JSON response: {e}\nRaw response: {content}")

    def embed(self, text: str) -> List[float]:
        """
        生成文本嵌入

        Args:
            text: 输入文本

        Returns:
            嵌入向量
        """
        response = self._client.embeddings.create(
            model=self._get_embedding_model(),
            input=text
        )
        return response.data[0].embedding

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        批量生成文本嵌入

        Args:
            texts: 输入文本列表

        Returns:
            嵌入向量列表
        """
        response = self._client.embeddings.create(
            model=self._get_embedding_model(),
            input=texts
        )
        return [item.embedding for item in response.data]

    def _get_embedding_model(self) -> str:
        """
        获取嵌入模型名称

        Returns:
            嵌入模型名称
        """
        # 根据主模型推断嵌入模型
        if "gpt-4o" in self._model:
            return "text-embedding-3-large"
        elif "gpt-4" in self._model:
            return "text-embedding-3-large"
        elif "gpt-3.5" in self._model:
            return "text-embedding-ada-002"
        else:
            return "text-embedding-ada-002"

    def health_check(self) -> Dict[str, Any]:
        """
        健康检查

        Returns:
            健康检查结果
        """
        import time
        start = time.time()

        try:
            self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=1
            )

            return {
                "status": "healthy",
                "latency_ms": int((time.time() - start) * 1000),
                "provider": self._provider,
                "model": self._model
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "latency_ms": 0,
                "error": str(e)
            }

    def close(self) -> None:
        """
        关闭客户端连接
        """
        # OpenAI客户端不需要显式关闭
        pass
