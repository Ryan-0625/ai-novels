"""
Context Manager 单元测试 - Phase 1 Core层
真实环境测试，不使用Mock
"""

import pytest
import time
import threading
from typing import List

import sys
sys.path.insert(0, "e:/VScode(study)/Project/AI-Novels/src")

from ai_novels.core.context_manager import (
    ContextManager,
    ContextItem,
    ContextScope,
    ContextPriority,
    ContextSnapshot,
    SharedContextPool,
    create_context_manager,
)


class TestContextItem:
    """测试 ContextItem 类"""
    
    def test_context_item_init(self):
        """测试 ContextItem 初始化"""
        item = ContextItem(
            key="test_key",
            value="test_value",
            scope=ContextScope.LOCAL,
            priority=ContextPriority.HIGH
        )
        
        assert item.key == "test_key"
        assert item.value == "test_value"
        assert item.scope == ContextScope.LOCAL
        assert item.priority == ContextPriority.HIGH
        assert item.timestamp > 0
        assert item.access_count == 0
        
    def test_context_item_is_expired_no_ttl(self):
        """测试无TTL时不过期"""
        item = ContextItem(key="test", value="value", ttl=None)
        assert item.is_expired() == False
        
    def test_context_item_is_expired_with_ttl(self):
        """测试有TTL时正确过期"""
        item = ContextItem(key="test", value="value", ttl=1)
        assert item.is_expired() == False
        
        time.sleep(1.1)
        assert item.is_expired() == True
        
    def test_context_item_touch(self):
        """测试 touch 方法更新访问信息"""
        item = ContextItem(key="test", value="value")
        original_access = item.last_access
        
        time.sleep(0.01)
        item.touch()
        
        assert item.access_count == 1
        assert item.last_access > original_access
        
    def test_context_item_to_dict(self):
        """测试转换为字典"""
        item = ContextItem(
            key="test",
            value="value",
            scope=ContextScope.SHARED,
            priority=ContextPriority.CRITICAL,
            ttl=300
        )
        
        data = item.to_dict()
        
        assert data["key"] == "test"
        assert data["value"] == "value"
        assert data["scope"] == "shared"
        assert data["priority"] == 0  # CRITICAL = 0
        assert data["ttl"] == 300
        
    def test_context_item_from_dict(self):
        """测试从字典创建"""
        data = {
            "key": "test",
            "value": "value",
            "scope": "global",
            "priority": 2,
            "timestamp": 1234567890.0,
            "ttl": 600,
            "metadata": {"source": "test"},
            "access_count": 5,
            "last_access": 1234567890.0
        }
        
        item = ContextItem.from_dict(data)
        
        assert item.key == "test"
        assert item.value == "value"
        assert item.scope == ContextScope.GLOBAL
        assert item.priority == ContextPriority.NORMAL
        assert item.access_count == 5


class TestContextManager:
    """测试 ContextManager 类"""
    
    @pytest.fixture
    def context_manager(self):
        """提供 ContextManager 实例"""
        cm = ContextManager(agent_name="test_agent", session_id="test_session")
        yield cm
        cm.destroy()
    
    def test_context_manager_init(self, context_manager):
        """测试 ContextManager 初始化"""
        assert context_manager._agent_name == "test_agent"
        assert context_manager._session_id == "test_session"
        assert context_manager._max_items == 1000
        assert len(context_manager._local_context) == 0
        assert len(context_manager._shared_context) == 0
        assert len(context_manager._global_context) == 0
        
    def test_set_and_get_local(self, context_manager):
        """测试设置和获取本地上下文"""
        context_manager.set("key1", "value1", scope=ContextScope.LOCAL)
        
        value = context_manager.get("key1")
        assert value == "value1"
        
    def test_set_and_get_shared(self, context_manager):
        """测试设置和获取共享上下文"""
        context_manager.set("key2", "value2", scope=ContextScope.SHARED)
        
        value = context_manager.get("key2", scope=ContextScope.SHARED)
        assert value == "value2"
        
    def test_set_and_get_global(self, context_manager):
        """测试设置和获取全局上下文"""
        context_manager.set("key3", "value3", scope=ContextScope.GLOBAL)
        
        value = context_manager.get("key3", scope=ContextScope.GLOBAL)
        assert value == "value3"
        
    def test_get_default_value(self, context_manager):
        """测试获取不存在的键返回默认值"""
        value = context_manager.get("nonexistent", default="default_value")
        assert value == "default_value"
        
    def test_get_without_default(self, context_manager):
        """测试获取不存在的键无默认值"""
        value = context_manager.get("nonexistent")
        assert value is None
        
    def test_scope_priority_lookup(self, context_manager):
        """测试作用域优先级查找（Local > Shared > Global）"""
        # 在不同作用域设置同名键
        context_manager.set("key", "local_value", scope=ContextScope.LOCAL)
        context_manager.set("key", "shared_value", scope=ContextScope.SHARED)
        context_manager.set("key", "global_value", scope=ContextScope.GLOBAL)
        
        # 不指定作用域时应该返回 Local
        value = context_manager.get("key")
        assert value == "local_value"
        
    def test_delete_existing_key(self, context_manager):
        """测试删除存在的键"""
        context_manager.set("key_to_delete", "value")
        
        result = context_manager.delete("key_to_delete")
        assert result == True
        assert context_manager.get("key_to_delete") is None
        
    def test_delete_nonexistent_key(self, context_manager):
        """测试删除不存在的键"""
        result = context_manager.delete("nonexistent")
        assert result == False
        
    def test_exists(self, context_manager):
        """测试检查键是否存在"""
        context_manager.set("existing_key", "value")
        
        assert context_manager.exists("existing_key") == True
        assert context_manager.exists("nonexistent") == False
        
    def test_keys(self, context_manager):
        """测试获取所有键"""
        context_manager.set("key1", "value1", scope=ContextScope.LOCAL)
        context_manager.set("key2", "value2", scope=ContextScope.SHARED)
        context_manager.set("key3", "value3", scope=ContextScope.GLOBAL)
        
        all_keys = context_manager.keys()
        assert set(all_keys) == {"key1", "key2", "key3"}
        
    def test_keys_with_scope(self, context_manager):
        """测试获取指定作用域的键"""
        context_manager.set("key1", "value1", scope=ContextScope.LOCAL)
        context_manager.set("key2", "value2", scope=ContextScope.LOCAL)
        context_manager.set("key3", "value3", scope=ContextScope.SHARED)
        
        local_keys = context_manager.keys(scope=ContextScope.LOCAL)
        assert set(local_keys) == {"key1", "key2"}
        
    def test_get_all(self, context_manager):
        """测试获取所有上下文值"""
        context_manager.set("key1", "value1")
        context_manager.set("key2", "value2")
        
        all_values = context_manager.get_all()
        assert all_values == {"key1": "value1", "key2": "value2"}
        
    def test_clear_all(self, context_manager):
        """测试清空所有上下文"""
        context_manager.set("key1", "value1", scope=ContextScope.LOCAL)
        context_manager.set("key2", "value2", scope=ContextScope.SHARED)
        context_manager.set("key3", "value3", scope=ContextScope.GLOBAL)
        
        context_manager.clear()
        
        assert len(context_manager._local_context) == 0
        assert len(context_manager._shared_context) == 0
        assert len(context_manager._global_context) == 0
        
    def test_clear_with_scope(self, context_manager):
        """测试清空指定作用域"""
        context_manager.set("key1", "value1", scope=ContextScope.LOCAL)
        context_manager.set("key2", "value2", scope=ContextScope.SHARED)
        
        context_manager.clear(scope=ContextScope.LOCAL)
        
        assert len(context_manager._local_context) == 0
        assert context_manager.get("key2") == "value2"
        
    def test_get_item_with_metadata(self, context_manager):
        """测试获取完整上下文项（含元数据）"""
        context_manager.set(
            "key",
            "value",
            scope=ContextScope.LOCAL,
            priority=ContextPriority.HIGH,
            metadata={"source": "test"}
        )
        
        item = context_manager.get_item("key")
        assert item is not None
        assert item.value == "value"
        assert item.priority == ContextPriority.HIGH
        assert item.metadata == {"source": "test"}
        
    def test_listener_notification(self, context_manager):
        """测试监听器通知"""
        notifications = []
        
        def listener(key, old_value, new_value):
            notifications.append((key, old_value, new_value))
        
        context_manager.add_listener(listener)
        
        # 设置新值
        context_manager.set("key", "value1")
        assert len(notifications) == 1
        assert notifications[0] == ("key", None, "value1")
        
        # 更新值
        context_manager.set("key", "value2")
        assert len(notifications) == 2
        assert notifications[1] == ("key", "value1", "value2")
        
    def test_remove_listener(self, context_manager):
        """测试移除监听器"""
        notifications = []
        
        def listener(key, old_value, new_value):
            notifications.append((key, old_value, new_value))
        
        context_manager.add_listener(listener)
        context_manager.set("key", "value1")
        
        context_manager.remove_listener(listener)
        context_manager.set("key", "value2")
        
        # 应该只收到一次通知
        assert len(notifications) == 1
        
    def test_create_snapshot(self, context_manager):
        """测试创建快照"""
        context_manager.set("key1", "value1", scope=ContextScope.LOCAL)
        context_manager.set("key2", "value2", scope=ContextScope.SHARED)
        
        snapshot = context_manager.create_snapshot(metadata={"test": True})
        
        assert snapshot is not None
        assert snapshot.snapshot_id is not None
        assert snapshot.session_id == "test_session"
        assert snapshot.agent_name == "test_agent"
        assert len(snapshot.items) == 2
        assert snapshot.metadata == {"test": True}
        
    def test_restore_snapshot(self, context_manager):
        """测试恢复快照"""
        context_manager.set("key1", "value1")
        snapshot = context_manager.create_snapshot()
        
        # 修改上下文
        context_manager.set("key1", "modified")
        context_manager.set("key2", "value2")
        
        # 恢复快照
        result = context_manager.restore_snapshot(snapshot.snapshot_id)
        assert result == True
        
        # 验证恢复
        assert context_manager.get("key1") == "value1"
        assert context_manager.get("key2") is None
        
    def test_restore_snapshot_not_found(self, context_manager):
        """测试恢复不存在的快照"""
        result = context_manager.restore_snapshot("nonexistent_id")
        assert result == False
        
    def test_list_snapshots(self, context_manager):
        """测试列出快照"""
        context_manager.set("key", "value")
        context_manager.create_snapshot(metadata={"name": "snapshot1"})
        context_manager.create_snapshot(metadata={"name": "snapshot2"})
        
        snapshots = context_manager.list_snapshots()
        assert len(snapshots) == 2
        
    def test_get_stats(self, context_manager):
        """测试获取统计信息"""
        context_manager.set("key1", "value1", scope=ContextScope.LOCAL)
        context_manager.set("key2", "value2", scope=ContextScope.SHARED)
        context_manager.set("key3", "value3", scope=ContextScope.GLOBAL)
        
        stats = context_manager.get_stats()
        
        assert stats["session_id"] == "test_session"
        assert stats["agent_name"] == "test_agent"
        assert stats["local_items"] == 1
        assert stats["shared_items"] == 1
        assert stats["global_items"] == 1
        assert stats["total_items"] == 3
        
    def test_export_import_context(self, context_manager):
        """测试导出和导入上下文"""
        context_manager.set("key1", "value1", priority=ContextPriority.HIGH)
        context_manager.set("key2", "value2")
        
        # 导出
        exported = context_manager.export_context()
        assert exported["session_id"] == "test_session"
        assert "items" in exported
        
        # 创建新的管理器并导入
        cm2 = ContextManager(agent_name="agent2")
        count = cm2.import_context(exported)
        
        assert count == 2
        assert cm2.get("key1") == "value1"
        cm2.destroy()


class TestSharedContextPool:
    """测试 SharedContextPool 类"""
    
    def test_shared_context_pool_singleton(self):
        """测试 SharedContextPool 是单例"""
        pool1 = SharedContextPool()
        pool2 = SharedContextPool()
        assert pool1 is pool2
        
    def test_register_and_unregister_agent(self):
        """测试注册和注销 Agent"""
        pool = SharedContextPool()
        cm = ContextManager(agent_name="agent1", session_id="session1")
        
        pool.register_agent("agent1", "session1", cm)
        assert "agent1" in pool._contexts
        
        pool.unregister_agent("agent1")
        assert "agent1" not in pool._contexts
        
        cm.destroy()
        
    def test_get_session_agents(self):
        """测试获取会话中的所有 Agent"""
        pool = SharedContextPool()
        cm1 = ContextManager(agent_name="agent1", session_id="session1")
        cm2 = ContextManager(agent_name="agent2", session_id="session1")
        cm3 = ContextManager(agent_name="agent3", session_id="session2")
        
        pool.register_agent("agent1", "session1", cm1)
        pool.register_agent("agent2", "session1", cm2)
        pool.register_agent("agent3", "session2", cm3)
        
        agents = pool.get_session_agents("session1")
        assert set(agents) == {"agent1", "agent2"}
        
        cm1.destroy()
        cm2.destroy()
        cm3.destroy()


class TestCreateContextManager:
    """测试 create_context_manager 函数"""
    
    def test_create_context_manager(self):
        """测试创建上下文管理器"""
        cm = create_context_manager(
            agent_name="test_agent",
            session_id="test_session",
            register_to_pool=False
        )
        
        assert cm is not None
        assert cm._agent_name == "test_agent"
        assert cm._session_id == "test_session"
        
        cm.destroy()
