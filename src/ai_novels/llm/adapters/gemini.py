"""
Gemini 适配器

@file: llm/adapters/gemini.py
@date: 2026-03-12
@author: AI-Novels Team
@version: 1.0
@description: Gemini API客户端适配器，支持gemini-pro
"""

import os
from typing import Any, Dict, List, Optional

from ..base import BaseLLMClient, EmbeddingClient


class GeminiClient(BaseLLMClient, EmbeddingClient):
    """
    Gemini LLM客户端适配器

    支持的模型:
    - gemini-pro
    - gemini-pro-vision
    - gemini-1.5-flash
    - gemini-1.5-pro
    """

    def __init__(self, config: Dict[str, Any]):
        """
        初始化Gemini客户端

        Args:
            config: Gemini配置
                - api_key: Google API密钥
                - model: 模型名称 (默认: gemini-pro)
                - base_url: API地址 (默认: 使用Google官方endpoints)
                - timeout: 请求超时秒数 (默认: 30)
        """
        super().__init__(config)
        try:
            import google.generativeai as genai
            self._genai = genai
            genai.configure(
                api_key=config.get("api_key") or os.environ.get("GOOGLE_API_KEY")
            )
            self._client = genai.GenerativeModel(self._model)
        except ImportError:
            raise ImportError("Please install google-generativeai: pip install google-generativeai")

        self._model = config.get("model", "gemini-pro")
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
            **kwargs: 其他参数

        Returns:
            生成的文本
        """
        if system_prompt:
            self._client.start_chat(system_instruction=system_prompt)

        response = self._client.generate_content(
            prompt,
            generation_config={
                "temperature": kwargs.get("temperature", self._temperature),
                "max_output_tokens": kwargs.get("max_tokens", self._max_tokens)
            }
        )
        return response.text

    def generate_json(
        self,
        prompt: str,
        response_schema: Dict[str, Any],
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        生成JSON格式文本（使用Gemini的JSON模式）

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
        response = self._genai.embed_content(
            model="models/text-embedding-004",
            content=text
        )
        return response["embedding"]

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        批量生成文本嵌入

        Args:
            texts: 输入文本列表

        Returns:
            嵌入向量列表
        """
        embeddings = []
        for text in texts:
            response = self._genai.embed_content(
                model="models/text-embedding-004",
                content=text
            )
            embeddings.append(response["embedding"])
        return embeddings

    def health_check(self) -> Dict[str, Any]:
        """
        健康检查

        Returns:
            健康检查结果
        """
        import time
        start = time.time()

        try:
            self._client.generate_content("hi")
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
        # Gemini客户端不需要显式关闭
        pass
