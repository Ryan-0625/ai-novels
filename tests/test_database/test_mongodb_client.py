"""
MongoDB客户端测试

@file: test_database/test_mongodb_client.py
@description: 测试MongoDB数据库客户端功能
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pymongo.errors import PyMongoError, ConnectionFailure
from bson import ObjectId

from ai_novels.database.mongodb_client import MongoDBClient


class TestMongoDBClientInit:
    """测试MongoDB客户端初始化"""
    
    def test_init_with_config_dict(self):
        """测试使用配置字典初始化"""
        config = {
            "host": "test_host",
            "port": 27018,
            "username": "test_user",
            "password": "test_pass",
            "database": "test_db",
            "auth_source": "test_auth"
        }
        
        client = MongoDBClient(config=config)
        
        assert client._host == "test_host"
        assert client._port == 27018
        assert client._username == "test_user"
        assert client._password == "test_pass"
        assert client._database == "test_db"
        assert client._auth_source == "test_auth"
    
    def test_init_with_default_config(self):
        """测试使用默认配置初始化"""
        with patch('ai_novels.database.mongodb_client.settings') as mock_settings:
            mock_settings.get_database.return_value = {
                "host": "localhost",
                "port": 27017,
                "username": "root",
                "password": "",
                "database": "ai_novels",
                "auth_source": "admin"
            }
            
            client = MongoDBClient()
            
            assert client._host == "localhost"
            assert client._port == 27017
            assert client._username == "root"
            assert client._client is None
            assert client._is_connected is False
    
    def test_init_with_explicit_params(self):
        """测试使用显式参数初始化"""
        with patch('ai_novels.database.mongodb_client.settings') as mock_settings:
            mock_settings.get_database.return_value = {}
            
            client = MongoDBClient(
                host="explicit_host",
                port=27019,
                username="explicit_user",
                password="explicit_pass",
                database="explicit_db"
            )
            
            assert client._host == "explicit_host"
            assert client._port == 27019
            assert client._username == "explicit_user"
            assert client._password == "explicit_pass"
            assert client._database == "explicit_db"


class TestMongoDBClientConnect:
    """测试MongoDB连接功能"""
    
    @patch('ai_novels.database.mongodb_client.MongoClient')
    def test_connect_with_auth_success(self, mock_client_class):
        """测试带认证连接成功"""
        mock_db = Mock()
        mock_client = Mock()
        mock_client.admin.command.return_value = {"ok": 1}
        mock_client.__getitem__ = Mock(return_value=mock_db)
        mock_client_class.return_value = mock_client
        
        client = MongoDBClient(config={
            "host": "localhost",
            "port": 27017,
            "username": "user",
            "password": "pass",
            "database": "test"
        })
        
        result = client.connect()
        
        assert result is True
        assert client._is_connected is True
        mock_client_class.assert_called_once()
    
    @patch('ai_novels.database.mongodb_client.MongoClient')
    def test_connect_without_auth_success(self, mock_client_class):
        """测试无认证连接成功"""
        mock_db = Mock()
        mock_client = Mock()
        mock_client.admin.command.return_value = {"ok": 1}
        mock_client.__getitem__ = Mock(return_value=mock_db)
        mock_client_class.return_value = mock_client
        
        client = MongoDBClient(config={
            "host": "localhost",
            "port": 27017,
            "username": "",
            "password": "",
            "database": "test"
        })
        
        result = client.connect()
        
        assert result is True
        assert client._is_connected is True
    
    @patch('ai_novels.database.mongodb_client.MongoClient')
    def test_connect_failure(self, mock_client_class):
        """测试连接失败"""
        mock_client_class.side_effect = ConnectionFailure("Connection refused")
        
        client = MongoDBClient(config={
            "host": "invalid_host",
            "port": 27017,
            "database": "test"
        })
        
        result = client.connect()
        
        assert result is False
        assert client._is_connected is False


class TestMongoDBClientDisconnect:
    """测试MongoDB断开连接"""
    
    def test_disconnect_success(self):
        """测试断开连接成功"""
        client = MongoDBClient(config={"host": "localhost"})
        client._client = Mock()
        client._is_connected = True
        
        result = client.disconnect()
        
        assert result is True
        assert client._is_connected is False
        client._client.close.assert_called_once()
    
    def test_disconnect_with_error(self):
        """测试断开连接时出错"""
        client = MongoDBClient(config={"host": "localhost"})
        client._client = Mock()
        client._client.close.side_effect = PyMongoError("Close error")
        client._is_connected = True
        
        result = client.disconnect()
        
        assert result is False
        assert client._is_connected is False


class TestMongoDBClientIsConnected:
    """测试连接状态检查"""
    
    def test_is_connected_no_client(self):
        """测试没有客户端时返回False"""
        client = MongoDBClient(config={"host": "localhost"})
        client._client = None
        
        assert client.is_connected() is False
    
    def test_is_connected_success(self):
        """测试连接状态正常"""
        client = MongoDBClient(config={"host": "localhost"})
        client._client = Mock()
        client._client.admin.command.return_value = {"ok": 1}
        
        result = client.is_connected()
        
        assert result is True
    
    def test_is_connected_failure(self):
        """测试连接状态异常"""
        client = MongoDBClient(config={"host": "localhost"})
        client._client = Mock()
        client._client.admin.command.side_effect = PyMongoError("Connection lost")
        
        result = client.is_connected()
        
        assert result is False
        assert client._is_connected is False


class TestMongoDBClientHealthCheck:
    """测试健康检查"""
    
    def test_health_check_not_connected(self):
        """测试未连接时的健康检查"""
        client = MongoDBClient(config={"host": "localhost"})
        
        with patch.object(client, 'is_connected', return_value=False):
            with patch.object(client, 'connect', return_value=False):
                result = client.health_check()
        
        assert result["status"] == "unhealthy"
        assert "error" in result["details"]
    
    def test_health_check_healthy(self):
        """测试健康状态"""
        client = MongoDBClient(config={"host": "localhost", "database": "test_db"})
        
        mock_client = Mock()
        mock_client.admin.command.return_value = {"ok": 1}
        mock_client.server_info.return_value = {"version": "5.0.0"}
        
        mock_db = Mock()
        mock_db.command.return_value = {"collections": 5, "objects": 100}
        mock_db.list_collection_names.return_value = ["col1", "col2"]
        
        client._client = mock_client
        client._db = mock_db
        
        result = client.health_check()
        
        assert result["status"] == "healthy"
        assert "latency_ms" in result
        assert result["details"]["database"] == "test_db"
        assert result["details"]["server_version"] == "5.0.0"
        assert result["details"]["collections_count"] == 5
    
    def test_health_check_unhealthy(self):
        """测试不健康状态"""
        client = MongoDBClient(config={"host": "localhost"})
        
        mock_client = Mock()
        # 第一次ping成功（is_connected检查），第二次失败
        call_count = 0
        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                raise PyMongoError("Database error")
            return {"ok": 1}
        
        mock_client.admin.command.side_effect = side_effect
        client._client = mock_client
        
        result = client.health_check()
        
        assert result["status"] == "unhealthy"
        assert "error" in result["details"]


class TestMongoDBClientCRUD:
    """测试CRUD操作"""
    
    @pytest.fixture
    def mock_client(self):
        """创建带模拟连接的客户端"""
        client = MongoDBClient(config={"host": "localhost", "database": "test"})
        
        mock_db = Mock()
        mock_collection = Mock()
        mock_db.__getitem__ = Mock(return_value=mock_collection)
        
        client._db = mock_db
        client._is_connected = True
        
        return client, mock_collection
    
    def test_create_success(self, mock_client):
        """测试创建记录成功"""
        client, mock_collection = mock_client
        mock_result = Mock()
        mock_result.inserted_id = ObjectId("507f1f77bcf86cd799439011")
        mock_collection.insert_one.return_value = mock_result
        
        document = {"name": "test", "value": 100}
        result = client.create("test_collection", document)
        
        assert result == "507f1f77bcf86cd799439011"
        mock_collection.insert_one.assert_called_once_with(document)
    
    def test_create_failure(self, mock_client):
        """测试创建记录失败"""
        client, mock_collection = mock_client
        mock_collection.insert_one.side_effect = PyMongoError("Insert failed")
        
        document = {"name": "test"}
        result = client.create("test_collection", document)
        
        assert result is None
    
    def test_read_all(self, mock_client):
        """测试读取所有记录"""
        client, mock_collection = mock_client
        mock_collection.find.return_value = [
            {"_id": ObjectId("507f1f77bcf86cd799439011"), "name": "item1"},
            {"_id": ObjectId("507f1f77bcf86cd799439012"), "name": "item2"}
        ]
        
        result = client.read("test_collection", {})
        
        assert len(result) == 2
        assert result[0]["name"] == "item1"
        assert isinstance(result[0]["_id"], str)  # ObjectId已转换为字符串
    
    def test_read_with_query(self, mock_client):
        """测试带条件查询"""
        client, mock_collection = mock_client
        mock_collection.find.return_value = [{"_id": ObjectId(), "name": "test"}]
        
        result = client.read("test_collection", {"name": "test"})
        
        assert len(result) == 1
        mock_collection.find.assert_called_once_with({"name": "test"})
    
    def test_read_with_limit(self, mock_client):
        """测试带限制的查询"""
        client, mock_collection = mock_client
        mock_cursor = Mock()
        mock_cursor.limit.return_value = [{"_id": ObjectId()}]
        mock_collection.find.return_value = mock_cursor
        
        result = client.read("test_collection", {}, limit=5)
        
        mock_cursor.limit.assert_called_once_with(5)
    
    def test_update_success(self, mock_client):
        """测试更新成功"""
        client, mock_collection = mock_client
        mock_result = Mock()
        mock_result.matched_count = 1
        mock_result.upserted_id = None
        mock_collection.update_one.return_value = mock_result
        
        result = client.update("test_collection", {"_id": "123"}, {"name": "updated"})
        
        assert result is True
        mock_collection.update_one.assert_called_once_with(
            {"_id": "123"},
            {"$set": {"name": "updated"}},
            upsert=False
        )
    
    def test_update_with_upsert(self, mock_client):
        """测试upsert更新"""
        client, mock_collection = mock_client
        mock_result = Mock()
        mock_result.matched_count = 0
        mock_result.upserted_id = ObjectId()
        mock_collection.update_one.return_value = mock_result
        
        result = client.update("test_collection", {"_id": "new"}, {"name": "new"}, upsert=True)
        
        assert result is True
    
    def test_update_failure(self, mock_client):
        """测试更新失败"""
        client, mock_collection = mock_client
        mock_collection.update_one.side_effect = PyMongoError("Update failed")
        
        result = client.update("test_collection", {"_id": "123"}, {"name": "updated"})
        
        assert result is False
    
    def test_delete_success(self, mock_client):
        """测试删除成功"""
        client, mock_collection = mock_client
        mock_result = Mock()
        mock_result.deleted_count = 3
        mock_collection.delete_many.return_value = mock_result
        
        result = client.delete("test_collection", {"status": "deleted"})
        
        assert result == 3
    
    def test_delete_failure(self, mock_client):
        """测试删除失败"""
        client, mock_collection = mock_client
        mock_collection.delete_many.side_effect = PyMongoError("Delete failed")
        
        result = client.delete("test_collection", {"_id": "123"})
        
        assert result == 0
    
    def test_count_all(self, mock_client):
        """测试统计所有记录"""
        client, mock_collection = mock_client
        mock_collection.count_documents.return_value = 100
        
        result = client.count("test_collection")
        
        assert result == 100
        mock_collection.count_documents.assert_called_once_with({})
    
    def test_count_with_query(self, mock_client):
        """测试带条件统计"""
        client, mock_collection = mock_client
        mock_collection.count_documents.return_value = 10
        
        result = client.count("test_collection", {"status": "active"})
        
        assert result == 10
        mock_collection.count_documents.assert_called_once_with({"status": "active"})


class TestMongoDBClientSpecificMethods:
    """测试MongoDB特有方法"""
    
    @pytest.fixture
    def connected_client(self):
        """创建已连接的模拟客户端"""
        client = MongoDBClient(config={"host": "localhost", "database": "test"})
        
        mock_db = Mock()
        mock_collection = Mock()
        mock_db.__getitem__ = Mock(return_value=mock_collection)
        mock_db.list_collection_names.return_value = ["col1", "col2"]
        
        client._db = mock_db
        client._is_connected = True
        
        return client, mock_collection, mock_db
    
    def test_get_collection(self, connected_client):
        """测试获取集合"""
        client, _, mock_db = connected_client
        
        result = client.get_collection("test_collection")
        
        assert result is not None
    
    def test_list_collections(self, connected_client):
        """测试列出集合"""
        client, _, mock_db = connected_client
        
        result = client.list_collections()
        
        assert result == ["col1", "col2"]
    
    def test_create_index(self, connected_client):
        """测试创建索引"""
        client, mock_collection, _ = connected_client
        mock_collection.create_index.return_value = "field_1"
        
        result = client.create_index("test_collection", "field", unique=True)
        
        assert result == "field_1"
        mock_collection.create_index.assert_called_once_with(
            [("field", 1)],
            unique=True
        )
    
    def test_create_compound_index(self, connected_client):
        """测试创建复合索引"""
        client, mock_collection, _ = connected_client
        mock_collection.create_index.return_value = "field1_1_field2_-1"
        
        result = client.create_compound_index(
            "test_collection",
            [("field1", 1), ("field2", -1)],
            unique=True
        )
        
        assert result == "field1_1_field2_-1"
    
    def test_bulk_insert(self, connected_client):
        """测试批量插入"""
        client, mock_collection, _ = connected_client
        mock_result = Mock()
        mock_result.inserted_ids = [ObjectId(), ObjectId()]
        mock_collection.insert_many.return_value = mock_result
        
        documents = [{"name": "doc1"}, {"name": "doc2"}]
        result = client.bulk_insert("test_collection", documents)
        
        assert len(result) == 2
    
    def test_find_one(self, connected_client):
        """测试查询单条记录"""
        client, mock_collection, _ = connected_client
        mock_collection.find_one.return_value = {
            "_id": ObjectId("507f1f77bcf86cd799439011"),
            "name": "test"
        }
        
        result = client.find_one("test_collection", {"name": "test"})
        
        assert result is not None
        assert result["name"] == "test"
        assert isinstance(result["_id"], str)
    
    def test_find_one_not_found(self, connected_client):
        """测试查询单条记录不存在"""
        client, mock_collection, _ = connected_client
        mock_collection.find_one.return_value = None
        
        result = client.find_one("test_collection", {"name": "nonexistent"})
        
        assert result is None
    
    def test_aggregate(self, connected_client):
        """测试聚合查询"""
        client, mock_collection, _ = connected_client
        mock_collection.aggregate.return_value = [
            {"_id": "category1", "count": 10},
            {"_id": "category2", "count": 20}
        ]
        
        pipeline = [{"$group": {"_id": "$category", "count": {"$sum": 1}}}]
        result = client.aggregate("test_collection", pipeline)
        
        assert len(result) == 2
        assert result[0]["count"] == 10
    
    def test_drop_collection(self, connected_client):
        """测试删除集合"""
        client, mock_collection, _ = connected_client
        
        result = client.drop_collection("test_collection")
        
        assert result is True
        mock_collection.drop.assert_called_once()
    
    def test_test_connection_healthy(self, connected_client):
        """测试连接测试-健康"""
        client, _, mock_db = connected_client
        
        with patch.object(client, 'health_check') as mock_health:
            mock_health.return_value = {"status": "healthy"}
            result = client.test_connection()
        
        assert result is True
    
    def test_test_connection_unhealthy(self, connected_client):
        """测试连接测试-不健康"""
        client, _, _ = connected_client
        
        with patch.object(client, 'health_check') as mock_health:
            mock_health.return_value = {"status": "unhealthy"}
            result = client.test_connection()
        
        assert result is False


class TestMongoDBClientObjectIdConversion:
    """测试ObjectId转换"""
    
    def test_convert_objectid_simple(self):
        """测试简单ObjectId转换"""
        client = MongoDBClient(config={"host": "localhost"})
        
        doc = {"_id": ObjectId("507f1f77bcf86cd799439011"), "name": "test"}
        result = client._convert_objectid(doc)
        
        assert result["_id"] == "507f1f77bcf86cd799439011"
        assert result["name"] == "test"
    
    def test_convert_objectid_nested(self):
        """测试嵌套ObjectId转换"""
        client = MongoDBClient(config={"host": "localhost"})
        
        doc = {
            "_id": ObjectId("507f1f77bcf86cd799439011"),
            "nested": {
                "sub_id": ObjectId("507f1f77bcf86cd799439012")
            }
        }
        result = client._convert_objectid(doc)
        
        assert result["_id"] == "507f1f77bcf86cd799439011"
        assert result["nested"]["sub_id"] == "507f1f77bcf86cd799439012"
    
    def test_convert_objectid_in_list(self):
        """测试列表中ObjectId转换"""
        client = MongoDBClient(config={"host": "localhost"})
        
        doc = {
            "_id": ObjectId("507f1f77bcf86cd799439011"),
            "items": [
                {"item_id": ObjectId("507f1f77bcf86cd799439012")},
                {"item_id": ObjectId("507f1f77bcf86cd799439013")}
            ]
        }
        result = client._convert_objectid(doc)
        
        assert isinstance(result["items"][0]["item_id"], str)
        assert isinstance(result["items"][1]["item_id"], str)
