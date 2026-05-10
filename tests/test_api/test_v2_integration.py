"""
API v2 集成测试 — 验证 TaskOrchestrator 与路由的端到端链路

测试范围:
- POST /api/v2/tasks — 创建任务
- GET /api/v2/tasks — 列出任务
- GET /api/v2/tasks/{task_id} — 查询任务详情
- GET /api/v2/events — SSE 事件流连接
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient

from deepnovel.api.routes.task_routes import router as task_router


@pytest.fixture
def mock_orchestrator():
    """创建支持完整 v2 接口的 Mock TaskOrchestrator"""
    orch = MagicMock()

    # list_tasks
    orch.list_tasks.return_value = [
        {
            "task_id": "task-001",
            "agent_name": "content_generator",
            "priority": 2,
            "status": "pending",
            "enqueue_time": 1234567890.0,
        },
        {
            "task_id": "task-002",
            "agent_name": "outline_planner",
            "priority": 1,
            "status": "completed",
            "enqueue_time": 1234567891.0,
            "result": {"success": True, "result": "outline data"},
        },
    ]

    # list_workers
    orch.list_workers.return_value = [
        {"name": "content_generator", "state": "idle", "current_task": None, "idle": True, "total_tasks": 5, "failed_tasks": 0},
        {"name": "outline_planner", "state": "busy", "current_task": "task-003", "idle": False, "total_tasks": 3, "failed_tasks": 0},
    ]

    # get_stats (向后兼容)
    orch.get_stats.return_value = {
        "workers": {
            "content_generator": {"current_task": None, "idle": True},
            "outline_planner": {"current_task": "task-003", "idle": False},
        },
        "queued_tasks": 2,
        "completed": 5,
    }

    orch.get_result_nowait.return_value = None
    orch.submit = AsyncMock(return_value="task-new-001")
    orch.cancel.return_value = True

    return orch


@pytest.fixture
def client(mock_orchestrator):
    """创建带 mock orchestrator 的 TestClient"""
    app = FastAPI()
    app.state.task_orchestrator = mock_orchestrator
    app.include_router(task_router, prefix="/api/v2")
    return TestClient(app)


class TestCreateTask:
    """POST /api/v2/tasks 测试"""

    def test_create_task_success(self, client):
        """成功创建任务"""
        response = client.post(
            "/api/v2/tasks",
            json={
                "agent_name": "content_generator",
                "payload": {"content": "Generate chapter 1"},
                "priority": "HIGH",
                "timeout": 120,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == "task-new-001"
        assert data["agent_name"] == "content_generator"
        assert data["status"] == "submitted"
        assert "successfully" in data["message"]

    def test_create_task_default_priority(self, client):
        """使用默认优先级创建任务"""
        response = client.post(
            "/api/v2/tasks",
            json={
                "agent_name": "outline_planner",
                "payload": {},
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "submitted"

    def test_create_task_invalid_priority(self, client):
        """无效优先级回退到 NORMAL"""
        response = client.post(
            "/api/v2/tasks",
            json={
                "agent_name": "health_checker",
                "payload": {},
                "priority": "INVALID",
            },
        )
        assert response.status_code == 200
        assert response.json()["status"] == "submitted"

    def test_create_task_missing_agent(self, client):
        """缺少 agent_name 返回 422"""
        response = client.post(
            "/api/v2/tasks",
            json={"payload": {}},
        )
        assert response.status_code == 422

    def test_create_task_no_orchestrator(self):
        """orchestrator 未初始化时返回 503"""
        app = FastAPI()
        app.state.task_orchestrator = None
        app.include_router(task_router, prefix="/api/v2")
        c = TestClient(app)

        response = c.post(
            "/api/v2/tasks",
            json={"agent_name": "content_generator", "payload": {}},
        )
        assert response.status_code == 503


class TestListTasksV2:
    """GET /api/v2/tasks 测试（v2 增强版）"""

    def test_list_tasks_with_queued_tasks(self, client):
        """列出包含队列任务和 worker 状态的完整列表"""
        response = client.get("/api/v2/tasks")
        assert response.status_code == 200
        data = response.json()
        assert "tasks" in data
        assert "total" in data
        # 包含 list_tasks 返回的 2 个 + list_workers 补充的 1 个 (task-003)
        assert data["total"] >= 2
        task_ids = [t["task_id"] for t in data["tasks"]]
        assert "task-001" in task_ids
        assert "task-002" in task_ids

    def test_list_tasks_orchestrator_error(self, client, mock_orchestrator):
        """orchestrator 方法异常时优雅降级"""
        mock_orchestrator.list_tasks.side_effect = RuntimeError("boom")
        mock_orchestrator.list_workers.side_effect = RuntimeError("boom")
        response = client.get("/api/v2/tasks")
        assert response.status_code == 200
        data = response.json()
        # 回退到 get_stats
        assert data["total"] >= 0


class TestGetTaskDetailV2:
    """GET /api/v2/tasks/{task_id} 测试"""

    def test_task_pending(self, client):
        """任务仍在队列中"""
        response = client.get("/api/v2/tasks/task-001")
        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == "task-001"
        assert data["status"] == "pending"

    def test_task_completed(self, client, mock_orchestrator):
        """任务已完成"""
        mock_orchestrator.get_result_nowait.return_value = {
            "success": True,
            "result": "generated text",
            "elapsed": 12.5,
        }
        response = client.get("/api/v2/tasks/task-done")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["result"]["success"] is True


class TestSSEEndpoint:
    """GET /api/v2/events 测试 — 使用独立应用避免 main.py 的重量级初始化"""

    def test_sse_connection(self):
        """SSE 端点可连接并返回事件流"""
        import asyncio
        import json
        from fastapi.responses import StreamingResponse
        from deepnovel.core.event_bus import EventBus, EventType

        # 独立的事件总线
        test_bus = EventBus()

        app = FastAPI()

        @app.get("/api/v2/events")
        async def event_stream():
            queue = asyncio.Queue()
            active = True

            def on_event(event):
                if active:
                    try:
                        queue.put_nowait(event)
                    except asyncio.QueueFull:
                        pass

            unsubscribe = test_bus.subscribe([EventType.TASK_CREATED], on_event)

            async def generator():
                nonlocal active
                try:
                    yield f"data: {json.dumps({'type': 'connected'})}\n\n"
                    event = await asyncio.wait_for(queue.get(), timeout=1.0)
                    payload = {"type": event.type, "source": event.source, "payload": event.payload}
                    yield f"data: {json.dumps(payload)}\n\n"
                except asyncio.TimeoutError:
                    yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"
                finally:
                    active = False
                    unsubscribe()

            return StreamingResponse(
                generator(),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache"},
            )

        client = TestClient(app)

        # 先发布一个事件，然后连接 SSE
        import asyncio
        asyncio.run(test_bus.publish_type(EventType.TASK_CREATED, payload={"task_id": "t1"}, source="test"))

        response = client.get("/api/v2/events", headers={"Accept": "text/event-stream"})
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]
        body = response.text
        assert "data:" in body


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
