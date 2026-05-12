"""
ChromaDB客户端实现

@file: database/chromadb_client.py
@date: 2026-03-12
@author: AI-Novels Team
@version: 1.0
@description: ChromaDB向量数据库客户端实现 # updated，支持向量搜索和语义检索
"""

import chromadb
from chromadb import Client as Clients, Settings
from chromadb.api.types import Documents, EmbeddingFunction, Embeddings
from typing import Any, Dict, List, Optional, Callable
from contextlib import contextmanager

from ..config.manager import settings
from .base import DatabaseBase, VectorInterface

# 导入内置嵌入函数
try:
    from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

# 尝试导入 Ollama
try:
    import ollama
    HAS_OLLAMA = True
except ImportError:
    HAS_OLLAMA = False


class ChromaDBClient(DatabaseBase, VectorInterface):
    """
    ChromaDB向量数据库客户端实现 # updated

    特性:
    - 向量索引和搜索
    - 元数据过滤
    - 集合管理
    - 持久化存储
    """

    def __init__(
        self,
        host: str = None,
        port: int = None,
        path: str = None,
        collection_name: str = None,
        embed_function: str = None,
        openai_api_key: str = None,
        openai_model: str = None,
        config: Dict[str, Any] = None
    ):
        """
        初始化ChromaDB客户端

        Args:
            host: ChromaDB服务器地址
            port: ChromaDB服务器端口
            path: 本地持久化路径（当使用本地模式时）
            collection_name: 默认集合名称
            embed_function: 嵌入函数类型 ('default', 'openai')
            openai_api_key: OpenAI API密钥（当使用openai嵌入时）
            openai_model: OpenAI嵌入模型
            config: 数据库配置字典，优先级最高
        """
        # 优先使用传入的配置字典
        if config:
            self._host = config.get("host", "localhost")
            self._port = config.get("port", 8000)
            self._path = config.get("persist_dir", "./chroma_db")
            # 使用collection_prefix作为前缀，但确保名称符合ChromaDB规则
            prefix = config.get("collection_prefix", "ai_novels")
            self._collection_name = collection_name or prefix.rstrip("_")
            self._embed_function = config.get("embedding_function", "default")
            self._openai_api_key = config.get("openai_api_key")
            self._openai_model = config.get("openai_model", "text-embedding-ada-002")
        else:
            # 从全局配置管理器读取
            db_config = settings.get_database("chromadb")
            self._host = host or db_config.get("host", "localhost")
            self._port = port or db_config.get("port", 8000)
            self._path = path or db_config.get("persist_dir", "./chroma_db")
            # 使用collection_prefix作为前缀，但确保名称符合ChromaDB规则
            prefix = db_config.get("collection_prefix", "ai_novels")
            # 移除可能导致问题的下划线结尾
            self._collection_name = collection_name or prefix.rstrip("_")
            self._embed_function = embed_function or db_config.get("embedding_function", "default")
            self._openai_api_key = openai_api_key or db_config.get("openai_api_key")
            self._openai_model = openai_model or db_config.get("openai_model", "text-embedding-ada-002")

        self._client: Optional[Clients] = None
        self._collection = None
        self._embedder = None
        self._is_connected = False

        # 初始化嵌入函数
        self._init_embedding_function()

    def _init_embedding_function(self):
        """
        初始化嵌入函数
        """
        if self._embed_function == "openai":
            if not HAS_OPENAI:
                raise ValueError("OpenAIEmbeddingFunction not available. Please install chromadb with openai extra.")
            if not self._openai_api_key:
                raise ValueError("OpenAI API key is required for openai embed function")
            self._embedder = OpenAIEmbeddingFunction(
                api_key=self._openai_api_key,
                model_name=self._openai_model
            )
        elif self._embed_function == "ollama" or (self._embed_function == "default" and HAS_OLLAMA):
            # 使用 Ollama 作为后端嵌入函数
            class OllamaChromaEmbeddingFunction(EmbeddingFunction[Documents]):
                def __init__(self, model: str = "qwen2.5", base_url: str = "http://localhost:11434"):
                    import ollama
                    self._client = ollama.Client(host=base_url)
                    self._model = model

                def __call__(self, input: Documents) -> Embeddings:
                    return [
                        self._client.embeddings(model=self._model, prompt=doc)["embedding"]
                        for doc in input
                    ]

                def name(self) -> str:
                    return f"ollama_{self._model}"

            import os
            model = os.environ.get("OLLAMA_EMBEDDING_MODEL", "qwen2.5")
            self._embedder = OllamaChromaEmbeddingFunction(model=model)
        else:
            raise ValueError(
                f"No usable embedding backend. "
                f"Set embed_function='openai' with OPENAI_API_KEY, "
                f"or install ollama (pip install ollama) for local embeddings. "
                f"Got: {self._embed_function}, HAS_OLLAMA={HAS_OLLAMA}, HAS_OPENAI={HAS_OPENAI}"
            )

    def connect(self) -> bool:
        """
        建立数据库连接

        Returns:
            bool: 连接成功返回True，否则返回False
        """
        try:
            from chromadb.config import Settings

            # 如果配置了host和port，使用远程模式；否则使用本地持久化模式
            if self._host and self._port:
                # 远程模式
                settings = Settings(
                    chroma_server_host=self._host,
                    chroma_server_http_port=self._port,
                    chroma_server_ssl_enabled=False
                )
                self._client = Clients(settings)
            else:
                # 本地持久化模式
                settings = Settings(
                    is_persistent=True,
                    persist_directory=self._path
                )
                self._client = Clients(settings)

            # 获取或创建集合
            self._collection = self._client.get_or_create_collection(
                name=self._collection_name,
                embedding_function=self._embedder
            )

            self._is_connected = True
            return True

        except Exception as e:
            self._is_connected = False
            return False

    def disconnect(self) -> bool:
        """
        断开数据库连接

        Returns:
            bool: 断开成功返回True，否则返回False
        """
        try:
            if self._client:
                self._client.reset()
            self._is_connected = False
            return True
        except Exception:
            self._is_connected = False
            return False

    def is_connected(self) -> bool:
        """
        检查数据库是否已连接

        Returns:
            bool: 已连接返回True，否则返回False
        """
        if not self._client:
            return False
        # 首先检查内部状态
        if self._is_connected:
            return True
        # 尝试实际连接测试
        try:
            collections = self._client.list_collections()
            self._is_connected = True
            return True
        except Exception:
            self._is_connected = False
            return False

    def health_check(self) -> dict:
        """
        数据库健康检查

        Returns:
            dict: 健康检查结果
        """
        try:
            if not self.is_connected():
                return {
                    "status": "unhealthy",
                    "latency_ms": 0,
                    "details": {"error": "Database not connected"}
                }

            import time
            start_time = time.time()

            # 获取集合列表
            collections = self._client.list_collections()

            # 获取集合统计信息
            collection_stats = {}
            for coll in collections:
                count = coll.count()
                collection_stats[coll.name] = count

            latency_ms = int((time.time() - start_time) * 1000)

            return {
                "status": "healthy",
                "latency_ms": latency_ms,
                "details": {
                    "collection_count": len(collections),
                    "collections": collection_stats,
                    "default_collection": self._collection_name
                }
            }

        except Exception as e:
            return {
                "status": "unhealthy",
                "latency_ms": 0,
                "details": {"error": str(e)}
            }

    def close(self) -> None:
        """
        关闭数据库连接
        """
        self.disconnect()

    # Vector Interface Implementation
    def add(
        self,
        collection: str,
        ids: List[str],
        documents: List[str],
        metadatas: List[Dict[str, Any]] = None
    ) -> None:
        """
        添加向量

        Args:
            collection: 集合名
            ids: ID列表
            documents: 文本列表
            metadatas: 元数据列表
        """
        try:
            # 获取或创建集合
            coll = self._client.get_or_create_collection(
                name=collection,
                embedding_function=self._embedder
            )

            coll.add(
                ids=ids,
                documents=documents,
                metadatas=metadatas if metadatas else [{} for _ in documents]
            )

        except Exception as e:
            raise Exception(f"Failed to add documents: {str(e)}")

    def query(
        self,
        collection: str,
        query_texts: List[str],
        n_results: int = 5,
        where: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        语义检索

        Args:
            collection: 集合名
            query_texts: 查询文本列表
            n_results: 返回数量
            where: 元数据过滤条件

        Returns:
            Dict[str, Any]: 检索结果
        """
        try:
            coll = self._client.get_collection(
                name=collection,
                embedding_function=self._embedder
            )

            results = coll.query(
                query_texts=query_texts,
                n_results=n_results,
               where=where
            )

            # 格式化结果
            formatted_results = {
                "query_texts": query_texts,
                "n_results": n_results,
                "results": []
            }

            if results.get("ids"):
                for i in range(len(query_texts)):
                    query_results = {
                        "query": query_texts[i],
                        "ids": results["ids"][i] if i < len(results.get("ids", [])) else [],
                        "distances": results["distances"][i] if i < len(results.get("distances", [])) else [],
                        "documents": results["documents"][i] if i < len(results.get("documents", [])) else [],
                        "metadatas": results["metadatas"][i] if i < len(results.get("metadatas", [])) else []
                    }
                    formatted_results["results"].append(query_results)

            return formatted_results

        except Exception as e:
            return {
                "query_texts": query_texts,
                "error": str(e)
            }

    def get(
        self,
        collection: str,
        ids: List[str] = None,
        limit: int = 0
    ) -> Dict[str, Any]:
        """
        按ID获取文档

        Args:
            collection: 集合名
            ids: ID列表
            limit: 限制条数

        Returns:
            Dict[str, Any]: 文档字典
        """
        try:
            coll = self._client.get_collection(
                name=collection,
                embedding_function=self._embedder
            )

            if ids:
                results = coll.get(ids=ids)
            else:
                results = coll.get(limit=limit if limit > 0 else None)

            return results

        except Exception as e:
            return {"error": str(e)}

    def delete(
        self,
        collection: str,
        ids: List[str] = None,
        where: Dict[str, Any] = None
    ) -> None:
        """
        删除向量

        Args:
            collection: 集合名
            ids: ID列表
            where: 元数据过滤条件
        """
        try:
            coll = self._client.get_collection(
                name=collection,
                embedding_function=self._embedder
            )

            if ids:
                coll.delete(ids=ids)
            elif where:
                coll.delete(where=where)
            else:
                raise ValueError("Either ids or where must be provided")

        except Exception as e:
            raise Exception(f"Failed to delete documents: {str(e)}")

    # AI-Novels Specific Methods
    def add_character_memories(
        self,
        char_id: str,
        memories: List[str],
        metadata: List[Dict[str, Any]] = None
    ) -> List[str]:
        """
        添加角色记忆

        Args:
            char_id: 角色ID
            memories: 记忆文本列表
            metadata: 元数据列表

        Returns:
            List[str]: 插入的ID列表
        """
        if not metadata:
            metadata = [{"char_id": char_id, "type": "memory"} for _ in memories]

        # 生成唯一ID
        import uuid
        ids = [f"{char_id}_mem_{uuid.uuid4().hex[:8]}" for _ in memories]

        self.add("character_memories", ids, memories, metadata)
        return ids

    def add_plot_points(
        self,
        outline_id: str,
        points: List[str],
        metadata: List[Dict[str, Any]] = None
    ) -> List[str]:
        """
        添加剧情点

        Args:
            outline_id: 大纲ID
            points: 剧情点文本列表
            metadata: 元数据列表

        Returns:
            List[str]: 插入的ID列表
        """
        if not metadata:
            metadata = [{"outline_id": outline_id, "type": "plot_point"} for _ in points]

        import uuid
        ids = [f"{outline_id}_plot_{uuid.uuid4().hex[:8]}" for _ in points]

        self.add("plot_points", ids, points, metadata)
        return ids

    def add_world_knowledge(
        self,
        world_id: str,
        facts: List[str],
        metadata: List[Dict[str, Any]] = None
    ) -> List[str]:
        """
        添加世界观知识

        Args:
            world_id: 世界观ID
            facts: 事实文本列表
            metadata: 元数据列表

        Returns:
            List[str]: 插入的ID列表
        """
        if not metadata:
            metadata = [{"world_id": world_id, "type": "world_knowledge"} for _ in facts]

        import uuid
        ids = [f"{world_id}_fact_{uuid.uuid4().hex[:8]}" for _ in facts]

        self.add("world_knowledge", ids, facts, metadata)
        return ids

    def search_character_memories(
        self,
        char_id: str,
        query: str,
        n_results: int = 5
    ) -> Dict[str, Any]:
        """
        搜索角色记忆

        Args:
            char_id: 角色ID
            query: 查询文本
            n_results: 返回数量

        Returns:
            Dict: 检索结果
        """
        return self.query(
            collection="character_memories",
            query_texts=[query],
            n_results=n_results,
            where={"char_id": char_id}
        )

    def search_world_knowledge(
        self,
        world_id: str,
        query: str,
        n_results: int = 5
    ) -> Dict[str, Any]:
        """
        搜索世界观知识

        Args:
            world_id: 世界观ID
            query: 查询文本
            n_results: 返回数量

        Returns:
            Dict: 检索结果
        """
        return self.query(
            collection="world_knowledge",
            query_texts=[query],
            n_results=n_results,
            where={"world_id": world_id}
        )

    def search_plot_points(
        self,
        outline_id: str,
        query: str,
        n_results: int = 5
    ) -> Dict[str, Any]:
        """
        搜索剧情点

        Args:
            outline_id: 大纲ID
            query: 查询文本
            n_results: 返回数量

        Returns:
            Dict: 检索结果
        """
        return self.query(
            collection="plot_points",
            query_texts=[query],
            n_results=n_results,
            where={"outline_id": outline_id}
        )

    def get_collection_stats(self, collection: str = None) -> Dict[str, int]:
        """
        获取集合统计信息

        Args:
            collection: 集合名，None表示所有集合

        Returns:
            Dict[str, int]: 集合名到数量的映射
        """
        try:
            if collection:
                coll = self._client.get_collection(name=collection)
                return {collection: coll.count()}
            else:
                stats = {}
                for coll in self._client.list_collections():
                    stats[coll.name] = coll.count()
                return stats
        except Exception:
            return {}

    def test_connection(self) -> bool:
        """
        测试数据库连接

        Returns:
            bool: 连接成功返回True
        """
        return self.health_check()["status"] == "healthy"

    def reconnect(self) -> bool:
        """
        重新连接数据库（断开后重新连接）

        Returns:
            bool: 连接成功返回True
        """
        try:
            self.disconnect()
            import time
            time.sleep(0.1)  # 短暂延迟避免立即重连
            return self.connect()
        except Exception:
            return False

    def health_check_with_reconnect(self, max_retries: int = 2) -> dict:
        """
        带自动重连的健康检查

        Args:
            max_retries: 最大重连次数

        Returns:
            dict: 健康检查结果
        """
        retry = 0
        while retry <= max_retries:
            try:
                if not self.is_connected():
                    if retry < max_retries:
                        self.reconnect()
                        retry += 1
                        continue
                    return {
                        "status": "unhealthy",
                        "latency_ms": 0,
                        "details": {"error": "Database not connected after retries"}
                    }

                import time
                start_time = time.time()

                # 获取集合列表
                collections = self._client.list_collections()

                # 获取集合统计信息
                collection_stats = {}
                for coll in collections:
                    count = coll.count()
                    collection_stats[coll.name] = count

                latency_ms = int((time.time() - start_time) * 1000)

                return {
                    "status": "healthy",
                    "latency_ms": latency_ms,
                    "details": {
                        "collection_count": len(collections),
                        "collections": collection_stats,
                        "default_collection": self._collection_name,
                        "reconnects": retry
                    }
                }

            except Exception as e:
                if retry < max_retries:
                    self.reconnect()
                    retry += 1
                else:
                    return {
                        "status": "unhealthy",
                        "latency_ms": 0,
                        "details": {"error": str(e), "reconnects": retry},
                        "last_error": str(e)
                    }
        return {
            "status": "unhealthy",
            "latency_ms": 0,
            "details": {"error": "Max retries exceeded"}
        }
