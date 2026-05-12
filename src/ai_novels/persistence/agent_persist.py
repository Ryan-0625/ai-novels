"""
Agent持久化工具类

@file: persistence/agent_persist.py
@date: 2026-03-20
@version: 1.0
@description: 为各个Agent提供数据持久化支持
"""

import os
import json
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime

from .manager import get_persistence_manager, PersistenceManager

_OUTPUT_DIR = "output"

def _file_fallback(subdir: str, task_id: str, filename: str, data: dict) -> str:
    """当数据库不可用时的文件回退保存"""
    dirpath = os.path.join(_OUTPUT_DIR, subdir, task_id)
    os.makedirs(dirpath, exist_ok=True)
    filepath = os.path.join(dirpath, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return f"file::{filepath}"


class CharacterPersistence:
    """角色数据持久化"""

    COLLECTION = "character_profiles"

    @staticmethod
    def save_character(
        pm: PersistenceManager,
        task_id: str,
        name: str,
        char_type: str,
        character_data: Dict[str, Any]
    ) -> Optional[str]:
        """
        保存角色到MongoDB并创建Neo4j节点

        Args:
            pm: 持久化管理器
            task_id: 任务ID
            name: 角色名称
            char_type: 角色类型 (protagonist/antagonist/supporting/etc.)
            character_data: 角色数据

        Returns:
            MongoDB插入的ID
        """
        if not pm.mongodb_client or not pm.neo4j_client:
            # Fallback: 保存到文件
            char_id = f"char_{uuid.uuid4().hex[:8]}"
            return _file_fallback("characters", task_id, f"{name}.json", {
                "char_id": char_id,
                "task_id": task_id,
                "name": name,
                "char_type": char_type,
                "data": character_data,
                "created_at": datetime.utcnow().isoformat(),
            })

        try:
            # 1. 生成唯一ID
            char_id = f"char_{uuid.uuid4().hex[:8]}"

            # 2. 准备MongoDB文档
            doc = {
                "char_id": char_id,
                "task_id": task_id,
                "name": name,
                "char_type": char_type,
                "created_at": datetime.utcnow(),
                **character_data
            }

            # 3. 插入MongoDB
            mongoid = pm.mongodb_client.create(
                collection=CharacterPersistence.COLLECTION,
                document=doc
            )

            # 4. 创建Neo4j Character节点
            properties = {
                "id": char_id,
                "name": name,
                "type": char_type,
                "age": character_data.get("age", 25),
                "gender": character_data.get("gender", "Male"),
                "personality": json.dumps(character_data.get("personality", [])),
                "goals": json.dumps(character_data.get("goals", [])),
                "background": character_data.get("background", ""),
                "weaknesses": json.dumps(character_data.get("weaknesses", [])),
                "secrets": json.dumps(character_data.get("secrets", [])),
                "task_id": task_id,
                "created_at": datetime.utcnow().isoformat()
            }

            neo4j_result = pm.neo4j_client.create_node("Character", properties)

            # 5. 创建任务-角色关系
            pm.neo4j_client.create_relationship(
                from_label="Task",
                from_id=task_id,
                from_prop="id",
                to_label="Character",
                to_id=char_id,
                to_prop="id",
                rel_type="GENERATES"
            )

            return mongoid

        except Exception as e:
            print(f"Failed to save character: {e}")
            return None

    @staticmethod
    def save_relationship(
        pm: PersistenceManager,
        task_id: str,
        char1_id: str,
        char2_id: str,
        rel_type: str,
        strength: int = 75
    ) -> bool:
        """
        在Neo4j中创建角色关系

        Args:
            pm: 持久化管理器
            task_id: 任务ID
            char1_id: 角色1 ID
            char2_id: 角色2 ID
            rel_type: 关系类型 (FRIEND/ENEMY/FAMILY/ALLY/RIVAL/LOVER)
            strength: 关系强度 0-100

        Returns:
            是否成功
        """
        if not pm.neo4j_client:
            return False

        try:
            # 创建关系
            success = pm.neo4j_client.create_relationship(
                from_label="Character",
                from_id=char1_id,
                from_prop="id",
                to_label="Character",
                to_id=char2_id,
                to_prop="id",
                rel_type=rel_type,
                properties={"strength": strength, "task_id": task_id}
            )
            return success
        except Exception as e:
            print(f"Failed to save relationship: {e}")
            return False


class WorldPersistence:
    """世界观数据持久化"""

    COLLECTION_LOCATIONS = "world_locations"
    COLLECTION_CULTURES = "world_cultures"
    COLLECTION_FACTIONS = "world_factions"
    COLLECTION_EVENTS = "world_events"

    @staticmethod
    def save_location(
        pm: PersistenceManager,
        task_id: str,
        location_data: Dict[str, Any]
    ) -> Optional[str]:
        """保存地点到MongoDB并创建Neo4j节点"""
        if not pm.mongodb_client or not pm.neo4j_client:
            # Fallback: 保存到文件
            loc_id = f"loc_{uuid.uuid4().hex[:8]}"
            return _file_fallback("locations", task_id, f"{location_data.get('name', 'unknown')}.json", {
                "loc_id": loc_id,
                "task_id": task_id,
                **location_data,
                "created_at": datetime.utcnow().isoformat(),
            })

        try:
            loc_id = f"loc_{uuid.uuid4().hex[:8]}"

            # MongoDB文档
            doc = {
                "loc_id": loc_id,
                "task_id": task_id,
                "created_at": datetime.utcnow(),
                **location_data
            }

            mongoid = pm.mongodb_client.create(
                collection=WorldPersistence.COLLECTION_LOCATIONS,
                document=doc
            )

            # Neo4j节点
            properties = {
                "id": loc_id,
                "name": location_data.get("name", "Unknown"),
                "type": location_data.get("type", "city"),
                "description": location_data.get("description", ""),
                "features": json.dumps(location_data.get("features", [])),
                "significance": location_data.get("significance", ""),
                "danger_level": location_data.get("danger_level", 0),
                "task_id": task_id,
                "created_at": datetime.utcnow().isoformat()
            }

            pm.neo4j_client.create_node("Location", properties)

            # 创建任务-地点关系
            pm.neo4j_client.create_relationship(
                from_label="Task",
                from_id=task_id,
                from_prop="id",
                to_label="Location",
                to_id=loc_id,
                to_prop="id",
                rel_type="HAS_LOCATION"
            )

            return mongoid

        except Exception as e:
            print(f"Failed to save location: {e}")
            return None

    @staticmethod
    def save_faction(
        pm: PersistenceManager,
        task_id: str,
        faction_data: Dict[str, Any]
    ) -> Optional[str]:
        """保存势力到MongoDB并创建Neo4j节点"""
        if not pm.mongodb_client or not pm.neo4j_client:
            # Fallback: 保存到文件
            fact_id = f"fact_{uuid.uuid4().hex[:8]}"
            return _file_fallback("factions", task_id, f"{faction_data.get('name', 'unknown')}.json", {
                "fact_id": fact_id,
                "task_id": task_id,
                **faction_data,
                "created_at": datetime.utcnow().isoformat(),
            })

        try:
            fact_id = f"fact_{uuid.uuid4().hex[:8]}"

            doc = {
                "fact_id": fact_id,
                "task_id": task_id,
                "created_at": datetime.utcnow(),
                **faction_data
            }

            mongoid = pm.mongodb_client.create(
                collection=WorldPersistence.COLLECTION_FACTIONS,
                document=doc
            )

            properties = {
                "id": fact_id,
                "name": faction_data.get("name", "Unknown"),
                "ideology": faction_data.get("ideology", ""),
                "goals": json.dumps(faction_data.get("goals", [])),
                "leader": faction_data.get("leader", ""),
                "members": faction_data.get("members", 0),
                "influence": faction_data.get("influence", 0),
                "task_id": task_id,
                "created_at": datetime.utcnow().isoformat()
            }

            pm.neo4j_client.create_node("Faction", properties)

            pm.neo4j_client.create_relationship(
                from_label="Task",
                from_id=task_id,
                from_prop="id",
                to_label="Faction",
                to_id=fact_id,
                to_prop="id",
                rel_type="HAS_FACTION"
            )

            return mongoid

        except Exception as e:
            print(f"Failed to save faction: {e}")
            return None


class OutlinePersistence:
    """大纲数据持久化"""

    COLLECTION = "chapter_outlines"

    @staticmethod
    def save_outline(
        pm: PersistenceManager,
        task_id: str,
        chapter_num: int,
        outline_data: Dict[str, Any]
    ) -> Optional[str]:
        """保存章节大纲"""
        if not pm.mongodb_client or not pm.neo4j_client:
            # Fallback: 保存到文件
            outline_id = f"outline_{chapter_num}_{uuid.uuid4().hex[:8]}"
            return _file_fallback("outlines", task_id, f"chapter_{chapter_num}_outline.json", {
                "outline_id": outline_id,
                "task_id": task_id,
                "chapter_num": chapter_num,
                **outline_data,
                "created_at": datetime.utcnow().isoformat(),
            })

        try:
            outline_id = f"outline_{chapter_num}_{uuid.uuid4().hex[:4]}"

            doc = {
                "outline_id": outline_id,
                "task_id": task_id,
                "chapter_num": chapter_num,
                "created_at": datetime.utcnow(),
                **outline_data
            }

            mongoid = pm.mongodb_client.create(
                collection=OutlinePersistence.COLLECTION,
                document=doc
            )

            # Neo4j PlotArc节点
            arc_id = f"arc_{chapter_num}_{uuid.uuid4().hex[:4]}"
            pm.neo4j_client.create_node("PlotArc", {
                "id": arc_id,
                "chapter_num": chapter_num,
                "title": outline_data.get("title", f"Chapter {chapter_num}"),
                "description": outline_data.get("summary", ""),
                "structure": json.dumps(outline_data.get("structure", {})),
                "task_id": task_id,
                "created_at": datetime.utcnow().isoformat()
            })

            # 创建关系
            pm.neo4j_client.create_relationship(
                from_label="Task",
                from_id=task_id,
                from_prop="id",
                to_label="PlotArc",
                to_id=arc_id,
                to_prop="id",
                rel_type="HAS_ARC"
            )

            return mongoid

        except Exception as e:
            print(f"Failed to save outline: {e}")
            return None


class ChapterPersistence:
    """章节数据持久化"""

    COLLECTION = "chapters"

    @staticmethod
    def save_chapter(
        pm: PersistenceManager,
        task_id: str,
        chapter_num: int,
        title: str,
        content: str,
        word_count: int,
        extra_data: Dict[str, Any] = None
    ) -> Optional[str]:
        """
        保存章节到MongoDB并添加向量到ChromaDB

        Args:
            pm: 持久化管理器
            task_id: 任务ID
            chapter_num: 章节号
            title: 章节标题
            content: 章节内容
            word_count: 字数
            extra_data: 额外数据

        Returns:
            MongoDB插入的ID
        """
        if not pm.mongodb_client:
            # Fallback: 保存到文件
            chapter_id = f"chapter_{chapter_num}_{uuid.uuid4().hex[:8]}"
            _file_fallback("chapters", task_id, f"chapter_{chapter_num}.json", {
                "chapter_id": chapter_id,
                "task_id": task_id,
                "chapter_num": chapter_num,
                "title": title,
                "content": content,
                "word_count": word_count,
                **(extra_data or {}),
                "created_at": datetime.utcnow().isoformat(),
            })
            return chapter_id

        try:
            chapter_id = f"chapter_{chapter_num}_{uuid.uuid4().hex[:8]}"

            doc = {
                "chapter_id": chapter_id,
                "task_id": task_id,
                "chapter_num": chapter_num,
                "title": title,
                "content": content,
                "word_count": word_count,
                "created_at": datetime.utcnow(),
                **(extra_data or {})
            }

            mongoid = pm.mongodb_client.create(
                collection=ChapterPersistence.COLLECTION,
                document=doc
            )

            # 如果有ChromaDB客户端，添加向量
            if pm.chromadb_client:
                try:
                    # 使用章节摘要作为向量搜索的文本
                    chunk_size = 500
                    for i in range(0, len(content), chunk_size):
                        chunk = content[i:i + chunk_size]
                        chunk_id = f"{chapter_id}_chunk_{i // chunk_size}"

                        pm.chromadb_client._collection.add(
                            ids=[chunk_id],
                            documents=[chunk],
                            metadatas=[{
                                "chapter_id": chapter_id,
                                "chapter_num": chapter_num,
                                "task_id": task_id,
                                "chunk_index": i // chunk_size
                            }]
                        )
                except Exception as e:
                    print(f"Failed to add chapter to ChromaDB: {e}")

            return mongoid

        except Exception as e:
            print(f"Failed to save chapter: {e}")
            return None


class QualityReportPersistence:
    """质量报告持久化"""

    COLLECTION = "quality_reports"

    @staticmethod
    def save_report(
        pm: PersistenceManager,
        task_id: str,
        report_data: Dict[str, Any]
    ) -> Optional[str]:
        """保存质量报告"""
        if not pm.mongodb_client:
            # Fallback: 保存到文件
            report_id = f"quality_{uuid.uuid4().hex[:8]}"
            _file_fallback("reports", task_id, f"{report_id}.json", {
                "report_id": report_id,
                "task_id": task_id,
                "data": report_data,
                "created_at": datetime.utcnow().isoformat(),
            })
            return report_id

        try:
            report_id = f"quality_{uuid.uuid4().hex[:8]}"

            doc = {
                "report_id": report_id,
                "task_id": task_id,
                "created_at": datetime.utcnow(),
                **report_data
            }

            return pm.mongodb_client.create(
                collection=QualityReportPersistence.COLLECTION,
                document=doc
            )

        except Exception as e:
            print(f"Failed to save quality report: {e}")
            return None


# 兼容性函数 - 从PersistenceManager调用
def save_character_to_db(
    task_id: str,
    name: str,
    char_type: str,
    character_data: Dict[str, Any]
) -> Optional[str]:
    """便捷函数：保存角色"""
    pm = get_persistence_manager()
    return CharacterPersistence.save_character(pm, task_id, name, char_type, character_data)


def save_chapter_to_db(
    task_id: str,
    chapter_num: int,
    title: str,
    content: str,
    word_count: int,
    extra_data: Dict[str, Any] = None
) -> Optional[str]:
    """便捷函数：保存章节"""
    pm = get_persistence_manager()
    return ChapterPersistence.save_chapter(pm, task_id, chapter_num, title, content, word_count, extra_data)


class TaskPersistence:
    """任务状态持久化"""

    COLLECTION = "tasks"

    @staticmethod
    def save_task(
        pm: PersistenceManager,
        task_id: str,
        task_data: Dict[str, Any]
    ) -> Optional[str]:
        """保存任务状态到 MongoDB（文件回退）"""
        if not pm.mongodb_client:
            return _file_fallback("tasks", task_id, "task.json", {
                "task_id": task_id,
                **task_data,
                "saved_at": datetime.utcnow().isoformat(),
            })
        try:
            doc = {
                "task_id": task_id,
                "updated_at": datetime.utcnow(),
                **task_data,
            }
            # 使用 upsert 避免重复
            return pm.mongodb_client.update(
                collection=TaskPersistence.COLLECTION,
                query={"task_id": task_id},
                updates={"$set": doc},
                upsert=True,
            )
        except Exception as e:
            print(f"Failed to save task {task_id}: {e}")
            return _file_fallback("tasks", task_id, "task.json", {
                "task_id": task_id,
                **task_data,
                "saved_at": datetime.utcnow().isoformat(),
            })

    @staticmethod
    def load_task(
        pm: PersistenceManager,
        task_id: str
    ) -> Optional[Dict[str, Any]]:
        """从 MongoDB 加载任务（文件回退）"""
        if pm.mongodb_client:
            try:
                doc = pm.mongodb_client.find_one(
                    collection=TaskPersistence.COLLECTION,
                    query={"task_id": task_id},
                )
                if doc:
                    return doc
            except Exception:
                pass
        # 文件回退
        filepath = os.path.join(_OUTPUT_DIR, "tasks", task_id, "task.json")
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        return None

    @staticmethod
    def list_tasks(
        pm: PersistenceManager,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """列出最近的任务"""
        if pm.mongodb_client:
            try:
                return list(pm.mongodb_client.read(
                    collection=TaskPersistence.COLLECTION,
                    query={},
                    limit=limit,
                ))
            except Exception:
                pass
        # 文件回退：扫描 output/tasks/ 目录
        tasks_dir = os.path.join(_OUTPUT_DIR, "tasks")
        results = []
        if os.path.isdir(tasks_dir):
            for tid in sorted(os.listdir(tasks_dir))[-limit:]:
                task_file = os.path.join(tasks_dir, tid, "task.json")
                if os.path.exists(task_file):
                    with open(task_file, "r", encoding="utf-8") as f:
                        results.append(json.load(f))
        return results
