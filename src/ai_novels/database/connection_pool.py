"""
数据库连接池模块

@file: database/connection_pool.py
@date: 2026-04-08
@version: 1.0.0
@description: 数据库连接池实现
"""

import time
import threading
from typing import Any, Dict, List, Optional
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod

from ai_novels.utils import log_error, get_logger


class ConnectionStatus(Enum):
    """连接状态"""
    IDLE = "idle"
    IN_USE = "in_use"
    ERROR = "error"


@dataclass
class ConnectionWrapper:
    """连接包装器"""
    connection: Any
    created_at: float = field(default_factory=time.time)
    last_used: float = field(default_factory=time.time)
    use_count: int = 0
    status: ConnectionStatus = ConnectionStatus.IDLE
    
    def touch(self):
        self.last_used = time.time()
        self.use_count += 1


class BaseConnectionPool(ABC):
    """数据库连接池基类"""
    
    def __init__(
        self,
        name: str,
        max_size: int = 10,
        min_size: int = 2,
        max_idle_time: float = 300,
        max_lifetime: float = 3600
    ):
        self.name = name
        self._max_size = max_size
        self._min_size = min_size
        self._max_idle_time = max_idle_time
        self._max_lifetime = max_lifetime
        
        self._pool: List[ConnectionWrapper] = []
        self._in_use: Dict[int, ConnectionWrapper] = {}
        self._lock = threading.RLock()
        self._semaphore = threading.Semaphore(max_size)
        self._logger = get_logger()
    
    @abstractmethod
    def _create_connection(self):
        pass
    
    @abstractmethod
    def _close_connection(self, conn):
        pass
    
    def initialize(self):
        """初始化连接池"""
        with self._lock:
            for _ in range(self._min_size):
                try:
                    conn = self._create_connection()
                    if conn:
                        self._pool.append(ConnectionWrapper(connection=conn))
                except Exception as e:
                    log_error(f"Failed to create connection: {e}")
    
    @contextmanager
    def acquire(self, timeout: float = 30.0):
        """获取连接"""
        wrapper = None
        acquired = self._semaphore.acquire(timeout=timeout)
        
        if not acquired:
            raise TimeoutError(f"Failed to acquire connection within {timeout}s")
        
        try:
            with self._lock:
                # 获取可用连接
                for i, w in enumerate(self._pool):
                    if time.time() - w.created_at < self._max_lifetime:
                        wrapper = w
                        wrapper.status = ConnectionStatus.IN_USE
                        wrapper.touch()
                        self._in_use[id(wrapper.connection)] = wrapper
                        self._pool.pop(i)
                        break
                
                # 创建新连接
                if wrapper is None and len(self._in_use) < self._max_size:
                    conn = self._create_connection()
                    if conn:
                        wrapper = ConnectionWrapper(connection=conn)
                        wrapper.status = ConnectionStatus.IN_USE
                        self._in_use[id(conn)] = wrapper
            
            if wrapper is None:
                raise RuntimeError("Failed to get connection")
            
            yield wrapper.connection
            
        finally:
            if wrapper:
                with self._lock:
                    if id(wrapper.connection) in self._in_use:
                        del self._in_use[id(wrapper.connection)]
                    wrapper.status = ConnectionStatus.IDLE
                    self._pool.append(wrapper)
            self._semaphore.release()
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self._lock:
            return {
                "name": self.name,
                "pool_size": len(self._pool),
                "in_use": len(self._in_use),
                "max_size": self._max_size
            }
    
    def close_all(self):
        """关闭所有连接"""
        with self._lock:
            for wrapper in self._pool:
                self._close_connection(wrapper.connection)
            for wrapper in self._in_use.values():
                self._close_connection(wrapper.connection)
            self._pool.clear()
            self._in_use.clear()
