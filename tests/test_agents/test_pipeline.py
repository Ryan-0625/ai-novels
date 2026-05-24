"""
Tests: PipelineNode timeout, circuit breaker, execution
"""

import asyncio
import pytest
from ai_novels.agents.base import BaseAgent, Message, MessageType, AgentConfig
from ai_novels.agents.pipeline import PipelineNode, AgentPipeline, PipelineError
from ai_novels.core.context import WorkflowContext


class SlowAgent(BaseAgent):
    """Agent that always times out"""

    def process(self, message: Message) -> Message:
        import time
        time.sleep(10)  # longer than timeout
        return message


class FastAgent(BaseAgent):
    """Agent that returns immediately"""

    def process(self, message: Message) -> Message:
        message.content = "processed"
        return message


class FailingAgent(BaseAgent):
    """Agent that always fails"""

    def process(self, message: Message) -> Message:
        raise RuntimeError("intentional failure")


@pytest.fixture
def ctx():
    return WorkflowContext.default()


@pytest.fixture
def msg():
    return Message(
        id="test-1",
        type=MessageType.TEXT,
        content="hello",
    )


@pytest.mark.asyncio
async def test_fast_node(ctx, msg):
    agent = FastAgent(AgentConfig(name="fast", model="test"))
    node = PipelineNode(name="test", agent=agent, timeout_seconds=5)
    result = await node.execute(msg, ctx)
    assert result["status"] == "success"
    assert result["message"].content == "processed"
    assert result["duration_ms"] >= 0


@pytest.mark.asyncio
async def test_timeout_node(ctx, msg):
    agent = SlowAgent(AgentConfig(name="slow", model="test"))
    node = PipelineNode(name="slow", agent=agent, timeout_seconds=1)
    result = await node.execute(msg, ctx)
    assert result["status"] == "failed"
    assert "Timeout" in result["error"]


@pytest.mark.asyncio
async def test_failing_node(ctx, msg):
    agent = FailingAgent(AgentConfig(name="fail", model="test"))
    node = PipelineNode(name="fail", agent=agent, timeout_seconds=5)
    result = await node.execute(msg, ctx)
    assert result["status"] == "failed"
    assert "intentional failure" in result["error"]


@pytest.mark.asyncio
async def test_pipeline_success(ctx, msg):
    agent1 = FastAgent(AgentConfig(name="a1", model="test"))
    agent2 = FastAgent(AgentConfig(name="a2", model="test"))
    pipeline = AgentPipeline(ctx, [
        PipelineNode(name="node1", agent=agent1, timeout_seconds=5),
        PipelineNode(name="node2", agent=agent2, timeout_seconds=5),
    ])
    result = await pipeline.run(msg)
    assert result.content == "processed"
    assert len(pipeline.execution_log) == 2
    assert all(e["status"] == "success" for e in pipeline.execution_log)


@pytest.mark.asyncio
async def test_pipeline_failure_stops(ctx, msg):
    agent1 = FastAgent(AgentConfig(name="a1", model="test"))
    agent2 = FailingAgent(AgentConfig(name="a2", model="test"))
    agent3 = FastAgent(AgentConfig(name="a3", model="test"))
    pipeline = AgentPipeline(ctx, [
        PipelineNode(name="n1", agent=agent1, timeout_seconds=5),
        PipelineNode(name="n2", agent=agent2, timeout_seconds=5),
        PipelineNode(name="n3", agent=agent3, timeout_seconds=5),
    ])
    with pytest.raises(PipelineError, match="n2"):
        await pipeline.run(msg)

    assert len(pipeline.execution_log) == 2
    assert pipeline.execution_log[0]["status"] == "success"
    assert pipeline.execution_log[1]["status"] == "failed"


@pytest.mark.asyncio
async def test_empty_pipeline(ctx, msg):
    with pytest.raises(ValueError, match="at least one node"):
        AgentPipeline(ctx, [])


@pytest.mark.asyncio
async def test_pipeline_log_contains_context(ctx, msg):
    agent = FastAgent(AgentConfig(name="a1", model="test"))
    pipeline = AgentPipeline(ctx, [
        PipelineNode(name="n1", agent=agent, timeout_seconds=5),
    ])
    await pipeline.run(msg)
    log = pipeline.execution_log[0]
    assert log["tenant_id"] == ctx.tenant_id
    assert log["trace_id"] == ctx.trace_id
    assert log["session_id"] == ctx.session_id
