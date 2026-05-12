"""
数据库基类定义

@file: database/base.py
@date: 2026-03-12
@author: AI-Novels Team
@version: 1.0
@description: 定义所有数据库客户端的统一接口基类
"""

from abc import ABC, abstractmethod
from typing import Any, List, Optional, Dict
from contextlib import contextmanager


class DatabaseBase(ABC):
    """
    数据库基类，定义所有数据库客户端的统一接口

    所有数据库客户端（MySQL, Neo4j, MongoDB, ChromaDB）都应继承此类
    实现统一的连接管理、事务处理和基本操作接口
    """

    @abstractmethod
    def connect(self) -> bool:
        """
        建立数据库连接

        Returns:
            bool: 连接成功返回True，否则返回False
        """
        pass

    @abstractmethod
    def disconnect(self) -> bool:
        """
        断开数据库连接

        Returns:
            bool: 断开成功返回True，否则返回False
        """
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """
        检查数据库是否已连接

        Returns:
            bool: 已连接返回True，否则返回False
        """
        pass

    @abstractmethod
    def health_check(self) -> dict:
        """
        数据库健康检查

        Returns:
            dict: 健康检查结果，包含以下字段:
                - status: 'healthy' | 'unhealthy' | 'degraded'
                - latency_ms: int
                - details: dict
        """
        pass

    @abstractmethod
    def close(self) -> None:
        """
        关闭数据库连接（与disconnect语义相同，用于with语句）
        """
        pass

    @contextmanager
    def session(self):
        """
        上下文管理器，用于自动管理连接生命周期

        Usage:
            with db.session() as s:
                result = s.query("MATCH (n) RETURN n")
        """
        try:
            self.connect()
            yield self
        finally:
            self.close()


class CRUDInterface(ABC):
    """
    CRUD接口基类，定义标准的增删改查操作

    适用于支持CRUD操作的数据库（MongoDB, MySQL）
    """

    @abstractmethod
    def create(self, collection: str, document: Dict[str, Any]) -> Optional[str]:
        """
        创建单条记录

        Args:
            collection: 集合/表名
            document: 要插入的数据字典

        Returns:
            str: 插入记录的ID，失败返回None
        """
        pass

    @abstractmethod
    def read(self, collection: str, query: Dict[str, Any],
             limit: int = 0) -> List[Dict[str, Any]]:
        """
        读取记录

        Args:
            collection: 集合/表名
            query: 查询条件字典
            limit: 限制返回数量（0为不限制）

        Returns:
            List[Dict[str, Any]]: 查询结果列表
        """
        pass

    @abstractmethod
    def update(self, collection: str, query: Dict[str, Any],
               updates: Dict[str, Any], upsert: bool = False) -> bool:
        """
        更新记录

        Args:
            collection: 集合/表名
            query: 查询条件字典
            updates: 更新数据字典
            upsert: 查询不到时是否插入

        Returns:
            bool: 更新成功返回True，否则返回False
        """
        pass

    @abstractmethod
    def delete(self, collection: str, query: Dict[str, Any]) -> int:
        """
        删除记录

        Args:
            collection: 集合/表名
            query: 查询条件字典

        Returns:
            int: 删除的记录数量
        """
        pass

    @abstractmethod
    def count(self, collection: str, query: Dict[str, Any] = None) -> int:
        """
        计数

        Args:
            collection: 集合/表名
            query: 查询条件字典

        Returns:
            int: 记录数量
        """
        pass


class GraphInterface(ABC):
    """
    图数据库接口基类，定义图操作相关方法

    适用于Neo4j等图数据库
    """

    @abstractmethod
    def create_node(self, label: str, properties: Dict[str, Any]) -> Dict[str, Any]:
        """
        创建节点

        Args:
            label: 节点标签
            properties: 节点属性

        Returns:
            Dict[str, Any]: 创建的节点
        """
        pass

    @abstractmethod
    def find_nodes(self, label: str, property_name: str,
                   value: Any) -> List[Dict[str, Any]]:
        """
        查找节点

        Args:
            label: 节点标签
            property_name: 属性名
            value: 属性值

        Returns:
            List[Dict[str, Any]]: 节点列表
        """
        pass

    @abstractmethod
    def create_relationship(self, from_label: str, from_id: Any, from_prop: str,
                            to_label: str, to_id: Any, to_prop: str,
                            rel_type: str, properties: Dict[str, Any] = None) -> bool:
        """
        创建关系

        Args:
            from_label: 起始节点标签
            from_id: 起始节点ID
            from_prop: 起始节点属性名
            to_label: 目标节点标签
            to_id: 目标节点ID
            to_prop: 目标节点属性名
            rel_type: 关系类型
            properties: 关系属性

        Returns:
            bool: 创建成功返回True，否则返回False
        """
        pass

    @abstractmethod
    def traverse(self, start_node: Dict[str, Any], rel_types: List[str],
                 max_depth: int) -> List[Dict[str, Any]]:
        """
        图遍历

        Args:
            start_node: 起始节点
            rel_types: 关系类型列表
            max_depth: 最大深度

        Returns:
            List[Dict[str, Any]]: 遍历结果
        """
        pass

    @abstractmethod
    def execute_cypher(self, cypher: str, params: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        执行Cypher查询

        Args:
            cypher: Cypher查询语句
            params: 参数字典

        Returns:
            List[Dict[str, Any]]: 查询结果
        """
        pass


class VectorInterface(ABC):
    """
    向量数据库接口基类，定义向量搜索相关方法

    适用于ChromaDB等向量数据库
    """

    @abstractmethod
    def add(self, collection: str, ids: List[str], documents: List[str],
            metadatas: List[Dict[str, Any]] = None) -> None:
        """
        添加向量

        Args:
            collection: 集合名
            ids: ID列表
            documents: 文本列表
            metadatas: 元数据列表
        """
        pass

    @abstractmethod
    def query(self, collection: str, query_texts: List[str], n_results: int = 5,
              where: Dict[str, Any] = None) -> Dict[str, Any]:
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
        pass

    @abstractmethod
    def get(self, collection: str, ids: List[str] = None,
            limit: int = 0) -> Dict[str, Any]:
        """
        按ID获取文档

        Args:
            collection: 集合名
            ids: ID列表
            limit: 限制条数

        Returns:
            Dict[str, Any]: 文档字典
        """
        pass

    @abstractmethod
    def delete(self, collection: str, ids: List[str] = None,
               where: Dict[str, Any] = None) -> None:
        """
        删除向量

        Args:
            collection: 集合名
            ids: ID列表
            where: 元数据过滤条件
        """
        pass


# 类型别名，方便使用
DatabaseClient = DatabaseBase
CRUDDatabase = CRUDInterface
GraphDatabase = GraphInterface
VectorDatabase = VectorInterface
