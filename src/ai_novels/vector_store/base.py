"""
向量存储基类定义

@file: vector_store/base.py
@date: 2026-03-16
@version: 1.0
@description: 定义向量存储的统一接口
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional


class BaseVectorStore(ABC):
    """
    向量存储基类
    """

    @abstractmethod
    def connect(self) -> bool:
        """建立连接"""
        pass

    @abstractmethod
    def disconnect(self) -> bool:
        """断开连接"""
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """检查连接状态"""
        pass

    @abstractmethod
    def add(self, docs: List[str], metadatas: List[Dict[str, Any]], ids: List[str]) -> None:
        """
        添加文档

        Args:
            docs: 文档内容列表
            metadatas: 元数据列表
            ids: ID列表
        """
        pass

    @abstractmethod
    def query(self, query_texts: List[str], n_results: int = 5) -> Dict[str, Any]:
        """
        语义搜索

        Args:
            query_texts: 查询文本列表
            n_results: 返回数量

        Returns:
            搜索结果
        """
        pass

    @abstractmethod
    def delete(self, ids: List[str]) -> None:
        """
        删除文档

        Args:
            ids: 要删除的ID列表
        """
        pass

    @abstractmethod
    def update(self, ids: List[str], metadatas: List[Dict[str, Any]]) -> None:
        """
        更新元数据

        Args:
            ids: ID列表
            metadatas: 新的元数据列表
        """
        pass

    @abstractmethod
    def get(self, ids: List[str]) -> Dict[str, Any]:
        """
        获取文档

        Args:
            ids: ID列表

        Returns:
            文档数据
        """
        pass
