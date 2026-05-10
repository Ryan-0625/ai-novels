"""
chromadb 向量存储实现

@file: vector_store/chroma_store.py
@date: 2026-03-16
@version: 1.0
@description: chromadb 向量数据库客户端实现
"""

import time
import chromadb
from typing import List, Dict, Any, Optional

from .base import BaseVectorStore
from ..utils import log_info, log_error


class ChromaVectorStore(BaseVectorStore):
    """
    chromadb 向量存储实现

    使用 chromadb 进行向量相似度搜索和存储
    """

    def __init__(
        self,
        collection_name: str = "default",
        embedding_model: str = "all-MiniLM-L6-v2",
        persist_path: str = "./chroma_db"
    ):
        """
        初始化 ChromaVectorStore

        Args:
            collection_name: 集合名称
            embedding_model: 嵌入模型名称
            persist_path: 持久化路径
        """
        self.collection_name = collection_name
        self.embedding_model = embedding_model
        self.persist_path = persist_path
        self._client: Optional[chromadb.Client] = None
        self._collection = None
        self._connected = False

    def connect(self) -> bool:
        """建立数据库连接"""
        try:
            self._client = chromadb.Client(
                persist_directory=self.persist_path
            )
            self._collection = self._client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"}
            )
            self._connected = True
            log_info(f"Connected to chromadb collection: {self.collection_name}")
            return True
        except Exception as e:
            log_error(f"Failed to connect to chromadb: {e}")
            return False

    def disconnect(self) -> bool:
        """断开数据库连接"""
        try:
            if self._client:
                self._client.persist()
                self._client = None
                self._collection = None
                self._connected = False
                log_info("Disconnected from chromadb")
            return True
        except Exception as e:
            log_error(f"Failed to disconnect from chromadb: {e}")
            return False

    def is_connected(self) -> bool:
        """检查连接状态"""
        return self._connected and self._client is not None

    def add(self, docs: List[str], metadatas: List[Dict[str, Any]], ids: List[str]) -> None:
        """
        添加文档到向量库

        Args:
            docs: 文档内容列表
            metadatas: 元数据列表
            ids: ID列表
        """
        if not self._collection:
            raise RuntimeError("Collection not initialized. Call connect() first.")

        # 生成嵌入（简化实现）
        embeddings = [self._generate_embedding(doc) for doc in docs]

        self._collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=docs,
            metadatas=metadatas
        )

    def query(self, query_texts: List[str], n_results: int = 5) -> Dict[str, Any]:
        """
        语义搜索

        Args:
            query_texts: 查询文本列表
            n_results: 返回数量

        Returns:
            搜索结果
        """
        if not self._collection:
            raise RuntimeError("Collection not initialized. Call connect() first.")

        query_embeddings = [self._generate_embedding(text) for text in query_texts]

        results = self._collection.query(
            query_embeddings=query_embeddings,
            n_results=n_results
        )

        return results

    def delete(self, ids: List[str]) -> None:
        """
        删除文档

        Args:
            ids: 要删除的ID列表
        """
        if not self._collection:
            raise RuntimeError("Collection not initialized. Call connect() first.")

        self._collection.delete(ids=ids)

    def update(self, ids: List[str], metadatas: List[Dict[str, Any]]) -> None:
        """
        更新元数据

        Args:
            ids: ID列表
            metadatas: 新的元数据列表
        """
        if not self._collection:
            raise RuntimeError("Collection not initialized. Call connect() first.")

        self._collection.update(ids=ids, metadatas=metadatas)

    def get(self, ids: List[str]) -> Dict[str, Any]:
        """
        获取文档

        Args:
            ids: ID列表

        Returns:
            文档数据
        """
        if not self._collection:
            raise RuntimeError("Collection not initialized. Call connect() first.")

        return self._collection.get(ids=ids)

    def _generate_embedding(self, text: str) -> List[float]:
        """
        生成文本嵌入（简化实现）

        Args:
            text: 输入文本

        Returns:
            嵌入向量
        """
        import hashlib
        h = hashlib.md5(text.encode()).digest()
        return [float(b % 100) / 100.0 for b in h[:384]]

    def health_check(self) -> Dict[str, Any]:
        """
        健康检查

        Returns:
            健康检查结果
        """
        if not self._connected:
            return {
                "status": "unhealthy",
                "error": "Not connected"
            }

        try:
            # 测试查询
            test_result = self._collection.count()
            return {
                "status": "healthy",
                "collection_name": self.collection_name,
                "document_count": test_result,
                "latency_ms": 0
            }
        except Exception as e:
            return {
                "status": "degraded",
                "error": str(e)
            }

    def __enter__(self):
        """上下文管理器入口"""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.disconnect()
