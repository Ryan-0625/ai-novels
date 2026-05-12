"""
Neo4j客户端实现

@file: database/neo4j_client.py
@date: 2026-03-12
@author: AI-Novels Team
@version: 1.0
@description: Neo4j图数据库客户端实现，支持Cypher查询和图操作
"""

from neo4j import GraphDatabase, Driver, Result, Transaction
from neo4j.exceptions import Neo4jError
from typing import Any, Dict, List, Optional, Tuple
from contextlib import contextmanager

from ..config.manager import settings
from .base import DatabaseBase, GraphInterface


class Neo4jClient(DatabaseBase, GraphInterface):
    """
    Neo4j图数据库客户端实现

    特性:
    - 连接池管理（内置）
    - Cypher查询支持
    - 事务处理
    - 图遍历操作
    """

    def __init__(
        self,
        uri: str = None,
        user: str = None,
        password: str = None,
        database: str = None,
        encrypted: bool = False,
        config: Dict[str, Any] = None
    ):
        """
        初始化Neo4j客户端

        Args:
            uri: Neo4j连接URI (bolt:// 或 neo4j://)
            user: 数据库用户名
            password: 数据库密码
            database: 数据库名称
            encrypted: 是否启用加密
            config: 数据库配置字典，优先级最高
        """
        # 优先使用传入的配置字典
        if config:
            self._uri = config.get("uri", "bolt://localhost:7687")
            self._user = config.get("user", "neo4j")
            self._password = config.get("password", "")
            self._database = config.get("database", "neo4j")
            self._encrypted = config.get("encrypted", False)
        else:
            # 从全局配置管理器读取
            db_config = settings.get_database("neo4j")
            self._uri = uri or db_config.get("uri", "bolt://localhost:7687")
            self._user = user or db_config.get("user", "neo4j")
            self._password = password or db_config.get("password", "")
            self._database = database or db_config.get("database", "neo4j")
            self._encrypted = encrypted

        self._driver: Optional[Driver] = None
        self._is_connected = False

    def connect(self) -> bool:
        """
        建立数据库连接

        Returns:
            bool: 连接成功返回True，否则返回False
        """
        try:
            self._driver = GraphDatabase.driver(
                self._uri,
                auth=(self._user, self._password),
                encrypted=self._encrypted
            )
            # 测试连接
            self._is_connected = self._verify_connectivity()
            return self._is_connected
        except Neo4jError:
            self._is_connected = False
            return False

    def disconnect(self) -> bool:
        """
        断开数据库连接

        Returns:
            bool: 断开成功返回True，否则返回False
        """
        try:
            if self._driver:
                self._driver.close()
            self._is_connected = False
            return True
        except Exception:
            self._is_connected = False
            return False

    def is_connected(self) -> bool:
        """
        检查数据库是否已连接

        Returns:
            bool: 已连接返回True，否则返回False
        """
        if not self._driver:
            return False
        return self._verify_connectivity()

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

            with self._driver.session(database=self._database) as session:
                # 执行简单的查询
                result = session.run("RETURN 1 AS value")
                record = result.single()
                value = record["value"] if record else None

                # 获取数据库信息
                info_result = session.run("CALL db.info()")
                info = info_result.single()

                latency_ms = int((time.time() - start_time) * 1000)

                return {
                    "status": "healthy",
                    "latency_ms": latency_ms,
                    "details": {
                        "database": self._database,
                        "test_result": value
                    }
                }

        except Neo4jError as e:
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

    def _verify_connectivity(self) -> bool:
        """
        验证连接是否有效

        Returns:
            bool: 连接有效返回True
        """
        if not self._driver:
            return False

        try:
            with self._driver.session() as session:
                result = session.run("RETURN 1 AS value")
                return result.single() is not None
        except Exception:
            return False

    @contextmanager
    def session(self):
        """
        获取会话的上下文管理器

        Usage:
            with db.session() as session:
                result = session.run("MATCH (n) RETURN n")
        """
        session = None
        try:
            session = self._driver.session(database=self._database)
            yield session
        finally:
            if session:
                session.close()

    # Graph Interface Implementation
    def create_node(self, label: str, properties: Dict[str, Any]) -> Dict[str, Any]:
        """
        创建节点

        Args:
            label: 节点标签
            properties: 节点属性

        Returns:
            Dict: 创建的节点
        """
        with self.session() as session:
            try:
                # 构建属性SET子句
                props = ", ".join([f"{k}: ${k}" for k in properties.keys()])

                query = f"""
                    CREATE (n:{label} {{ {props} }})
                    RETURN n
                """

                result = session.run(query, **properties)
                record = result.single()

                if record:
                    node = record["n"]
                    return {
                        "id": node.element_id,
                        "labels": list(node.labels),
                        "properties": dict(node.items())
                    }
                return {}

            except Neo4jError as e:
                return {"error": str(e)}

    def find_nodes(self, label: str, property_name: str, value: Any) -> List[Dict[str, Any]]:
        """
        查找节点

        Args:
            label: 节点标签
            property_name: 属性名
            value: 属性值

        Returns:
            List[Dict]: 节点列表
        """
        with self.session() as session:
            try:
                query = f"""
                    MATCH (n:{label} {{ {property_name}: $value }})
                    RETURN n
                """

                result = session.run(query, value=value)
                nodes = []

                for record in result:
                    node = record["n"]
                    nodes.append({
                        "id": node.element_id,
                        "labels": list(node.labels),
                        "properties": dict(node.items())
                    })

                return nodes

            except Neo4jError:
                return []

    def create_relationship(
        self,
        from_label: str,
        from_id: Any,
        from_prop: str,
        to_label: str,
        to_id: Any,
        to_prop: str,
        rel_type: str,
        properties: Dict[str, Any] = None
    ) -> bool:
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
            bool: 创建成功返回True
        """
        with self.session() as session:
            try:
                props = ""
                if properties:
                    props = ", ".join([f"{k}: ${k}" for k in properties.keys()])
                    props = ", {" + props + "}"

                query = f"""
                    MATCH (a:{from_label} {{ {from_prop}: $from_id }}),
                          (b:{to_label} {{ {to_prop}: $to_id }})
                    CREATE (a)-[r:{rel_type}{props}]->(b)
                    RETURN r
                """

                params = {"from_id": from_id, "to_id": to_id}
                if properties:
                    params.update(properties)

                result = session.run(query, **params)
                record = result.single()

                return record is not None

            except Neo4jError:
                return False

    def traverse(
        self,
        start_node: Dict[str, Any],
        rel_types: List[str],
        max_depth: int
    ) -> List[Dict[str, Any]]:
        """
        图遍历

        Args:
            start_node: 起始节点(包含id和labels)
            rel_types: 关系类型列表
            max_depth: 最大深度

        Returns:
            List[Dict]: 遍历结果
        """
        with self.session() as session:
            try:
                # 构建关系类型列表
                rel_patterns = "|".join(rel_types) if rel_types else "*"

                query = f"""
                    MATCH (start {{"id": $node_id}})
                    WHERE any(label IN labels(start) WHERE label IN $labels)
                    CALL apoc.path.expandConfig(start, {{
                        relationshipFilter: "{rel_patterns}>",
                        maxLevel: $max_depth
                    }})
                    YIELD path
                    RETURN nodes(path) as path_nodes, relationships(path) as path_rels
                """

                result = session.run(
                    query,
                    node_id=start_node.get("id"),
                    labels=start_node.get("labels", []),
                    max_depth=max_depth
                )

                results = []
                for record in result:
                    path_nodes = record["path_nodes"]
                    path_rels = record["path_rels"]

                    path_data = {
                        "nodes": [],
                        "relationships": []
                    }

                    for node in path_nodes:
                        path_data["nodes"].append({
                            "id": node.element_id,
                            "labels": list(node.labels),
                            "properties": dict(node.items())
                        })

                    for rel in path_rels:
                        path_data["relationships"].append({
                            "id": rel.element_id,
                            "type": rel.type,
                            "start_node": rel.start_node.element_id,
                            "end_node": rel.end_node.element_id,
                            "properties": dict(rel.items())
                        })

                    results.append(path_data)

                return results

            except Neo4jError as e:
                return [{"error": str(e)}]

    def execute_cypher(self, cypher: str, params: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        执行Cypher查询

        Args:
            cypher: Cypher查询语句
            params: 参数字典

        Returns:
            List[Dict]: 查询结果
        """
        with self.session() as session:
            try:
                result = session.run(cypher, **params if params else {})
                records = []

                for record in result:
                    records.append(dict(record.items()))

                return records

            except Neo4jError as e:
                return [{"error": str(e)}]

    # AI-Novels Specific Methods
    def create_character_node(self, char_data: Dict[str, Any]) -> Optional[str]:
        """
        创建角色节点

        Args:
            char_data: 角色数据

        Returns:
            str: 节点ID
        """
        node = self.create_node("Character", char_data)
        return node.get("id") if node else None

    def create_world_entity_node(self, entity_data: Dict[str, Any]) -> Optional[str]:
        """
        创建世界观实体节点

        Args:
            entity_data: 实体数据

        Returns:
            str: 节点ID
        """
        node = self.create_node("WorldEntity", entity_data)
        return node.get("id") if node else None

    def find_characters_by_name(self, name: str) -> List[Dict[str, Any]]:
        """
        根据名称查找角色

        Args:
            name: 角色名称

        Returns:
            List[Dict]: 角色列表
        """
        return self.find_nodes("Character", "name", name)

    def find_world_entities_by_type(self, entity_type: str) -> List[Dict[str, Any]]:
        """
        根据类型查找世界观实体

        Args:
            entity_type: 实体类型

        Returns:
            List[Dict]: 实体列表
        """
        return self.find_nodes("WorldEntity", "type", entity_type)

    def create_character_relationship(
        self,
        char1_id: str,
        char2_id: str,
        rel_type: str,
        properties: Dict[str, Any] = None
    ) -> bool:
        """
        创建角色之间的关系

        Args:
            char1_id: 第一个角色ID
            char2_id: 第二个角色ID
            rel_type: 关系类型 ( Relationships: FRIEND, ENEMY, FAMILY, ALLY, RIVAL, LOVER, etc.)
            properties: 关系属性

        Returns:
            bool: 创建成功返回True
        """
        return self.create_relationship(
            "Character", char1_id, "id",
            "Character", char2_id, "id",
            rel_type,
            properties
        )

    def get_character_network(self, char_id: str, max_depth: int = 3) -> List[Dict[str, Any]]:
        """
        获取角色的关系网络

        Args:
            char_id: 角色ID
            max_depth: 最大深度

        Returns:
            List[Dict]: 关系网络数据
        """
        return self.traverse(
            {"id": char_id, "labels": ["Character"]},
            ["FRIEND", "ENEMY", "FAMILY", "ALLY", "RIVAL", "LOVER"],
            max_depth
        )

    def create_plot_arc(
        self,
        arc_data: Dict[str, Any],
        related_entities: List[Dict[str, Any]] = None
    ) -> Optional[str]:
        """
        创建剧情弧节点

        Args:
            arc_data: 剧情弧数据
            related_entities: 相关实体列表

        Returns:
            str: 节点ID
        """
        node_id = self.create_node("PlotArc", arc_data)

        if node_id and related_entities:
            for entity in related_entities:
                self.create_relationship(
                    "PlotArc", node_id, "id",
                    entity.get("label", "Entity"), entity.get("id"), "id",
                    "INVOLVES"
                )

        return node_id

    def test_connection(self) -> bool:
        """
        测试数据库连接

        Returns:
            bool: 连接成功返回True
        """
        return self.health_check()["status"] == "healthy"
