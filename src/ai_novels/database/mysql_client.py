"""
MySQL客户端实现

@file: database/mysql_client.py
@date: 2026-03-12
@author: AI-Novels Team
@version: 1.0
@description: MySQL数据库客户端实现，支持连接池和CRUD操作
"""

import mysql.connector
from mysql.connector import pooling, Error
from typing import Any, Dict, List, Optional, Tuple, Union, Callable, Tuple
from contextlib import contextmanager

from ..config.manager import settings
from .base import DatabaseBase, CRUDInterface
from ..utils import log_info, log_error, get_logger


class MySQLClient(DatabaseBase, CRUDInterface):
    """
    MySQL数据库客户端实现

    特性:
    - 连接池管理
    - 自动健康检查
    - 事务支持
    - 上下文管理
    """

    def __init__(
        self,
        host: str = None,
        port: int = None,
        user: str = None,
        password: str = None,
        database: str = None,
        pool_name: str = None,
        pool_size: int = None,
        pool_reset_session: bool = True,
        config: Dict[str, Any] = None
    ):
        """
        初始化MySQL客户端

        Args:
            host: 数据库主机地址
            port: 数据库端口
            user: 数据库用户名
            password: 数据库密码
            database: 数据库名称
            pool_name: 连接池名称
            pool_size: 连接池大小
            pool_reset_session:是否重置会话
            config: 数据库配置字典，优先级最高
        """
        # 优先使用传入的配置字典
        if config:
            self._host = config.get("host", "localhost")
            self._port = config.get("port", 3306)
            self._user = config.get("user", "root")
            self._password = config.get("password", "")
            self._database = config.get("database", "ai_novels")
            self._pool_name = config.get("pool_name", "ai_novels_pool")
            self._pool_size = config.get("pool_size", 5)
        else:
            # 从全局配置管理器读取
            db_config = settings.get_database("mysql")
            self._host = host or db_config.get("host", "localhost")
            self._port = port or db_config.get("port", 3306)
            self._user = user or db_config.get("user", "root")
            self._password = password or db_config.get("password", "")
            self._database = database or db_config.get("database", "ai_novels")
            self._pool_name = pool_name or db_config.get("pool_name", "ai_novels_pool")
            self._pool_size = pool_size or db_config.get("max_connections", 5)

        self._pool_reset_session = pool_reset_session

        self._logger = get_logger()
        self._logger.database(f"MySQL configured: {self._host}:{self._port}/{self._database} [pool_size={self._pool_size}]")

        self._pool: Optional[mysql.connector.pooling.MySQLConnectionPool] = None
        self._is_connected = False

    def connect(self) -> bool:
        """
        建立数据库连接池

        Returns:
            bool: 连接成功返回True，否则返回False
        """
        try:
            self._logger.database_debug(f"MySQL connecting: {self._host}:{self._port}/{self._database}")
            self._pool = pooling.MySQLConnectionPool(
                host=self._host,
                port=self._port,
                user=self._user,
                password=self._password,
                database=self._database,
                pool_name=self._pool_name,
                pool_size=self._pool_size,
                pool_reset_session=self._pool_reset_session,
                charset='utf8mb4',
                collation='utf8mb4_unicode_ci',
                autocommit=False
            )
            self._is_connected = True
            self._logger.database(f"MySQL connected: {self._host}:{self._port}/{self._database} [pool_size={self._pool_size}]")
            return True
        except Error as e:
            self._is_connected = False
            return False

    def disconnect(self) -> bool:
        """
        断开数据库连接池

        Returns:
            bool: 断开成功返回True，否则返回False
        """
        try:
            if self._pool:
                self._pool.disconnect()
            self._is_connected = False
            return True
        except Error:
            self._is_connected = False
            return False

    def is_connected(self) -> bool:
        """
        检查数据库是否已连接

        Returns:
            bool: 已连接返回True，否则返回False
        """
        if not self._pool:
            return False

        try:
            conn = self._pool.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
            conn.close()
            return True
        except Error:
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
                        "latency_ms": 0,
                        "details": {"error": "Failed to connect to database"}
                    }

            conn = self._pool.get_connection()
            cursor = conn.cursor()

            # 检查表存在
            cursor.execute("SHOW TABLES")
            tables = [row[0] for row in cursor.fetchall()]

            # 检查连接池状态
            cursor.execute("SHOW STATUS LIKE 'Threads_connected'")
            threads_connected = cursor.fetchone()[1]

            cursor.close()
            conn.close()

            latency_ms = int((time.time() - start_time) * 1000)

            return {
                "status": "healthy",
                "latency_ms": latency_ms,
                "details": {
                    "tables": tables,
                    "threads_connected": int(threads_connected),
                    "pool_size": self._pool_size,
                    "pool_name": self._pool_name
                }
            }

        except Error as e:
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

    @contextmanager
    def get_connection(self):
        """
        获取连接的上下文管理器

        Usage:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM table")
                result = cursor.fetchall()
        """
        conn = None
        try:
            conn = self._pool.get_connection()
            yield conn
        finally:
            if conn:
                conn.close()

    @contextmanager
    def get_cursor(self):
        """
        获取游标的上下文管理器（自动提交）

        Usage:
            with db.get_cursor() as cursor:
                cursor.execute("SELECT * FROM table")
                result = cursor.fetchall()
        """
        conn = None
        cursor = None
        try:
            conn = self._pool.get_connection()
            cursor = conn.cursor(dictionary=True)
            yield cursor
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    # CRUD Interface Implementation
    def create(self, collection: str, document: Dict[str, Any]) -> Optional[str]:
        """
        创建单条记录（插入）

        Args:
            collection: 表名
            document: 要插入的数据字典

        Returns:
            str: 插入记录的ID（自增主键），失败返回None
        """
        with self.get_cursor() as cursor:
            try:
                columns = list(document.keys())
                values = list(document.values())

                placeholders = ", ".join(["%s"] * len(columns))
                columns_str = ", ".join([f"`{col}`" for col in columns])

                query = f"INSERT INTO `{collection}` ({columns_str}) VALUES ({placeholders})"
                cursor.execute(query, values)

                # 获取自增ID
                cursor.execute("SELECT LAST_INSERT_ID()")
                result = cursor.fetchone()
                insert_id = result.get('LAST_INSERT_ID()') if result else None

                cursor.execute("COMMIT")
                return str(insert_id) if insert_id else None

            except Error as e:
                cursor.execute("ROLLBACK")
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
            collection: 表名
            query: 查询条件字典
            limit: 限制返回数量（0为不限制）

        Returns:
            List[Dict[str, Any]]: 查询结果列表
        """
        with self.get_cursor() as cursor:
            try:
                if not query:
                    sql = f"SELECT * FROM `{collection}`"
                    params = []
                else:
                    conditions = []
                    params = []

                    for key, value in query.items():
                        if isinstance(value, dict):
                            # 支持复杂查询操作符
                            for op, val in value.items():
                                if op == "$gt":
                                    conditions.append(f"`{key}` > %s")
                                    params.append(val)
                                elif op == "$gte":
                                    conditions.append(f"`{key}` >= %s")
                                    params.append(val)
                                elif op == "$lt":
                                    conditions.append(f"`{key}` < %s")
                                    params.append(val)
                                elif op == "$lte":
                                    conditions.append(f"`{key}` <= %s")
                                    params.append(val)
                                elif op == "$ne":
                                    conditions.append(f"`{key}` != %s")
                                    params.append(val)
                                elif op == "$in":
                                    placeholders = ", ".join(["%s"] * len(val))
                                    conditions.append(f"`{key}` IN ({placeholders})")
                                    params.extend(val)
                        else:
                            conditions.append(f"`{key}` = %s")
                            params.append(value)

                    where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
                    sql = f"SELECT * FROM `{collection}`{where_clause}"

                # 添加LIMIT
                if limit > 0:
                    sql += f" LIMIT %s"
                    params.append(limit)

                cursor.execute(sql, params)
                result = cursor.fetchall()
                return result

            except Error:
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
            collection: 表名
            query: 查询条件字典
            updates: 更新数据字典
            upsert: 查询不到时是否插入

        Returns:
            bool: 更新成功返回True，否则返回False
        """
        with self.get_cursor() as cursor:
            try:
                # 构建SET语句
                set_parts = []
                set_values = []
                for key, value in updates.items():
                    set_parts.append(f"`{key}` = %s")
                    set_values.append(value)

                # 构建WHERE语句
                where_parts = []
                where_values = []
                for key, value in query.items():
                    if isinstance(value, dict):
                        for op, val in value.items():
                            if op == "$gt":
                                where_parts.append(f"`{key}` > %s")
                                where_values.append(val)
                            elif op == "$gte":
                                where_parts.append(f"`{key}` >= %s")
                                where_values.append(val)
                            elif op == "$lt":
                                where_parts.append(f"`{key}` < %s")
                                where_values.append(val)
                            elif op == "$lte":
                                where_parts.append(f"`{key}` <= %s")
                                where_values.append(val)
                            elif op == "$ne":
                                where_parts.append(f"`{key}` != %s")
                                where_values.append(val)
                            elif op == "$in":
                                placeholders = ", ".join(["%s"] * len(val))
                                where_parts.append(f"`{key}` IN ({placeholders})")
                                where_values.extend(val)
                    else:
                        where_parts.append(f"`{key}` = %s")
                        where_values.append(value)

                set_clause = ", ".join(set_parts)
                where_clause = " WHERE " + " AND ".join(where_parts) if where_parts else ""

                sql = f"UPDATE `{collection}` SET {set_clause}{where_clause}"
                params = set_values + where_values

                cursor.execute(sql, params)
                affected_rows = cursor.rowcount

                # 如果没有匹配行且upsert为True，则插入
                if affected_rows == 0 and upsert:
                    all_values = list(updates.values())
                    if query:
                        all_values.extend(query.values())

                    columns = list(updates.keys())
                    if query:
                        columns.extend(list(query.keys()))

                    placeholders = ", ".join(["%s"] * len(columns))
                    columns_str = ", ".join([f"`{col}`" for col in columns])

                    insert_sql = f"INSERT INTO `{collection}` ({columns_str}) VALUES ({placeholders})"
                    cursor.execute(insert_sql, all_values)
                    affected_rows = 1

                cursor.execute("COMMIT")
                return affected_rows > 0

            except Error:
                cursor.execute("ROLLBACK")
                return False

    def delete(self, collection: str, query: Dict[str, Any]) -> int:
        """
        删除记录

        Args:
            collection: 表名
            query: 查询条件字典

        Returns:
            int: 删除的记录数量
        """
        with self.get_cursor() as cursor:
            try:
                where_parts = []
                params = []

                for key, value in query.items():
                    if isinstance(value, dict):
                        for op, val in value.items():
                            if op == "$gt":
                                where_parts.append(f"`{key}` > %s")
                                params.append(val)
                            elif op == "$gte":
                                where_parts.append(f"`{key}` >= %s")
                                params.append(val)
                            elif op == "$lt":
                                where_parts.append(f"`{key}` < %s")
                                params.append(val)
                            elif op == "$lte":
                                where_parts.append(f"`{key}` <= %s")
                                params.append(val)
                            elif op == "$ne":
                                where_parts.append(f"`{key}` != %s")
                                params.append(val)
                            elif op == "$in":
                                placeholders = ", ".join(["%s"] * len(val))
                                where_parts.append(f"`{key}` IN ({placeholders})")
                                params.extend(val)
                    else:
                        where_parts.append(f"`{key}` = %s")
                        params.append(value)

                where_clause = " WHERE " + " AND ".join(where_parts) if where_parts else ""
                sql = f"DELETE FROM `{collection}`{where_clause}"

                cursor.execute(sql, params)
                affected_rows = cursor.rowcount
                cursor.execute("COMMIT")

                return affected_rows

            except Error:
                cursor.execute("ROLLBACK")
                return 0

    def count(self, collection: str, query: Dict[str, Any] = None) -> int:
        """
        计数

        Args:
            collection: 表名
            query: 查询条件字典

        Returns:
            int: 记录数量
        """
        with self.get_cursor() as cursor:
            try:
                if not query:
                    sql = f"SELECT COUNT(*) as count FROM `{collection}`"
                    cursor.execute(sql)
                else:
                    where_parts = []
                    params = []

                    for key, value in query.items():
                        if isinstance(value, dict):
                            for op, val in value.items():
                                if op == "$gt":
                                    where_parts.append(f"`{key}` > %s")
                                    params.append(val)
                                elif op == "$gte":
                                    where_parts.append(f"`{key}` >= %s")
                                    params.append(val)
                                elif op == "$lt":
                                    where_parts.append(f"`{key}` < %s")
                                    params.append(val)
                                elif op == "$lte":
                                    where_parts.append(f"`{key}` <= %s")
                                    params.append(val)
                                elif op == "$ne":
                                    where_parts.append(f"`{key}` != %s")
                                    params.append(val)
                                elif op == "$in":
                                    placeholders = ", ".join(["%s"] * len(val))
                                    where_parts.append(f"`{key}` IN ({placeholders})")
                                    params.extend(val)
                        else:
                            where_parts.append(f"`{key}` = %s")
                            params.append(value)

                    where_clause = " WHERE " + " AND ".join(where_parts) if where_parts else ""
                    sql = f"SELECT COUNT(*) as count FROM `{collection}`{where_clause}"
                    cursor.execute(sql, params)

                result = cursor.fetchone()
                return result.get("count", 0) if result else 0

            except Error:
                return 0

    # AI-Novels Specific Methods
    def create_task(self, task_data: Dict[str, Any]) -> Optional[str]:
        """
        创建小说生成任务

        Args:
            task_data: 任务数据字典

        Returns:
            str: 任务ID，失败返回None
        """
        return self.create("novel_tasks", task_data)

    def update_task_status(
        self,
        task_id: str,
        status: str,
        current_stage: str = None,
        progress: float = None,
        error_message: str = None
    ) -> bool:
        """
        更新任务状态

        Args:
            task_id: 任务ID
            status: 新状态
            current_stage: 当前阶段
            progress: 进度百分比
            error_message: 错误信息

        Returns:
            bool: 更新成功返回True
        """
        updates = {"task_status": status}

        if current_stage:
            updates["current_stage"] = current_stage
        if progress is not None:
            updates["progress"] = progress
        if error_message:
            updates["error_message"] = error_message

        return self.update("novel_tasks", {"task_id": task_id}, updates)

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        获取任务详情

        Args:
            task_id: 任务ID

        Returns:
            Dict: 任务数据，不存在返回None
        """
        tasks = self.read("novel_tasks", {"task_id": task_id}, limit=1)
        return tasks[0] if tasks else None

    def insert_logs(self, logs: List[Dict[str, Any]]) -> int:
        """
        批量插入生成日志

        Args:
            logs: 日志数据列表

        Returns:
            int: 插入的记录数量
        """
        if not logs:
            return 0

        inserted = 0
        for log in logs:
            if self.create("generation_logs", log):
                inserted += 1

        return inserted

    def get_tasks_by_status(
        self,
        status: str,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        根据状态获取任务列表

        Args:
            status: 任务状态
            limit: 返回数量限制

        Returns:
            List[Dict]: 任务列表
        """
        return self.read("novel_tasks", {"task_status": status}, limit=limit)

    def get_tasks_by_user(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        获取用户的所有任务

        Args:
            user_id: 用户ID
            limit: 返回数量限制

        Returns:
            List[Dict]: 任务列表
        """
        return self.read("novel_tasks", {"user_id": user_id}, limit=limit)

    def test_connection(self) -> bool:
        """
        测试数据库连接（简化方法）

        Returns:
            bool: 连接成功返回True
        """
        return self.health_check()["status"] == "healthy"
