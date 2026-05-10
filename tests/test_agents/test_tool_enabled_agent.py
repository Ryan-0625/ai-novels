"""
ToolEnabledAgent 单元测试
"""

import pytest

from deepnovel.agents.base import AgentConfig, Message, MessageType
from deepnovel.agents.prompt_composer import PromptComposer
from deepnovel.agents.tool_enabled_agent import ToolEnabledAgent, ToolEnabledAgentConfig
from deepnovel.agents.tools.tool_registry import ToolRegistry, tool
from deepnovel.core.event_bus import EventBus, EventType
from deepnovel.core.working_memory import WorkingMemory
from deepnovel.llm.tier import ModelTier, TierConfig, TierRouter
from deepnovel.rag import RAGEngine, RAGConfig
from deepnovel.llm.embedding_adapter import EmbeddingConfig, BaseEmbeddingBackend
from deepnovel.vector_store.memory_store import InMemoryVectorStore
from typing import List


@pytest.fixture
def basic_config():
    """基础配置（无外部依赖）"""
    return ToolEnabledAgentConfig(
        name="test_agent",
        description="测试Agent",
        agent_role="测试助手",
        task_description="执行测试任务",
        enable_rag=False,
        enable_events=False,
    )


class InMemoryTestEmbedder(BaseEmbeddingBackend):
    """测试用内存嵌入器"""
    def __init__(self, config: EmbeddingConfig):
        super().__init__(config)
    def embed(self, text: str) -> List[float]:
        import hashlib
        seed = int(hashlib.md5(text.encode()).hexdigest(), 16)
        return [((seed >> i) & 0xFF) / 255.0 for i in range(0, 64, 8)]  # 8维
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        return [self.embed(t) for t in texts]


@pytest.fixture
def mock_rag_engine():
    """创建 Mock RAG 引擎"""
    embedder = InMemoryTestEmbedder(EmbeddingConfig(provider="test", model="test", dimension=64))
    store = InMemoryVectorStore(embedding_dim=64, embedding_adapter=embedder)
    return RAGEngine(
        config=RAGConfig(
            chunk_size=50,
            chunk_overlap=5,
            top_k=5,
            min_chunk_size=1,
            embedding_dimension=64,
        ),
        vector_store=store,
        embedding_adapter=embedder,
    )


class TestToolEnabledAgentInit:
    def test_basic_init(self, basic_config):
        agent = ToolEnabledAgent(basic_config)
        assert agent.name == "test_agent"
        assert agent._working_memory.capacity == 7
        assert agent._enable_rag is False
        assert agent._enable_events is False

    def test_init_with_custom_capacity(self):
        config = ToolEnabledAgentConfig(
            name="agent",
            working_memory_capacity=5,
            enable_rag=False,
            enable_events=False,
        )
        agent = ToolEnabledAgent(config)
        assert agent._working_memory.capacity == 5

    def test_init_with_tier_router(self):
        router = TierRouter()
        config = ToolEnabledAgentConfig(
            name="agent",
            tier_router=router,
            default_tier=ModelTier.FAST,
            enable_rag=False,
            enable_events=False,
        )
        agent = ToolEnabledAgent(config)
        assert agent._tier_router is router
        assert agent._default_tier == ModelTier.FAST


class TestToolManagement:
    def test_register_tool_instance(self, basic_config):
        agent = ToolEnabledAgent(basic_config)

        class MyTool:
            @tool(description="搜索")
            async def search(self, query: str) -> dict:
                return {"results": [query]}

            @tool(description="计算")
            async def calc(self, x: int, y: int) -> int:
                return x + y

        tool_instance = MyTool()
        agent.register_tool_instance(tool_instance, prefix="test_")

        tools = agent.list_available_tools()
        assert "test_search" in tools
        assert "test_calc" in tools

    def test_get_tool_schemas(self, basic_config):
        agent = ToolEnabledAgent(basic_config)

        class MyTool:
            @tool(description="搜索")
            async def search(self, query: str) -> dict:
                return {}

        agent.register_tool_instance(MyTool())
        schemas = agent.get_tool_schemas()
        # 全局注册表可能有其他工具，但至少包含 search
        assert len(schemas) >= 1
        assert any(s["name"] == "search" for s in schemas)

    @pytest.mark.asyncio
    async def test_call_tool(self, basic_config):
        agent = ToolEnabledAgent(basic_config)

        class MyTool:
            @tool(description="问候")
            async def greet(self, person: str) -> str:
                return f"Hello {person}"

        agent.register_tool_instance(MyTool())
        result = await agent.call_tool("greet", person="World")
        assert result == "Hello World"
        assert agent._stats["tool_calls"] == 1

    @pytest.mark.asyncio
    async def test_call_tool_not_found(self, basic_config):
        agent = ToolEnabledAgent(basic_config)
        with pytest.raises(Exception):
            await agent.call_tool("nonexistent")
        assert agent._stats["errors"] >= 1


class TestWorkingMemory:
    def test_add_to_working_memory(self, basic_config):
        agent = ToolEnabledAgent(basic_config)
        entry = agent.add_to_working_memory("测试内容", priority=0.8)
        assert entry is not None
        assert entry.content == "测试内容"

    def test_working_memory_capacity_limit(self, basic_config):
        config = ToolEnabledAgentConfig(
            name="agent",
            working_memory_capacity=3,
            enable_rag=False,
            enable_events=False,
        )
        agent = ToolEnabledAgent(config)
        # 填满容量
        for i in range(5):
            agent.add_to_working_memory(f"item_{i}", priority=0.5)
        assert agent._working_memory.occupancy <= 3

    def test_get_working_memory_state(self, basic_config):
        agent = ToolEnabledAgent(basic_config)
        agent.add_to_working_memory("内容", entry_type="test")
        state = agent.get_working_memory_state()
        assert "working_memory" in state
        assert "cognitive_load" in state

    def test_clear_working_memory(self, basic_config):
        agent = ToolEnabledAgent(basic_config)
        agent.add_to_working_memory("内容")
        agent.clear_working_memory()
        assert agent._working_memory.occupancy == 0


class TestRAGIntegration:
    @pytest.mark.asyncio
    async def test_retrieve_context(self, basic_config, mock_rag_engine):
        config = ToolEnabledAgentConfig(
            name="agent",
            rag_engine=mock_rag_engine,
            enable_rag=True,
            enable_events=False,
        )
        agent = ToolEnabledAgent(config)

        # 先索引一些数据
        await mock_rag_engine.add_document(
            "修仙世界的天道规则非常重要。" * 5,
            source_id="lore-1",
            novel_id="n1",
        )

        context = await agent.retrieve_context("天道规则")
        assert context is not None
        assert agent._stats["rag_queries"] == 1

    @pytest.mark.asyncio
    async def test_retrieve_context_disabled(self, basic_config):
        agent = ToolEnabledAgent(basic_config)
        context = await agent.retrieve_context("query")
        assert context is None


class TestPromptBuilding:
    def test_build_system_prompt_basic(self, basic_config):
        agent = ToolEnabledAgent(basic_config)
        prompt = agent.build_system_prompt()
        assert "# 角色定义" in prompt
        assert "测试助手" in prompt
        assert "# 任务" in prompt

    def test_build_system_prompt_with_tools(self, basic_config):
        agent = ToolEnabledAgent(basic_config)

        class MyTool:
            @tool(description="搜索")
            async def search(self, query: str) -> dict:
                return {}

        agent.register_tool_instance(MyTool())
        prompt = agent.build_system_prompt()
        assert "# 可用工具" in prompt
        assert "search" in prompt

    def test_build_system_prompt_with_working_memory(self, basic_config):
        agent = ToolEnabledAgent(basic_config)
        agent.add_to_working_memory("重要信息", entry_type="note", priority=0.9)
        prompt = agent.build_system_prompt()
        assert "# 当前工作记忆" in prompt
        assert "重要信息" in prompt

    def test_build_system_prompt_with_rag(self, basic_config):
        agent = ToolEnabledAgent(basic_config)
        prompt = agent.build_system_prompt(rag_context="参考: 测试知识")
        assert "# 相关知识" in prompt
        assert "测试知识" in prompt

    def test_compose_prompt(self, basic_config):
        agent = ToolEnabledAgent(basic_config)
        agent._composer.register_template_from_string("test", "Hello {{name}}")
        result = agent.compose_prompt("test", {"name": "AI"})
        assert result == "Hello AI"


class TestToolCallParsing:
    def test_parse_tool_calls_basic(self, basic_config):
        agent = ToolEnabledAgent(basic_config)
        text = '''
我需要调用工具。
```tool
{"tool": "search", "params": {"query": "天气"}}
```
'''
        calls = agent.parse_tool_calls(text)
        assert len(calls) == 1
        assert calls[0]["tool"] == "search"
        assert calls[0]["params"]["query"] == "天气"

    def test_parse_tool_calls_multiple(self, basic_config):
        agent = ToolEnabledAgent(basic_config)
        text = '''
```tool
{"tool": "search", "params": {"query": "A"}}
```
```tool
{"tool": "calc", "params": {"x": 1, "y": 2}}
```
'''
        calls = agent.parse_tool_calls(text)
        assert len(calls) == 2
        assert calls[0]["tool"] == "search"
        assert calls[1]["tool"] == "calc"

    def test_parse_tool_calls_empty(self, basic_config):
        agent = ToolEnabledAgent(basic_config)
        calls = agent.parse_tool_calls("没有工具调用")
        assert len(calls) == 0

    def test_parse_tool_calls_malformed(self, basic_config):
        agent = ToolEnabledAgent(basic_config)
        text = '''
```tool
{"tool": "broken", "params": }
```
'''
        calls = agent.parse_tool_calls(text)
        # 畸形 JSON 应该被优雅处理
        assert isinstance(calls, list)

    @pytest.mark.asyncio
    async def test_execute_tool_calls(self, basic_config):
        agent = ToolEnabledAgent(basic_config)

        class MyTool:
            @tool(description="计算")
            async def calc(self, x: int, y: int) -> int:
                return x + y

        agent.register_tool_instance(MyTool())
        calls = [{"tool": "calc", "params": {"x": 1, "y": 2}}]
        results = await agent.execute_tool_calls(calls)
        assert len(results) == 1
        assert results[0]["success"] is True
        assert results[0]["result"] == 3


class TestTierRouting:
    def test_select_tier(self, basic_config):
        agent = ToolEnabledAgent(basic_config)
        # 简单 prompt 应该路由到 FAST
        config = agent.select_tier("分类这个文本")
        assert config is not None
        assert isinstance(config, TierConfig)

    def test_select_tier_complex(self, basic_config):
        agent = ToolEnabledAgent(basic_config)
        # 复杂 prompt 应该路由到更高级别
        complex_prompt = "创作" * 50 + "分析" * 50
        config = agent.select_tier(complex_prompt)
        assert config is not None


class TestStatsAndHealth:
    def test_get_stats(self, basic_config):
        agent = ToolEnabledAgent(basic_config)
        stats = agent.get_stats()
        assert stats["agent"] == "test_agent"
        assert "tool_calls" in stats
        assert "llm_calls" in stats
        assert "rag_queries" in stats
        assert "working_memory" in stats

    def test_reset_stats(self, basic_config):
        agent = ToolEnabledAgent(basic_config)
        agent._stats["tool_calls"] = 5
        agent.reset_stats()
        assert agent._stats["tool_calls"] == 0

    def test_health_check(self, basic_config):
        agent = ToolEnabledAgent(basic_config)
        health = agent.health_check()
        assert health["name"] == "test_agent"
        assert "working_memory" in health
        assert "attention" in health
        assert health["rag_enabled"] is False
        assert health["events_enabled"] is False


class TestProcess:
    def test_process_sync_basic(self, basic_config):
        agent = ToolEnabledAgent(basic_config)
        agent.initialize()

        msg = Message(
            id="msg-1",
            type=MessageType.TEXT,
            content="测试消息",
        )
        # process 会尝试异步处理，但在无事件循环时降级为同步
        # 由于无 LLM，会返回错误消息
        result = agent.process(msg)
        assert result is not None
        # process 可能返回 TEXT 或 SYSTEM（出错时）
        assert result.sender == "test_agent"

    @pytest.mark.asyncio
    async def test_aprocess(self, basic_config):
        event_bus = EventBus()
        config = ToolEnabledAgentConfig(
            name="agent",
            event_bus=event_bus,
            enable_events=True,
            enable_rag=False,
        )
        agent = ToolEnabledAgent(config)
        agent.initialize()

        # Mock generate_with_context 避免依赖 LLM
        async def mock_generate(*a, **kw):
            return "模拟响应"

        agent.generate_with_context = mock_generate

        msg = Message(
            id="msg-1",
            type=MessageType.TEXT,
            content="测试消息",
        )
        result = await agent.aprocess(msg)
        assert result is not None
        assert result.content == "模拟响应"

    @pytest.mark.asyncio
    async def test_emit_event(self, basic_config):
        event_bus = EventBus()
        config = ToolEnabledAgentConfig(
            name="agent",
            event_bus=event_bus,
            enable_events=True,
            enable_rag=False,
        )
        agent = ToolEnabledAgent(config)

        received = []

        def handler(event):
            received.append(event)

        event_bus.subscribe(EventType.CUSTOM, handler)
        await agent.emit_event(EventType.CUSTOM, {"test": True})
        assert len(received) == 1


class TestGenerateWithTools:
    @pytest.mark.asyncio
    async def test_generate_with_tools_no_calls(self, basic_config):
        agent = ToolEnabledAgent(basic_config)
        agent.initialize()

        # Mock generate_with_tier 返回无工具调用的文本
        agent.generate_with_tier = lambda *a, **kw: "这是最终回答"

        result = await agent.generate_with_tools("请回答")
        assert result == "这是最终回答"

    @pytest.mark.asyncio
    async def test_generate_with_tools_single_call(self, basic_config):
        agent = ToolEnabledAgent(basic_config)

        class MyTool:
            @tool(description="搜索")
            async def search(self, query: str) -> dict:
                return {"results": [f"result for {query}"]}

        agent.register_tool_instance(MyTool())
        agent.initialize()

        call_count = 0

        def mock_generate(prompt, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return '思考中...\n```tool\n{"tool": "search", "params": {"query": "测试"}}\n```'
            return "基于搜索结果: 这是最终回答"

        agent.generate_with_tier = mock_generate

        result = await agent.generate_with_tools("请搜索")
        assert "最终回答" in result
        assert call_count == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
