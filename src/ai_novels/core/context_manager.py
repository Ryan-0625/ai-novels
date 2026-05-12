"""
增强型上下文管理模块

@file: core/context_manager.py
@date: 2026-04-08
@author: AI-Novels Team
@version: 2.0
@description: 提供强大的上下文管理能力，支持跨Agent上下文传递和持久化
"""

import json
import time
import uuid
from typing import Any, Dict, List, Optional, Set, Callable, Union
from dataclasses import dataclass, field, asdict
from enum import Enum
from datetime import datetime
from collections import OrderedDict
import threading
import copy

from ai_novels.utils import log_info, log_error, log_warn, get_logger


class ContextScope(Enum):
    """上下文作用域"""
    LOCAL = "local"           # 仅当前Agent可用
    SHARED = "shared"         # 同一会话内的Agent共享
    GLOBAL = "global"         # 全局共享
    EPHEMERAL = "ephemeral"   # 临时，不持久化


class ContextPriority(Enum):
    """上下文优先级"""
    CRITICAL = 0      # 关键信息，必须保留
    HIGH = 1          # 高优先级
    NORMAL = 2        # 普通优先级
    LOW = 3           # 低优先级，可被清理


@dataclass
class ContextItem:
    """上下文项"""
    key: str
    value: Any
    scope: ContextScope = ContextScope.LOCAL
    priority: ContextPriority = ContextPriority.NORMAL
    timestamp: float = field(default_factory=time.time)
    ttl: Optional[int] = None  # 生存时间（秒），None表示永久
    metadata: Dict[str, Any] = field(default_factory=dict)
    access_count: int = 0
    last_access: float = field(default_factory=time.time)
    
    def is_expired(self) -> bool:
        """检查是否过期"""
        if self.ttl is None:
            return False
        return time.time() - self.timestamp > self.ttl
    
    def touch(self):
        """更新访问时间"""
        self.last_access = time.time()
        self.access_count += 1
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "key": self.key,
            "value": self.value,
            "scope": self.scope.value,
            "priority": self.priority.value,
            "timestamp": self.timestamp,
            "ttl": self.ttl,
            "metadata": self.metadata,
            "access_count": self.access_count,
            "last_access": self.last_access
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ContextItem':
        """从字典创建"""
        return cls(
            key=data["key"],
            value=data["value"],
            scope=ContextScope(data.get("scope", "local")),
            priority=ContextPriority(data.get("priority", 2)),
            timestamp=data.get("timestamp", time.time()),
            ttl=data.get("ttl"),
            metadata=data.get("metadata", {}),
            access_count=data.get("access_count", 0),
            last_access=data.get("last_access", time.time())
        )


@dataclass
class ContextSnapshot:
    """上下文快照"""
    snapshot_id: str
    session_id: str
    agent_name: str
    timestamp: float
    items: Dict[str, ContextItem]
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "snapshot_id": self.snapshot_id,
            "session_id": self.session_id,
            "agent_name": self.agent_name,
            "timestamp": self.timestamp,
            "items": {k: v.to_dict() for k, v in self.items.items()},
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ContextSnapshot':
        """从字典创建"""
        return cls(
            snapshot_id=data["snapshot_id"],
            session_id=data["session_id"],
            agent_name=data["agent_name"],
            timestamp=data["timestamp"],
            items={k: ContextItem.from_dict(v) for k, v in data.get("items", {}).items()},
            metadata=data.get("metadata", {})
        )


class ContextManager:
    """
    增强型上下文管理器
    
    功能：
    1. 分层上下文存储（Local/Shared/Global）
    2. 上下文优先级管理
    3. 上下文过期自动清理
    4. 上下文快照和恢复
    5. 跨Agent上下文传递
    6. 上下文变更监听
    7. 读取缓存优化（NEW）
    """
    
    def __init__(
        self,
        agent_name: str,
        session_id: str = None,
        max_items: int = 1000,
        cleanup_interval: int = 300,
        cache_ttl: float = 5.0  # 缓存TTL（秒）
    ):
        """
        初始化上下文管理器
        
        Args:
            agent_name: Agent名称
            session_id: 会话ID
            max_items: 最大上下文项数
            cleanup_interval: 清理间隔（秒）
            cache_ttl: 读取缓存TTL（秒）
        """
        self._agent_name = agent_name
        self._session_id = session_id or str(uuid.uuid4())
        self._max_items = max_items
        self._cleanup_interval = cleanup_interval
        self._cache_ttl = cache_ttl
        
        # 上下文存储
        self._local_context: OrderedDict[str, ContextItem] = OrderedDict()
        self._shared_context: OrderedDict[str, ContextItem] = OrderedDict()
        self._global_context: OrderedDict[str, ContextItem] = OrderedDict()
        
        # 读取缓存 - 优化高频读取性能
        self._read_cache: Dict[str, tuple] = {}  # key -> (value, timestamp, scope)
        self._cache_lock = threading.RLock()
        
        # 线程安全
        self._lock = threading.RLock()
        
        # 监听器
        self._listeners: List[Callable[[str, Any, Any], None]] = []
        
        # 快照历史
        self._snapshots: Dict[str, ContextSnapshot] = {}
        self._max_snapshots = 10
        
        # 统计信息
        self._cache_hits = 0
        self._cache_misses = 0
        
        # 启动清理线程
        self._cleanup_thread: Optional[threading.Thread] = None
        self._stop_cleanup = False
        self._start_cleanup_thread()
        
        log_info(f"ContextManager initialized for {agent_name}, session: {self._session_id}")
    
    def _start_cleanup_thread(self):
        """启动清理线程"""
        def cleanup_loop():
            while not self._stop_cleanup:
                time.sleep(self._cleanup_interval)
                if not self._stop_cleanup:
                    self._cleanup_expired()
        
        self._cleanup_thread = threading.Thread(target=cleanup_loop, daemon=True)
        self._cleanup_thread.start()
    
    def _cleanup_expired(self):
        """清理过期项"""
        with self._lock:
            for storage in [self._local_context, self._shared_context, self._global_context]:
                expired_keys = [
                    key for key, item in storage.items()
                    if item.is_expired()
                ]
                for key in expired_keys:
                    del storage[key]
                    log_info(f"Cleaned up expired context: {key}")
    
    def _get_storage(self, scope: ContextScope) -> OrderedDict:
        """获取对应作用域的存储"""
        if scope == ContextScope.LOCAL:
            return self._local_context
        elif scope == ContextScope.SHARED:
            return self._shared_context
        elif scope == ContextScope.GLOBAL:
            return self._global_context
        else:
            return self._local_context
    
    def set(
        self,
        key: str,
        value: Any,
        scope: ContextScope = ContextScope.LOCAL,
        priority: ContextPriority = ContextPriority.NORMAL,
        ttl: Optional[int] = None,
        metadata: Dict[str, Any] = None
    ) -> ContextItem:
        """
        设置上下文项
        
        Args:
            key: 键
            value: 值
            scope: 作用域
            priority: 优先级
            ttl: 生存时间（秒）
            metadata: 元数据
            
        Returns:
            ContextItem: 创建的上下文项
        """
        with self._lock:
            # 检查容量限制
            storage = self._get_storage(scope)
            if len(storage) >= self._max_items:
                self._evict_items(scope)
            
            # 创建或更新项
            old_value = storage.get(key)
            item = ContextItem(
                key=key,
                value=value,
                scope=scope,
                priority=priority,
                ttl=ttl,
                metadata=metadata or {}
            )
            
            storage[key] = item
            
            # 使该key的缓存失效
            self._invalidate_cache(key)
            
            # 通知监听器
            old_val = old_value.value if old_value else None
            self._notify_listeners(key, old_val, value)
            
            log_info(f"Context set: {key} (scope: {scope.value})")
            return item
    
    def _get_cache_key(self, key: str, scope: ContextScope = None) -> str:
        """生成缓存键"""
        scope_str = scope.value if scope else "any"
        return f"{scope_str}:{key}"
    
    def _get_from_cache(self, cache_key: str) -> tuple:
        """从缓存获取值，返回(value, is_hit)"""
        with self._cache_lock:
            if cache_key in self._read_cache:
                value, timestamp, scope = self._read_cache[cache_key]
                if time.time() - timestamp < self._cache_ttl:
                    self._cache_hits += 1
                    return value, True
                else:
                    # 缓存过期，删除
                    del self._read_cache[cache_key]
            self._cache_misses += 1
            return None, False
    
    def _set_to_cache(self, cache_key: str, value: Any, scope: ContextScope):
        """设置缓存值"""
        with self._cache_lock:
            self._read_cache[cache_key] = (value, time.time(), scope)
    
    def _invalidate_cache(self, key: str = None):
        """使缓存失效"""
        with self._cache_lock:
            if key is None:
                self._read_cache.clear()
            else:
                # 删除所有作用域的该key缓存
                for scope in ContextScope:
                    cache_key = self._get_cache_key(key, scope)
                    self._read_cache.pop(cache_key, None)
                # 删除any作用域的缓存
                self._read_cache.pop(self._get_cache_key(key, None), None)
    
    def get(
        self,
        key: str,
        default: Any = None,
        scope: ContextScope = None,
        use_cache: bool = True
    ) -> Any:
        """
        获取上下文项（带缓存优化）
        
        Args:
            key: 键
            default: 默认值
            scope: 指定作用域，None则按优先级查找
            use_cache: 是否使用读取缓存
            
        Returns:
            值或默认值
        """
        # 尝试从缓存获取
        if use_cache:
            cache_key = self._get_cache_key(key, scope)
            cached_value, is_hit = self._get_from_cache(cache_key)
            if is_hit:
                return cached_value
        
        with self._lock:
            if scope:
                storage = self._get_storage(scope)
                item = storage.get(key)
                if item and not item.is_expired():
                    item.touch()
                    # 更新缓存
                    if use_cache:
                        self._set_to_cache(cache_key, item.value, scope)
                    return item.value
            else:
                # 按优先级查找：Local > Shared > Global
                for s in [ContextScope.LOCAL, ContextScope.SHARED, ContextScope.GLOBAL]:
                    storage = self._get_storage(s)
                    item = storage.get(key)
                    if item and not item.is_expired():
                        item.touch()
                        # 更新缓存
                        if use_cache:
                            cache_key = self._get_cache_key(key, None)
                            self._set_to_cache(cache_key, item.value, s)
                        return item.value
            
            return default
    
    def get_item(self, key: str, scope: ContextScope = None) -> Optional[ContextItem]:
        """获取完整的上下文项（包含元数据）"""
        with self._lock:
            if scope:
                storage = self._get_storage(scope)
                item = storage.get(key)
                if item and not item.is_expired():
                    item.touch()
                    return copy.deepcopy(item)
            else:
                for s in [ContextScope.LOCAL, ContextScope.SHARED, ContextScope.GLOBAL]:
                    storage = self._get_storage(s)
                    item = storage.get(key)
                    if item and not item.is_expired():
                        item.touch()
                        return copy.deepcopy(item)
            return None
    
    def delete(self, key: str, scope: ContextScope = None) -> bool:
        """
        删除上下文项
        
        Args:
            key: 键
            scope: 指定作用域
            
        Returns:
            是否成功删除
        """
        with self._lock:
            if scope:
                storage = self._get_storage(scope)
                if key in storage:
                    old_value = storage[key].value
                    del storage[key]
                    self._notify_listeners(key, old_value, None)
                    return True
            else:
                for s in [ContextScope.LOCAL, ContextScope.SHARED, ContextScope.GLOBAL]:
                    storage = self._get_storage(s)
                    if key in storage:
                        old_value = storage[key].value
                        del storage[key]
                        self._notify_listeners(key, old_value, None)
                        return True
            return False
    
    def exists(self, key: str, scope: ContextScope = None) -> bool:
        """检查键是否存在"""
        return self.get_item(key, scope) is not None
    
    def keys(self, scope: ContextScope = None) -> List[str]:
        """获取所有键"""
        with self._lock:
            if scope:
                storage = self._get_storage(scope)
                return [k for k, v in storage.items() if not v.is_expired()]
            else:
                all_keys = set()
                for s in [ContextScope.LOCAL, ContextScope.SHARED, ContextScope.GLOBAL]:
                    storage = self._get_storage(s)
                    all_keys.update(k for k, v in storage.items() if not v.is_expired())
                return list(all_keys)
    
    def get_all(self, scope: ContextScope = None) -> Dict[str, Any]:
        """获取所有上下文值"""
        with self._lock:
            result = {}
            scopes = [scope] if scope else [ContextScope.LOCAL, ContextScope.SHARED, ContextScope.GLOBAL]
            for s in scopes:
                storage = self._get_storage(s)
                for k, v in storage.items():
                    if not v.is_expired():
                        result[k] = v.value
            return result
    
    def get_all_items(self, scope: ContextScope = None) -> Dict[str, ContextItem]:
        """获取所有上下文项（包含元数据）"""
        with self._lock:
            result = {}
            scopes = [scope] if scope else [ContextScope.LOCAL, ContextScope.SHARED, ContextScope.GLOBAL]
            for s in scopes:
                storage = self._get_storage(s)
                for k, v in storage.items():
                    if not v.is_expired():
                        result[k] = copy.deepcopy(v)
            return result
    
    def _evict_items(self, scope: ContextScope):
        """淘汰低优先级项"""
        storage = self._get_storage(scope)
        
        # 按优先级和最后访问时间排序
        items = sorted(
            storage.items(),
            key=lambda x: (x[1].priority.value, x[1].last_access)
        )
        
        # 淘汰10%的低优先级项
        evict_count = max(1, len(items) // 10)
        for i in range(evict_count):
            key = items[i][0]
            if items[i][1].priority != ContextPriority.CRITICAL:
                del storage[key]
                log_warn(f"Evicted context item: {key}")
    
    def clear(self, scope: ContextScope = None):
        """清空上下文"""
        with self._lock:
            if scope:
                self._get_storage(scope).clear()
            else:
                self._local_context.clear()
                self._shared_context.clear()
                self._global_context.clear()
        
        log_info(f"Context cleared (scope: {scope.value if scope else 'all'})")
    
    def add_listener(self, callback: Callable[[str, Any, Any], None]):
        """添加变更监听器"""
        self._listeners.append(callback)
    
    def remove_listener(self, callback: Callable[[str, Any, Any], None]):
        """移除变更监听器"""
        if callback in self._listeners:
            self._listeners.remove(callback)
    
    def _notify_listeners(self, key: str, old_value: Any, new_value: Any):
        """通知监听器"""
        for listener in self._listeners:
            try:
                listener(key, old_value, new_value)
            except Exception as e:
                log_error(f"Context listener error: {e}")
    
    def create_snapshot(self, metadata: Dict[str, Any] = None) -> ContextSnapshot:
        """
        创建上下文快照
        
        Args:
            metadata: 快照元数据
            
        Returns:
            ContextSnapshot: 快照对象
        """
        with self._lock:
            snapshot_id = str(uuid.uuid4())
            
            # 合并所有作用域的上下文
            all_items = {}
            for scope in [ContextScope.LOCAL, ContextScope.SHARED, ContextScope.GLOBAL]:
                storage = self._get_storage(scope)
                for k, v in storage.items():
                    if not v.is_expired():
                        all_items[k] = copy.deepcopy(v)
            
            snapshot = ContextSnapshot(
                snapshot_id=snapshot_id,
                session_id=self._session_id,
                agent_name=self._agent_name,
                timestamp=time.time(),
                items=all_items,
                metadata=metadata or {}
            )
            
            self._snapshots[snapshot_id] = snapshot
            
            # 限制快照数量
            if len(self._snapshots) > self._max_snapshots:
                oldest = min(self._snapshots.keys(), key=lambda k: self._snapshots[k].timestamp)
                del self._snapshots[oldest]
            
            log_info(f"Context snapshot created: {snapshot_id}")
            return snapshot
    
    def restore_snapshot(self, snapshot_id: str, merge: bool = False) -> bool:
        """
        恢复快照
        
        Args:
            snapshot_id: 快照ID
            merge: 是否合并而非替换
            
        Returns:
            是否成功
        """
        with self._lock:
            snapshot = self._snapshots.get(snapshot_id)
            if not snapshot:
                log_error(f"Snapshot not found: {snapshot_id}")
                return False
            
            if not merge:
                self.clear()
            
            for key, item in snapshot.items.items():
                storage = self._get_storage(item.scope)
                storage[key] = copy.deepcopy(item)
            
            log_info(f"Context restored from snapshot: {snapshot_id}")
            return True
    
    def get_snapshot(self, snapshot_id: str) -> Optional[ContextSnapshot]:
        """获取快照"""
        return self._snapshots.get(snapshot_id)
    
    def list_snapshots(self) -> List[Dict[str, Any]]:
        """列出所有快照"""
        return [
            {
                "snapshot_id": s.snapshot_id,
                "timestamp": s.timestamp,
                "item_count": len(s.items),
                "metadata": s.metadata
            }
            for s in sorted(self._snapshots.values(), key=lambda x: x.timestamp, reverse=True)
        ]
    
    def export_context(self, scope: ContextScope = None) -> Dict[str, Any]:
        """
        导出上下文（用于跨Agent传递）
        
        Args:
            scope: 指定作用域
            
        Returns:
            导出的上下文数据
        """
        with self._lock:
            items = self.get_all_items(scope)
            
            return {
                "session_id": self._session_id,
                "agent_name": self._agent_name,
                "export_time": time.time(),
                "items": {k: v.to_dict() for k, v in items.items()}
            }
    
    def import_context(
        self,
        data: Dict[str, Any],
        merge: bool = True,
        prefix: str = ""
    ) -> int:
        """
        导入上下文
        
        Args:
            data: 导出的上下文数据
            merge: 是否合并
            prefix: 键前缀
            
        Returns:
            导入的项数
        """
        with self._lock:
            if not merge:
                self.clear()
            
            count = 0
            items = data.get("items", {})
            for key, item_data in items.items():
                item = ContextItem.from_dict(item_data)
                item.key = prefix + key
                item.timestamp = time.time()  # 更新时间戳
                
                storage = self._get_storage(item.scope)
                storage[item.key] = item
                count += 1
            
            log_info(f"Imported {count} context items")
            return count
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息（包含缓存统计）"""
        with self._lock:
            total_requests = self._cache_hits + self._cache_misses
            cache_hit_rate = self._cache_hits / total_requests if total_requests > 0 else 0
            
            return {
                "session_id": self._session_id,
                "agent_name": self._agent_name,
                "local_items": len(self._local_context),
                "shared_items": len(self._shared_context),
                "global_items": len(self._global_context),
                "total_items": len(self._local_context) + len(self._shared_context) + len(self._global_context),
                "snapshots": len(self._snapshots),
                "max_items": self._max_items,
                # 缓存统计
                "cache": {
                    "size": len(self._read_cache),
                    "hits": self._cache_hits,
                    "misses": self._cache_misses,
                    "hit_rate": round(cache_hit_rate, 4),
                    "ttl": self._cache_ttl
                }
            }
    
    def destroy(self):
        """销毁管理器"""
        self._stop_cleanup = True
        if self._cleanup_thread and self._cleanup_thread.is_alive():
            self._cleanup_thread.join(timeout=5)
        self.clear()
        log_info(f"ContextManager destroyed for {self._agent_name}")


class SharedContextPool:
    """
    共享上下文池
    
    用于跨Agent共享上下文数据
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._contexts: Dict[str, ContextManager] = {}
        self._session_mappings: Dict[str, Set[str]] = {}  # session_id -> set of agent_names
        self._lock = threading.RLock()
        self._initialized = True
        
        log_info("SharedContextPool initialized")
    
    def register_agent(
        self,
        agent_name: str,
        session_id: str,
        context_manager: ContextManager
    ):
        """注册Agent的上下文管理器"""
        with self._lock:
            self._contexts[agent_name] = context_manager
            
            if session_id not in self._session_mappings:
                self._session_mappings[session_id] = set()
            self._session_mappings[session_id].add(agent_name)
            
            log_info(f"Agent {agent_name} registered to session {session_id}")
    
    def unregister_agent(self, agent_name: str):
        """注销Agent"""
        with self._lock:
            if agent_name in self._contexts:
                session_id = self._contexts[agent_name]._session_id
                del self._contexts[agent_name]
                
                if session_id in self._session_mappings:
                    self._session_mappings[session_id].discard(agent_name)
                
                log_info(f"Agent {agent_name} unregistered")
    
    def get_session_agents(self, session_id: str) -> List[str]:
        """获取会话中的所有Agent"""
        with self._lock:
            return list(self._session_mappings.get(session_id, set()))
    
    def share_context(
        self,
        from_agent: str,
        to_agents: List[str],
        keys: List[str] = None,
        scope: ContextScope = ContextScope.SHARED
    ) -> int:
        """
        在Agent间共享上下文
        
        Args:
            from_agent: 源Agent
            to_agents: 目标Agent列表
            keys: 要共享的键，None表示全部
            scope: 目标作用域
            
        Returns:
            共享的项数
        """
        with self._lock:
            if from_agent not in self._contexts:
                return 0
            
            source = self._contexts[from_agent]
            count = 0
            
            # 获取要共享的数据
            if keys:
                items = {k: source.get_item(k) for k in keys}
                items = {k: v for k, v in items.items() if v}
            else:
                items = source.get_all_items()
            
            # 共享给目标Agent
            for target in to_agents:
                if target in self._contexts and target != from_agent:
                    target_mgr = self._contexts[target]
                    for key, item in items.items():
                        target_mgr.set(
                            key=f"shared.{from_agent}.{key}",
                            value=item.value,
                            scope=scope,
                            priority=item.priority,
                            metadata={
                                **item.metadata,
                                "shared_from": from_agent,
                                "original_key": key
                            }
                        )
                        count += 1
            
            log_info(f"Shared {count} context items from {from_agent} to {len(to_agents)} agents")
            return count
    
    def broadcast_context(
        self,
        from_agent: str,
        data: Dict[str, Any],
        scope: ContextScope = ContextScope.SHARED
    ) -> int:
        """
        广播上下文给同会话的所有Agent
        
        Args:
            from_agent: 源Agent
            data: 要广播的数据
            scope: 目标作用域
            
        Returns:
            广播的Agent数
        """
        with self._lock:
            if from_agent not in self._contexts:
                return 0
            
            source = self._contexts[from_agent]
            session_id = source._session_id
            agents = self.get_session_agents(session_id)
            
            count = 0
            for target in agents:
                if target in self._contexts and target != from_agent:
                    target_mgr = self._contexts[target]
                    for key, value in data.items():
                        target_mgr.set(
                            key=f"broadcast.{from_agent}.{key}",
                            value=value,
                            scope=scope,
                            metadata={"broadcast_from": from_agent}
                        )
                    count += 1
            
            log_info(f"Broadcast context from {from_agent} to {count} agents")
            return count


# 全局共享上下文池实例
shared_context_pool = SharedContextPool()


def create_context_manager(
    agent_name: str,
    session_id: str = None,
    register_to_pool: bool = True,
    **kwargs
) -> ContextManager:
    """
    创建上下文管理器
    
    Args:
        agent_name: Agent名称
        session_id: 会话ID
        register_to_pool: 是否注册到共享池
        **kwargs: 其他参数
        
    Returns:
        ContextManager实例
    """
    manager = ContextManager(agent_name, session_id, **kwargs)
    
    if register_to_pool:
        shared_context_pool.register_agent(agent_name, manager._session_id, manager)
    
    return manager
