"""
连接池模块测试

@file: test_database/test_connection_pool.py
@description: 测试数据库连接池的核心功能
"""

import pytest
import time
import threading
from unittest.mock import Mock, patch

from ai_novels.database.connection_pool import (
    ConnectionStatus,
    ConnectionWrapper,
    BaseConnectionPool
)


class MockConnectionPool(BaseConnectionPool):
    """模拟连接池实现，用于测试"""
    
    def _create_connection(self):
        return Mock()
    
    def _close_connection(self, conn):
        pass


class TestConnectionStatus:
    """测试连接状态枚举"""
    
    def test_status_values(self):
        """测试状态枚举值"""
        assert ConnectionStatus.IDLE.value == "idle"
        assert ConnectionStatus.IN_USE.value == "in_use"
        assert ConnectionStatus.ERROR.value == "error"


class TestConnectionWrapper:
    """测试连接包装器"""
    
    def test_init_default_values(self):
        """测试初始化默认值"""
        mock_conn = Mock()
        wrapper = ConnectionWrapper(connection=mock_conn)
        
        assert wrapper.connection == mock_conn
        assert wrapper.status == ConnectionStatus.IDLE
        assert wrapper.use_count == 0
        assert isinstance(wrapper.created_at, float)
        assert isinstance(wrapper.last_used, float)
    
    def test_touch_updates_fields(self):
        """测试touch方法更新字段"""
        mock_conn = Mock()
        wrapper = ConnectionWrapper(connection=mock_conn)
        
        initial_last_used = wrapper.last_used
        time.sleep(0.01)
        
        wrapper.touch()
        
        assert wrapper.use_count == 1
        assert wrapper.last_used > initial_last_used
    
    def test_touch_multiple_times(self):
        """测试多次touch"""
        mock_conn = Mock()
        wrapper = ConnectionWrapper(connection=mock_conn)
        
        for i in range(5):
            wrapper.touch()
        
        assert wrapper.use_count == 5


class TestBaseConnectionPool:
    """测试连接池基类"""
    
    def test_init_default_params(self):
        """测试默认参数初始化"""
        pool = MockConnectionPool(name="test_pool")
        
        assert pool.name == "test_pool"
        assert pool._max_size == 10
        assert pool._min_size == 2
        assert pool._max_idle_time == 300
        assert pool._max_lifetime == 3600
    
    def test_init_custom_params(self):
        """测试自定义参数初始化"""
        pool = MockConnectionPool(
            name="custom_pool",
            max_size=20,
            min_size=5,
            max_idle_time=600,
            max_lifetime=7200
        )
        
        assert pool.name == "custom_pool"
        assert pool._max_size == 20
        assert pool._min_size == 5
        assert pool._max_idle_time == 600
        assert pool._max_lifetime == 7200
    
    def test_initialize_creates_min_connections(self):
        """测试初始化创建最小连接数"""
        pool = MockConnectionPool(name="test_pool", min_size=3)
        pool.initialize()
        
        assert len(pool._pool) == 3
        for wrapper in pool._pool:
            assert wrapper.status == ConnectionStatus.IDLE
    
    def test_initialize_handles_creation_failure(self):
        """测试初始化处理连接创建失败"""
        pool = MockConnectionPool(name="test_pool", min_size=3)
        
        # 模拟前两次创建失败
        call_count = 0
        def mock_create():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise Exception("Connection failed")
            return Mock()
        
        pool._create_connection = mock_create
        
        with patch('ai_novels.database.connection_pool.log_error'):
            pool.initialize()
        
        # 只有第三次成功
        assert len(pool._pool) == 1
    
    def test_acquire_gets_connection(self):
        """测试获取连接"""
        pool = MockConnectionPool(name="test_pool", min_size=1)
        pool.initialize()
        
        with pool.acquire() as conn:
            assert conn is not None
            assert len(pool._in_use) == 1
    
    def test_acquire_releases_connection(self):
        """测试释放连接"""
        pool = MockConnectionPool(name="test_pool", min_size=1)
        pool.initialize()
        
        with pool.acquire() as conn:
            pass
        
        # 释放后应该回到池中
        assert len(pool._in_use) == 0
        assert len(pool._pool) == 1
    
    def test_acquire_timeout(self):
        """测试获取连接超时"""
        pool = MockConnectionPool(name="test_pool", max_size=1, min_size=0)
        
        # 占用唯一连接
        with pool.acquire() as conn:
            # 尝试再次获取应该超时
            with pytest.raises(TimeoutError):
                with pool.acquire(timeout=0.1) as conn2:
                    pass
    
    def test_acquire_creates_new_connection(self):
        """测试获取时创建新连接"""
        pool = MockConnectionPool(name="test_pool", min_size=0)
        
        with pool.acquire() as conn:
            assert conn is not None
            assert len(pool._in_use) == 1
    
    def test_get_stats(self):
        """测试获取统计信息"""
        pool = MockConnectionPool(name="test_pool", max_size=10, min_size=2)
        pool.initialize()
        
        stats = pool.get_stats()
        
        assert stats["name"] == "test_pool"
        assert stats["pool_size"] == 2
        assert stats["in_use"] == 0
        assert stats["max_size"] == 10
    
    def test_get_stats_with_in_use(self):
        """测试有连接在使用时的统计"""
        pool = MockConnectionPool(name="test_pool", min_size=2)
        pool.initialize()
        
        with pool.acquire() as conn:
            stats = pool.get_stats()
            assert stats["in_use"] == 1
            assert stats["pool_size"] == 1
    
    def test_close_all(self):
        """测试关闭所有连接"""
        pool = MockConnectionPool(name="test_pool", min_size=3)
        pool.initialize()
        
        pool.close_all()
        
        assert len(pool._pool) == 0
        assert len(pool._in_use) == 0
    
    def test_close_all_with_in_use(self):
        """测试关闭包含使用中的连接"""
        pool = MockConnectionPool(name="test_pool", min_size=2)
        pool.initialize()
        
        with pool.acquire() as conn:
            pool.close_all()
            
            assert len(pool._pool) == 0
            assert len(pool._in_use) == 0
    
    def test_acquire_expired_connection(self):
        """测试获取过期连接时创建新连接"""
        pool = MockConnectionPool(
            name="test_pool",
            min_size=1,
            max_lifetime=0.01  # 10ms过期
        )
        pool.initialize()
        
        # 等待连接过期
        time.sleep(0.02)
        
        with pool.acquire() as conn:
            assert conn is not None
    
    def test_concurrent_acquire(self):
        """测试并发获取连接"""
        pool = MockConnectionPool(name="test_pool", max_size=5, min_size=2)
        pool.initialize()
        
        results = []
        errors = []
        
        def worker():
            try:
                with pool.acquire() as conn:
                    results.append(conn)
                    time.sleep(0.05)
            except Exception as e:
                errors.append(e)
        
        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert len(errors) == 0
        assert len(results) == 10
