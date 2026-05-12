"""
LLM 基类定义

@file: llm/base.py
@date: 2026-03-12
@author: AI-Novels Team
@version: 1.0
@description: 定义LLM客户端的统一接口
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Callable


class BaseLLMClient(ABC):
    """
    LLM客户端基类

    所有LLM适配器都应继承此类并实现抽象方法
    """

    def __init__(self, config: Dict[str, Any]):
        """
        初始化LLM客户端

        Args:
            config: LLM配置字典
        """
        self.config = config
        self._provider = config.get("provider", "unknown")
        self._model = config.get("model", "unknown")

    @property
    def provider(self) -> str:
        """获取提供商名称"""
        return self._provider

    @property
    def model(self) -> str:
        """获取模型名称"""
        return self._model

    @abstractmethod
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
        pass

    @abstractmethod
    def generate_json(
        self,
        prompt: str,
        response_schema: Dict[str, Any],
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        生成JSON格式文本

        Args:
            prompt: 用户提示
            response_schema: 响应JSON Schema定义
            system_prompt: 系统提示
            **kwargs: 其他参数

        Returns:
            JSON格式的响应
        """
        pass

    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        """
        健康检查

        Returns:
            健康检查结果
        """
        pass

    @abstractmethod
    def close(self) -> None:
        """
        关闭客户端连接
        """
        pass


class EmbeddingClient(ABC):
    """
    文本嵌入客户端基类
    """

    @abstractmethod
    def embed(self, text: str) -> List[float]:
        """
        生成文本嵌入

        Args:
            text: 输入文本

        Returns:
            嵌入向量
        """
        pass

    @abstractmethod
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        批量生成文本嵌入

        Args:
            texts: 输入文本列表

        Returns:
            嵌入向量列表
        """
        pass
