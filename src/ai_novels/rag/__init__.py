"""
RAG (Retrieval-Augmented Generation) 模块

提供文档分块、向量索引、语义检索的完整流水线。

@file: rag/__init__.py
@date: 2026-04-29
"""

from .chunker import Chunk, ChunkStrategy, TextChunker
from .indexer import DocumentIndexer
from .retriever import RetrievedChunk, SemanticRetriever
from .rag_engine import RAGConfig, RAGResult, RAGEngine

__all__ = [
    # 分块
    "Chunk",
    "ChunkStrategy",
    "TextChunker",
    # 索引
    "DocumentIndexer",
    # 检索
    "RetrievedChunk",
    "SemanticRetriever",
    # 引擎
    "RAGConfig",
    "RAGResult",
    "RAGEngine",
]
