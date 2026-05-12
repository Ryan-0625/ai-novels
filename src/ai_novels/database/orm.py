"""
统一ORM模块

提供简洁、类型安全的数据库操作接口
支持模型定义、查询构建、关系映射等功能
"""

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass, field, fields
from datetime import datetime
from enum import Enum
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    Type,
    TypeVar,
    Union,
    get_type_hints,
)
import json
import sqlite3

from .connection_pool import ConnectionPool, PoolConfig
from ..core.exceptions import DatabaseError, ErrorCode
from ..utils.logger import get_logger

logger = get_logger(__name__)

T = TypeVar('T', bound='Model')


class FieldType(Enum):
    """字段类型"""
    INTEGER = "INTEGER"
    REAL = "REAL"
    TEXT = "TEXT"
    BLOB = "BLOB"
    BOOLEAN = "BOOLEAN"
    DATETIME = "DATETIME"
    JSON = "JSON"
    FOREIGN_KEY = "FOREIGN_KEY"


@dataclass
class Column:
    """列定义"""
    name: str
    field_type: FieldType
    primary_key: bool = False
    auto_increment: bool = False
    nullable: bool = True
    default: Any = None
    unique: bool = False
    index: bool = False
    foreign_key: Optional[str] = None  # "table.column"


@dataclass
class QueryResult(Generic[T]):
    """查询结果"""
    data: List[T]
    total: int
    page: int
    page_size: int
    
    @property
    def has_next(self) -> bool:
        return self.page * self.page_size < self.total
    
    @property
    def has_prev(self) -> bool:
        return self.page > 1
    
    @property
    def total_pages(self) -> int:
        return (self.total + self.page_size - 1) // self.page_size


class QueryBuilder(Generic[T]):
    """
    查询构建器
    
    提供链式调用方式构建SQL查询
    """
    
    def __init__(self, model_class: Type[T], pool: ConnectionPool):
        self.model_class = model_class
        self.pool = pool
        self.table_name = model_class.__name__.lower()
        self._where: List[tuple] = []
        self._order_by: List[tuple] = []
        self._limit: Optional[int] = None
        self._offset: Optional[int] = None
        self._joins: List[tuple] = []
        self._select: List[str] = ["*"]
    
    def where(self, **conditions) -> 'QueryBuilder[T]':
        """添加WHERE条件"""
        for key, value in conditions.items():
            if "__" in key:
                field, op = key.rsplit("__", 1)
                self._where.append((field, op.upper(), value))
            else:
                self._where.append((key, "=", value))
        return self
    
    def filter(self, condition: str, *values) -> 'QueryBuilder[T]':
        """添加原始WHERE条件"""
        self._where.append((condition, "RAW", values))
        return self
    
    def order_by(self, field: str, desc: bool = False) -> 'QueryBuilder[T]':
        """添加ORDER BY"""
        self._order_by.append((field, "DESC" if desc else "ASC"))
        return self
    
    def limit(self, n: int) -> 'QueryBuilder[T]':
        """设置LIMIT"""
        self._limit = n
        return self
    
    def offset(self, n: int) -> 'QueryBuilder[T]':
        """设置OFFSET"""
        self._offset = n
        return self
    
    def join(
        self,
        table: str,
        on: str,
        join_type: str = "INNER"
    ) -> 'QueryBuilder[T]':
        """添加JOIN"""
        self._joins.append((join_type, table, on))
        return self
    
    def select(self, *fields: str) -> 'QueryBuilder[T]':
        """选择特定字段"""
        self._select = list(fields)
        return self
    
    def _build_query(self) -> tuple:
        """构建SQL查询"""
        # SELECT
        sql = f"SELECT {', '.join(self._select)} FROM {self.table_name}"
        params = []
        
        # JOIN
        for join_type, table, on in self._joins:
            sql += f" {join_type} JOIN {table} ON {on}"
        
        # WHERE
        if self._where:
            conditions = []
            for item in self._where:
                if item[1] == "RAW":
                    conditions.append(item[0])
                    params.extend(item[2])
                elif item[1] == "=":
                    conditions.append(f"{item[0]} = ?")
                    params.append(item[2])
                elif item[1] == "IN":
                    placeholders = ', '.join(['?' for _ in item[2]])
                    conditions.append(f"{item[0]} IN ({placeholders})")
                    params.extend(item[2])
                elif item[1] in ("LIKE", "GT", "LT", "GTE", "LTE", "NE"):
                    op_map = {
                        "GT": ">", "LT": "<", "GTE": ">=", 
                        "LTE": "<=", "NE": "!=", "LIKE": "LIKE"
                    }
                    conditions.append(f"{item[0]} {op_map[item[1]]} ?")
                    params.append(item[2])
            sql += " WHERE " + " AND ".join(conditions)
        
        # ORDER BY
        if self._order_by:
            order_parts = [f"{f} {d}" for f, d in self._order_by]
            sql += " ORDER BY " + ", ".join(order_parts)
        
        # LIMIT/OFFSET
        if self._limit is not None:
            sql += f" LIMIT {self._limit}"
        if self._offset is not None:
            sql += f" OFFSET {self._offset}"
        
        return sql, params
    
    async def count(self) -> int:
        """获取总数"""
        sql, params = self._build_query()
        sql = sql.replace(f"SELECT {', '.join(self._select)}", "SELECT COUNT(*)")
        
        async with self.pool.acquire() as conn:
            cursor = await conn.execute(sql, params)
            row = await cursor.fetchone()
            return row[0] if row else 0
    
    async def exists(self) -> bool:
        """检查是否存在"""
        return await self.count() > 0
    
    async def first(self) -> Optional[T]:
        """获取第一条记录"""
        self._limit = 1
        results = await self.all()
        return results[0] if results else None
    
    async def all(self) -> List[T]:
        """获取所有记录"""
        sql, params = self._build_query()
        
        async with self.pool.acquire() as conn:
            cursor = await conn.execute(sql, params)
            rows = await cursor.fetchall()
            
            results = []
            for row in rows:
                instance = self._row_to_model(row, cursor)
                results.append(instance)
            return results
    
    async def paginate(self, page: int = 1, page_size: int = 20) -> QueryResult[T]:
        """分页查询"""
        total = await self.count()
        self._offset = (page - 1) * page_size
        self._limit = page_size
        data = await self.all()
        
        return QueryResult(
            data=data,
            total=total,
            page=page,
            page_size=page_size
        )
    
    async def delete(self) -> int:
        """删除匹配的记录"""
        sql = f"DELETE FROM {self.table_name}"
        params = []
        
        if self._where:
            conditions = []
            for item in self._where:
                if item[1] == "=":
                    conditions.append(f"{item[0]} = ?")
                    params.append(item[2])
            sql += " WHERE " + " AND ".join(conditions)
        
        async with self.pool.acquire() as conn:
            cursor = await conn.execute(sql, params)
            return cursor.rowcount
    
    async def update(self, **values) -> int:
        """更新匹配的记录"""
        if not values:
            return 0
        
        sql = f"UPDATE {self.table_name} SET "
        set_parts = []
        params = []
        
        for key, value in values.items():
            set_parts.append(f"{key} = ?")
            params.append(self._serialize_value(value))
        
        sql += ", ".join(set_parts)
        
        if self._where:
            conditions = []
            for item in self._where:
                if item[1] == "=":
                    conditions.append(f"{item[0]} = ?")
                    params.append(item[2])
            sql += " WHERE " + " AND ".join(conditions)
        
        async with self.pool.acquire() as conn:
            cursor = await conn.execute(sql, params)
            return cursor.rowcount
    
    def _row_to_model(self, row: tuple, cursor) -> T:
        """将行转换为模型实例"""
        columns = [desc[0] for desc in cursor.description]
        data = dict(zip(columns, row))
        return self.model_class.from_dict(data)
    
    def _serialize_value(self, value: Any) -> Any:
        """序列化值"""
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False)
        return value


class Model:
    """
    基础模型类
    
    所有数据模型都应继承此类
    """
    
    _id: Optional[int] = None
    _created_at: Optional[datetime] = None
    _updated_at: Optional[datetime] = None
    _pool: Optional[ConnectionPool] = None
    
    @classmethod
    def set_pool(cls, pool: ConnectionPool):
        """设置连接池"""
        cls._pool = pool
    
    @classmethod
    def get_columns(cls) -> List[Column]:
        """获取列定义"""
        columns = []
        type_hints = get_type_hints(cls)
        
        for field_name, field_type in type_hints.items():
            if field_name.startswith('_'):
                continue
            
            col = Column(name=field_name, field_type=cls._python_type_to_sql(field_type))
            
            # 处理可选类型
            if hasattr(field_type, '__origin__') and field_type.__origin__ is Union:
                args = field_type.__args__
                if type(None) in args:
                    col.nullable = True
                    field_type = [a for a in args if a is not type(None)][0]
            
            # ID字段特殊处理
            if field_name == 'id':
                col.primary_key = True
                col.auto_increment = True
                col.nullable = False
            
            columns.append(col)
        
        return columns
    
    @classmethod
    def _python_type_to_sql(cls, py_type: Type) -> FieldType:
        """Python类型映射到SQL类型"""
        type_map = {
            int: FieldType.INTEGER,
            float: FieldType.REAL,
            str: FieldType.TEXT,
            bool: FieldType.BOOLEAN,
            datetime: FieldType.DATETIME,
            bytes: FieldType.BLOB,
        }
        
        # 处理Optional
        if hasattr(py_type, '__origin__') and py_type.__origin__ is Union:
            args = py_type.__args__
            py_type = [a for a in args if a is not type(None)][0]
        
        # 处理List/Dict作为JSON
        if hasattr(py_type, '__origin__'):
            if py_type.__origin__ in (list, dict):
                return FieldType.JSON
        
        return type_map.get(py_type, FieldType.TEXT)
    
    @classmethod
    def from_dict(cls: Type[T], data: Dict[str, Any]) -> T:
        """从字典创建实例"""
        # 处理JSON字段
        type_hints = get_type_hints(cls)
        processed = {}
        
        for key, value in data.items():
            if key in type_hints:
                hint = type_hints[key]
                if hint in (dict, list) or (
                    hasattr(hint, '__origin__') and 
                    hint.__origin__ in (dict, list)
                ):
                    if isinstance(value, str):
                        try:
                            value = json.loads(value)
                        except json.JSONDecodeError:
                            logger.warning("ORM: failed to parse JSON for field %s=%r", key, value[:50])
                elif hint == datetime and isinstance(value, str):
                    try:
                        value = datetime.fromisoformat(value)
                    except ValueError:
                        logger.warning("ORM: failed to parse datetime for field %s=%r", key, value)
            processed[key] = value
        
        instance = cls(**processed)
        
        # 设置元数据
        if '_id' in data or 'id' in data:
            instance._id = data.get('_id') or data.get('id')
        if '_created_at' in data:
            instance._created_at = data['_created_at']
        if '_updated_at' in data:
            instance._updated_at = data['_updated_at']
        
        return instance
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result = {}
        type_hints = get_type_hints(self.__class__)
        
        for field_name in type_hints.keys():
            if field_name.startswith('_'):
                continue
            value = getattr(self, field_name, None)
            result[field_name] = value
        
        return result
    
    @property
    def id(self) -> Optional[int]:
        return self._id
    
    @property
    def created_at(self) -> Optional[datetime]:
        return self._created_at
    
    @property
    def updated_at(self) -> Optional[datetime]:
        return self._updated_at
    
    @classmethod
    def query(cls: Type[T]) -> QueryBuilder[T]:
        """开始查询"""
        if not cls._pool:
            raise DatabaseError(
                ErrorCode.DB_POOL_NOT_INITIALIZED,
                "Connection pool not set. Call set_pool() first."
            )
        return QueryBuilder(cls, cls._pool)
    
    async def save(self) -> 'Model':
        """保存实例"""
        if not self._pool:
            raise DatabaseError(
                ErrorCode.DB_POOL_NOT_INITIALIZED,
                "Connection pool not set"
            )
        
        table_name = self.__class__.__name__.lower()
        columns = self.get_columns()
        data = self.to_dict()
        
        if self._id is None:
            # INSERT
            fields = [c.name for c in columns if not c.auto_increment]
            values = [self._serialize_value(data.get(f)) for f in fields]
            placeholders = ', '.join(['?' for _ in fields])
            
            sql = f"INSERT INTO {table_name} ({', '.join(fields)}) VALUES ({placeholders})"
            
            async with self._pool.acquire() as conn:
                cursor = await conn.execute(sql, values)
                self._id = cursor.lastrowid
                self._created_at = datetime.now()
        else:
            # UPDATE
            fields = [c.name for c in columns if not c.primary_key]
            values = [self._serialize_value(data.get(f)) for f in fields]
            values.append(self._id)
            
            set_clause = ', '.join([f"{f} = ?" for f in fields])
            sql = f"UPDATE {table_name} SET {set_clause} WHERE id = ?"
            
            async with self._pool.acquire() as conn:
                await conn.execute(sql, values)
                self._updated_at = datetime.now()
        
        return self
    
    async def delete(self) -> bool:
        """删除实例"""
        if not self._id:
            return False
        
        table_name = self.__class__.__name__.lower()
        
        async with self._pool.acquire() as conn:
            cursor = await conn.execute(
                f"DELETE FROM {table_name} WHERE id = ?",
                (self._id,)
            )
            return cursor.rowcount > 0
    
    def _serialize_value(self, value: Any) -> Any:
        """序列化值"""
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False)
        return value
    
    @classmethod
    async def create_table(cls, pool: ConnectionPool):
        """创建表"""
        table_name = cls.__name__.lower()
        columns = cls.get_columns()
        
        col_defs = []
        for col in columns:
            def_str = f"{col.name} {col.field_type.value}"
            if col.primary_key:
                def_str += " PRIMARY KEY"
            if col.auto_increment:
                def_str += " AUTOINCREMENT"
            if not col.nullable:
                def_str += " NOT NULL"
            if col.unique:
                def_str += " UNIQUE"
            if col.default is not None:
                def_str += f" DEFAULT {col.default}"
            col_defs.append(def_str)
        
        sql = f"CREATE TABLE IF NOT EXISTS {table_name} ({', '.join(col_defs)})"
        
        async with pool.acquire() as conn:
            await conn.execute(sql)
            
            # 创建索引
            for col in columns:
                if col.index:
                    await conn.execute(
                        f"CREATE INDEX IF NOT EXISTS idx_{table_name}_{col.name} "
                        f"ON {table_name}({col.name})"
                    )
        
        logger.info(f"Created table: {table_name}")
    
    @classmethod
    async def drop_table(cls, pool: ConnectionPool):
        """删除表"""
        table_name = cls.__name__.lower()
        async with pool.acquire() as conn:
            await conn.execute(f"DROP TABLE IF EXISTS {table_name}")
        logger.info(f"Dropped table: {table_name}")


class Database:
    """
    数据库管理器
    
    统一管理连接池和模型
    """
    
    def __init__(self, db_path: str, pool_size: int = 10):
        self.db_path = db_path
        self.pool = ConnectionPool(
            lambda: sqlite3.connect(db_path),
            PoolConfig(max_size=pool_size)
        )
        self._models: List[Type[Model]] = []
    
    async def connect(self):
        """连接数据库"""
        await self.pool.initialize()
        logger.info(f"Connected to database: {self.db_path}")
    
    async def disconnect(self):
        """断开连接"""
        await self.pool.close()
        logger.info("Disconnected from database")
    
    def register_model(self, model_class: Type[Model]):
        """注册模型"""
        model_class.set_pool(self.pool)
        self._models.append(model_class)
    
    async def create_tables(self):
        """创建所有表"""
        for model in self._models:
            await model.create_table(self.pool)
    
    async def drop_tables(self):
        """删除所有表"""
        for model in self._models:
            await model.drop_table(self.pool)
    
    @asynccontextmanager
    async def transaction(self):
        """事务上下文"""
        async with self.pool.acquire() as conn:
            await conn.execute("BEGIN")
            try:
                yield conn
                await conn.execute("COMMIT")
            except Exception as e:
                await conn.execute("ROLLBACK")
                raise


# 便捷函数
def create_model(name: str, fields: Dict[str, Type]) -> Type[Model]:
    """
    动态创建模型类
    
    Args:
        name: 模型名称
        fields: 字段名到类型的映射
    
    Returns:
        模型类
    """
    return type(name, (Model,), {"__annotations__": fields})
