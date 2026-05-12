"""
数据库模块初始化

@file: database/__init__.py
@date: 2026-03-12
@version: 1.0
@description: 导出数据库模块的公共接口
"""

from .base import (
    DatabaseBase,
    CRUDInterface,
    GraphInterface,
    VectorInterface,
    DatabaseClient,
    CRUDDatabase,
    GraphDatabase,
    VectorDatabase
)

from .mysql_client import MySQLClient
from .neo4j_client import Neo4jClient
from .mongodb_client import MongoDBClient
from .chromadb_client import ChromaDBClient

# 导入配置管理器
from typing import Dict, Any
from ..config.manager import settings

# 导入CRUD工具函数
from .mysql_crud import (
    mysql_insert,
    mysql_select,
    mysql_update,
    mysql_delete,
    mysql_count,
    mysql_batch_insert,
    mysql_get_or_insert,
    mysql_exists,
    mysql_transaction
)

from .neo4j_crud import (
    neo4j_create_node,
    neo4j_find_nodes,
    neo4j_create_relationship,
    neo4j_get_node,
    neo4j_delete_node,
    neo4j_delete_relationship,
    neo4j_update_node_properties,
    neo4j_traverse,
    neo4j_find_related_nodes,
    neo4j_create_unique_constraint
)

from .mongodb_crud import (
    mongodb_insert_one,
    mongodb_insert_many,
    mongodb_find_one,
    mongodb_find_many,
    mongodb_update_one,
    mongodb_update_many,
    mongodb_delete_one,
    mongodb_delete_many,
    mongodb_count,
    mongodb_exists,
    mongodb_find_by_id,
    mongodb_upsert,
    mongodb_aggregate,
    mongodb_distinct,
    mongodb_create_index
)

from .chromadb_crud import (
    chromadb_add,
    chromadb_query,
    chromadb_get,
    chromadb_delete,
    chromadb_update,
    chromadb_update_metadata,
    chromadb_count,
    chromadb_get_or_create_collection,
    chromadb_clear,
    chromadb_search_by_metadata,
    chromadb_get_all
)

__all__ = [
    # 基类
    'DatabaseBase',
    'CRUDInterface',
    'GraphInterface',
    'VectorInterface',
    'DatabaseClient',
    'CRUDDatabase',
    'GraphDatabase',
    'VectorDatabase',
    # 客户端
    'MySQLClient',
    'Neo4jClient',
    'MongoDBClient',
    'ChromaDBClient',
    # 工厂函数
    'get_mysql_client',
    'get_neo4j_client',
    'get_mongodb_client',
    'get_chromadb_client',
    # MySQL CRUD
    'mysql_insert',
    'mysql_select',
    'mysql_update',
    'mysql_delete',
    'mysql_count',
    'mysql_batch_insert',
    'mysql_get_or_insert',
    'mysql_exists',
    'mysql_transaction',
    # Neo4j CRUD
    'neo4j_create_node',
    'neo4j_find_nodes',
    'neo4j_create_relationship',
    'neo4j_get_node',
    'neo4j_delete_node',
    'neo4j_delete_relationship',
    'neo4j_update_node_properties',
    'neo4j_traverse',
    'neo4j_find_related_nodes',
    'neo4j_create_unique_constraint',
    # MongoDB CRUD
    'mongodb_insert_one',
    'mongodb_insert_many',
    'mongodb_find_one',
    'mongodb_find_many',
    'mongodb_update_one',
    'mongodb_update_many',
    'mongodb_delete_one',
    'mongodb_delete_many',
    'mongodb_count',
    'mongodb_exists',
    'mongodb_find_by_id',
    'mongodb_upsert',
    'mongodb_aggregate',
    'mongodb_distinct',
    'mongodb_create_index',
    # ChromaDB CRUD
    'chromadb_add',
    'chromadb_query',
    'chromadb_get',
    'chromadb_delete',
    'chromadb_update',
    'chromadb_update_metadata',
    'chromadb_count',
    'chromadb_get_or_create_collection',
    'chromadb_clear',
    'chromadb_search_by_metadata',
    'chromadb_get_all',
]


def get_mysql_client(config: Dict[str, Any] = None) -> MySQLClient:
    """
    获取MySQL客户端实例（单例模式）

    Args:
        config: 配置字典，None则从settings读取

    Returns:
        MySQLClient实例
    """
    if config is None:
        config = settings.get_database("mysql")
    return MySQLClient(config=config)


def get_neo4j_client(config: Dict[str, Any] = None) -> Neo4jClient:
    """
    获取Neo4j客户端实例（单例模式）

    Args:
        config: 配置字典，None则从settings读取

    Returns:
        Neo4jClient实例
    """
    if config is None:
        config = settings.get_database("neo4j")
    return Neo4jClient(config=config)


def get_mongodb_client(config: Dict[str, Any] = None) -> MongoDBClient:
    """
    获取MongoDB客户端实例（单例模式）

    Args:
        config: 配置字典，None则从settings读取

    Returns:
        MongoDBClient实例
    """
    if config is None:
        config = settings.get_database("mongodb")
    return MongoDBClient(config=config)


def get_chromadb_client(config: Dict[str, Any] = None) -> ChromaDBClient:
    """
    获取ChromaDB客户端实例（单例模式）

    Args:
        config: 配置字典，None则从settings读取

    Returns:
        ChromaDBClient实例
    """
    if config is None:
        config = settings.get_database("chromadb")
    return ChromaDBClient(config=config)
