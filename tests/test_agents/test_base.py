"""
Agent基类测试

@file: tests/test_agents/test_base.py
@description: 测试Agent基类、Message、AgentConfig、AgentRouter
"""

import pytest
import time
import uuid
from typing import Optional
from unittest.mock import Mock, patch, MagicMock

from deepnovel.agents.base import (
    AgentState, MessageType, Message, AgentConfig,
    BaseAgent, AgentRouter
)


# ============================================================================
# Message 测试
# ============================================================================

class TestMessage:
    """Message类测试"""
    
    def test_message_init(self):
        """测试Message初始化"""
        msg = Message(
            id="test-id",
            type=MessageType.TEXT,
            content="test content",
            metadata={"key": "value"},
            timestamp=1234567890.0,
            sender="sender1",
            receiver="receiver1"
        )
        
        assert msg.id == "test-id"
        assert msg.type == MessageType.TEXT
        assert msg.content == "test content"
        assert msg.metadata == {"key": "value"}
        assert msg.timestamp == 1234567890.0
        assert msg.sender == "sender1"
        assert msg.receiver == "receiver1"
    
    def test_message_init_defaults(self):
        """测试Message初始化默认值"""
        msg = Message(
            id="test-id",
            type=MessageType.TEXT,
            content="test"
        )
        
        assert msg.metadata == {}
        assert isinstance(msg.timestamp, float)
        assert msg.sender is None
        assert msg.receiver is None
    
    def test_message_to_dict(self):
        """测试Message转换为字典"""
        msg = Message(
            id="test-id",
            type=MessageType.TEXT,
            content="test content",
            metadata={"key": "value"},
            timestamp=1234567890.0,
            sender="sender1",
            receiver="receiver1"
        )
        
        data = msg.to_dict()
        
        assert data["id"] == "test-id"
        assert data["type"] == "text"
        assert data["content"] == "test content"
        assert data["metadata"] == {"key": "value"}
        assert data["timestamp"] == 1234567890.0
        assert data["sender"] == "sender1"
        assert data["receiver"] == "receiver1"
    
    def test_message_from_dict(self):
        """测试从字典创建Message"""
        data = {
            "id": "test-id",
            "type": "text",
            "content": "test content",
            "metadata": {"key": "value"},
            "timestamp": 1234567890.0,
            "sender": "sender1",
            "receiver": "receiver1"
        }
        
        msg = Message.from_dict(data)
        
        assert msg.id == "test-id"
        assert msg.type == MessageType.TEXT
        assert msg.content == "test content"
        assert msg.metadata == {"key": "value"}
        assert msg.timestamp == 1234567890.0
        assert msg.sender == "sender1"
        assert msg.receiver == "receiver1"
    
    def test_message_from_dict_defaults(self):
        """测试从字典创建Message使用默认值"""
        data = {
            "type": "text",
            "content": "test"
        }
        
        msg = Message.from_dict(data)
        
        assert msg.id  # 自动生成UUID
        assert msg.type == MessageType.TEXT
        assert msg.content == "test"
        assert msg.metadata == {}
        assert isinstance(msg.timestamp, float)
        assert msg.sender is None
        assert msg.receiver is None
    
    def test_message_from_dict_all_types(self):
        """测试从字典创建所有消息类型的Message"""
        for msg_type in MessageType:
            data = {
                "id": "test-id",
                "type": msg_type.value,
                "content": "test"
            }
            msg = Message.from_dict(data)
            assert msg.type == msg_type


# ============================================================================
# AgentConfig 测试
# ============================================================================

class TestAgentConfig:
    """AgentConfig类测试"""
    
    def test_agent_config_init(self):
        """测试AgentConfig初始化"""
        config = AgentConfig(
            name="test-agent",
            description="Test agent description",
            provider="openai",
            model="gpt-4",
            temperature=0.5,
            max_tokens=4096,
            system_prompt="You are a test agent",
            tools=["tool1", "tool2"],
            retry_times=5,
            timeout=120
        )
        
        assert config.name == "test-agent"
        assert config.description == "Test agent description"
        assert config.provider == "openai"
        assert config.model == "gpt-4"
        assert config.temperature == 0.5
        assert config.max_tokens == 4096
        assert config.system_prompt == "You are a test agent"
        assert config.tools == ["tool1", "tool2"]
        assert config.retry_times == 5
        assert config.timeout == 120
    
    def test_agent_config_init_defaults(self):
        """测试AgentConfig初始化默认值"""
        config = AgentConfig(name="test-agent")
        
        assert config.name == "test-agent"
        assert config.description == ""
        assert config.provider == "ollama"
        assert config.model == "qwen2.5-7b"
        assert config.temperature == 0.7
        assert config.max_tokens == 8192
        assert config.system_prompt == ""
        assert config.tools == []
        assert config.retry_times == 3
        assert config.timeout == 60
    
    def test_agent_config_from_config(self):
        """测试从配置字典创建AgentConfig"""
        config_dict = {
            "description": "Custom agent",
            "provider": "qwen",
            "model": "qwen-max",
            "temperature": 0.3,
            "max_tokens": 2048,
            "system_prompt": "Custom prompt",
            "tools": ["database_query"],
            "retry_times": 2,
            "timeout": 30
        }
        
        config = AgentConfig.from_config("custom-agent", config_dict)
        
        assert config.name == "custom-agent"
        assert config.description == "Custom agent"
        assert config.provider == "qwen"
        assert config.model == "qwen-max"
        assert config.temperature == 0.3
        assert config.max_tokens == 2048
        assert config.system_prompt == "Custom prompt"
        assert config.tools == ["database_query"]
        assert config.retry_times == 2
        assert config.timeout == 30
    
    def test_agent_config_from_config_none(self):
        """测试从None配置创建AgentConfig使用全局设置"""
        with patch('deepnovel.agents.base.settings') as mock_settings:
            mock_settings.get_agent.return_value = {
                "provider": "gemini",
                "model": "gemini-pro"
            }
            
            config = AgentConfig.from_config("test-agent", None)
            
            assert config.name == "test-agent"
            assert config.provider == "gemini"
            assert config.model == "gemini-pro"


# ============================================================================
# BaseAgent 测试
# ============================================================================

class MockAgent(BaseAgent):
    """Mock Agent用于测试"""
    
    def process(self, message: Message) -> Message:
        return Message(
            id=str(uuid.uuid4()),
            type=MessageType.TEXT,
            content=f"Processed: {message.content}",
            sender=self.name
        )

    def _generate_with_llm(self, prompt: str, system_prompt: str = None) -> Optional[str]:
        return f"LLM generated: {prompt}"


class TestBaseAgent:
    """BaseAgent类测试"""
    
    def test_base_agent_init(self):
        """测试BaseAgent初始化"""
        config = AgentConfig(name="test-agent", description="Test")
        agent = MockAgent(config)
        
        assert agent.name == "test-agent"
        assert agent.description == "Test"
        assert agent.state == AgentState.IDLE
        assert agent.config == config
        assert agent.last_message is None
        assert agent.history == []
        assert agent._additional_context == {}
        assert agent._llm_router is None
        assert agent._initialized_llm is False
    
    def test_base_agent_properties(self):
        """测试BaseAgent属性"""
        config = AgentConfig(name="test-agent", description="Test description")
        agent = MockAgent(config)
        
        assert agent.name == "test-agent"
        assert agent.description == "Test description"
        assert agent.state == AgentState.IDLE
        assert agent.last_message is None
        assert agent.history == []
    
    def test_base_agent_initialize_success(self):
        """测试BaseAgent初始化成功"""
        config = AgentConfig(name="test-agent")
        agent = MockAgent(config)
        
        with patch.object(agent, '_initialize_llm'):
            result = agent.initialize()
        
        assert result is True
        assert agent.state == AgentState.READY
    
    def test_base_agent_initialize_failure(self):
        """测试BaseAgent初始化失败"""
        config = AgentConfig(name="test-agent")
        agent = MockAgent(config)
        
        with patch.object(agent, '_on_initialize', side_effect=Exception("Init error")):
            result = agent.initialize()
        
        assert result is False
        assert agent.state == AgentState.ERROR
    
    def test_base_agent_cleanup_success(self):
        """测试BaseAgent清理成功"""
        config = AgentConfig(name="test-agent")
        agent = MockAgent(config)
        agent.initialize()
        
        result = agent.cleanup()
        
        assert result is True
        assert agent.state == AgentState.STOPPED
    
    def test_base_agent_cleanup_failure(self):
        """测试BaseAgent清理失败"""
        config = AgentConfig(name="test-agent")
        agent = MockAgent(config)
        
        with patch.object(agent, '_on_cleanup', side_effect=Exception("Cleanup error")):
            result = agent.cleanup()
        
        assert result is False
    
    def test_base_agent_context_operations(self):
        """测试BaseAgent上下文操作"""
        config = AgentConfig(name="test-agent")
        agent = MockAgent(config)
        
        # 设置上下文
        agent.set_context("key1", "value1")
        agent.set_context("key2", {"nested": "data"})
        
        # 获取上下文
        assert agent.get_context("key1") == "value1"
        assert agent.get_context("key2") == {"nested": "data"}
        assert agent.get_context("nonexistent") is None
        assert agent.get_context("nonexistent", "default") == "default"
        
        # 清空上下文
        agent.clear_context()
        assert agent.get_context("key1") is None
    
    def test_base_agent_add_message(self):
        """测试BaseAgent添加消息到历史"""
        config = AgentConfig(name="test-agent")
        agent = MockAgent(config)
        
        msg1 = Message(id="1", type=MessageType.TEXT, content="Message 1")
        msg2 = Message(id="2", type=MessageType.TEXT, content="Message 2")
        
        agent.add_message(msg1)
        assert len(agent.history) == 1
        assert agent._last_message == msg1
        
        agent.add_message(msg2)
        assert len(agent.history) == 2
        assert agent._last_message == msg2
    
    def test_base_agent_add_message_limit(self):
        """测试BaseAgent历史消息长度限制"""
        config = AgentConfig(name="test-agent")
        agent = MockAgent(config)
        
        # 添加超过100条消息
        for i in range(105):
            msg = Message(id=str(i), type=MessageType.TEXT, content=f"Message {i}")
            agent.add_message(msg)
        
        # 历史记录应该被限制为100条
        assert len(agent.history) == 100
        # 只保留最新的消息
        assert agent.history[0].content == "Message 5"
        assert agent.history[-1].content == "Message 104"
    
    def test_base_agent_process_abstract(self):
        """测试BaseAgent process抽象方法"""
        config = AgentConfig(name="test-agent")
        agent = MockAgent(config)
        
        msg = Message(id="1", type=MessageType.TEXT, content="Hello")
        result = agent.process(msg)
        
        assert isinstance(result, Message)
        assert "Processed: Hello" in result.content
        assert result.sender == "test-agent"
    
    def test_base_agent_generate_response(self):
        """测试BaseAgent使用LLM生成响应"""
        config = AgentConfig(name="test-agent")
        agent = MockAgent(config)

        result = agent.generate_response("Test prompt")

        assert isinstance(result, str)
        assert "LLM generated: Test prompt" in result
    
    def test_base_agent_health_check(self):
        """测试BaseAgent健康检查"""
        config = AgentConfig(name="test-agent")
        agent = MockAgent(config)
        
        health = agent.health_check()
        
        assert health["name"] == "test-agent"
        assert health["state"] == "idle"
        assert health["last_message"] is None
        assert health["history_length"] == 0
    
    def test_base_agent_health_check_with_history(self):
        """测试BaseAgent健康检查（有历史消息）"""
        config = AgentConfig(name="test-agent")
        agent = MockAgent(config)
        
        msg = Message(id="msg-1", type=MessageType.TEXT, content="Test")
        agent.add_message(msg)
        
        health = agent.health_check()
        
        assert health["last_message"] == "msg-1"
        assert health["history_length"] == 1
    
    def test_base_agent_create_message(self):
        """测试BaseAgent创建消息"""
        config = AgentConfig(name="test-agent")
        agent = MockAgent(config)
        
        msg = agent._create_message("Test content", MessageType.TEXT, custom_key="custom_value")
        
        assert isinstance(msg, Message)
        assert msg.content == "Test content"
        assert msg.type == MessageType.TEXT
        assert msg.sender == "test-agent"
        assert msg.metadata == {"custom_key": "custom_value"}
    
    def test_base_agent_execute_tool_file_read(self, tmp_path):
        """测试BaseAgent执行file_read工具"""
        config = AgentConfig(name="test-agent", tools=["file_read"])
        agent = MockAgent(config)
        
        # 创建测试文件
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello World", encoding="utf-8")
        
        result = agent.execute_tool("file_read", {"path": str(test_file)})
        
        assert result["success"] is True
        assert result["content"] == "Hello World"
    
    def test_base_agent_execute_tool_file_read_error(self):
        """测试BaseAgent执行file_read工具错误"""
        config = AgentConfig(name="test-agent", tools=["file_read"])
        agent = MockAgent(config)
        
        result = agent.execute_tool("file_read", {"path": "/nonexistent/file.txt"})
        
        assert result["success"] is False
        assert "error" in result
    
    def test_base_agent_execute_tool_file_write(self, tmp_path):
        """测试BaseAgent执行file_write工具"""
        config = AgentConfig(name="test-agent", tools=["file_write"])
        agent = MockAgent(config)
        
        test_file = tmp_path / "output.txt"
        
        result = agent.execute_tool("file_write", {
            "path": str(test_file),
            "content": "Test content"
        })
        
        assert result["success"] is True
        assert result["bytes_written"] == 12
        assert test_file.read_text(encoding="utf-8") == "Test content"
    
    def test_base_agent_execute_tool_calculation(self):
        """测试BaseAgent执行calculation工具"""
        config = AgentConfig(name="test-agent", tools=["calculation"])
        agent = MockAgent(config)
        
        result = agent.execute_tool("calculation", {"expression": "2 + 3 * 4"})
        
        assert result["success"] is True
        assert result["result"] == 14
    
    def test_base_agent_execute_tool_calculation_invalid(self):
        """测试BaseAgent执行calculation工具无效表达式"""
        config = AgentConfig(name="test-agent", tools=["calculation"])
        agent = MockAgent(config)
        
        result = agent.execute_tool("calculation", {"expression": "2 + abc"})
        
        assert "error" in result
    
    def test_base_agent_execute_tool_format_text(self):
        """测试BaseAgent执行format_text工具"""
        config = AgentConfig(name="test-agent", tools=["format_text"])
        agent = MockAgent(config)
        
        # upper
        result = agent.execute_tool("format_text", {"text": "hello", "type": "upper"})
        assert result["result"] == "HELLO"
        
        # lower
        result = agent.execute_tool("format_text", {"text": "WORLD", "type": "lower"})
        assert result["result"] == "world"
        
        # title
        result = agent.execute_tool("format_text", {"text": "hello world", "type": "title"})
        assert result["result"] == "Hello World"
        
        # strip
        result = agent.execute_tool("format_text", {"text": "  hello  ", "type": "strip"})
        assert result["result"] == "hello"
    
    def test_base_agent_execute_tool_echo(self):
        """测试BaseAgent执行echo工具"""
        config = AgentConfig(name="test-agent", tools=["echo"])
        agent = MockAgent(config)
        
        result = agent.execute_tool("echo", {"key": "value", "number": 123})
        
        assert result["echo"] == {"key": "value", "number": 123}
    
    def test_base_agent_execute_tool_not_registered(self):
        """测试BaseAgent执行未注册的工具"""
        config = AgentConfig(name="test-agent", tools=[])
        agent = MockAgent(config)
        
        result = agent.execute_tool("echo", {"test": "data"})
        
        assert result is None
    
    def test_base_agent_execute_tool_not_implemented(self):
        """测试BaseAgent执行未实现的工具"""
        config = AgentConfig(name="test-agent", tools=["unknown_tool"])
        agent = MockAgent(config)
        
        result = agent.execute_tool("unknown_tool", {})
        
        assert "error" in result
        assert "not implemented" in result["error"].lower()


# ============================================================================
# AgentRouter 测试
# ============================================================================

class TestAgentRouter:
    """AgentRouter类测试"""
    
    def test_agent_router_init(self):
        """测试AgentRouter初始化"""
        router = AgentRouter()
        
        assert router._agents == {}
        assert router._routes == {}
    
    def test_agent_router_register_agent(self):
        """测试AgentRouter注册Agent"""
        router = AgentRouter()
        config = AgentConfig(name="test-agent")
        agent = MockAgent(config)
        
        with patch.object(agent, 'initialize', return_value=None):
            result = router.register_agent(agent)
        
        assert result is True
        assert "test-agent" in router._agents
    
    def test_agent_router_register_agent_with_keywords(self):
        """测试AgentRouter注册Agent带关键词"""
        router = AgentRouter()
        config = AgentConfig(name="test-agent")
        agent = MockAgent(config)
        
        with patch.object(agent, 'initialize', return_value=None):
            router.register_agent(agent, keywords=["hello", "hi"])
        
        assert router._routes["hello"] == "test-agent"
        assert router._routes["hi"] == "test-agent"
    
    def test_agent_router_register_agent_failure(self):
        """测试AgentRouter注册Agent失败"""
        router = AgentRouter()
        config = AgentConfig(name="test-agent")
        agent = MockAgent(config)
        
        with patch.object(agent, 'initialize', side_effect=Exception("Init failed")):
            result = router.register_agent(agent)
        
        assert result is False
    
    def test_agent_router_unregister_agent(self):
        """测试AgentRouter注销Agent"""
        router = AgentRouter()
        config = AgentConfig(name="test-agent")
        agent = MockAgent(config)
        
        with patch.object(agent, 'initialize', return_value=None):
            router.register_agent(agent)
        
        with patch.object(agent, 'cleanup', return_value=None):
            result = router.unregister_agent("test-agent")
        
        assert result is True
        assert "test-agent" not in router._agents
    
    def test_agent_router_unregister_agent_failure(self):
        """测试AgentRouter注销Agent失败"""
        router = AgentRouter()
        config = AgentConfig(name="test-agent")
        agent = MockAgent(config)
        
        with patch.object(agent, 'initialize', return_value=None):
            router.register_agent(agent)
        
        with patch.object(agent, 'cleanup', side_effect=Exception("Cleanup failed")):
            result = router.unregister_agent("test-agent")
        
        assert result is False
    
    def test_agent_router_route_by_keyword(self):
        """测试AgentRouter根据关键词路由"""
        router = AgentRouter()
        config = AgentConfig(name="test-agent")
        agent = MockAgent(config)
        
        with patch.object(agent, 'initialize', return_value=None):
            router.register_agent(agent, keywords=["hello"])
        
        msg = Message(id="1", type=MessageType.TEXT, content="Hello there")
        result = router.route(msg)
        
        assert result == agent
    
    def test_agent_router_route_default(self):
        """测试AgentRouter默认路由"""
        router = AgentRouter()
        config = AgentConfig(name="test-agent")
        agent = MockAgent(config)
        
        with patch.object(agent, 'initialize', return_value=None):
            router.register_agent(agent)
        
        msg = Message(id="1", type=MessageType.TEXT, content="Random message")
        result = router.route(msg)
        
        assert result == agent
    
    def test_agent_router_route_no_agent(self):
        """测试AgentRouter无Agent时路由"""
        router = AgentRouter()
        
        msg = Message(id="1", type=MessageType.TEXT, content="Hello")
        result = router.route(msg)
        
        assert result is None
    
    def test_agent_router_process(self):
        """测试AgentRouter处理消息"""
        router = AgentRouter()
        config = AgentConfig(name="test-agent")
        agent = MockAgent(config)
        
        with patch.object(agent, 'initialize', return_value=None):
            router.register_agent(agent)
        
        msg = Message(id="1", type=MessageType.TEXT, content="Hello")
        result = router.process(msg)
        
        assert isinstance(result, Message)
        assert "Processed: Hello" in result.content
    
    def test_agent_router_process_no_agent(self):
        """测试AgentRouter无Agent时处理消息"""
        router = AgentRouter()
        
        msg = Message(id="1", type=MessageType.TEXT, content="Hello")
        result = router.process(msg)
        
        assert result is None
    
    def test_agent_router_process_error(self):
        """测试AgentRouter处理消息错误"""
        router = AgentRouter()
        config = AgentConfig(name="test-agent")
        agent = MockAgent(config)
        
        with patch.object(agent, 'initialize', return_value=None):
            router.register_agent(agent)
        
        with patch.object(agent, 'process', side_effect=Exception("Process error")):
            msg = Message(id="1", type=MessageType.TEXT, content="Hello")
            result = router.process(msg)
        
        assert result is None
    
    def test_agent_router_get_agent(self):
        """测试AgentRouter获取Agent"""
        router = AgentRouter()
        config = AgentConfig(name="test-agent")
        agent = MockAgent(config)
        
        with patch.object(agent, 'initialize', return_value=None):
            router.register_agent(agent)
        
        result = router.get_agent("test-agent")
        assert result == agent
        
        result = router.get_agent("nonexistent")
        assert result is None
    
    def test_agent_router_list_agents(self):
        """测试AgentRouter列出所有Agent"""
        router = AgentRouter()
        
        config1 = AgentConfig(name="agent1")
        agent1 = MockAgent(config1)
        config2 = AgentConfig(name="agent2")
        agent2 = MockAgent(config2)
        
        with patch.object(agent1, 'initialize', return_value=None):
            router.register_agent(agent1)
        with patch.object(agent2, 'initialize', return_value=None):
            router.register_agent(agent2)
        
        agents = router.list_agents()
        
        assert "agent1" in agents
        assert "agent2" in agents
        assert len(agents) == 2


# ============================================================================
# AgentState 枚举测试
# ============================================================================

class TestAgentState:
    """AgentState枚举测试"""
    
    def test_agent_state_values(self):
        """测试AgentState枚举值"""
        assert AgentState.IDLE.value == "idle"
        assert AgentState.INITIALIZING.value == "initializing"
        assert AgentState.READY.value == "ready"
        assert AgentState.BUSY.value == "busy"
        assert AgentState.ERROR.value == "error"
        assert AgentState.STOPPED.value == "stopped"
    
    def test_agent_state_all_states(self):
        """测试所有AgentState状态"""
        states = list(AgentState)
        assert len(states) == 6
        assert AgentState.IDLE in states
        assert AgentState.INITIALIZING in states
        assert AgentState.READY in states
        assert AgentState.BUSY in states
        assert AgentState.ERROR in states
        assert AgentState.STOPPED in states


# ============================================================================
# MessageType 枚举测试
# ============================================================================

class TestMessageType:
    """MessageType枚举测试"""
    
    def test_message_type_values(self):
        """测试MessageType枚举值"""
        assert MessageType.TEXT.value == "text"
        assert MessageType.IMAGE.value == "image"
        assert MessageType.AUDIO.value == "audio"
        assert MessageType.FILE.value == "file"
        assert MessageType.COMMAND.value == "command"
        assert MessageType.SYSTEM.value == "system"
    
    def test_message_type_all_types(self):
        """测试所有MessageType类型"""
        types = list(MessageType)
        assert len(types) == 6
        assert MessageType.TEXT in types
        assert MessageType.IMAGE in types
        assert MessageType.AUDIO in types
        assert MessageType.FILE in types
        assert MessageType.COMMAND in types
        assert MessageType.SYSTEM in types
