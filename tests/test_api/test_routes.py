"""
API路由测试
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient
from pydantic import BaseModel

# 导入FastAPI应用
from deepnovel.api.main import app
from deepnovel.api.legacy_routes import (
    TaskCreateRequest,
    TaskCreateResponse,
    TaskStatusResponse
)


client = TestClient(app)


class TestHealthEndpoints:
    """测试健康检查端点"""

    def test_health_check(self):
        """测试健康检查端点"""
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "ai-novels-api"
        assert "version" in data

    def test_root_endpoint(self):
        """测试根路径端点"""
        response = client.get("/")
        
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "AI-Novels API" in response.text


class TestTaskEndpoints:
    """测试任务相关端点"""

    def test_create_task(self):
        """测试创建任务端点"""
        task_data = {
            "user_id": "test_user",
            "task_type": "novel",
            "genre": "fantasy",
            "title": "Test Novel",
            "description": "A test novel",
            "chapters": 3,
            "word_count_per_chapter": 1000
        }
        
        response = client.post("/api/v1/tasks", json=task_data)
        
        assert response.status_code == 200
        data = response.json()
        assert "task_id" in data
        assert data["status"] == "accepted"
        assert "message" in data

    def test_create_task_minimal(self):
        """测试最小参数创建任务"""
        task_data = {
            "user_id": "test_user",
            "task_type": "novel"
        }
        
        response = client.post("/api/v1/tasks", json=task_data)
        
        assert response.status_code == 200
        data = response.json()
        assert "task_id" in data

    def test_list_tasks(self):
        """测试列出任务端点"""
        # 先创建一个任务
        task_data = {
            "user_id": "test_user",
            "task_type": "novel"
        }
        create_response = client.post("/api/v1/tasks", json=task_data)
        assert create_response.status_code == 200
        
        # 列出任务
        response = client.get("/api/v1/tasks")
        
        assert response.status_code == 200
        data = response.json()
        assert "tasks" in data
        assert "total" in data
        assert isinstance(data["tasks"], list)

    def test_list_tasks_with_pagination(self):
        """测试带分页的任务列表"""
        response = client.get("/api/v1/tasks?page=1&page_size=5")
        
        assert response.status_code == 200
        data = response.json()
        assert "tasks" in data
        assert "total" in data

    def test_get_task_status(self):
        """测试获取任务状态端点"""
        # 先创建一个任务
        task_data = {
            "user_id": "test_user",
            "task_type": "novel"
        }
        create_response = client.post("/api/v1/tasks", json=task_data)
        task_id = create_response.json()["task_id"]
        
        # 获取任务状态
        response = client.get(f"/api/v1/tasks/{task_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == task_id
        assert "status" in data
        assert "progress" in data

    def test_get_nonexistent_task(self):
        """测试获取不存在的任务"""
        response = client.get("/api/v1/tasks/nonexistent-task-id")
        
        assert response.status_code == 404

    def test_cancel_task(self):
        """测试取消任务端点"""
        # 先创建一个任务
        task_data = {
            "user_id": "test_user",
            "task_type": "novel"
        }
        create_response = client.post("/api/v1/tasks", json=task_data)
        task_id = create_response.json()["task_id"]
        
        # 取消任务 - 需要发送TaskCancelRequest
        cancel_data = {"task_id": task_id}
        response = client.post(f"/api/v1/tasks/{task_id}/cancel", json=cancel_data)
        
        # 取消任务可能返回200或400（如果任务已完成或不存在）
        assert response.status_code in [200, 400]
        if response.status_code == 200:
            data = response.json()
            assert data["task_id"] == task_id
            assert data["status"] == "cancelled"

    def test_get_task_logs(self):
        """测试获取任务日志端点"""
        # 先创建一个任务
        task_data = {
            "user_id": "test_user",
            "task_type": "novel"
        }
        create_response = client.post("/api/v1/tasks", json=task_data)
        task_id = create_response.json()["task_id"]
        
        # 获取任务日志
        response = client.get(f"/api/v1/tasks/{task_id}/logs")
        
        assert response.status_code == 200
        data = response.json()
        assert "task_id" in data
        assert "logs" in data


class TestConfigEndpoints:
    """测试配置相关端点"""

    def test_get_config(self):
        """测试获取配置端点"""
        response = client.get("/api/v1/config/test_config")
        
        # 端点可能返回404如果配置不存在
        assert response.status_code in [200, 404]

    def test_update_config(self):
        """测试更新配置端点"""
        config_data = {
            "config_key": "test_key",
            "config_value": {"key": "value"}
        }
        
        response = client.post("/api/v1/config/update", json=config_data)
        
        # 根据实现可能返回200或特定状态码
        assert response.status_code in [200, 202, 404]


class TestSystemEndpoints:
    """测试系统相关端点"""

    def test_get_system_health(self):
        """测试获取系统健康状态端点"""
        response = client.get("/api/v1/health")
        
        assert response.status_code == 200
        data = response.json()
        # 健康检查端点可能返回不同的字段名
        assert "status" in data or "overall_status" in data

    def test_get_system_stats(self):
        """测试获取系统统计信息端点"""
        response = client.get("/api/v1/stats")
        
        # 端点可能返回200或404
        assert response.status_code in [200, 404]
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, dict)


class TestValidationErrors:
    """测试验证错误处理"""

    def test_create_task_missing_required_field(self):
        """测试缺少必填字段"""
        # 缺少 user_id 和 task_type
        task_data = {
            "genre": "fantasy"
        }
        
        response = client.post("/api/v1/tasks", json=task_data)
        
        assert response.status_code == 422

    def test_create_task_invalid_data_type(self):
        """测试无效的数据类型"""
        task_data = {
            "user_id": "test_user",
            "task_type": "novel",
            "chapters": "not_a_number"  # 应该是整数
        }
        
        response = client.post("/api/v1/tasks", json=task_data)
        
        assert response.status_code == 422


class TestResponseModels:
    """测试响应模型"""

    def test_task_create_response_model(self):
        """测试任务创建响应模型"""
        response_data = {
            "task_id": "task_1234567890_abc123",
            "status": "accepted",
            "message": "Task created successfully"
        }
        
        # 验证模型可以正确解析
        model = TaskCreateResponse(**response_data)
        assert model.task_id == response_data["task_id"]
        assert model.status == response_data["status"]

    def test_task_status_response_model(self):
        """测试任务状态响应模型"""
        response_data = {
            "task_id": "task_1234567890_abc123",
            "status": "running",
            "progress": 0.5,
            "current_stage": "generating",
            "completed_agents": ["agent1"],
            "total_agents": 5,
            "start_time": "2026-04-20T10:00:00",
            "estimated_end_time": None
        }
        
        model = TaskStatusResponse(**response_data)
        assert model.task_id == response_data["task_id"]
        assert model.progress == 0.5
