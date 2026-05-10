"""
Agent 路由测试 (Step 11)

测试范围:
- GET /api/v2/agents — 列出所有 Agent
- GET /api/v2/agents/{agent_name} — 获取 Agent 详情
- PATCH /api/v2/agents/{agent_name}/config — 更新 Agent 配置
- GET /api/v2/agents/{agent_name}/metrics — 获取 Agent 指标
"""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI

from deepnovel.api.routes.agent_routes import router as agent_router


@pytest.fixture
def mock_orchestrator():
    """创建 Mock TaskOrchestrator"""
    orch = MagicMock()
    orch.list_workers.return_value = [
        {"name": "writer_agent", "idle": True, "state": "idle"},
        {"name": "editor_agent", "idle": False, "state": "busy", "current_task": "task-1"},
    ]
    return orch


@pytest.fixture
def client(mock_orchestrator):
    """创建带 mock orchestrator 的 TestClient"""
    app = FastAPI()
    app.state.task_orchestrator = mock_orchestrator
    app.include_router(agent_router, prefix="/api/v2")
    return TestClient(app)


class TestListAgents:
    """GET /api/v2/agents 测试"""

    def test_list_agents_success(self, client):
        """正常列出所有 Agent"""
        response = client.get("/api/v2/agents")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["name"] == "writer_agent"
        assert data[0]["status"] == "idle"
        assert data[1]["name"] == "editor_agent"
        assert data[1]["status"] == "busy"
        assert "text_generation" in data[0]["capabilities"]

    def test_list_agents_no_orchestrator(self):
        """未初始化 orchestrator 时返回 503"""
        app = FastAPI()
        app.state.task_orchestrator = None
        app.include_router(agent_router, prefix="/api/v2")
        c = TestClient(app)

        response = c.get("/api/v2/agents")
        assert response.status_code == 503


class TestGetAgentDetail:
    """GET /api/v2/agents/{agent_name} 测试"""

    def test_get_existing_agent(self, client):
        """获取存在的 Agent"""
        response = client.get("/api/v2/agents/writer_agent")

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "writer_agent"
        assert data["status"] == "idle"

    def test_get_nonexistent_agent(self, client):
        """获取不存在的 Agent 返回 404"""
        response = client.get("/api/v2/agents/ghost_agent")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestUpdateAgentConfig:
    """PATCH /api/v2/agents/{agent_name}/config 测试"""

    def test_update_config_not_supported(self, client):
        """当前版本不支持更新配置"""
        response = client.patch(
            "/api/v2/agents/writer_agent/config",
            json={"config": {"temperature": 0.8}},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "not yet supported" in data["message"]

    def test_update_config_invalid_payload(self, client):
        """无效的 payload"""
        response = client.patch(
            "/api/v2/agents/writer_agent/config",
            json={},
        )

        assert response.status_code == 422


class TestGetAgentMetrics:
    """GET /api/v2/agents/{agent_name}/metrics 测试"""

    def test_get_metrics(self, client):
        """获取 Agent 指标"""
        response = client.get("/api/v2/agents/writer_agent/metrics")

        assert response.status_code == 200
        data = response.json()
        assert data["agent_name"] == "writer_agent"
        assert data["success_rate"] == 1.0
        assert data["total_tasks"] == 0

    def test_get_metrics_no_orchestrator(self):
        """未初始化 orchestrator 时返回 503"""
        app = FastAPI()
        app.state.task_orchestrator = None
        app.include_router(agent_router, prefix="/api/v2")
        c = TestClient(app)

        response = c.get("/api/v2/agents/writer_agent/metrics")
        assert response.status_code == 503


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
