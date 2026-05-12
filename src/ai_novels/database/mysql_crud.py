"""
MySQL数据库CRUD工具函数

@file: database/mysql_crud.py
@date: 2026-03-13
@version: 1.0.0
@description: MySQL增删改查工具函数
"""

import json
import logging
from typing import Dict, List, Optional, Any
from contextlib import contextmanager

logger = logging.getLogger(__name__)


def mysql_insert(table: str, data: Dict[str, Any], client) -> bool:
    """
    MySQL插入记录

    Args:
        table: 表名
        data: 数据字典
        client: MySQLClient实例

    Returns:
        是否成功
    """
    try:
        connection = client._get_connection()
        cursor = connection.cursor()

        # 构建SQL
        columns = ', '.join(data.keys())
        placeholders = ', '.join(['%s'] * len(data))
        sql = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"

        cursor.execute(sql, list(data.values()))
        connection.commit()

        # 获取插入的ID
        inserted_id = cursor.lastrowid
        cursor.close()
        client._return_connection(connection)

        return inserted_id
    except Exception as e:
        print(f"MySQL insert error: {e}")
        return False


def mysql_select(table: str, where: Dict[str, Any], limit: int = 0, client = None) -> List[Dict[str, Any]]:
    """
    MySQL查询记录

    Args:
        table: 表名
        where: 查询条件
        limit: 限制条数
        client: MySQLClient实例

    Returns:
        记录列表
    """
    try:
        connection = client._get_connection()
        cursor = connection.cursor(dictionary=True)

        # 构建WHERE子句
        if where:
            where_clause = " AND ".join([f"{k} = %s" for k in where.keys()])
            sql = f"SELECT * FROM {table} WHERE {where_clause}"
        else:
            sql = f"SELECT * FROM {table}"

        # 添加LIMIT
        if limit > 0:
            sql += f" LIMIT {limit}"

        cursor.execute(sql, list(where.values()) if where else [])
        results = cursor.fetchall()

        cursor.close()
        client._return_connection(connection)

        return results
    except Exception as e:
        print(f"MySQL select error: {e}")
        return []


def mysql_update(table: str, where: Dict[str, Any], data: Dict[str, Any], client = None) -> bool:
    """
    MySQL更新记录

    Args:
        table: 表名
        where: 查询条件
        data: 更新数据
        client: MySQLClient实例

    Returns:
        是否成功
    """
    try:
        connection = client._get_connection()
        cursor = connection.cursor()

        # 构建SET子句
        set_clause = ', '.join([f"{k} = %s" for k in data.keys()])

        # 构建WHERE子句
        where_clause = " AND ".join([f"{k} = %s" for k in where.keys()])

        sql = f"UPDATE {table} SET {set_clause} WHERE {where_clause}"

        # 参数顺序：SET值在前，WHERE值在后
        params = list(data.values()) + list(where.values())

        cursor.execute(sql, params)
        connection.commit()

        updated_rows = cursor.rowcount
        cursor.close()
        client._return_connection(connection)

        return updated_rows > 0
    except Exception as e:
        print(f"MySQL update error: {e}")
        return False


def mysql_delete(table: str, where: Dict[str, Any], client = None) -> int:
    """
    MySQL删除记录

    Args:
        table: 表名
        where: 删除条件
        client: MySQLClient实例

    Returns:
        删除的记录数
    """
    try:
        connection = client._get_connection()
        cursor = connection.cursor()

        # 构建WHERE子句
        where_clause = " AND ".join([f"{k} = %s" for k in where.keys()])
        sql = f"DELETE FROM {table} WHERE {where_clause}"

        cursor.execute(sql, list(where.values()))
        connection.commit()

        deleted_rows = cursor.rowcount
        cursor.close()
        client._return_connection(connection)

        return deleted_rows
    except Exception as e:
        print(f"MySQL delete error: {e}")
        return 0


def mysql_count(table: str, where: Dict[str, Any] = None, client = None) -> int:
    """
    MySQL计数

    Args:
        table: 表名
        where: 查询条件
        client: MySQLClient实例

    Returns:
        记录数量
    """
    try:
        connection = client._get_connection()
        cursor = connection.cursor()

        if where:
            where_clause = " AND ".join([f"{k} = %s" for k in where.keys()])
            sql = f"SELECT COUNT(*) FROM {table} WHERE {where_clause}"
            cursor.execute(sql, list(where.values()))
        else:
            sql = f"SELECT COUNT(*) FROM {table}"
            cursor.execute(sql)

        count = cursor.fetchone()[0]
        cursor.close()
        client._return_connection(connection)

        return count
    except Exception as e:
        print(f"MySQL count error: {e}")
        return 0


def mysql_batch_insert(table: str, data_list: List[Dict[str, Any]], client) -> int:
    """
    MySQL批量插入

    Args:
        table: 表名
        data_list: 数据列表
        client: MySQLClient实例

    Returns:
        插入的记录数
    """
    if not data_list:
        return 0

    try:
        connection = client._get_connection()
        cursor = connection.cursor()

        # 构建SQL
        columns = ', '.join(data_list[0].keys())
        placeholders = ', '.join(['%s'] * len(data_list[0]))
        sql = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"

        # 批量执行
        values = [list(data.values()) for data in data_list]
        cursor.executemany(sql, values)
        connection.commit()

        inserted_count = cursor.rowcount
        cursor.close()
        client._return_connection(connection)

        return inserted_count
    except Exception as e:
        print(f"MySQL batch insert error: {e}")
        return 0


def mysql_get_or_insert(table: str, unique_key: Dict[str, Any], insert_data: Dict[str, Any], client) -> Any:
    """
    获取或插入记录（upsert）

    Args:
        table: 表名
        unique_key: 唯一键
        insert_data: 插入数据
        client: MySQLClient实例

    Returns:
        记录ID或None
    """
    # 先查询
    existing = mysql_select(table, unique_key, client=client)

    if existing:
        return existing[0].get('id')

    # 插入
    data = {**unique_key, **insert_data}
    return mysql_insert(table, data, client)


def mysql_exists(table: str, where: Dict[str, Any], client = None) -> bool:
    """
    检查记录是否存在

    Args:
        table: 表名
        where: 查询条件
        client: MySQLClient实例

    Returns:
        是否存在
    """
    count = mysql_count(table, where, client)
    return count > 0


@contextmanager
def mysql_transaction(client):
    """
    MySQL事务上下文管理器

    Args:
        client: MySQLClient实例
    """
    connection = client._get_connection()
    connection.autocommit = False

    try:
        yield connection
        connection.commit()
    except Exception as e:
        connection.rollback()
        raise e
    finally:
        connection.autocommit = True
        client._return_connection(connection)


if __name__ == "__main__":
    logger.info("MySQL CRUD utils loaded successfully!")
