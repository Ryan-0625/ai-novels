"""
增强版向量存储抽象层

支持异步操作、过滤查询、批量处理。
为从 ChromaDB 迁移到 Qdrant 提供统一接口。

@file: vector_store/enhanced_base.py
@date: 2026-04-29
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class VectorDocument:
    """向量文档"""

    id: str
    content: str
    embedding: Optional[List[float]] = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class SearchResult:
    """搜索结果"""

    id: str
    content: str
    score: float
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class VectorStore(ABC):
    """向量存储抽象基类（增强版）

    提供统一的向量操作接口，隐藏底层数据库差异。
    支持 ChromaDB、Qdrant、Milvus 等实现。
    """

    @abstractmethod
    async def connect(self) -> bool:
        """建立连接"""
        pass

    @abstractmethod
    async def disconnect(self) -> bool:
        """断开连接"""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """健康检查"""
        pass

    @abstractmethod
    async def upsert(
        self,
        documents: List[VectorDocument],
        *,
        batch_size: int = 100,
    ) -> int:
        """批量插入或更新文档

        Args:
            documents: 文档列表
            batch_size: 批量大小

        Returns:
            成功处理的文档数
        """
        pass

    @abstractmethod
    async def search(
        self,
        query: str,
        *,
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[SearchResult]:
        """语义搜索

        Args:
            query: 查询文本
            top_k: 返回结果数
            filters: 元数据过滤条件

        Returns:
            搜索结果列表
        """
        pass

    @abstractmethod
    async def delete(
        self,
        ids: List[str],
        *,
        filters: Optional[Dict[str, Any]] = None,
    ) -> int:
        """删除文档

        Args:
            ids: 文档ID列表
            filters: 额外过滤条件

        Returns:
            删除的文档数
        """
        pass

    @abstractmethod
    async def get(self, ids: List[str]) -> List[VectorDocument]:
        """根据ID获取文档

        Args:
            ids: 文档ID列表

        Returns:
            文档列表
        """
        pass

    @abstractmethod
    async def count(self, *, filters: Optional[Dict[str, Any]] = None) -> int:
        """获取文档数量

        Args:
            filters: 过滤条件

        Returns:
            文档数量
        """
        pass

    @abstractmethod
    async def clear(self) -> bool:
        """清空集合"""
        pass
