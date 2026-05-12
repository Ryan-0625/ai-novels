"""
LLM 缓存层实现

@file: llm/cache.py
@date: 2026-03-13
@author: AI-Novels Team
@version: 1.0
@description: 实现 LLM 调用结果缓存，提高响应速度和降低成本
"""

import hashlib
import json
import time
import threading
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
from functools import wraps


class CacheStrategy(Enum):
    """缓存策略"""
    LRU = "lru"
    FIFO = "fifo"
    LFU = "lfu"
    TTL = "ttl"


@dataclass
class CacheEntry:
    """缓存条目"""
    key: str
    value: Any
    created_at: float = field(default_factory=time.time)
    accessed_at: float = field(default_factory=time.time)
    hit_count: int = 0
    ttl: Optional[int] = None

    def is_expired(self) -> bool:
        """检查是否过期"""
        if self.ttl is None:
            return False
        return time.time() - self.created_at > self.ttl

    def touch(self):
        """更新访问时间"""
        self.accessed_at = time.time()
        self.hit_count += 1


class LRUCache:
    """LRU 缓存实现"""

    def __init__(self, capacity: int = 1000):
        self.capacity = capacity
        self.cache: Dict[str, CacheEntry] = {}
        self.lru_list: List[str] = []
        self.lock = threading.RLock()

    def get(self, key: str) -> Optional[CacheEntry]:
        """获取缓存项"""
        with self.lock:
            if key not in self.cache:
                return None

            entry = self.cache[key]
            if entry.is_expired():
                self._remove(key)
                return None

            self._touch(key)
            entry.touch()
            return entry

    def put(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """添加缓存项"""
        with self.lock:
            if key in self.cache:
                self._remove(key)

            while len(self.cache) >= self.capacity:
                if self.lru_list:
                    oldest_key = self.lru_list.pop(0)
                    self._remove(oldest_key)

            entry = CacheEntry(key=key, value=value, ttl=ttl)
            self.cache[key] = entry
            self.lru_list.append(key)
            return True

    def delete(self, key: str) -> bool:
        """删除缓存项"""
        with self.lock:
            return self._remove(key)

    def clear(self):
        """清空缓存"""
        with self.lock:
            self.cache.clear()
            self.lru_list.clear()

    def size(self) -> int:
        """获取缓存大小"""
        with self.lock:
            return len(self.cache)

    def keys(self) -> List[str]:
        """获取所有键"""
        with self.lock:
            return list(self.cache.keys())

    def _remove(self, key: str) -> bool:
        """内部删除方法"""
        if key in self.cache:
            del self.cache[key]
            if key in self.lru_list:
                self.lru_list.remove(key)
            return True
        return False

    def _touch(self, key: str):
        """更新访问顺序"""
        if key in self.lru_list:
            self.lru_list.remove(key)
        self.lru_list.append(key)


class TTLCache:
    """基于 TTL 的缓存实现"""

    def __init__(self, default_ttl: int = 3600):
        self.default_ttl = default_ttl
        self.cache: Dict[str, CacheEntry] = {}
        self.lock = threading.RLock()

    def get(self, key: str, ttl: Optional[int] = None) -> Optional[CacheEntry]:
        """获取缓存项"""
        with self.lock:
            if key not in self.cache:
                return None

            entry = self.cache[key]
            if entry.is_expired():
                self._remove(key)
                return None

            entry.touch()
            return entry

    def put(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """添加缓存项"""
        with self.lock:
            if key in self.cache:
                self._remove(key)

            entry = CacheEntry(key=key, value=value, ttl=ttl or self.default_ttl)
            self.cache[key] = entry
            return True

    def delete(self, key: str) -> bool:
        """删除缓存项"""
        with self.lock:
            return self._remove(key)

    def clear(self):
        """清空缓存"""
        with self.lock:
            self.cache.clear()

    def cleanup_expired(self) -> int:
        """清理过期项"""
        with self.lock:
            expired_keys = [
                key for key, entry in self.cache.items()
                if entry.is_expired()
            ]
            for key in expired_keys:
                self._remove(key)
            return len(expired_keys)

    def _remove(self, key: str) -> bool:
        """内部删除方法"""
        if key in self.cache:
            del self.cache[key]
            return True
        return False


class LLMCache:
    """LLM 调用缓存"""

    def __init__(
        self,
        strategy: CacheStrategy = CacheStrategy.LRU,
        capacity: int = 1000,
        default_ttl: int = 3600
    ):
        self.strategy = strategy
        self.capacity = capacity
        self.default_ttl = default_ttl

        if strategy == CacheStrategy.LRU:
            self.backend = LRUCache(capacity)
        elif strategy == CacheStrategy.TTL:
            self.backend = TTLCache(default_ttl)
        else:
            self.backend = LRUCache(capacity)

        self.stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'deletes': 0,
            'cache_size': 0
        }
        self.stats_lock = threading.RLock()

    def generate_key(self, prompt: str, provider: str = None, model: str = None, **kwargs) -> str:
        """生成缓存键"""
        key_parts = {
            'prompt': prompt,
            'provider': provider or 'default',
            'model': model or 'default',
        }

        if 'temperature' in kwargs:
            key_parts['temperature'] = kwargs['temperature']
        if 'max_tokens' in kwargs:
            key_parts['max_tokens'] = kwargs['max_tokens']
        if 'system_prompt' in kwargs and kwargs['system_prompt']:
            key_parts['system_prompt'] = kwargs['system_prompt']

        key_str = json.dumps(key_parts, sort_keys=True)
        return hashlib.sha256(key_str.encode()).hexdigest()[:32]

    def get(self, key: str) -> Optional[Any]:
        """获取缓存结果"""
        entry = self.backend.get(key)
        if entry:
            with self.stats_lock:
                self.stats['hits'] += 1
            return entry.value
        else:
            with self.stats_lock:
                self.stats['misses'] += 1
            return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """设置缓存结果"""
        result = self.backend.put(key, value, ttl or self.default_ttl)
        with self.stats_lock:
            self.stats['sets'] += 1
            self.stats['cache_size'] = self.backend.size()
        return result

    def delete(self, key: str) -> bool:
        """删除缓存项"""
        result = self.backend.delete(key)
        with self.stats_lock:
            self.stats['deletes'] += 1
            self.stats['cache_size'] = self.backend.size()
        return result

    def clear(self):
        """清空缓存"""
        self.backend.clear()
        with self.stats_lock:
            self.stats['cache_size'] = 0

    def cleanup(self) -> int:
        """清理过期项"""
        if hasattr(self.backend, 'cleanup_expired'):
            return self.backend.cleanup_expired()
        return 0

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self.stats_lock:
            total = self.stats['hits'] + self.stats['misses']
            hit_rate = self.stats['hits'] / total if total > 0 else 0

            return {
                **self.stats,
                'hit_rate': f"{hit_rate:.2%}",
                'total_requests': total
            }

    def size(self) -> int:
        """获取缓存大小"""
        return self.backend.size()


# 全局缓存实例
_global_cache: Optional[LLMCache] = None


def get_llm_cache() -> LLMCache:
    """获取全局 LLM 缓存实例"""
    global _global_cache
    if _global_cache is None:
        _global_cache = LLMCache(
            strategy=CacheStrategy.LRU,
            capacity=1000,
            default_ttl=3600
        )
    return _global_cache


def cache_result(ttl: Optional[int] = None, key_prefix: str = ""):
    """缓存装饰器"""
    def decorator(func: Callable) -> Callable:
        cache = get_llm_cache()

        @wraps(func)
        def wrapper(*args, **kwargs):
            cache_key = f"{key_prefix}:{cache.generate_key(str(args), **kwargs)}"

            cached = cache.get(cache_key)
            if cached is not None:
                return cached

            result = func(*args, **kwargs)
            cache.set(cache_key, result, ttl)

            return result

        return wrapper
    return decorator


def start_cache_cleanup_scheduler(interval: int = 300):
    """启动缓存清理定时任务"""
    import threading

    def cleanup_loop():
        while True:
            time.sleep(interval)
            cache = get_llm_cache()
            cleaned = cache.cleanup()
            if cleaned > 0:
                print(f"[LLMCache] Cleaned up {cleaned} expired entries")

    thread = threading.Thread(target=cleanup_loop, daemon=True)
    thread.start()
    return thread


if __name__ == "__main__":
    cache = get_llm_cache()

    key = cache.generate_key(
        prompt="你好",
        provider="ollama",
        model="qwen2.5-14b"
    )
    print(f"Cache key: {key}")

    cache.set(key, {"result": "Hello!"})
    result = cache.get(key)
    print(f"Cache result: {result}")

    print(f"Stats: {cache.get_stats()}")
