"""
TaskOrchestrator 单元测试
"""

import asyncio

import pytest

from deepnovel.agents.base import AgentConfig, Message, MessageType
from deepnovel.agents.task_orchestrator import (
    DAGTaskNode,
    QueuedTask,
    TaskOrchestrator,
    TaskPriority,
    WorkerSlot,
)
from deepnovel.agents.workflow_orchestrator import TaskState
from deepnovel.agents.tool_enabled_agent import ToolEnabledAgent, ToolEnabledAgentConfig
from deepnovel.core.event_bus import EventBus, EventType


# ---- Fixtures ----

@pytest.fixture
def event_bus():
    return EventBus()


@pytest.fixture
def mock_agent():
    """创建 Mock ToolEnabledAgent"""
    config = ToolEnabledAgentConfig(
        name="mock_agent",
        description="测试Agent",
        enable_rag=False,
        enable_events=False,
    )
    agent = ToolEnabledAgent(config)
    agent.initialize()
    return agent


@pytest.fixture
async def orchestrator(event_bus, mock_agent):
    """创建已启动的 TaskOrchestrator"""
    orch = TaskOrchestrator(event_bus=event_bus, max_workers=2)
    await orch.start()
    orch.register_worker(mock_agent)
    yield orch
    await orch.shutdown(wait=False)


# ---- 生命周期 ----

class TestLifecycle:
    @pytest.mark.asyncio
    async def test_start_shutdown(self, event_bus):
        orch = TaskOrchestrator(event_bus=event_bus)
        assert not orch._running
        await orch.start()
        assert orch._running
        assert orch._dispatcher_task is not None
        await orch.shutdown()
        assert not orch._running

    @pytest.mark.asyncio
    async def test_double_start(self, event_bus):
        orch = TaskOrchestrator(event_bus=event_bus)
        await orch.start()
        await orch.start()  # 不应出错
        assert orch._running
        await orch.shutdown()

    @pytest.mark.asyncio
    async def test_shutdown_without_start(self, event_bus):
        orch = TaskOrchestrator(event_bus=event_bus)
        await orch.shutdown()  # 不应出错
        assert not orch._running


# ---- 工作器管理 ----

class TestWorkerManagement:
    def test_register_worker(self, mock_agent):
        orch = TaskOrchestrator()
        assert orch.register_worker(mock_agent) is True
        assert "mock_agent" in orch._workers

    def test_register_duplicate(self, mock_agent):
        orch = TaskOrchestrator()
        orch.register_worker(mock_agent)
        assert orch.register_worker(mock_agent) is False

    def test_unregister_worker(self, mock_agent):
        orch = TaskOrchestrator()
        orch.register_worker(mock_agent)
        assert orch.unregister_worker("mock_agent") is True
        assert "mock_agent" not in orch._workers

    def test_list_workers(self, mock_agent):
        orch = TaskOrchestrator()
        orch.register_worker(mock_agent)
        workers = orch.list_workers()
        assert len(workers) == 1
        assert workers[0]["name"] == "mock_agent"
        assert workers[0]["idle"] is True

    def test_get_available_workers(self, mock_agent):
        orch = TaskOrchestrator()
        orch.register_worker(mock_agent)
        available = orch.get_available_workers()
        assert available == ["mock_agent"]


# ---- 任务提交 ----

class TestTaskSubmission:
    @pytest.mark.asyncio
    async def test_submit_basic(self, orchestrator):
        task_id = await orchestrator.submit(
            "mock_agent",
            {"content": "测试任务"},
            priority=TaskPriority.NORMAL,
        )
        assert task_id is not None
        assert len(task_id) > 0
        assert orchestrator._stats["submitted"] == 1

    @pytest.mark.asyncio
    async def test_submit_with_correlation_id(self, orchestrator):
        cid = "batch-123"
        task_id = await orchestrator.submit(
            "mock_agent",
            {"content": "测试"},
            correlation_id=cid,
        )
        queued = orchestrator._queued_tasks.get(task_id)
        assert queued.correlation_id == cid

    @pytest.mark.asyncio
    async def test_submit_batch(self, orchestrator):
        tasks = [
            ("mock_agent", {"content": f"任务{i}"})
            for i in range(3)
        ]
        ids = await orchestrator.submit_batch(tasks)
        assert len(ids) == 3
        assert orchestrator._stats["submitted"] == 3

    @pytest.mark.asyncio
    async def test_submit_different_priorities(self, orchestrator):
        ids = []
        for priority in [TaskPriority.LOW, TaskPriority.HIGH, TaskPriority.NORMAL]:
            tid = await orchestrator.submit(
                "mock_agent", {"content": "x"}, priority=priority
            )
            ids.append(tid)
        assert len(ids) == 3


# ---- 任务执行 ----

class TestTaskExecution:
    @pytest.mark.asyncio
    async def test_execute_and_get_result(self, orchestrator):
        task_id = await orchestrator.submit(
            "mock_agent",
            {"content": "请回答"},
        )

        # 等待执行完成
        result = await orchestrator.get_result(task_id, timeout=5.0)
        assert result is not None
        assert "success" in result
        assert result["success"] is True
        assert orchestrator._stats["completed"] >= 1

    @pytest.mark.asyncio
    async def test_execute_multiple_tasks(self, orchestrator):
        ids = []
        for i in range(3):
            tid = await orchestrator.submit(
                "mock_agent",
                {"content": f"任务{i}"},
            )
            ids.append(tid)

        # 等待所有完成
        for tid in ids:
            result = await orchestrator.get_result(tid, timeout=5.0)
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_get_result_nowait(self, orchestrator):
        task_id = await orchestrator.submit(
            "mock_agent",
            {"content": "测试"},
        )

        # 立即获取应返回 None
        assert orchestrator.get_result_nowait(task_id) is None

        # 等待完成后应能获取
        result = await orchestrator.get_result(task_id, timeout=5.0)
        assert result is not None

    @pytest.mark.asyncio
    async def test_get_result_timeout(self, orchestrator):
        # 提交一个不存在的任务应抛出 KeyError
        with pytest.raises(KeyError):
            await orchestrator.get_result("nonexistent", timeout=0.1)


# ---- DAG 执行 ----

class TestDAGExecution:
    @pytest.mark.asyncio
    async def test_dag_linear_chain(self, event_bus, mock_agent):
        orch = TaskOrchestrator(event_bus=event_bus, max_workers=2)
        await orch.start()
        orch.register_worker(mock_agent)

        # 创建线性 DAG: A -> B -> C
        node_a = DAGTaskNode(
            task_id="dag_a",
            agent_name="mock_agent",
            payload={"content": "A", "dag_id": "dag1"},
            dependencies=[],
        )
        node_b = DAGTaskNode(
            task_id="dag_b",
            agent_name="mock_agent",
            payload={"content": "B", "dag_id": "dag1"},
            dependencies=["dag_a"],
        )
        node_c = DAGTaskNode(
            task_id="dag_c",
            agent_name="mock_agent",
            payload={"content": "C", "dag_id": "dag1"},
            dependencies=["dag_b"],
        )

        dag_id = await orch.submit_dag([node_a, node_b, node_c])
        assert dag_id is not None

        # 等待所有任务完成
        for tid in ["dag_a", "dag_b", "dag_c"]:
            result = await orch.get_result(tid, timeout=5.0)
            assert result["success"] is True

        # 验证 DAG 状态
        status = await orch.get_dag_status("dag1")
        assert status is not None
        assert status["done"] == 3

        await orch.shutdown(wait=False)

    @pytest.mark.asyncio
    async def test_dag_fan_out(self, event_bus, mock_agent):
        orch = TaskOrchestrator(event_bus=event_bus, max_workers=2)
        await orch.start()
        orch.register_worker(mock_agent)

        # 扇出: A -> B, C
        node_a = DAGTaskNode(
            task_id="fan_a",
            agent_name="mock_agent",
            payload={"content": "A", "dag_id": "fan"},
        )
        node_b = DAGTaskNode(
            task_id="fan_b",
            agent_name="mock_agent",
            payload={"content": "B", "dag_id": "fan"},
            dependencies=["fan_a"],
        )
        node_c = DAGTaskNode(
            task_id="fan_c",
            agent_name="mock_agent",
            payload={"content": "C", "dag_id": "fan"},
            dependencies=["fan_a"],
        )

        await orch.submit_dag([node_a, node_b, node_c])

        for tid in ["fan_a", "fan_b", "fan_c"]:
            result = await orch.get_result(tid, timeout=5.0)
            assert result["success"] is True

        await orch.shutdown(wait=False)

    @pytest.mark.asyncio
    async def test_dag_failure_propagation(self, event_bus):
        """测试 DAG 失败传播"""
        orch = TaskOrchestrator(event_bus=event_bus, max_workers=2)
        await orch.start()

        # 创建一个会失败的 Agent（无 aprocess/process）
        class BadAgent(ToolEnabledAgent):
            async def aprocess(self, message):
                raise RuntimeError("模拟失败")

            def process(self, message):
                raise RuntimeError("模拟失败")

        bad_config = ToolEnabledAgentConfig(
            name="bad_agent",
            enable_rag=False,
            enable_events=False,
        )
        bad_agent = BadAgent(bad_config)
        bad_agent.initialize()
        orch.register_worker(bad_agent)

        node_a = DAGTaskNode(
            task_id="fail_a",
            agent_name="bad_agent",
            payload={"content": "fail", "dag_id": "fail_dag"},
        )
        node_b = DAGTaskNode(
            task_id="fail_b",
            agent_name="bad_agent",
            payload={"content": "depends on a", "dag_id": "fail_dag"},
            dependencies=["fail_a"],
        )

        await orch.submit_dag([node_a, node_b])

        # 等待失败
        result_a = await orch.get_result("fail_a", timeout=10.0)
        assert result_a["success"] is False

        # B 应该被标记为失败（上游失败）
        async with orch._dag_lock:
            node_b_state = orch._dag_nodes["fail_b"].state.value
        assert node_b_state == "failed"

        await orch.shutdown(wait=False)


# ---- 事件集成 ----

class TestEventIntegration:
    @pytest.mark.asyncio
    async def test_task_created_event(self, event_bus, mock_agent):
        events = []

        def handler(event):
            if event.type == EventType.TASK_CREATED.value:
                events.append(event)

        event_bus.subscribe(EventType.TASK_CREATED, handler)

        orch = TaskOrchestrator(event_bus=event_bus)
        await orch.start()
        orch.register_worker(mock_agent)

        await orch.submit("mock_agent", {"content": "x"})
        await asyncio.sleep(0.3)

        assert len(events) >= 1
        assert events[0].payload["agent_name"] == "mock_agent"

        await orch.shutdown(wait=False)

    @pytest.mark.asyncio
    async def test_task_completed_event(self, event_bus, mock_agent):
        events = []

        def handler(event):
            if event.type == EventType.TASK_COMPLETED.value:
                events.append(event)

        event_bus.subscribe(EventType.TASK_COMPLETED, handler)

        orch = TaskOrchestrator(event_bus=event_bus)
        await orch.start()
        orch.register_worker(mock_agent)

        await orch.submit("mock_agent", {"content": "x"})
        await asyncio.sleep(0.5)

        assert len(events) >= 1
        assert "task_id" in events[0].payload

        await orch.shutdown(wait=False)


# ---- 工作流适配 ----

class TestWorkflowAdapter:
    @pytest.mark.asyncio
    async def test_execute_workflow(self, event_bus, mock_agent):
        from deepnovel.agents.workflow_orchestrator import (
            WorkflowDefinition,
            WorkflowStage,
        )

        orch = TaskOrchestrator(event_bus=event_bus)
        await orch.start()
        orch.register_worker(mock_agent)

        # 注册简单工作流
        workflow = WorkflowDefinition(
            name="test_flow",
            description="测试工作流",
            stages=[
                WorkflowStage(
                    name="stage1",
                    description="阶段1",
                    agent_name="mock_agent",
                    input_mapping={"content": "task.initial_data.content"},
                    output_mapping={"result": "output.result"},
                    next_stages=[],
                )
            ],
        )
        orch.register_workflow(workflow)

        dag_id = await orch.execute_workflow("test_flow", {"content": "测试"})
        assert dag_id is not None

        await orch.shutdown(wait=False)


# ---- 统计与健康 ----

class TestStatsAndHealth:
    @pytest.mark.asyncio
    async def test_get_stats(self, orchestrator):
        await orchestrator.submit("mock_agent", {"content": "x"})
        stats = orchestrator.get_stats()
        assert stats["submitted"] >= 1
        assert "workers" in stats
        assert "dag_nodes" in stats

    @pytest.mark.asyncio
    async def test_get_health(self, orchestrator):
        health = orchestrator.get_health()
        assert health["running"] is True
        assert health["dispatcher_alive"] is True
        assert health["workers_total"] >= 1

    @pytest.mark.asyncio
    async def test_clear_results(self, orchestrator):
        tid = await orchestrator.submit("mock_agent", {"content": "x"})
        await orchestrator.get_result(tid, timeout=5.0)
        assert orchestrator.get_result_nowait(tid) is not None

        orchestrator.clear_results()
        assert orchestrator.get_result_nowait(tid) is None


# ---- 辅助类测试 ----

class TestWorkerSlot:
    def test_worker_lifecycle(self, mock_agent):
        slot = WorkerSlot(agent=mock_agent)
        assert slot.is_available is True
        assert slot.state.value == "idle"

        slot.assign("task-1")
        assert slot.is_available is False
        assert slot.state.value == "busy"
        assert slot.current_task == "task-1"

        slot.release(success=True)
        assert slot.is_available is True
        assert slot.total_tasks == 1
        assert slot.failed_tasks == 0

        slot.assign("task-2")
        slot.release(success=False)
        assert slot.failed_tasks == 1

    def test_heartbeat(self, mock_agent):
        slot = WorkerSlot(agent=mock_agent)
        old_time = slot.last_heartbeat
        slot.heartbeat()
        assert slot.last_heartbeat > old_time


class TestDAGTaskNode:
    def test_is_ready_no_deps(self):
        node = DAGTaskNode(
            task_id="t1",
            agent_name="a1",
            payload={},
            dependencies=[],
        )
        assert node.is_ready is True

    def test_is_ready_with_deps(self):
        node = DAGTaskNode(
            task_id="t1",
            agent_name="a1",
            payload={},
            dependencies=["t0"],
        )
        assert node.is_ready is False

    def test_to_dict(self):
        node = DAGTaskNode(
            task_id="t1",
            agent_name="a1",
            payload={"x": 1},
            state=TaskState.INBOX,
        )
        d = node.to_dict()
        assert d["task_id"] == "t1"
        assert d["state"] == "inbox"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
