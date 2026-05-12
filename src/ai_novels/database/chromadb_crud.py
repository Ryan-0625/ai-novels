"""
ChromaDB向量数据库CRUD工具函数

@file: database/chromadb_crud.py
@date: 2026-03-13
@version: 1.0.0
@description: ChromaDB向量数据库操作工具函数
"""

import logging
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


def chromadb_add(collection: str, ids: List[str], documents: List[str],
                 metadatas: List[Dict[str, Any]] = None, client = None) -> bool:
    """
    ChromaDB添加向量

    Args:
        collection: 集合名
        ids: ID列表
        documents: 文本列表
        metadatas: 元数据列表
        client: ChromaDBClient实例

    Returns:
        是否成功
    """
    try:
        client._collection.add(
            ids=ids,
            documents=documents,
            metadatas=metadatas
        )
        return True
    except Exception as e:
        print(f"ChromaDB add error: {e}")
        return False


def chromadb_query(collection: str, query_texts: List[str], n_results: int = 5,
                   where: Dict[str, Any] = None, client = None) -> Dict[str, Any]:
    """
    ChromaDB语义检索

    Args:
        collection: 集合名
        query_texts: 查询文本列表
        n_results: 返回数量
        where: 元数据过滤条件
        client: ChromaDBClient实例

    Returns:
        检索结果
    """
    try:
        result = client._collection.query(
            query_texts=query_texts,
            n_results=n_results,
            where=where
        )
        return result
    except Exception as e:
        print(f"ChromaDB query error: {e}")
        return {
            "ids": [],
            "documents": [],
            "metadatas": [],
            "distances": []
        }


def chromadb_get(collection: str, ids: List[str] = None, limit: int = 0,
                 where: Dict[str, Any] = None, client = None) -> Dict[str, Any]:
    """
    ChromaDB按ID获取文档

    Args:
        collection: 集合名
        ids: ID列表
        limit: 限制条数
        where: 元数据过滤条件
        client: ChromaDBClient实例

    Returns:
        文档字典
    """
    try:
        result = client._collection.get(
            ids=ids,
            limit=limit,
            where=where
        )
        return result
    except Exception as e:
        print(f"ChromaDB get error: {e}")
        return {
            "ids": [],
            "documents": [],
            "metadatas": []
        }


def chromadb_delete(collection: str, ids: List[str] = None, where: Dict[str, Any] = None,
                    client = None) -> bool:
    """
    ChromaDB删除向量

    Args:
        collection: 集合名
        ids: ID列表
        where: 元数据过滤条件

    Returns:
        是否成功
    """
    try:
        if ids:
            client._collection.delete(ids=ids)
        elif where:
            client._collection.delete(where=where)
        return True
    except Exception as e:
        print(f"ChromaDB delete error: {e}")
        return False


def chromadb_update(collection: str, ids: List[str], documents: List[str],
                    metadatas: List[Dict[str, Any]] = None, client = None) -> bool:
    """
    ChromaDB更新向量

    Args:
        collection: 集合名
        ids: ID列表
        documents: 文本列表
        metadatas: 元数据列表
        client: ChromaDBClient实例

    Returns:
        是否成功
    """
    try:
        client._collection.update(
            ids=ids,
            documents=documents,
            metadatas=metadatas
        )
        return True
    except Exception as e:
        logger.error(f"ChromaDB update error: {e}")
        return False


def chromadb_update_metadata(collection: str, ids: List[str],
                             metadatas: List[Dict[str, Any]], client = None) -> bool:
    """
    ChromaDB更新元数据

    Args:
        collection: 集合名
        ids: ID列表
        metadatas: 元数据列表
        client: ChromaDBClient实例

    Returns:
        是否成功
    """
    try:
        client._collection.update(
            ids=ids,
            metadatas=metadatas
        )
        return True
    except Exception as e:
        print(f"ChromaDB update metadata error: {e}")
        return False


def chromadb_count(collection: str, client = None) -> int:
    """
    ChromaDB统计文档数

    Args:
        collection: 集合名
        client: ChromaDBClient实例

    Returns:
        文档数量
    """
    try:
        return client._collection.count()
    except Exception as e:
        print(f"ChromaDB count error: {e}")
        return 0


def chromadb_get_or_create_collection(collection: str, client = None) -> bool:
    """
    ChromaDB获取或创建集合

    Args:
        collection: 集合名
        client: ChromaDBClient实例

    Returns:
        是否成功
    """
    try:
        # ChromaDB get_or_create_collection 由客户端处理
        # 这里仅作为 Bool 返回
        return client._collection is not None
    except Exception as e:
        print(f"ChromaDB get or create collection error: {e}")
        return False


def chromadb_clear(collection: str, client = None) -> bool:
    """
    ChromaDB清空集合

    Args:
        collection: 集合名
        client: ChromaDBClient实例

    Returns:
        是否成功
    """
    try:
        client._collection.delete(where={})
        return True
    except Exception as e:
        print(f"ChromaDB clear error: {e}")
        return False


def chromadb_search_by_metadata(collection: str, metadata: Dict[str, Any],
                                 limit: int = 10, client = None) -> Dict[str, Any]:
    """
    ChromaDB按元数据搜索

    Args:
        collection: 集合名
        metadata: 元数据条件
        limit: 限制条数
        client: ChromaDBClient实例

    Returns:
        搜索结果
    """
    try:
        result = client._collection.get(
            where=metadata,
            limit=limit
        )
        return result
    except Exception as e:
        print(f"ChromaDB search by metadata error: {e}")
        return {
            "ids": [],
            "documents": [],
            "metadatas": []
        }


def chromadb_get_all(collection: str, client = None) -> Dict[str, Any]:
    """
    ChromaDB获取所有文档

    Args:
        collection: 集合名
        client: ChromaDBClient实例

    Returns:
        所有文档
    """
    try:
        result = client._collection.get(
            include=['documents', 'metadatas']
        )
        return result
    except Exception as e:
        print(f"ChromaDB get all error: {e}")
        return {
            "ids": [],
            "documents": [],
            "metadatas": []
        }


if __name__ == "__main__":
    print("ChromaDB CRUD utils loaded successfully!")
