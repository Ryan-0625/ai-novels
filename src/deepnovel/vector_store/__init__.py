"""
向量存储模块初始化

@file: vector_store/__init__.py
@date: 2026-04-29
@description: 导出向量存储模块的公共接口
"""

from .base import BaseVectorStore

# 增强版抽象层（未来迁移到 Qdrant 的基础）
from .enhanced_base import SearchResult, VectorDocument, VectorStore
from .memory_store import InMemoryVectorStore

try:
    from .chroma_store import ChromaVectorStore
except ImportError:
    ChromaVectorStore = None  # type: ignore

__all__ = [
    "BaseVectorStore",
    "ChromaVectorStore",
    "VectorStore",
    "VectorDocument",
    "SearchResult",
    "InMemoryVectorStore",
]
