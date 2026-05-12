"""
数据库查询优化实现

@file: database/optimized_clients.py
@date: 2026-03-13
@author: AI-Novels Team
@version: 1.0
@description: 实现数据库批量操作和查询优化
"""

import time
import logging
from typing import Any, Dict, List, Optional, Tuple
from contextlib import contextmanager
from dataclasses import dataclass
from abc import ABC, abstractmethod

# 导入原始客户端
from ai_novels.database.base import DatabaseBase, CRUDInterface, GraphInterface, VectorInterface
from ai_novels.database.mysql_client import MySQLClient, MySQLConfig
from ai_novels.database.mongodb_client import MongoDBClient, MongoDBConfig
from ai_novels.database.neo4j_client import Neo4jClient, Neo4jConfig
from ai_novels.database.chromadb_client import ChromaDBClient, ChromaDBConfig

logger = logging.getLogger(__name__)


# ========== 批量操作优化 ==========
@dataclass
class BatchResult:
    """批量操作结果"""
    success_count: int
    failed_count: int
    errors: List[Dict[str, Any]]
    total_time_ms: float


class OptimizedMySQLClient:
    """
    优化的 MySQL 客户端

    实现批量操作优化：
    - 批量插入
    - 批量更新
    - 批量查询
    """

    def __init__(self, config: MySQLConfig = None):
        self._original = MySQLClient(config)
        self._batch_buffer: List[Dict[str, Any]] = []
        self._batch_size = 100
        self._batch_insert_buffer: List[Dict[str, Any]] = []
        self._batch_insert_size = 500

    def connect(self) -> bool:
        return self._original.connect()

    def disconnect(self) -> bool:
        return self._original.disconnect()

    def is_connected(self) -> bool:
        return self._original.is_connected()

    def health_check(self) -> dict:
        return self._original.health_check()

    def close(self) -> None:
        self._original.close()

    @contextmanager
    def session(self):
        with self._original.session() as s:
            yield s

    # ========== 批量插入优化 ==========
    def batch_insert(self, table: str, data_list: List[Dict[str, Any]]) -> BatchResult:
        """
        批量插入优化

        Args:
            table: 表名
            data_list: 数据列表

        Returns:
            BatchResult: 批量操作结果
        """
        start_time = time.time()
        success_count = 0
        failed_count = 0
        errors = []

        if not data_list:
            return BatchResult(0, 0, [], time.time() - start_time)

        try:
            connection = self._original._get_connection()
            cursor = connection.cursor()

            for i, data in enumerate(data_list):
                try:
                    columns = ', '.join(data.keys())
                    placeholders = ', '.join(['%s'] * len(data))
                    sql = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"
                    cursor.execute(sql, list(data.values()))
                    success_count += 1

                    # 批量提交
                    if (i + 1) % self._batch_insert_size == 0:
                        connection.commit()
                except Exception as e:
                    failed_count += 1
                    errors.append({
                        'index': i,
                        'data': data,
                        'error': str(e)
                    })

            # 提交剩余
            connection.commit()
            cursor.close()
            self._original._return_connection(connection)

        except Exception as e:
            errors.append({'error': str(e)})

        return BatchResult(
            success_count,
            failed_count,
            errors,
            (time.time() - start_time) * 1000
        )

    # ========== 批量查询优化 ==========
    def batch_query(self, table: str, conditions_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        批量查询优化

        Args:
            table: 表名
            conditions_list: 查询条件列表

        Returns:
            List[Dict[str, Any]]: 查询结果列表
        """
        results = []

        if not conditions_list:
            return results

        connection = self._original._get_connection()
        cursor = connection.cursor(dictionary=True)

        try:
            for conditions in conditions_list:
                if not conditions:
                    continue

                where_clause = " AND ".join([f"{k} = %s" for k in conditions.keys()])
                sql = f"SELECT * FROM {table} WHERE {where_clause}"

                cursor.execute(sql, list(conditions.values()))
                result = cursor.fetchall()
                results.extend(result)

        finally:
            cursor.close()
            self._original._return_connection(connection)

        return results

    # ========== 批量更新优化 ==========
    def batch_update(self, table: str, updates_list: List[Dict[str, Any]]) -> BatchResult:
        """
        批量更新优化

        Args:
            table: 表名
            updates_list: 更新数据列表，每个字典包含:
                - conditions: 查询条件
                - updates: 更新数据

        Returns:
            BatchResult: 批量操作结果
        """
        start_time = time.time()
        success_count = 0
        failed_count = 0
        errors = []

        if not updates_list:
            return BatchResult(0, 0, [], time.time() - start_time)

        connection = self._original._get_connection()
        cursor = connection.cursor()

        try:
            for i, item in enumerate(updates_list):
                try:
                    conditions = item.get('conditions', {})
                    updates = item.get('updates', {})

                    if not conditions or not updates:
                        continue

                    set_clause = ', '.join([f"{k} = %s" for k in updates.keys()])
                    where_clause = " AND ".join([f"{k} = %s" for k in conditions.keys()])
                    sql = f"UPDATE {table} SET {set_clause} WHERE {where_clause}"

                    params = list(updates.values()) + list(conditions.values())
                    cursor.execute(sql, params)
                    success_count += 1

                    if (i + 1) % self._batch_size == 0:
                        connection.commit()

                except Exception as e:
                    failed_count += 1
                    errors.append({
                        'index': i,
                        'item': item,
                        'error': str(e)
                    })

            connection.commit()

        finally:
            cursor.close()
            self._original._return_connection(connection)

        return BatchResult(
            success_count,
            failed_count,
            errors,
            (time.time() - start_time) * 1000
        )

    # ========== 索引优化 ==========
    def create_index(self, table: str, column: str, index_name: str = None) -> bool:
        """
        创建索引

        Args:
            table: 表名
            column: 列名
            index_name: 索引名

        Returns:
            bool: 是否成功
        """
        if index_name is None:
            index_name = f"idx_{table}_{column}"

        sql = f"CREATE INDEX {index_name} ON {table} ({column})"

        try:
            connection = self._original._get_connection()
            cursor = connection.cursor()
            cursor.execute(sql)
            connection.commit()
            cursor.close()
            self._original._return_connection(connection)
            return True
        except Exception as e:
            logger.error(f"Failed to create index {index_name}: {e}")
            return False

    def create复合_index(self, table: str, columns: List[str], index_name: str = None) -> bool:
        """
        创建复合索引

        Args:
            table: 表名
            columns: 列名列表
            index_name: 索引名

        Returns:
            bool: 是否成功
        """
        if index_name is None:
            index_name = f"idx_{table}_{'_'.join(columns)}"

        columns_str = ', '.join(columns)
        sql = f"CREATE INDEX {index_name} ON {table} ({columns_str})"

        try:
            connection = self._original._get_connection()
            cursor = connection.cursor()
            cursor.execute(sql)
            connection.commit()
            cursor.close()
            self._original._return_connection(connection)
            return True
        except Exception as e:
            logger.error(f"Failed to create index {index_name}: {e}")
            return False


class OptimizedMongoDBClient:
    """
    优化的 MongoDB 客户端

    实现批量操作优化
    """

    def __init__(self, config: MongoDBConfig = None):
        self._original = MongoDBClient(config)
        self._batch_size = 1000

    def connect(self) -> bool:
        return self._original.connect()

    def disconnect(self) -> bool:
        return self._original.disconnect()

    def is_connected(self) -> bool:
        return self._original.is_connected()

    def health_check(self) -> dict:
        return self._original.health_check()

    def close(self) -> None:
        self._original.close()

    @contextmanager
    def session(self):
        with self._original.session() as s:
            yield s

    def find_one(self, collection: str, query: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return self._original.find_one(collection, query)

    def find_many(self, collection: str, query: Dict[str, Any], limit: int = 0) -> List[Dict[str, Any]]:
        return self._original.find_many(collection, query, limit)

    def insert_one(self, collection: str, document: Dict[str, Any]) -> Optional[str]:
        return self._original.insert_one(collection, document)

    def insert_many(self, collection: str, documents: List[Dict[str, Any]]) -> BatchResult:
        """
        批量插入优化

        Args:
            collection: 集合名
            documents: 文档列表

        Returns:
            BatchResult: 批量操作结果
        """
        start_time = time.time()
        success_count = 0
        failed_count = 0
        errors = []

        if not documents:
            return BatchResult(0, 0, [], time.time() - start_time)

        try:
            collection_obj = self._original._db[collection]

            for i, doc in enumerate(documents):
                try:
                    result = collection_obj.insert_one(doc)
                    success_count += 1
                except Exception as e:
                    failed_count += 1
                    errors.append({
                        'index': i,
                        'doc': doc,
                        'error': str(e)
                    })

        except Exception as e:
            errors.append({'error': str(e)})

        return BatchResult(
            success_count,
            failed_count,
            errors,
            (time.time() - start_time) * 1000
        )

    def update_one(self, collection: str, query: Dict[str, Any], updates: Dict[str, Any], upsert: bool = False) -> bool:
        return self._original.update_one(collection, query, updates, upsert)

    def update_many(self, collection: str, query: Dict[str, Any], updates: Dict[str, Any]) -> int:
        return self._original.update_many(collection, query, updates)

    def delete_one(self, collection: str, query: Dict[str, Any]) -> int:
        return self._original.delete_one(collection, query)

    def delete_many(self, collection: str, query: Dict[str, Any]) -> int:
        return self._original.delete_many(collection, query)

    def count(self, collection: str, query: Dict[str, Any] = None) -> int:
        return self._original.count(collection, query)

    def create_index(self, collection: str, field: str, unique: bool = False) -> str:
        """
        创建索引
        """
        collection_obj = self._original._db[collection]
        index_name = collection_obj.create_index(field, unique=unique)
        return index_name

    def create复合_index(self, collection: str, fields: List[Tuple[str, int]]) -> str:
        """
        创建复合索引
        fields: [(field_name, 1 or -1), ...]
        """
        collection_obj = self._original._db[collection]
        index_name = collection_obj.create_index(fields)
        return index_name


class OptimizedNeo4jClient:
    """
    优化的 Neo4j 客户端

    实现批量操作和查询优化
    """

    def __init__(self, config: Neo4jConfig = None):
        self._original = Neo4jClient(config)

    def connect(self) -> bool:
        return self._original.connect()

    def disconnect(self) -> bool:
        return self._original.disconnect()

    def is_connected(self) -> bool:
        return self._original.is_connected()

    def health_check(self) -> dict:
        return self._original.health_check()

    def close(self) -> None:
        self._original.close()

    @contextmanager
    def session(self):
        with self._original.session() as s:
            yield s

    def create_node(self, label: str, properties: Dict[str, Any]) -> Dict[str, Any]:
        return self._original.create_node(label, properties)

    def find_nodes(self, label: str, property_name: str, value: Any) -> List[Dict[str, Any]]:
        return self._original.find_nodes(label, property_name, value)

    def create_relationship(self, from_label: str, from_id: Any, from_prop: str,
                            to_label: str, to_id: Any, to_prop: str,
                            rel_type: str, properties: Dict[str, Any] = None) -> bool:
        return self._original.create_relationship(from_label, from_id, from_prop,
                                                   to_label, to_id, to_prop,
                                                   rel_type, properties)

    def execute_cypher(self, cypher: str, params: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        return self._original.execute_cypher(cypher, params)

    def batch_create_nodes(self, nodes: List[Dict[str, Any]]) -> BatchResult:
        """
        批量创建节点

        Args:
            nodes: 节点列表，每个包含 label 和 properties

        Returns:
            BatchResult: 批量操作结果
        """
        start_time = time.time()
        success_count = 0
        failed_count = 0
        errors = []

        if not nodes:
            return BatchResult(0, 0, [], time.time() - start_time)

        try:
            with self._original.session() as session:
                for i, node in enumerate(nodes):
                    try:
                        label = node.get('label', 'Node')
                        properties = node.get('properties', {})

                        cypher = f"CREATE (n:{label} $properties) RETURN n"
                        result = session.run(cypher, properties=properties)
                        result.single()
                        success_count += 1

                        if (i + 1) % 100 == 0:
                            print(f"Batch created {i + 1} nodes")

                    except Exception as e:
                        failed_count += 1
                        errors.append({
                            'index': i,
                            'node': node,
                            'error': str(e)
                        })

        except Exception as e:
            errors.append({'error': str(e)})

        return BatchResult(
            success_count,
            failed_count,
            errors,
            (time.time() - start_time) * 1000
        )

    def batch_execute_cypher(self, cypher_list: List[Tuple[str, Dict[str, Any]]]) -> BatchResult:
        """
        批量执行 Cypher 查询

        Args:
            cypher_list: [(cypher, params), ...]

        Returns:
            BatchResult: 批量操作结果
        """
        start_time = time.time()
        success_count = 0
        failed_count = 0
        errors = []

        if not cypher_list:
            return BatchResult(0, 0, [], time.time() - start_time)

        try:
            with self._original.session() as session:
                for i, (cypher, params) in enumerate(cypher_list):
                    try:
                        result = session.run(cypher, **(params or {}))
                        result.single()
                        success_count += 1

                        if (i + 1) % 100 == 0:
                            print(f"Batch executed {i + 1} queries")

                    except Exception as e:
                        failed_count += 1
                        errors.append({
                            'index': i,
                            'cypher': cypher,
                            'error': str(e)
                        })

        except Exception as e:
            errors.append({'error': str(e)})

        return BatchResult(
            success_count,
            failed_count,
            errors,
            (time.time() - start_time) * 1000
        )


class OptimizedChromaDBClient:
    """
    优化的 ChromaDB 客户端

    实现批量操作优化
    """

    def __init__(self, config: ChromaDBConfig = None):
        self._original = ChromaDBClient(config)

    def connect(self) -> bool:
        return self._original.connect()

    def disconnect(self) -> bool:
        return self._original.disconnect()

    def is_connected(self) -> bool:
        return self._original.is_connected()

    def health_check(self) -> dict:
        return self._original.health_check()

    def close(self) -> None:
        self._original.close()

    @contextmanager
    def session(self):
        with self._original.session() as s:
            yield s

    def add(self, collection: str, ids: List[str], documents: List[str],
            metadatas: List[Dict[str, Any]] = None) -> None:
        self._original.add(collection, ids, documents, metadatas)

    def batch_add(self, collection: str, batch_list: List[Dict[str, Any]]) -> BatchResult:
        """
        批量添加向量

        Args:
            collection: 集合名
            batch_list: 每个字典包含 ids, documents, metadatas

        Returns:
            BatchResult: 批量操作结果
        """
        start_time = time.time()
        success_count = 0
        failed_count = 0
        errors = []

        if not batch_list:
            return BatchResult(0, 0, [], time.time() - start_time)

        for i, batch in enumerate(batch_list):
            try:
                ids = batch.get('ids', [])
                documents = batch.get('documents', [])
                metadatas = batch.get('metadatas', None)

                self._original.add(collection, ids, documents, metadatas)
                success_count += 1

                if (i + 1) % 10 == 0:
                    print(f"Batch added {i + 1} batches")

            except Exception as e:
                failed_count += 1
                errors.append({
                    'index': i,
                    'batch': batch,
                    'error': str(e)
                })

        return BatchResult(
            success_count,
            failed_count,
            errors,
            (time.time() - start_time) * 1000
        )

    def query(self, collection: str, query_texts: List[str], n_results: int = 5,
              where: Dict[str, Any] = None) -> Dict[str, Any]:
        return self._original.query(collection, query_texts, n_results, where)

    def get(self, collection: str, ids: List[str] = None,
            limit: int = 0) -> Dict[str, Any]:
        return self._original.get(collection, ids, limit)

    def delete(self, collection: str, ids: List[str] = None,
               where: Dict[str, Any] = None) -> None:
        self._original.delete(collection, ids, where)


if __name__ == "__main__":
    # 示例用法
    # 创建优化的客户端实例

    # MySQL 优化客户端
    mysql_config = MySQLConfig(
        host="localhost",
        port=3306,
        user="root",
        password="password",
        database="ai_novels"
    )
    optimized_mysql = OptimizedMySQLClient(mysql_config)

    # MongoDB 优化客户端
    mongodb_config = MongoDBConfig(
        host="localhost",
        port=27017,
        database="ai_novels"
    )
    optimized_mongo = OptimizedMongoDBClient(mongodb_config)

    # Neo4j 优化客户端
    neo4j_config = Neo4jConfig(
       _uri="bolt://localhost:7687",
        user="neo4j",
        password="password"
    )
    optimized_neo4j = OptimizedNeo4jClient(neo4j_config)

    # ChromaDB 优化客户端
    chromadb_config = ChromaDBConfig(
        path="./chromadb"
    )
    optimized_chromadb = OptimizedChromaDBClient(chromadb_config)

    logger.info("Optimized database clients initialized successfully!")
