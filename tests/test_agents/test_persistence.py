"""
持久化测试脚本

@file: tests/test_persistence.py
@date: 2026-03-20
@version: 1.0
@description: 测试持久化功能
"""

import sys
import os

# 获取项目根目录
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 添加src目录
src_path = os.path.join(project_root, 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)

import pytest
from deepnovel.persistence import (
    PersistenceManager, get_persistence_manager,
    CharacterPersistence, WorldPersistence, OutlinePersistence, ChapterPersistence
)
from deepnovel.persistence.agent_persist import save_character_to_db, save_chapter_to_db


@pytest.fixture
def persistence_manager():
    """提供持久化管理器实例"""
    return get_persistence_manager()


def test_persistence_manager(persistence_manager):
    """测试持久化管理器"""
    pm = persistence_manager

    # 健康检查
    health = pm.health_check()
    
    # 验证健康检查结果结构
    assert isinstance(health, dict)
    assert "overall" in health
    
    # 验证总体状态
    overall_status = health.get("overall", {}).get("status", "unknown")
    assert overall_status in ["healthy", "degraded", "unhealthy", "unknown"]


def test_character_persistence(persistence_manager):
    """测试角色持久化"""
    pm = persistence_manager
    
    # 如果数据库未连接，跳过测试
    if not pm.mongodb_client or not pm.neo4j_client:
        pytest.skip("数据库连接不可用")
    
    task_id = f"test_task_{os.urandom(4).hex()}"

    # 创建示例角色数据
    character_data = {
        "name": "沈砚",
        "age": 28,
        "gender": "Male",
        "personality": ["敏锐", "执着", "敏感"],
        "background": "档案员，记录'结冰者'",
        "goals": ["揭开结冰之谜", "保护所爱之人"],
        "secrets": ["自己也开始了结冰"],
        "weaknesses": ["过度怀疑", "情绪化"],
        "traits": ["智慧", "勇敢"]
    }

    # 保存角色
    mongoid = CharacterPersistence.save_character(
        pm=pm,
        task_id=task_id,
        name="沈砚",
        char_type="protagonist",
        character_data=character_data
    )

    if mongoid:
        print(f"\n角色保存成功!")
        print(f"  MongoDB ID: {mongoid}")
        print(f"  Task ID: {task_id}")

        # 验证MongoDB
        if pm.mongodb_client:
            doc = pm.mongodb_client.find_one(
                collection="character_profiles",
                query={"name": "沈砚"}
            )
            if doc:
                print(f"  MongoDB验证: 成功 - {doc.get('name', 'N/A')}")

        # 验证Neo4j
        if pm.neo4j_client:
            nodes = pm.neo4j_client.find_nodes("Character", "name", "沈砚")
            if nodes:
                print(f"  Neo4j验证: 成功 - 找到 {len(nodes)} 个节点")
    else:
        print("角色保存失败")


def test_world_persistence(persistence_manager):
    """测试世界观持久化"""
    pm = persistence_manager
    
    # 如果数据库未连接，跳过测试
    if not pm.mongodb_client or not pm.neo4j_client:
        pytest.skip("数据库连接不可用")

    task_id = f"test_task_{os.urandom(4).hex()}"

    # 保存地点
    location_data = {
        "name": "时间保存所",
        "type": "underground",
        "description": "位于地下的时间保存设施",
        "features": ["寂静", "时间凝固", "古老机械"],
        "significance": "故事主要发生地",
        "danger_level": 5
    }
    loc_id = WorldPersistence.save_location(pm, task_id, location_data)
    print(f"\n地点保存: {'成功' if loc_id else '失败'}")

    # 保存势力
    faction_data = {
        "name": "守时者",
        "ideology": "保护时间秩序",
        "goals": ["阻止时间滥用", "维护时间圣殿"],
        "leader": "时间守护者",
        "members": 1000,
        "influence": 85
    }
    fact_id = WorldPersistence.save_faction(pm, task_id, faction_data)
    print(f"势力保存: {'成功' if fact_id else '失败'}")


def test_outline_persistence(persistence_manager):
    """测试大纲持久化"""
    pm = persistence_manager
    
    # 如果数据库未连接，跳过测试
    if not pm.mongodb_client or not pm.neo4j_client:
        pytest.skip("数据库连接不可用")

    task_id = f"test_task_{os.urandom(4).hex()}"

    outline_data = {
        "title": "第一章：揭开序幕",
        "word_count_target": 2000,
        "perspective": "第一人称",
        "points_of_interest": ["发现异常记录", "遇到神秘人物"],
        "foreshadowing": ["结冰征兆", "古老预言"]
    }

    outline_id = OutlinePersistence.save_outline(pm, task_id, 1, outline_data)
    print(f"\n大纲保存: {'成功' if outline_id else '失败'}")


def test_chapter_persistence(persistence_manager):
    """测试章节持久化"""
    pm = persistence_manager
    
    # 如果数据库未连接，跳过测试
    if not pm.mongodb_client or not pm.neo4j_client:
        pytest.skip("数据库连接不可用")

    task_id = f"test_task_{os.urandom(4).hex()}"

    # 创建示例章节内容
    chapter_content = """
第一章：遗忘的档案

在没有冬天的城市里，沈砚开始了他的档案工作。

这里的时间是凝固的， Records被永久封存。
每一份档案都记录着一个被遗忘的时刻。

"欢迎来到时间保存所，"主管说，"我们的工作是..."
""".strip()

    chapter_id = ChapterPersistence.save_chapter(
        pm=pm,
        task_id=task_id,
        chapter_num=1,
        title="第一章：遗忘的档案",
        content=chapter_content,
        word_count=len(chapter_content.split()),
        extra_data={"genre": "scifi", "author": "AI"}
    )

    print(f"\n章节保存: {'成功' if chapter_id else '失败'}")
    print(f"  MongoDB ID: {chapter_id}")
    print(f"  Word Count: {len(chapter_content.split())}")


def test_convenience_functions(persistence_manager):
    """测试便捷函数"""
    pm = persistence_manager
    
    # 如果数据库未连接，跳过测试
    if not pm.mongodb_client or not pm.neo4j_client:
        pytest.skip("数据库连接不可用")

    task_id = f"test_task_{os.urandom(4).hex()}"

    # 测试save_character_to_db
    mongoid = save_character_to_db(
        task_id=task_id,
        name="测试角色",
        char_type="supporting",
        character_data={
            "name": "测试角色",
            "age": 25,
            "gender": "Female",
            "personality": ["善良", "勇敢"],
            "background": "普通的市民",
            "goals": ["帮助主角"],
            "secrets": [],
            "weaknesses": ["胆小"]
        }
    )
    print(f"\n便捷函数 save_character_to_db: {'成功' if mongoid else '失败'}")

    # 测试save_chapter_to_db
    chapter_content = "这是测试章节内容。"
    chap_id = save_chapter_to_db(
        task_id=task_id,
        chapter_num=2,
        title="测试章节",
        content=chapter_content,
        word_count=100
    )
    print(f"便捷函数 save_chapter_to_db: {'成功' if chap_id else '失败'}")


def main():
    """主函数"""
    print("\n持久化功能测试")
    print("=" * 60)

    # 测试持久化管理器
    pm = test_persistence_manager()

    if not pm.mongodb_client or not pm.neo4j_client:
        print("\n警告: 数据库连接失败，部分测试将跳过")
        return

    # 运行所有测试
    test_character_persistence(pm)
    test_world_persistence(pm)
    test_outline_persistence(pm)
    test_chapter_persistence(pm)
    test_convenience_functions(pm)

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
