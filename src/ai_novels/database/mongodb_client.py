"""
MongoDB客户端实现

@file: database/mongodb_client.py
@date: 2026-03-12
@author: AI-Novels Team
@version: 1.0
@description: MongoDB文档数据库客户端实现，支持CRUD操作和索引管理
"""

from pymongo import MongoClient, ReturnDocument
from pymongo.collection import Collection
from pymongo.errors import PyMongoError, ConnectionFailure
from typing import Any, Dict, List, Optional, Union, Tuple
from contextlib import contextmanager

from ..config.manager import settings
from .base import DatabaseBase, CRUDInterface
from bson import ObjectId


class MongoDBClient(DatabaseBase, CRUDInterface):
    """
    MongoDB数据库客户端实现

    特性:
    - 连接管理
    - 集合操作
    - 索引管理
    - 批量操作
    """

    def __init__(
        self,
        host: str = None,
        port: int = None,
        username: str = None,
        password: str = None,
        database: str = None,
        auth_source: str = None,
        config: Dict[str, Any] = None
    ):
        """
        初始化MongoDB客户端

        Args:
            host: MongoDB主机地址
            port: MongoDB端口
            username: 用户名
            password: 密码
            database: 数据库名称
            auth_source: 认证源
            config: 数据库配置字典，优先级最高
        """
        # 优先使用传入的配置字典
        if config:
            self._host = config.get("host", "localhost")
            self._port = config.get("port", 27017)
            self._username = config.get("username", "root")
            self._password = config.get("password", "")
            self._database = config.get("database", "ai_novels")
            self._auth_source = config.get("auth_source", "admin")
        else:
            # 从全局配置管理器读取
            db_config = settings.get_database("mongodb")
            self._host = host or db_config.get("host", "localhost")
            self._port = port or db_config.get("port", 27017)
            self._username = username or db_config.get("username", "root")
            self._password = password or db_config.get("password", "")
            self._database = database or db_config.get("database", "ai_novels")
            self._auth_source = auth_source or db_config.get("auth_source", "admin")

        self._client: Optional[MongoClient] = None
        self._db = None
        self._is_connected = False

    def connect(self) -> bool:
        """
        建立数据库连接

        Returns:
            bool: 连接成功返回True，否则返回False
        """
        try:
            # 构建连接URI
            if self._username and self._password:
                uri = f"mongodb://{self._username}:{self._password}@{self._host}:{self._port}/"
                self._client = MongoClient(
                    uri,
                    authSource=self._auth_source,
                    serverSelectionTimeoutMS=5000
                )
            else:
                uri = f"mongodb://{self._host}:{self._port}/"
                self._client = MongoClient(
                    uri,
                    serverSelectionTimeoutMS=5000
                )

            # 测试连接
            self._client.admin.command("ping")
            self._db = self._client[self._database]
            self._is_connected = True
            return True

        except ConnectionFailure:
            self._is_connected = False
            return False
        except PyMongoError:
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
                self._client.close()
            self._is_connected = False
            return True
        except PyMongoError:
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
        try:
            self._client.admin.command("ping")
            return True
        except PyMongoError:
            self._is_connected = False
            return False

    def health_check(self) -> dict:
        """
        数据库健康检查

        Returns:
            dict: 健康检查结果
        """
        import time
        start_time = time.time()

        try:
            # 如果未连接，先尝试连接
            if not self.is_connected():
                if not self.connect():
                    return {
                        "status": "unhealthy",
                        "latency_ms": int((time.time() - start_time) * 1000),
                        "details": {"error": "Failed to connect to database"}
                    }

            # 测试连接 - 使用 ping 命令（不需要认证）
            self._client.admin.command("ping")

            latency_ms = int((time.time() - start_time) * 1000)

            # 尝试获取更多信息（可能需要认证）
            details = {"database": self._database}
            try:
                server_info = self._client.server_info()
                details["server_version"] = server_info.get("version", "unknown")
            except Exception:
                pass  # 忽略认证错误

            try:
                db_stats = self._db.command("dbStats")
                details["collections_count"] = db_stats.get("collections", 0)
                details["objects_count"] = db_stats.get("objects", 0)
            except Exception:
                pass  # 忽略认证错误

            try:
                collections = self._db.list_collection_names()
                details["collections"] = collections
            except Exception:
                pass  # 忽略认证错误

            return {
                "status": "healthy",
                "latency_ms": latency_ms,
                "details": details
            }

        except PyMongoError as e:
            return {
                "status": "unhealthy",
                "latency_ms": int((time.time() - start_time) * 1000),
                "details": {"error": str(e)}
            }

    def close(self) -> None:
        """
        关闭数据库连接
        """
        self.disconnect()

    def get_collection(self, name: str) -> Collection:
        """
        获取集合对象

        Args:
            name: 集合名称

        Returns:
            Collection: 集合对象
        """
        return self._db[name]

    def list_collections(self) -> List[str]:
        """
        列出所有集合

        Returns:
            List[str]: 集合名称列表
        """
        return self._db.list_collection_names()

    # CRUD Interface Implementation
    def create(self, collection: str, document: Dict[str, Any]) -> Optional[str]:
        """
        创建单条记录

        Args:
            collection: 集合名
            document: 要插入的数据字典

        Returns:
            str: 插入记录的ID，失败返回None
        """
        try:
            result = self._db[collection].insert_one(document)
            return str(result.inserted_id)
        except PyMongoError:
            return None

    def read(
        self,
        collection: str,
        query: Dict[str, Any],
        limit: int = 0
    ) -> List[Dict[str, Any]]:
        """
        读取记录

        Args:
            collection: 集合名
            query: 查询条件字典
            limit: 限制返回数量（0为不限制）

        Returns:
            List[Dict[str, Any]]: 查询结果列表
        """
        try:
            cursor = self._db[collection].find(query)

            if limit > 0:
                cursor = cursor.limit(limit)

            results = []
            for doc in cursor:
                # 转换ObjectId为字符串
                doc = self._convert_objectid(doc)
                results.append(doc)

            return results

        except PyMongoError:
            return []

    def update(
        self,
        collection: str,
        query: Dict[str, Any],
        updates: Dict[str, Any],
        upsert: bool = False
    ) -> bool:
        """
        更新记录

        Args:
            collection: 集合名
            query: 查询条件字典
            updates: 更新数据字典
            upsert: 查询不到时是否插入

        Returns:
            bool: 更新成功返回True，否则返回False
        """
        try:
            # 转换更新字典为$set格式
            update_doc = {"$set": updates}

            result = self._db[collection].update_one(
                query,
                update_doc,
                upsert=upsert
            )

            return result.matched_count > 0 or (upsert and result.upserted_id is not None)

        except PyMongoError:
            return False

    def delete(self, collection: str, query: Dict[str, Any]) -> int:
        """
        删除记录

        Args:
            collection: 集合名
            query: 查询条件字典

        Returns:
            int: 删除的记录数量
        """
        try:
            result = self._db[collection].delete_many(query)
            return result.deleted_count
        except PyMongoError:
            return 0

    def count(self, collection: str, query: Dict[str, Any] = None) -> int:
        """
        计数

        Args:
            collection: 集合名
            query: 查询条件字典

        Returns:
            int: 记录数量
        """
        try:
            if query is None:
                return self._db[collection].count_documents({})
            return self._db[collection].count_documents(query)
        except PyMongoError:
            return 0

    def _convert_objectid(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        """
        将文档中的ObjectId转换为字符串

        Args:
            doc: 原始文档

        Returns:
            Dict: 转换后的文档
        """
        result = {}
        for key, value in doc.items():
            if isinstance(value, ObjectId):
                result[key] = str(value)
            elif isinstance(value, dict):
                result[key] = self._convert_objectid(value)
            elif isinstance(value, list):
                result[key] = [
                    self._convert_objectid(item) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                result[key] = value
        return result

    # MongoDB Specific Methods
    def create_index(self, collection: str, field: str, unique: bool = False) -> Optional[str]:
        """
        创建索引

        Args:
            collection: 集合名
            field: 字段名
            unique: 是否唯一索引

        Returns:
            str: 索引名称，失败返回None
        """
        try:
            index_name = self._db[collection].create_index(
                [(field, 1)],
                unique=unique
            )
            return index_name
        except PyMongoError:
            return None

    def create_compound_index(self, collection: str, fields: List[Tuple[str, int]], unique: bool = False) -> Optional[str]:
        """
        创建复合索引

        Args:
            collection: 集合名
            fields: 字段列表，每个元素为 (field_name, direction) 其中direction为1(升序)或-1(降序)
            unique: 是否唯一索引

        Returns:
            str: 索引名称，失败返回None
        """
        try:
            index_name = self._db[collection].create_index(
                fields,
                unique=unique
            )
            return index_name
        except PyMongoError:
            return None

    def bulk_insert(self, collection: str, documents: List[Dict[str, Any]]) -> List[str]:
        """
        批量插入

        Args:
            collection: 集合名
            documents: 文档列表

        Returns:
            List[str]: 插入的ID列表
        """
        try:
            result = self._db[collection].insert_many(documents)
            return [str(id) for id in result.inserted_ids]
        except PyMongoError:
            return []

    def find_one(self, collection: str, query: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        查询单条记录

        Args:
            collection: 集合名
            query: 查询条件

        Returns:
            Dict: 查询结果，不存在返回None
        """
        try:
            doc = self._db[collection].find_one(query)
            return self._convert_objectid(doc) if doc else None
        except PyMongoError:
            return None

    def find_one_and_update(
        self,
        collection: str,
        query: Dict[str, Any],
        updates: Dict[str, Any],
        return_new: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        查找并更新单条记录

        Args:
            collection: 集合名
            query: 查询条件
            updates: 更新数据
            return_new: 是否返回更新后的文档

        Returns:
            Dict: 结果，不存在返回None
        """
        try:
            doc = self._db[collection].find_one_and_update(
                query,
                {"$set": updates},
                return_document=ReturnDocument.AFTER if return_new else ReturnDocument.BEFORE
            )
            return self._convert_objectid(doc) if doc else None
        except PyMongoError:
            return None

    def aggregate(self, collection: str, pipeline: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        聚合查询

        Args:
            collection: 集合名
            pipeline: 聚合管道

        Returns:
            List[Dict]: 聚合结果
        """
        try:
            cursor = self._db[collection].aggregate(pipeline)
            return [self._convert_objectid(doc) for doc in cursor]
        except PyMongoError:
            return []

    def drop_collection(self, collection: str) -> bool:
        """
        删除集合

        Args:
            collection: 集合名

        Returns:
            bool: 删除成功返回True
        """
        try:
            self._db[collection].drop()
            return True
        except PyMongoError:
            return False

    def test_connection(self) -> bool:
        """
        测试数据库连接

        Returns:
            bool: 连接成功返回True
        """
        return self.health_check()["status"] == "healthy"
