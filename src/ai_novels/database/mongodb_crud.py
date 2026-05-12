"""
MongoDB文档操作CRUD工具函数

@file: database/mongodb_crud.py
@date: 2026-03-13
@version: 1.0.0
@description: MongoDB文档操作工具函数
"""

import logging
from typing import Dict, List, Optional, Any
from bson import ObjectId

logger = logging.getLogger(__name__)


def mongodb_insert_one(collection: str, document: Dict[str, Any], client) -> Optional[str]:
    """
    MongoDB插入单条文档

    Args:
        collection: 集合名
        document: 文档
        client: MongoDBClient实例

    Returns:
        插入的ID或None
    """
    try:
        result = client._db[collection].insert_one(document)
        return str(result.inserted_id)
    except Exception as e:
        print(f"MongoDB insert one error: {e}")
        return None


def mongodb_insert_many(collection: str, documents: List[Dict[str, Any]], client) -> List[str]:
    """
    MongoDB插入多条文档

    Args:
        collection: 集合名
        documents: 文档列表
        client: MongoDBClient实例

    Returns:
        插入的ID列表
    """
    try:
        result = client._db[collection].insert_many(documents)
        return [str(oid) for oid in result.inserted_ids]
    except Exception as e:
        print(f"MongoDB insert many error: {e}")
        return []


def mongodb_find_one(collection: str, query: Dict[str, Any], client,
                     projection: Dict[str, int] = None) -> Optional[Dict[str, Any]]:
    """
    MongoDB查询单条文档

    Args:
        collection: 集合名
        query: 查询条件
        client: MongoDBClient实例
        projection: 投影（字段选择）

    Returns:
        文档或None
    """
    try:
        if projection:
            result = client._db[collection].find_one(query, projection)
        else:
            result = client._db[collection].find_one(query)
        return result
    except Exception as e:
        print(f"MongoDB find one error: {e}")
        return None


def mongodb_find_many(collection: str, query: Dict[str, Any], limit: int = 0, client = None,
                      projection: Dict[str, int] = None) -> List[Dict[str, Any]]:
    """
    MongoDB查询多条文档

    Args:
        collection: 集合名
        query: 查询条件
        limit: 限制条数
        client: MongoDBClient实例
        projection: 投影（字段选择）

    Returns:
        文档列表
    """
    try:
        cursor = client._db[collection].find(query, projection)
        if limit > 0:
            cursor = cursor.limit(limit)
        return list(cursor)
    except Exception as e:
        print(f"MongoDB find many error: {e}")
        return []


def mongodb_update_one(collection: str, query: Dict[str, Any], update: Dict[str, Any],
                        client, upsert: bool = False) -> bool:
    """
    MongoDB更新单条文档

    Args:
        collection: 集合名
        query: 查询条件
        update: 更新数据
        client: MongoDBClient实例
        upsert: 查询不到时是否插入

    Returns:
        是否成功
    """
    try:
        result = client._db[collection].update_one(query, update, upsert=upsert)
        return result.modified_count > 0 or (upsert and result.upserted_id is not None)
    except Exception as e:
        print(f"MongoDB update one error: {e}")
        return False


def mongodb_update_many(collection: str, query: Dict[str, Any], update: Dict[str, Any],
                         client) -> int:
    """
    MongoDB更新多条文档

    Args:
        collection: 集合名
        query: 查询条件
        update: 更新数据
        client: MongoDBClient实例

    Returns:
        更新的文档数
    """
    try:
        result = client._db[collection].update_many(query, update)
        return result.modified_count
    except Exception as e:
        print(f"MongoDB update many error: {e}")
        return 0


def mongodb_delete_one(collection: str, query: Dict[str, Any], client) -> bool:
    """
    MongoDB删除单条文档

    Args:
        collection: 集合名
        query: 查询条件
        client: MongoDBClient实例

    Returns:
        是否成功
    """
    try:
        result = client._db[collection].delete_one(query)
        return result.deleted_count > 0
    except Exception as e:
        print(f"MongoDB delete one error: {e}")
        return False


def mongodb_delete_many(collection: str, query: Dict[str, Any], client) -> int:
    """
    MongoDB删除多条文档

    Args:
        collection: 集合名
        query: 查询条件
        client: MongoDBClient实例

    Returns:
        删除的文档数
    """
    try:
        result = client._db[collection].delete_many(query)
        return result.deleted_count
    except Exception as e:
        print(f"MongoDB delete many error: {e}")
        return 0


def mongodb_count(collection: str, query: Dict[str, Any] = None, client = None) -> int:
    """
    MongoDB计数

    Args:
        collection: 集合名
        query: 查询条件
        client: MongoDBClient实例

    Returns:
        文档数量
    """
    try:
        return client._db[collection].count_documents(query or {})
    except Exception as e:
        print(f"MongoDB count error: {e}")
        return 0


def mongodb_exists(collection: str, query: Dict[str, Any], client) -> bool:
    """
    检查文档是否存在

    Args:
        collection: 集合名
        query: 查询条件
        client: MongoDBClient实例

    Returns:
        是否存在
    """
    count = mongodb_count(collection, query, client)
    return count > 0


def mongodb_find_by_id(collection: str, doc_id: str, client) -> Optional[Dict[str, Any]]:
    """
    MongoDB按ID查询

    Args:
        collection: 集合名
        doc_id: 文档ID
        client: MongoDBClient实例

    Returns:
        文档或None
    """
    try:
        result = client._db[collection].find_one({"_id": ObjectId(doc_id)})
        return result
    except Exception as e:
        print(f"MongoDB find by id error: {e}")
        return None


def mongodb_upsert(collection: str, query: Dict[str, Any], update: Dict[str, Any], client) -> Optional[str]:
    """
    MongoDB upsert（存在则更新，不存在则插入）

    Args:
        collection: 集合名
        query: 查询条件
        update: 更新数据
        client: MongoDBClient实例

    Returns:
        文档ID或None
    """
    try:
        result = client._db[collection].update_one(query, update, upsert=True)
        if result.upserted_id:
            return str(result.upserted_id)
        # 查询更新后的文档
        doc = mongodb_find_one(collection, query, client)
        return str(doc['_id']) if doc else None
    except Exception as e:
        print(f"MongoDB upsert error: {e}")
        return None


def mongodb_aggregate(collection: str, pipeline: List[Dict[str, Any]], client) -> List[Dict[str, Any]]:
    """
    MongoDB聚合查询

    Args:
        collection: 集合名
        pipeline: 聚合管道
        client: MongoDBClient实例

    Returns:
        聚合结果
    """
    try:
        cursor = client._db[collection].aggregate(pipeline)
        return list(cursor)
    except Exception as e:
        print(f"MongoDB aggregate error: {e}")
        return []


def mongodb_distinct(collection: str, field: str, query: Dict[str, Any] = None, client = None) -> List[Any]:
    """
    MongoDB去重查询

    Args:
        collection: 集合名
        field: 字段名
        query: 查询条件
        client: MongoDBClient实例

    Returns:
        去重后的值列表
    """
    try:
        result = client._db[collection].distinct(field, query or {})
        return result
    except Exception as e:
        print(f"MongoDB distinct error: {e}")
        return []


def mongodb_create_index(collection: str, field: str, unique: bool = False, client = None) -> str:
    """
    MongoDB创建索引

    Args:
        collection: 集合名
        field: 字段名
        unique: 是否唯一索引
        client: MongoDBClient实例

    Returns:
        索引名
    """
    try:
        index_name = client._db[collection].create_index(field, unique=unique)
        return index_name
    except Exception as e:
        logger.error(f"MongoDB create index error: {e}")
        return ""


if __name__ == "__main__":
    print("MongoDB CRUD utils loaded successfully!")
