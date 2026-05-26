"""
Tests: PipelineNode — timeout, circuit breaker, process_with_context priority, hooks
Tests: AgentPipeline — success, failure, empty, log context
Tests: CircuitBreaker — OPEN, recovery, reset
Covers UT-44 ~ UT-58
"""

import asyncio
import pytest
from ai_novels.agents.base import BaseAgent, Message, MessageType, AgentConfig
from ai_novels.agents.pipeline import (
    PipelineNode, AgentPipeline, PipelineError,
    CircuitBreaker, CircuitBreakerOpen,
)
from ai_novels.core.context import WorkflowContext


# ── Test Agents ──

class FastAgent(BaseAgent):
    def process(self, message: Message) -> Message:
        message.content = "processed"
        return message


class SlowAgent(BaseAgent):
    def process(self, message: Message) -> Message:
        import time
        time.sleep(10)
        return message


class FailingAgent(BaseAgent):
    def process(self, message: Message) -> Message:
        raise RuntimeError("intentional failure")


class ContextAwareAgent(BaseAgent):
    """Agent that uses process_with_context"""
    def process_with_context(self, message: Message, ctx: WorkflowContext) -> Message:
        message.content = f"ctx:{ctx.tenant_id}"
        return message

    def process(self, message: Message) -> Message:
        return message  # should not be called


# ── Fixtures ──

@pytest.fixture
def ctx():
    return WorkflowContext.default()


@pytest.fixture
def msg():
    return Message(id="test-1", type=MessageType.TEXT, content="hello")


# ── UT-44: Normal execution ──

class TestNormalExecution:
    @pytest.mark.asyncio
    async def test_fast_node(self, ctx, msg):
        agent = FastAgent(AgentConfig(name="fast", model="test"))
        node = PipelineNode(name="test", agent=agent, timeout_seconds=5)
        result = await node.execute(msg, ctx)
        assert result["status"] == "success"
        assert result["message"].content == "processed"
        assert result["duration_ms"] >= 0

    @pytest.mark.asyncio
    async def test_duration_positive(self, ctx, msg):
        agent = FastAgent(AgentConfig(name="fast", model="test"))
        node = PipelineNode(name="t", agent=agent, timeout_seconds=5)
        result = await node.execute(msg, ctx)
        assert result["duration_ms"] >= 0


# ── UT-45: process_with_context priority ──

class TestProcessWithContextPriority:
    @pytest.mark.asyncio
    async def test_with_context_called(self, ctx, msg):
        agent = ContextAwareAgent(AgentConfig(name="ctx_aware", model="test"))
        node = PipelineNode(name="ctx_node", agent=agent, timeout_seconds=5)
        result = await node.execute(msg, ctx)
        assert result["status"] == "success"
        assert result["message"].content == f"ctx:{ctx.tenant_id}"


# ── UT-46: process fallback ──

class TestProcessFallback:
    @pytest.mark.asyncio
    async def test_process_fallback_metadata(self, ctx, msg):
        agent = FastAgent(AgentConfig(name="fallback", model="test"))
        node = PipelineNode(name="fb", agent=agent, timeout_seconds=5)
        result = await node.execute(msg, ctx)
        assert result["message"].metadata.get("tenant_id") == ctx.tenant_id
        assert result["message"].metadata.get("trace_id") == ctx.trace_id


# ── UT-47: Timeout ──

class TestTimeout:
    @pytest.mark.asyncio
    async def test_timeout_returns_failed(self, ctx, msg):
        agent = SlowAgent(AgentConfig(name="slow", model="test"))
        node = PipelineNode(name="slow", agent=agent, timeout_seconds=1)
        result = await node.execute(msg, ctx)
        assert result["status"] == "failed"
        assert "Timeout" in result["error"]

    @pytest.mark.asyncio
    async def test_timeout_duration_recorded(self, ctx, msg):
        agent = SlowAgent(AgentConfig(name="slow", model="test"))
        node = PipelineNode(name="slow", agent=agent, timeout_seconds=1)
        result = await node.execute(msg, ctx)
        assert result["duration_ms"] >= 0


# ── UT-48, 49, 50: Hooks ──

class TestHooks:
    @pytest.mark.asyncio
    async def test_pre_hook_executed(self, ctx, msg):
        hook_msg = {"called": False}

        async def pre_hook(message, context):
            hook_msg["called"] = True

        agent = FastAgent(AgentConfig(name="hooked", model="test"))
        node = PipelineNode(name="h", agent=agent, timeout_seconds=5, pre_hook=pre_hook)
        await node.execute(msg, ctx)
        assert hook_msg["called"] is True

    @pytest.mark.asyncio
    async def test_post_hook_executed(self, ctx, msg):
        hook_msg = {"called": False}

        async def post_hook(result, context):
            hook_msg["called"] = True

        agent = FastAgent(AgentConfig(name="hooked", model="test"))
        node = PipelineNode(name="h", agent=agent, timeout_seconds=5, post_hook=post_hook)
        await node.execute(msg, ctx)
        assert hook_msg["called"] is True

    @pytest.mark.asyncio
    async def test_hook_exception_does_not_block(self, ctx, msg):
        async def failing_hook(*args):
            raise RuntimeError("hook failed")

        agent = FastAgent(AgentConfig(name="hooked", model="test"))
        node = PipelineNode(
            name="h", agent=agent, timeout_seconds=5,
            pre_hook=failing_hook, post_hook=failing_hook,
        )
        result = await node.execute(msg, ctx)
        assert result["status"] == "success"


# ── UT-51, 52, 53: CircuitBreaker ──

class TestCircuitBreaker:
    def test_initial_state_closed(self):
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=30)
        assert cb.is_open is False

    def test_opened_after_threshold(self):
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=30)
        for _ in range(3):
            try:
                cb.call(lambda: (_ for _ in ()).throw(RuntimeError("fail")))
            except RuntimeError:
                pass
        assert cb.is_open is True

    def test_open_raises_circuit_breaker(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=30)
        try:
            cb.call(lambda: (_ for _ in ()).throw(RuntimeError("fail")))
        except RuntimeError:
            pass
        with pytest.raises(CircuitBreakerOpen):
            cb.call(lambda: "should not run")

    def test_success_resets_counter(self):
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=30)
        for _ in range(2):
            try:
                cb.call(lambda: (_ for _ in ()).throw(RuntimeError("fail")))
            except RuntimeError:
                pass
        cb.call(lambda: "success")  # reset counter
        try:
            cb.call(lambda: (_ for _ in ()).throw(RuntimeError("fail")))
        except RuntimeError:
            pass
        assert cb.is_open is False  # only 1 failure after reset

    def test_recover_after_timeout(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.01)
        try:
            cb.call(lambda: (_ for _ in ()).throw(RuntimeError("fail")))
        except RuntimeError:
            pass
        assert cb.is_open is True
        import time
        time.sleep(0.02)
        # This call should auto-recover and run
        result = cb.call(lambda: "recovered")
        assert result == "recovered"
        assert cb.is_open is False

    def test_async_call(self):
        import asyncio
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.01)

        async def fail():
            raise RuntimeError("async fail")

        async def succeed():
            return "ok"

        async def run():
            try:
                await cb.call_async(fail)
            except RuntimeError:
                pass
            assert cb.is_open is True
            import time
            time.sleep(0.02)
            result = await cb.call_async(succeed)
            assert result == "ok"

        asyncio.run(run())


# ── UT-54: Pipeline success ──

class TestPipelineSuccess:
    @pytest.mark.asyncio
    async def test_two_nodes(self, ctx, msg):
        agent = FastAgent(AgentConfig(name="a", model="test"))
        pipeline = AgentPipeline(ctx, [
            PipelineNode(name="n1", agent=agent, timeout_seconds=5),
            PipelineNode(name="n2", agent=agent, timeout_seconds=5),
        ])
        result = await pipeline.run(msg)
        assert result.content == "processed"
        assert len(pipeline.execution_log) == 2
        assert all(e["status"] == "success" for e in pipeline.execution_log)


# ── UT-55: Pipeline failure stops ──

class TestPipelineFailure:
    @pytest.mark.asyncio
    async def test_failure_stops_at_failed_node(self, ctx, msg):
        a1 = FastAgent(AgentConfig(name="a1", model="test"))
        a2 = FailingAgent(AgentConfig(name="a2", model="test"))
        a3 = FastAgent(AgentConfig(name="a3", model="test"))
        pipeline = AgentPipeline(ctx, [
            PipelineNode(name="n1", agent=a1, timeout_seconds=5),
            PipelineNode(name="n2", agent=a2, timeout_seconds=5),
            PipelineNode(name="n3", agent=a3, timeout_seconds=5),
        ])
        with pytest.raises(PipelineError, match="n2"):
            await pipeline.run(msg)
        assert len(pipeline.execution_log) == 2
        assert pipeline.execution_log[0]["status"] == "success"
        assert pipeline.execution_log[1]["status"] == "failed"


# ── UT-56: Empty pipeline ──

class TestEmptyPipeline:
    @pytest.mark.asyncio
    async def test_empty_raises(self, ctx, msg):
        with pytest.raises(ValueError, match="at least one node"):
            AgentPipeline(ctx, [])


# ── UT-57: Log context ──

class TestPipelineLogContext:
    @pytest.mark.asyncio
    async def test_log_contains_identity(self, ctx, msg):
        agent = FastAgent(AgentConfig(name="a1", model="test"))
        pipeline = AgentPipeline(ctx, [
            PipelineNode(name="n1", agent=agent, timeout_seconds=5),
        ])
        await pipeline.run(msg)
        log = pipeline.execution_log[0]
        assert log["tenant_id"] == ctx.tenant_id
        assert log["trace_id"] == ctx.trace_id
        assert log["session_id"] == ctx.session_id
        assert log["user_id"] == ctx.user_id

    @pytest.mark.asyncio
    async def test_log_on_failure(self, ctx, msg):
        agent = FailingAgent(AgentConfig(name="fail", model="test"))
        pipeline = AgentPipeline(ctx, [
            PipelineNode(name="n1", agent=agent, timeout_seconds=5),
        ])
        with pytest.raises(PipelineError):
            await pipeline.run(msg)
        log = pipeline.execution_log[0]
        assert log["status"] == "failed"
        assert log["error"] is not None
        assert log["tenant_id"] == ctx.tenant_id


# ── UT-58: PipelineLogEntry immutability ──

class TestPipelineLogEntry:
    def test_immutable(self):
        from ai_novels.agents.pipeline import PipelineLogEntry
        from dataclasses import FrozenInstanceError
        entry = PipelineLogEntry(
            node_name="n1", status="success", duration_ms=100,
            tenant_id="t1", user_id="u1", trace_id="tr1", session_id="s1",
        )
        with pytest.raises(FrozenInstanceError):
            entry.status = "failed"  # type: ignore
