"""
资源管理模块

@file: core/resource_manager.py
@date: 2026-04-08
@version: 1.0.0
@description: 统一资源管理，包括连接池、缓存、限流等
"""

import time
import asyncio
import threading
from typing import Any, Dict, List, Optional, Callable, TypeVar, Generic
from dataclasses import dataclass, field
from collections import deque
from contextlib import contextmanager
from enum import Enum
import weakref

from ai_novels.utils import log_info, log_warn, log_error, get_logger


T = TypeVar('T')


class ResourceStatus(Enum):
    """资源状态"""
    IDLE = "idle"
    IN_USE = "in_use"
    EXPIRED = "expired"
    ERROR = "error"


@dataclass
class ResourceInfo:
    """资源信息"""
    resource: Any
    created_at: float = field(default_factory=time.time)
    last_used: float = field(default_factory=time.time)
    use_count: int = 0
    status: ResourceStatus = ResourceStatus.IDLE
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def touch(self):
        """更新最后使用时间"""
        self.last_used = time.time()
        self.use_count += 1


class ConnectionPool:
    """
    通用连接池
    
    管理可重用资源的池化
    """
    
    def __init__(
        self,
        name: str,
        factory: Callable[[], T],
        max_size: int = 10,
        min_size: int = 2,
        max_idle_time: float = 300,  # 5分钟
        max_lifetime: float = 3600,  # 1小时
        validate_on_borrow: bool = True
    ):
        self.name = name
        self._factory = factory
        self._max_size = max_size
        self._min_size = min_size
        self._max_idle_time = max_idle_time
        self._max_lifetime = max_lifetime
        self._validate_on_borrow = validate_on_borrow
        
        self._pool: deque = deque()
        self._in_use: Dict[int, ResourceInfo] = {}
        self._lock = threading.RLock()
        self._semaphore = threading.Semaphore(max_size)
        
        self._logger = get_logger()
        
        # 初始化最小连接数
        self._initialize_min_connections()
    
    def _initialize_min_connections(self):
        """初始化最小连接数"""
        for _ in range(self._min_size):
            try:
                resource = self._factory()
                info = ResourceInfo(resource=resource)
                self._pool.append(info)
            except Exception as e:
                self._logger.database_error(f"Failed to create initial connection for {self.name}", error=str(e))
    
    def _create_resource(self) -> Optional[ResourceInfo]:
        """创建新资源"""
        try:
            resource = self._factory()
            return ResourceInfo(resource=resource)
        except Exception as e:
            self._logger.database_error(f"Failed to create resource for {self.name}", error=str(e))
            return None
    
    def _validate_resource(self, info: ResourceInfo) -> bool:
        """验证资源是否可用"""
        # 检查是否过期
        now = time.time()
        if now - info.created_at > self._max_lifetime:
            return False
        if now - info.last_used > self._max_idle_time:
            return False
        
        # 检查状态
        if info.status == ResourceStatus.ERROR:
            return False
        
        return True
    
    def _destroy_resource(self, info: ResourceInfo):
        """销毁资源"""
        try:
            if hasattr(info.resource, 'close'):
                info.resource.close()
            elif hasattr(info.resource, 'disconnect'):
                info.resource.disconnect()
        except Exception as e:
            self._logger.database_error(f"Error destroying resource for {self.name}", error=str(e))
    
    @contextmanager
    def acquire(self, timeout: float = 30.0):
        """
        获取资源（上下文管理器）
        
        Args:
            timeout: 获取超时时间（秒）
            
        Usage:
            with pool.acquire() as conn:
                conn.query(...)
        """
        info = None
        acquired = self._semaphore.acquire(timeout=timeout)
        
        if not acquired:
            raise TimeoutError(f"Failed to acquire resource from pool {self.name} within {timeout}s")
        
        try:
            with self._lock:
                # 尝试从池中获取可用资源
                while self._pool:
                    info = self._pool.popleft()
                    
                    if not self._validate_on_borrow or self._validate_resource(info):
                        break
                    else:
                        # 资源无效，销毁
                        self._destroy_resource(info)
                        info = None
                
                # 如果池中没有可用资源，创建新的
                if info is None:
                    info = self._create_resource()
                    if info is None:
                        raise RuntimeError(f"Failed to create resource for pool {self.name}")
                
                # 标记为使用中
                info.status = ResourceStatus.IN_USE
                info.touch()
                self._in_use[id(info.resource)] = info
            
            yield info.resource
            
        finally:
            if info is not None:
                with self._lock:
                    info.status = ResourceStatus.IDLE
                    if id(info.resource) in self._in_use:
                        del self._in_use[id(info.resource)]
                    
                    # 如果资源仍然有效，归还到池中
                    if self._validate_resource(info):
                        self._pool.append(info)
                    else:
                        self._destroy_resource(info)
                
                self._semaphore.release()
    
    def get_stats(self) -> Dict[str, Any]:
        """获取连接池统计信息"""
        with self._lock:
            return {
                "name": self.name,
                "pool_size": len(self._pool),
                "in_use": len(self._in_use),
                "max_size": self._max_size,
                "min_size": self._min_size
            }
    
    def close_all(self):
        """关闭所有连接"""
        with self._lock:
            # 关闭池中的连接
            while self._pool:
                info = self._pool.popleft()
                self._destroy_resource(info)
            
            # 关闭使用中的连接
            for info in list(self._in_use.values()):
                self._destroy_resource(info)
            self._in_use.clear()


class CacheManager:
    """
    缓存管理器
    
    支持TTL、LRU淘汰策略的多级缓存
    """
    
    def __init__(
        self,
        max_size: int = 1000,
        default_ttl: float = 300,  # 5分钟
        cleanup_interval: float = 60  # 1分钟
    ):
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._cleanup_interval = cleanup_interval
        
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._access_order: deque = deque()
        self._lock = threading.RLock()
        
        self._logger = get_logger()
        
        # 启动清理线程
        self._cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self._cleanup_thread.start()
    
    def _cleanup_loop(self):
        """清理过期条目的循环"""
        while True:
            time.sleep(self._cleanup_interval)
            try:
                self._cleanup_expired()
            except Exception as e:
                self._logger.error(f"Cache cleanup error: {e}")
    
    def _cleanup_expired(self):
        """清理过期条目"""
        now = time.time()
        expired_keys = []
        
        with self._lock:
            for key, entry in self._cache.items():
                if entry["expires_at"] < now:
                    expired_keys.append(key)
            
            for key in expired_keys:
                del self._cache[key]
                if key in self._access_order:
                    self._access_order.remove(key)
        
        if expired_keys:
            self._logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")
    
    def _evict_lru(self):
        """LRU淘汰"""
        while len(self._cache) >= self._max_size and self._access_order:
            oldest_key = self._access_order.popleft()
            if oldest_key in self._cache:
                del self._cache[oldest_key]
                break
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        获取缓存值
        
        Args:
            key: 缓存键
            default: 默认值
            
        Returns:
            缓存值或默认值
        """
        with self._lock:
            entry = self._cache.get(key)
            
            if entry is None:
                return default
            
            # 检查是否过期
            if entry["expires_at"] < time.time():
                del self._cache[key]
                if key in self._access_order:
                    self._access_order.remove(key)
                return default
            
            # 更新访问顺序
            if key in self._access_order:
                self._access_order.remove(key)
            self._access_order.append(key)
            
            return entry["value"]
    
    def set(
        self,
        key: str,
        value: Any,
        ttl: float = None,
        tags: List[str] = None
    ):
        """
        设置缓存值
        
        Args:
            key: 缓存键
            value: 缓存值
            ttl: 过期时间（秒），None使用默认值
            tags: 标签列表，用于批量清理
        """
        ttl = ttl or self._default_ttl
        
        with self._lock:
            # LRU淘汰
            if key not in self._cache and len(self._cache) >= self._max_size:
                self._evict_lru()
            
            self._cache[key] = {
                "value": value,
                "expires_at": time.time() + ttl,
                "created_at": time.time(),
                "tags": tags or []
            }
            
            # 更新访问顺序
            if key in self._access_order:
                self._access_order.remove(key)
            self._access_order.append(key)
    
    def delete(self, key: str) -> bool:
        """
        删除缓存条目
        
        Args:
            key: 缓存键
            
        Returns:
            是否成功删除
        """
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                if key in self._access_order:
                    self._access_order.remove(key)
                return True
            return False
    
    def clear_by_tag(self, tag: str):
        """
        按标签清理缓存
        
        Args:
            tag: 标签
        """
        with self._lock:
            keys_to_delete = [
                key for key, entry in self._cache.items()
                if tag in entry.get("tags", [])
            ]
            
            for key in keys_to_delete:
                del self._cache[key]
                if key in self._access_order:
                    self._access_order.remove(key)
            
            self._logger.debug(f"Cleared {len(keys_to_delete)} cache entries with tag '{tag}'")
    
    def clear(self):
        """清空所有缓存"""
        with self._lock:
            self._cache.clear()
            self._access_order.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        with self._lock:
            now = time.time()
            expired_count = sum(
                1 for entry in self._cache.values()
                if entry["expires_at"] < now
            )
            
            return {
                "size": len(self._cache),
                "max_size": self._max_size,
                "expired_entries": expired_count,
                "utilization": len(self._cache) / self._max_size if self._max_size > 0 else 0
            }


class RateLimiter:
    """
    限流器
    
    支持令牌桶和滑动窗口算法
    """
    
    def __init__(
        self,
        rate: float = 10.0,  # 每秒请求数
        burst: int = 20,     # 突发容量
        algorithm: str = "token_bucket"  # "token_bucket" or "sliding_window"
    ):
        self._rate = rate
        self._burst = burst
        self._algorithm = algorithm
        
        # 令牌桶
        self._tokens = burst
        self._last_update = time.time()
        self._lock = threading.Lock()
        
        # 滑动窗口
        self._window_size = 1.0  # 1秒窗口
        self._requests: deque = deque()
    
    def _update_tokens(self):
        """更新令牌数量"""
        now = time.time()
        elapsed = now - self._last_update
        self._tokens = min(self._burst, self._tokens + elapsed * self._rate)
        self._last_update = now
    
    def _allow_token_bucket(self) -> bool:
        """令牌桶算法"""
        with self._lock:
            self._update_tokens()
            
            if self._tokens >= 1:
                self._tokens -= 1
                return True
            return False
    
    def _allow_sliding_window(self) -> bool:
        """滑动窗口算法"""
        with self._lock:
            now = time.time()
            window_start = now - self._window_size
            
            # 移除窗口外的请求
            while self._requests and self._requests[0] < window_start:
                self._requests.popleft()
            
            # 检查是否超过限制
            if len(self._requests) < self._rate:
                self._requests.append(now)
                return True
            return False
    
    def allow(self) -> bool:
        """
        检查是否允许请求
        
        Returns:
            是否允许
        """
        if self._algorithm == "token_bucket":
            return self._allow_token_bucket()
        else:
            return self._allow_sliding_window()
    
    def acquire(self, timeout: float = None) -> bool:
        """
        获取许可（阻塞）
        
        Args:
            timeout: 超时时间（秒）
            
        Returns:
            是否成功获取
        """
        start_time = time.time()
        
        while True:
            if self.allow():
                return True
            
            if timeout is not None:
                if time.time() - start_time >= timeout:
                    return False
            
            time.sleep(0.01)  # 10ms


class ResourceManager:
    """
    资源管理器
    
    统一管理所有资源：连接池、缓存、限流器等
    """
    
    _instance: Optional['ResourceManager'] = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        
        self._initialized = True
        self._pools: Dict[str, ConnectionPool] = {}
        self._caches: Dict[str, CacheManager] = {}
        self._limiters: Dict[str, RateLimiter] = {}
        self._lock = threading.RLock()
        
        self._logger = get_logger()
    
    def create_pool(
        self,
        name: str,
        factory: Callable[[], T],
        **kwargs
    ) -> ConnectionPool:
        """
        创建连接池
        
        Args:
            name: 池名称
            factory: 资源工厂函数
            **kwargs: 其他配置参数
            
        Returns:
            连接池实例
        """
        with self._lock:
            if name in self._pools:
                return self._pools[name]
            
            pool = ConnectionPool(name, factory, **kwargs)
            self._pools[name] = pool
            self._logger.info(f"Created connection pool: {name}")
            return pool
    
    def get_pool(self, name: str) -> Optional[ConnectionPool]:
        """获取连接池"""
        with self._lock:
            return self._pools.get(name)
    
    def create_cache(
        self,
        name: str,
        max_size: int = 1000,
        default_ttl: float = 300
    ) -> CacheManager:
        """
        创建缓存
        
        Args:
            name: 缓存名称
            max_size: 最大容量
            default_ttl: 默认TTL
            
        Returns:
            缓存管理器实例
        """
        with self._lock:
            if name in self._caches:
                return self._caches[name]
            
            cache = CacheManager(max_size, default_ttl)
            self._caches[name] = cache
            self._logger.info(f"Created cache: {name}")
            return cache
    
    def get_cache(self, name: str) -> Optional[CacheManager]:
        """获取缓存"""
        with self._lock:
            return self._caches.get(name)
    
    def create_limiter(
        self,
        name: str,
        rate: float = 10.0,
        burst: int = 20,
        algorithm: str = "token_bucket"
    ) -> RateLimiter:
        """
        创建限流器
        
        Args:
            name: 限流器名称
            rate: 速率
            burst: 突发容量
            algorithm: 算法
            
        Returns:
            限流器实例
        """
        with self._lock:
            if name in self._limiters:
                return self._limiters[name]
            
            limiter = RateLimiter(rate, burst, algorithm)
            self._limiters[name] = limiter
            self._logger.info(f"Created rate limiter: {name}")
            return limiter
    
    def get_limiter(self, name: str) -> Optional[RateLimiter]:
        """获取限流器"""
        with self._lock:
            return self._limiters.get(name)
    
    def get_all_stats(self) -> Dict[str, Any]:
        """获取所有资源统计信息"""
        with self._lock:
            return {
                "pools": {name: pool.get_stats() for name, pool in self._pools.items()},
                "caches": {name: cache.get_stats() for name, cache in self._caches.items()},
                "limiters": {name: {"rate": limiter._rate, "burst": limiter._burst} 
                           for name, limiter in self._limiters.items()}
            }
    
    def shutdown(self):
        """关闭所有资源"""
        with self._lock:
            # 关闭所有连接池
            for name, pool in self._pools.items():
                self._logger.info(f"Closing connection pool: {name}")
                pool.close_all()
            self._pools.clear()
            
            # 清空所有缓存
            for name, cache in self._caches.items():
                self._logger.info(f"Clearing cache: {name}")
                cache.clear()
            self._caches.clear()
            
            self._limiters.clear()


# 全局资源管理器
resource_manager = ResourceManager()


# 便捷函数
def get_global_cache(name: str = "default") -> CacheManager:
    """获取全局缓存"""
    return resource_manager.get_cache(name) or resource_manager.create_cache(name)


def get_global_limiter(name: str = "default", rate: float = 10.0) -> RateLimiter:
    """获取全局限流器"""
    return resource_manager.get_limiter(name) or resource_manager.create_limiter(name, rate)
