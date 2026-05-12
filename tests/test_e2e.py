"""
端到端集成测试 — 验证完整生产链路

测试范围:
- CoordinatorAgent 协调工作流
- TaskOrchestrator 调度与执行
- Agent 执行过程（LLM mock）
- EventBus 事件发布
- 结果聚合与查询
"""

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from ai_novels.agents.base import AgentConfig, Message, MessageType
from ai_novels.agents.coordinator import CoordinatorAgent
from ai_novels.agents.implementations import (
    OutlinePlannerAgent,
    CharacterGeneratorAgent,
    ContentGeneratorAgent,
    QualityCheckerAgent,
)
from ai_novels.agents.task_orchestrator import TaskOrchestrator, TaskPriority
from ai_novels.core.event_bus import EventBus, EventType


@pytest.fixture
def event_bus():
    """创建独立的事件总线"""
    return EventBus()


@pytest.fixture
def orchestrator(event_bus):
    """创建带 mock worker 的 TaskOrchestrator"""
    orch = TaskOrchestrator(max_workers=2, event_bus=event_bus)
    return orch


class TestCoordinatorAgentE2E:
    """CoordinatorAgent 端到端测试"""

    def test_coordinator_init(self):
        """Coordinator 初始化"""
        agent = CoordinatorAgent()
        agent.initialize()
        assert agent.name == "coordinator"
        assert agent.state.value == "ready"

    def test_coordinator_start_request(self):
        """处理开始生成请求"""
        agent = CoordinatorAgent()
        agent.initialize()
        msg = Message(
            id="test-1",
            type=MessageType.TEXT,
            content="start generation: fantasy novel",
        )
        result = agent.process(msg)
        assert result is not None
        assert "start" in result.content.lower() or "initializ" in result.content.lower()

    def test_coordinator_status_request(self):
        """处理状态查询请求"""
        agent = CoordinatorAgent()
        agent.initialize()
        msg = Message(id="test-2", type=MessageType.TEXT, content="check status")
        result = agent.process(msg)
        assert result is not None
        assert result.sender == "coordinator"


class TestTaskOrchestratorE2E:
    """TaskOrchestrator 端到端测试"""

    @pytest.mark.asyncio
    async def test_submit_and_execute_task(self, orchestrator, event_bus):
        """提交任务并调度执行"""
        await orchestrator.start()

        # 注册一个 mock agent worker
        mock_agent = MagicMock()
        mock_agent.name = "outline_planner"
        mock_response = Message(
            id="resp-1", type=MessageType.TEXT, content="Outline done"
        )
        mock_agent.aprocess = AsyncMock(return_value=mock_response)
        orchestrator.register_worker(mock_agent)

        # 提交任务
        task_id = await orchestrator.submit(
            agent_name="outline_planner",
            payload={"content": "Plan a fantasy novel"},
            priority=TaskPriority.NORMAL,
        )
        assert task_id is not None

        # 等待任务执行完成
        await asyncio.sleep(0.5)

        # 查询结果
        result = orchestrator.get_result_nowait(task_id)
        assert result is not None
        assert result["success"] is True

        await orchestrator.shutdown()

    @pytest.mark.asyncio
    async def test_submit_dag_and_execute(self, orchestrator):
        """提交 DAG 并执行"""
        await orchestrator.start()

        # 注册 mock workers
        for name in ["config_enhancer", "outline_planner"]:
            mock_agent = MagicMock()
            mock_agent.name = name
            mock_agent.aprocess = AsyncMock(
                return_value=Message(id=f"r-{name}", type=MessageType.TEXT, content="done")
            )
            orchestrator.register_worker(mock_agent)

        # 提交 DAG
        from ai_novels.agents.task_orchestrator import DAGTaskNode

        nodes = [
            DAGTaskNode(
                task_id="dag-task-1",
                agent_name="config_enhancer",
                payload={"content": "config"},
                dependencies=[],
            ),
            DAGTaskNode(
                task_id="dag-task-2",
                agent_name="outline_planner",
                payload={"content": "outline"},
                dependencies=["dag-task-1"],
            ),
        ]

        dag_id = await orchestrator.submit_dag(nodes)
        assert dag_id is not None

        # 等待 DAG 执行
        await asyncio.sleep(1.0)

        # 验证结果
        result1 = orchestrator.get_result_nowait("dag-task-1")
        result2 = orchestrator.get_result_nowait("dag-task-2")
        assert result1 is not None or result2 is not None

        await orchestrator.shutdown()

    @pytest.mark.asyncio
    async def test_worker_registration(self, orchestrator):
        """Worker 注册与状态查询"""
        agent = OutlinePlannerAgent()
        agent.initialize()
        success = orchestrator.register_worker(agent)
        assert success is True

        workers = orchestrator.list_workers()
        assert len(workers) == 1
        assert workers[0]["name"] == "outline_planner"


class TestAgentExecutionE2E:
    """Agent 执行链路端到端测试"""

    def test_outline_planner_with_mock_llm(self):
        """OutlinePlannerAgent 完整执行链路"""
        agent = OutlinePlannerAgent()
        agent.initialize()

        mock_outline = json.dumps([
            {"chapter": 1, "title": "The Beginning", "events": ["Intro"]},
        ], ensure_ascii=False)

        with patch.object(agent, "_generate_with_llm", return_value=mock_outline):
            msg = Message(
                id="e2e-1",
                type=MessageType.TEXT,
                content='{"title": "Test", "genre": "fantasy", "chapters": 1}',
            )
            result = agent.process(msg)

        assert result is not None
        assert "大纲" in result.content or "Outline" in result.content

    def test_character_generator_with_mock_llm(self):
        """CharacterGeneratorAgent 完整执行链路"""
        agent = CharacterGeneratorAgent()
        agent.initialize()

        mock_chars = json.dumps([
            {"name": "Alice", "age": 25, "gender": "female"},
        ], ensure_ascii=False)

        with patch.object(agent, "_generate_with_llm", return_value=mock_chars):
            msg = Message(
                id="e2e-2",
                type=MessageType.TEXT,
                content='{"title": "Test", "genre": "fantasy"}',
            )
            result = agent.process(msg)

        assert result is not None
        assert "角色" in result.content or "Character" in result.content

    def test_content_generator_command_processing(self):
        """ContentGeneratorAgent 命令处理链路"""
        agent = ContentGeneratorAgent()
        agent.initialize()

        with patch.object(agent, "_generate_with_llm", return_value="Generated text."):
            msg = Message(
                id="e2e-3",
                type=MessageType.TEXT,
                content="generate content chapter_id=c1 outline=test beats=intro;end words=100 mode=balanced",
            )
            result = agent.process(msg)

        assert result is not None


class TestEventBusE2E:
    """EventBus 事件流端到端测试"""

    @pytest.mark.asyncio
    async def test_task_lifecycle_events(self, orchestrator, event_bus):
        """任务生命周期事件发布"""
        events_received = []

        def on_event(event):
            events_received.append(event.type)

        unsubscribe = event_bus.subscribe(
            [EventType.TASK_CREATED, EventType.TASK_STARTED, EventType.TASK_COMPLETED],
            on_event,
        )

        await orchestrator.start()

        mock_agent = MagicMock()
        mock_agent.name = "quality_checker"
        mock_agent.aprocess = AsyncMock(
            return_value=Message(id="r1", type=MessageType.TEXT, content="ok")
        )
        orchestrator.register_worker(mock_agent)

        task_id = await orchestrator.submit(
            agent_name="quality_checker",
            payload={"content": "check"},
        )

        await asyncio.sleep(0.5)
        await orchestrator.shutdown()

        unsubscribe()

        assert EventType.TASK_CREATED.value in [str(e) for e in events_received]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
