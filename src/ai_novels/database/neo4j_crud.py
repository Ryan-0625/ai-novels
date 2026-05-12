"""
Neo4j图数据库CRUD工具函数

@file: database/neo4j_crud.py
@date: 2026-03-13
@version: 1.0.0
@description: Neo4j图数据库操作工具函数
"""

from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)


def neo4j_create_node(label: str, properties: Dict[str, Any], client) -> Optional[Dict[str, Any]]:
    """
    Neo4j创建节点

    Args:
        label: 节点标签
        properties: 节点属性
        client: Neo4jClient实例

    Returns:
        创建的节点
    """
    try:
        query = f"CREATE (n:{label} $properties) RETURN n"
        result = client.execute_cypher(query, {"properties": properties})
        return result[0]['n'] if result else None
    except Exception as e:
        print(f"Neo4j create node error: {e}")
        return None


def neo4j_find_nodes(label: str, property_name: str, value: Any, client) -> List[Dict[str, Any]]:
    """
    Neo4j查找节点

    Args:
        label: 节点标签
        property_name: 属性名
        value: 属性值
        client: Neo4jClient实例

    Returns:
        节点列表
    """
    try:
        query = f"MATCH (n:{label}) WHERE n.{property_name} = $value RETURN n"
        result = client.execute_cypher(query, {"value": value})
        return [r['n'] for r in result]
    except Exception as e:
        print(f"Neo4j find nodes error: {e}")
        return []


def neo4j_create_relationship(
    from_label: str,
    from_id: Any,
    from_prop: str,
    to_label: str,
    to_id: Any,
    to_prop: str,
    rel_type: str,
    properties: Dict[str, Any] = None,
    client = None
) -> bool:
    """
    Neo4j创建关系

    Args:
        from_label: 起始节点标签
        from_id: 起始节点ID
        from_prop: 起始节点属性名
        to_label: 目标节点标签
        to_id: 目标节点ID
        to_prop: 目标节点属性名
        rel_type: 关系类型
        properties: 关系属性
        client: Neo4jClient实例

    Returns:
        是否成功
    """
    try:
        rel_props = properties or {}
        rel_prop_str = ', '.join([f"{k}: ${k}" for k in rel_props.keys()])

        query = f"""
            MATCH (a:{from_label} {{{from_prop}: $from_id}}),
                  (b:{to_label} {{{to_prop}: $to_id}})
            CREATE (a)-[r:{rel_type} {{{rel_prop_str}}}]->(b)
            RETURN r
        """

        params = {"from_id": from_id, "to_id": to_id}
        params.update(rel_props)

        result = client.execute_cypher(query, params)
        return result is not None
    except Exception as e:
        print(f"Neo4j create relationship error: {e}")
        return False


def neo4j_get_node(label: str, id_value: Any, id_prop: str = "id", client = None) -> Optional[Dict[str, Any]]:
    """
    Neo4j获取节点

    Args:
        label: 节点标签
        id_value: 节点ID值
        id_prop: ID属性名
        client: Neo4jClient实例

    Returns:
        节点或None
    """
    try:
        query = f"MATCH (n:{label} {{{id_prop}: $id}}) RETURN n"
        result = client.execute_cypher(query, {"id": id_value})
        return result[0]['n'] if result else None
    except Exception as e:
        print(f"Neo4j get node error: {e}")
        return None


def neo4j_delete_node(label: str, property_name: str, value: Any, client = None) -> bool:
    """
    Neo4j删除节点

    Args:
        label: 节点标签
        property_name: 属性名
        value: 属性值
        client: Neo4jClient实例

    Returns:
        是否成功
    """
    try:
        query = f"MATCH (n:{label}) WHERE n.{property_name} = $value DETACH DELETE n"
        result = client.execute_cypher(query, {"value": value})
        return True
    except Exception as e:
        print(f"Neo4j delete node error: {e}")
        return False


def neo4j_delete_relationship(from_label: str, from_id: str, to_label: str, to_id: str,
                               rel_type: str, client = None) -> bool:
    """
    Neo4j删除关系

    Args:
        from_label: 起始节点标签
        from_id: 起始节点ID
        to_label: 目标节点标签
        to_id: 目标节点ID
        rel_type: 关系类型
        client: Neo4jClient实例

    Returns:
        是否成功
    """
    try:
        query = f"""
            MATCH (a:{from_label} {{id: $from_id}})-[r:{rel_type}]-(b:{to_label} {{id: $to_id}})
            DELETE r
        """
        client.execute_cypher(query, {"from_id": from_id, "to_id": to_id})
        return True
    except Exception as e:
        print(f"Neo4j delete relationship error: {e}")
        return False


def neo4j_update_node_properties(label: str, id_value: Any, properties: Dict[str, Any],
                                   id_prop: str = "id", client = None) -> bool:
    """
    Neo4j更新节点属性

    Args:
        label: 节点标签
        id_value: 节点ID值
        properties: 要更新的属性
        id_prop: ID属性名
        client: Neo4jClient实例

    Returns:
        是否成功
    """
    try:
        prop_sets = ', '.join([f"n.{k} = ${k}" for k in properties.keys()])
        query = f"MATCH (n:{label} {{{id_prop}: $id}}) SET {prop_sets} RETURN n"

        params = {"id": id_value}
        params.update(properties)

        result = client.execute_cypher(query, params)
        return result is not None
    except Exception as e:
        print(f"Neo4j update node error: {e}")
        return False


def neo4j_traverse(start_node: Dict[str, Any], rel_types: List[str], max_depth: int,
                   client = None) -> List[Dict[str, Any]]:
    """
    Neo4j图遍历

    Args:
        start_node: 起始节点
        rel_types: 关系类型列表
        max_depth: 最大深度
        client: Neo4jClient实例

    Returns:
        遍历结果
    """
    try:
        start_id = start_node.get('id')
        rel_types_str = '|'.join(rel_types)

        query = f"""
            MATCH (start {{id: $start_id}})
            CALL apoc.paths.expand(
                start,
                $rel_types,
                $rel_types,
                0,
                {max_depth}
            )
            YIELD path
            RETURN path
        """

        result = client.execute_cypher(query, {
            "start_id": start_id,
            "rel_types": rel_types_str
        })

        return result
    except Exception as e:
        print(f"Neo4j traverse error: {e}")
        return []


def neo4j_find_related_nodes(node_id: str, rel_type: str = None, direction: str = "out",
                              client = None) -> List[Dict[str, Any]]:
    """
    Neo4j查找相关节点

    Args:
        node_id: 节点ID
        rel_type: 关系类型（可选）
        direction: 方向 (in/out/both)
        client: Neo4jClient实例

    Returns:
        相关节点列表
    """
    try:
        if rel_type:
            if direction == "out":
                query = f"MATCH (n {{id: $node_id}})-[:{rel_type}]->(m) RETURN m"
            elif direction == "in":
                query = f"MATCH (n {{id: $node_id}})<-[:{rel_type}]-(m) RETURN m"
            else:
                query = f"MATCH (n {{id: $node_id}})-[:{rel_type}]-(m) RETURN m"
        else:
            if direction == "out":
                query = "MATCH (n {id: $node_id})-[]->(m) RETURN m"
            elif direction == "in":
                query = "MATCH (n {id: $node_id})<-[]-(m) RETURN m"
            else:
                query = "MATCH (n {id: $node_id})-[]-(m) RETURN m"

        result = client.execute_cypher(query, {"node_id": node_id})
        return [r['m'] for r in result]
    except Exception as e:
        print(f"Neo4j find related nodes error: {e}")
        return []


def neo4j_create_unique_constraint(label: str, property_name: str, client) -> bool:
    """
    Neo4j创建唯一约束

    Args:
        label: 节点标签
        property_name: 属性名
        client: Neo4jClient实例

    Returns:
        是否成功
    """
    try:
        query = f"CREATE CONSTRAINT FOR (n:{label}) REQUIRE n.{property_name} IS UNIQUE"
        client.execute_cypher(query)
        return True
    except Exception as e:
        print(f"Neo4j create constraint error: {e}")
        return False


if __name__ == "__main__":
    logger.info("Neo4j CRUD utils loaded successfully!")
