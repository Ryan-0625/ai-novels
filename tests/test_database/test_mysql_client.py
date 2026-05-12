"""
MySQL客户端测试

@file: test_database/test_mysql_client.py
@description: 测试MySQL数据库客户端功能
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import mysql.connector
from mysql.connector import Error

from ai_novels.database.mysql_client import MySQLClient


class TestMySQLClientInit:
    """测试MySQL客户端初始化"""
    
    def test_init_with_config_dict(self):
        """测试使用配置字典初始化"""
        config = {
            "host": "test_host",
            "port": 3307,
            "user": "test_user",
            "password": "test_pass",
            "database": "test_db",
            "pool_name": "test_pool",
            "pool_size": 10
        }
        
        client = MySQLClient(config=config)
        
        assert client._host == "test_host"
        assert client._port == 3307
        assert client._user == "test_user"
        assert client._password == "test_pass"
        assert client._database == "test_db"
        assert client._pool_name == "test_pool"
        assert client._pool_size == 10
    
    def test_init_with_default_config(self):
        """测试使用默认配置初始化"""
        with patch('ai_novels.database.mysql_client.settings') as mock_settings:
            mock_settings.get_database.return_value = {
                "host": "localhost",
                "port": 3306,
                "user": "root",
                "password": "",
                "database": "ai_novels",
                "pool_name": "default_pool",
                "max_connections": 5
            }
            
            client = MySQLClient()
            
            assert client._host == "localhost"
            assert client._port == 3306
            assert client._user == "root"
            assert client._pool is None
            assert client._is_connected is False
    
    def test_init_with_explicit_params(self):
        """测试使用显式参数初始化"""
        with patch('ai_novels.database.mysql_client.settings') as mock_settings:
            mock_settings.get_database.return_value = {}
            
            client = MySQLClient(
                host="explicit_host",
                port=3308,
                user="explicit_user",
                password="explicit_pass",
                database="explicit_db"
            )
            
            assert client._host == "explicit_host"
            assert client._port == 3308
            assert client._user == "explicit_user"
            assert client._password == "explicit_pass"
            assert client._database == "explicit_db"


class TestMySQLClientConnect:
    """测试MySQL连接功能"""
    
    @patch('ai_novels.database.mysql_client.pooling.MySQLConnectionPool')
    def test_connect_success(self, mock_pool_class):
        """测试连接成功"""
        mock_pool = Mock()
        mock_pool_class.return_value = mock_pool
        
        client = MySQLClient(config={
            "host": "localhost",
            "port": 3306,
            "user": "root",
            "password": "pass",
            "database": "test"
        })
        
        result = client.connect()
        
        assert result is True
        assert client._is_connected is True
        mock_pool_class.assert_called_once()
    
    @patch('ai_novels.database.mysql_client.pooling.MySQLConnectionPool')
    def test_connect_failure(self, mock_pool_class):
        """测试连接失败"""
        mock_pool_class.side_effect = Error("Connection refused")
        
        client = MySQLClient(config={
            "host": "invalid_host",
            "port": 3306,
            "user": "root",
            "password": "pass",
            "database": "test"
        })
        
        result = client.connect()
        
        assert result is False
        assert client._is_connected is False


class TestMySQLClientDisconnect:
    """测试MySQL断开连接"""
    
    def test_disconnect_success(self):
        """测试断开连接成功"""
        client = MySQLClient(config={"host": "localhost"})
        client._pool = Mock()
        client._is_connected = True
        
        result = client.disconnect()
        
        assert result is True
        assert client._is_connected is False
        client._pool.disconnect.assert_called_once()
    
    def test_disconnect_with_error(self):
        """测试断开连接时出错"""
        client = MySQLClient(config={"host": "localhost"})
        client._pool = Mock()
        client._pool.disconnect.side_effect = Error("Disconnect error")
        client._is_connected = True
        
        result = client.disconnect()
        
        assert result is False
        assert client._is_connected is False
    
    def test_disconnect_no_pool(self):
        """测试没有连接池时断开"""
        client = MySQLClient(config={"host": "localhost"})
        client._pool = None
        client._is_connected = True
        
        result = client.disconnect()
        
        assert result is True
        assert client._is_connected is False


class TestMySQLClientIsConnected:
    """测试连接状态检查"""
    
    def test_is_connected_no_pool(self):
        """测试没有连接池时返回False"""
        client = MySQLClient(config={"host": "localhost"})
        client._pool = None
        
        assert client.is_connected() is False
    
    def test_is_connected_success(self):
        """测试连接状态正常"""
        client = MySQLClient(config={"host": "localhost"})
        
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        
        client._pool = Mock()
        client._pool.get_connection.return_value = mock_conn
        
        result = client.is_connected()
        
        assert result is True
        mock_cursor.execute.assert_called_once_with("SELECT 1")
        mock_cursor.close.assert_called_once()
        mock_conn.close.assert_called_once()
    
    def test_is_connected_failure(self):
        """测试连接状态异常"""
        client = MySQLClient(config={"host": "localhost"})
        client._pool = Mock()
        client._pool.get_connection.side_effect = Error("Connection lost")
        
        result = client.is_connected()
        
        assert result is False
        assert client._is_connected is False


class TestMySQLClientHealthCheck:
    """测试健康检查"""
    
    def test_health_check_not_connected(self):
        """测试未连接时的健康检查"""
        client = MySQLClient(config={"host": "localhost"})
        
        with patch.object(client, 'is_connected', return_value=False):
            with patch.object(client, 'connect', return_value=False):
                result = client.health_check()
        
        assert result["status"] == "unhealthy"
        assert result["latency_ms"] == 0
        assert "error" in result["details"]
    
    def test_health_check_healthy(self):
        """测试健康状态"""
        client = MySQLClient(config={"host": "localhost", "pool_name": "test_pool", "pool_size": 5})
        
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = [["table1"], ["table2"]]
        mock_cursor.fetchone.return_value = ["Threads_connected", "10"]
        mock_conn.cursor.return_value = mock_cursor
        
        client._pool = Mock()
        client._pool.get_connection.return_value = mock_conn
        
        result = client.health_check()
        
        assert result["status"] == "healthy"
        assert "latency_ms" in result
        assert result["details"]["tables"] == ["table1", "table2"]
        assert result["details"]["threads_connected"] == 10
        assert result["details"]["pool_name"] == "test_pool"
        assert result["details"]["pool_size"] == 5
    
    def test_health_check_unhealthy(self):
        """测试不健康状态"""
        client = MySQLClient(config={"host": "localhost"})
        
        client._pool = Mock()
        client._pool.get_connection.side_effect = Error("Database error")
        
        result = client.health_check()
        
        assert result["status"] == "unhealthy"
        assert "latency_ms" in result
        assert "error" in result["details"]


class TestMySQLClientCRUD:
    """测试CRUD操作"""
    
    @pytest.fixture
    def mock_client(self):
        """创建带模拟连接的客户端"""
        client = MySQLClient(config={"host": "localhost"})
        
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = {"LAST_INSERT_ID()": 123}
        mock_conn.cursor.return_value = mock_cursor
        
        client._pool = Mock()
        client._pool.get_connection.return_value = mock_conn
        
        return client, mock_cursor
    
    def test_create_success(self, mock_client):
        """测试创建记录成功"""
        client, mock_cursor = mock_client
        
        document = {"name": "test", "value": 100}
        result = client.create("test_table", document)
        
        assert result == "123"
        mock_cursor.execute.assert_any_call("COMMIT")
    
    def test_create_failure(self, mock_client):
        """测试创建记录失败"""
        client, mock_cursor = mock_client
        
        # 第一次执行INSERT失败，触发ROLLBACK
        call_count = 0
        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            sql = args[0] if args else ""
            if "INSERT" in sql and call_count <= 1:
                raise Error("Insert failed")
            return Mock()
        
        mock_cursor.execute.side_effect = side_effect
        
        document = {"name": "test"}
        result = client.create("test_table", document)
        
        assert result is None
    
    def test_read_all(self, mock_client):
        """测试读取所有记录"""
        client, mock_cursor = mock_client
        mock_cursor.fetchall.return_value = [
            {"id": 1, "name": "item1"},
            {"id": 2, "name": "item2"}
        ]
        
        result = client.read("test_table", {})
        
        assert len(result) == 2
        assert result[0]["name"] == "item1"
    
    def test_read_with_query(self, mock_client):
        """测试带条件查询"""
        client, mock_cursor = mock_client
        mock_cursor.fetchall.return_value = [{"id": 1, "name": "test"}]
        
        result = client.read("test_table", {"name": "test"})
        
        assert len(result) == 1
    
    def test_read_with_operators(self, mock_client):
        """测试带操作符的查询"""
        client, mock_cursor = mock_client
        mock_cursor.fetchall.return_value = [{"id": 1, "value": 50}]
        
        result = client.read("test_table", {"value": {"$gt": 10}})
        
        assert len(result) == 1
    
    def test_read_with_limit(self, mock_client):
        """测试带限制的查询"""
        client, mock_cursor = mock_client
        mock_cursor.fetchall.return_value = [{"id": 1}]
        
        result = client.read("test_table", {}, limit=5)
        
        assert len(result) == 1
    
    def test_update_success(self, mock_client):
        """测试更新成功"""
        client, mock_cursor = mock_client
        mock_cursor.rowcount = 1
        
        result = client.update("test_table", {"id": 1}, {"name": "updated"})
        
        assert result is True
    
    def test_update_with_upsert(self, mock_client):
        """测试upsert更新"""
        client, mock_cursor = mock_client
        mock_cursor.rowcount = 0  # 没有匹配行
        
        result = client.update("test_table", {"id": 99}, {"name": "new"}, upsert=True)
        
        assert result is True
    
    def test_update_failure(self, mock_client):
        """测试更新失败"""
        client, mock_cursor = mock_client
        
        # 第一次执行UPDATE失败，触发ROLLBACK
        call_count = 0
        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            sql = args[0] if args else ""
            if "UPDATE" in sql and call_count <= 1:
                raise Error("Update failed")
            return Mock()
        
        mock_cursor.execute.side_effect = side_effect
        
        result = client.update("test_table", {"id": 1}, {"name": "updated"})
        
        assert result is False
    
    def test_delete_success(self, mock_client):
        """测试删除成功"""
        client, mock_cursor = mock_client
        mock_cursor.rowcount = 3
        
        result = client.delete("test_table", {"status": "deleted"})
        
        assert result == 3
    
    def test_delete_failure(self, mock_client):
        """测试删除失败"""
        client, mock_cursor = mock_client
        
        # 第一次执行DELETE失败，触发ROLLBACK
        call_count = 0
        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            sql = args[0] if args else ""
            if "DELETE" in sql and call_count <= 1:
                raise Error("Delete failed")
            return Mock()
        
        mock_cursor.execute.side_effect = side_effect
        
        result = client.delete("test_table", {"id": 1})
        
        assert result == 0
    
    def test_count_all(self, mock_client):
        """测试统计所有记录"""
        client, mock_cursor = mock_client
        mock_cursor.fetchone.return_value = {"count": 100}
        
        result = client.count("test_table")
        
        assert result == 100
    
    def test_count_with_query(self, mock_client):
        """测试带条件统计"""
        client, mock_cursor = mock_client
        mock_cursor.fetchone.return_value = {"count": 10}
        
        result = client.count("test_table", {"status": "active"})
        
        assert result == 10


class TestMySQLClientBusinessMethods:
    """测试业务方法"""
    
    @pytest.fixture
    def connected_client(self):
        """创建已连接的模拟客户端"""
        client = MySQLClient(config={"host": "localhost"})
        
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        
        client._pool = Mock()
        client._pool.get_connection.return_value = mock_conn
        
        return client, mock_cursor
    
    def test_create_task(self, connected_client):
        """测试创建任务"""
        client, mock_cursor = connected_client
        mock_cursor.fetchone.return_value = {"LAST_INSERT_ID()": 456}
        
        task_data = {
            "task_id": "task-001",
            "user_id": "user-001",
            "task_status": "pending"
        }
        result = client.create_task(task_data)
        
        assert result == "456"
    
    def test_update_task_status(self, connected_client):
        """测试更新任务状态"""
        client, mock_cursor = connected_client
        mock_cursor.rowcount = 1
        
        result = client.update_task_status(
            "task-001",
            "running",
            current_stage="outline",
            progress=50.0,
            error_message=None
        )
        
        assert result is True
    
    def test_get_task(self, connected_client):
        """测试获取任务"""
        client, mock_cursor = connected_client
        mock_cursor.fetchall.return_value = [{
            "task_id": "task-001",
            "task_status": "completed"
        }]
        
        result = client.get_task("task-001")
        
        assert result is not None
        assert result["task_id"] == "task-001"
    
    def test_get_task_not_found(self, connected_client):
        """测试获取不存在的任务"""
        client, mock_cursor = connected_client
        mock_cursor.fetchall.return_value = []
        
        result = client.get_task("nonexistent")
        
        assert result is None
    
    def test_insert_logs(self, connected_client):
        """测试批量插入日志"""
        client, mock_cursor = connected_client
        mock_cursor.fetchone.return_value = {"LAST_INSERT_ID()": 1}
        
        logs = [
            {"log_id": "log-1", "message": "test1"},
            {"log_id": "log-2", "message": "test2"}
        ]
        result = client.insert_logs(logs)
        
        assert result == 2
    
    def test_insert_logs_empty(self, connected_client):
        """测试插入空日志列表"""
        client, mock_cursor = connected_client
        
        result = client.insert_logs([])
        
        assert result == 0
    
    def test_get_tasks_by_status(self, connected_client):
        """测试按状态获取任务"""
        client, mock_cursor = connected_client
        mock_cursor.fetchall.return_value = [
            {"task_id": "task-1", "task_status": "pending"},
            {"task_id": "task-2", "task_status": "pending"}
        ]
        
        result = client.get_tasks_by_status("pending", limit=10)
        
        assert len(result) == 2
    
    def test_get_tasks_by_user(self, connected_client):
        """测试获取用户任务"""
        client, mock_cursor = connected_client
        mock_cursor.fetchall.return_value = [
            {"task_id": "task-1", "user_id": "user-001"}
        ]
        
        result = client.get_tasks_by_user("user-001")
        
        assert len(result) == 1
    
    def test_test_connection_healthy(self, connected_client):
        """测试连接测试-健康"""
        client, mock_cursor = connected_client
        mock_cursor.fetchall.return_value = [["table1"]]
        mock_cursor.fetchone.return_value = ["Threads_connected", "5"]
        
        result = client.test_connection()
        
        assert result is True
    
    def test_test_connection_unhealthy(self, connected_client):
        """测试连接测试-不健康"""
        client, mock_cursor = connected_client
        client._pool.get_connection.side_effect = Error("Connection failed")
        
        result = client.test_connection()
        
        assert result is False


class TestMySQLClientContextManagers:
    """测试上下文管理器"""
    
    def test_get_connection_context_manager(self):
        """测试get_connection上下文管理器"""
        client = MySQLClient(config={"host": "localhost"})
        
        mock_conn = Mock()
        client._pool = Mock()
        client._pool.get_connection.return_value = mock_conn
        
        with client.get_connection() as conn:
            assert conn == mock_conn
        
        mock_conn.close.assert_called_once()
    
    def test_get_cursor_context_manager(self):
        """测试get_cursor上下文管理器"""
        client = MySQLClient(config={"host": "localhost"})
        
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        
        client._pool = Mock()
        client._pool.get_connection.return_value = mock_conn
        
        with client.get_cursor() as cursor:
            assert cursor == mock_cursor
        
        mock_cursor.close.assert_called_once()
        mock_conn.close.assert_called_once()
    
    def test_session_context_manager(self):
        """测试session上下文管理器（继承自基类）"""
        client = MySQLClient(config={"host": "localhost"})
        
        with patch.object(client, 'connect', return_value=True) as mock_connect:
            with patch.object(client, 'close') as mock_close:
                with client.session() as s:
                    assert s == client
                
                mock_connect.assert_called_once()
                mock_close.assert_called_once()
