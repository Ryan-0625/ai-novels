"""
持久化管理器

@file: persistence/manager.py
@date: 2026-03-20
@version: 1.0
@description: 统一的持久化管理器，管理Neo4j、MongoDB、ChromaDB连接
"""

import os
from typing import Dict, Any, Optional
from functools import lru_cache

from ..database import (
    Neo4jClient, MongoDBClient, ChromaDBClient,
    get_neo4j_client, get_mongodb_client, get_chromadb_client
)
from ..config.manager import settings


class PersistenceManager:
    """
    持久化管理器

    统一管理三个数据库连接：
    - Neo4j: 图数据库，存储知识图谱
    - MongoDB: 文档数据库，存储内容
    - ChromaDB: 向量数据库，存储向量和上下文
    """

    _instance: Optional['PersistenceManager'] = None

    def __init__(self, config: Dict[str, Any] = None):
        """
        初始化持久化管理器

        Args:
            config: 配置字典
        """
        self._config = config or {}

        # 数据库客户端（延迟初始化）
        self._neo4j_client: Optional[Neo4jClient] = None
        self._mongodb_client: Optional[MongoDBClient] = None
        self._chromadb_client: Optional[ChromaDBClient] = None

        # 是否已初始化
        self._initialized = False
        self._init_error: Optional[str] = None

    @classmethod
    def instance(cls, config: Dict[str, Any] = None) -> 'PersistenceManager':
        """获取单例实例"""
        if cls._instance is None:
            if config:
                cls._instance = cls(config)
            else:
                cls._instance = cls()
        return cls._instance

    @property
    def neo4j_client(self) -> Optional[Neo4jClient]:
        """获取Neo4j客户端"""
        if self._neo4j_client is None:
            try:
                self._neo4j_client = get_neo4j_client()
                if not self._neo4j_client.connect():
                    self._init_error = "Failed to connect to Neo4j"
                    return None
            except Exception as e:
                self._init_error = f"Neo4j initialization error: {e}"
                return None
        return self._neo4j_client

    @property
    def mongodb_client(self) -> Optional[MongoDBClient]:
        """获取MongoDB客户端"""
        if self._mongodb_client is None:
            try:
                self._mongodb_client = get_mongodb_client()
                if not self._mongodb_client.connect():
                    self._init_error = "Failed to connect to MongoDB"
                    return None
            except Exception as e:
                self._init_error = f"MongoDB initialization error: {e}"
                return None
        return self._mongodb_client

    @property
    def chromadb_client(self) -> Optional[ChromaDBClient]:
        """获取ChromaDB客户端"""
        if self._chromadb_client is None:
            try:
                self._chromadb_client = get_chromadb_client()
                if not self._chromadb_client.connect():
                    self._init_error = "Failed to connect to ChromaDB"
                    return None
            except Exception as e:
                self._init_error = f"ChromaDB initialization error: {e}"
                return None
        return self._chromadb_client

    def health_check(self) -> Dict[str, Any]:
        """检查所有数据库连接状态"""
        results = {}

        # Neo4j检查
        if self.neo4j_client:
            neo4j_status = self.neo4j_client.health_check()
            results["neo4j"] = neo4j_status
        else:
            results["neo4j"] = {
                "status": "unhealthy",
                "error": self._init_error or "Not initialized"
            }

        # MongoDB检查
        if self.mongodb_client:
            mongodb_status = self.mongodb_client.health_check()
            results["mongodb"] = mongodb_status
        else:
            results["mongodb"] = {
                "status": "unhealthy",
                "error": self._init_error or "Not initialized"
            }

        # ChromaDB检查
        if self.chromadb_client:
            chromadb_status = self.chromadb_client.health_check()
            results["chromadb"] = chromadb_status
        else:
            results["chromadb"] = {
                "status": "unhealthy",
                "error": self._init_error or "Not initialized"
            }

        # 总体状态
        all_healthy = all(
            r.get("status") == "healthy" for r in results.values()
        )
        results["overall"] = {
            "status": "healthy" if all_healthy else "unhealthy",
            "databases": list(results.keys())
        }

        return results

    def reset_connections(self) -> bool:
        """重置所有数据库连接（用于测试）"""
        try:
            if self._neo4j_client:
                self._neo4j_client.disconnect()
                self._neo4j_client = None
            if self._mongodb_client:
                self._mongodb_client.disconnect()
                self._mongodb_client = None
            if self._chromadb_client:
                self._chromadb_client.disconnect()
                self._chromadb_client = None
            self._init_error = None
            return True
        except Exception:
            return False

    def close(self) -> None:
        """关闭所有连接"""
        try:
            if self._neo4j_client:
                self._neo4j_client.close()
            if self._mongodb_client:
                self._mongodb_client.close()
            if self._chromadb_client:
                self._chromadb_client.close()
        except Exception:
            pass


def get_persistence_manager(config: Dict[str, Any] = None) -> PersistenceManager:
    """
    获取持久化管理器单例

    Args:
        config: 配置字典

    Returns:
        PersistenceManager实例
    """
    return PersistenceManager.instance(config)


def initialize_persistence(config: Dict[str, Any] = None) -> bool:
    """
    初始化持久化管理器（全局单例）

    Args:
        config: 配置字典

    Returns:
        是否初始化成功
    """
    pm = get_persistence_manager(config)
    health = pm.health_check()
    return health.get("overall", {}).get("status") == "healthy"


# 全局初始化
_global_pm: Optional[PersistenceManager] = None


def get_global_persistence_manager() -> Optional[PersistenceManager]:
    """获取全局持久化管理器"""
    global _global_pm
    return _global_pm


def set_global_persistence_manager(pm: PersistenceManager) -> None:
    """设置全局持久化管理器"""
    global _global_pm
    _global_pm = pm


# 初始化时自动创建实例（如果配置可用）
try:
    default_config = settings.get_database("neo4j")
    _global_pm = get_persistence_manager()
    _global_pm.health_check()  # 尝试连接
except Exception as e:
    # 配置不可用时忽略错误
    pass
