"""
TaskManagerAgent 单元测试

测试范围:
- Agent 初始化
- process() 各种命令处理
- 消息路由
"""

import pytest

from deepnovel.agents.implementations import TaskManagerAgent
from deepnovel.agents.base import AgentConfig, Message, MessageType


@pytest.fixture
def agent():
    config = AgentConfig(name="task_manager", provider="ollama", model="qwen2.5-7b")
    a = TaskManagerAgent(config)
    a.initialize()
    return a


class TestTaskManagerInitialization:
    def test_default_init(self):
        a = TaskManagerAgent()
        a.initialize()
        assert a.name == "task_manager"


class TestTaskManagerProcess:
    def test_create_task(self, agent):
        msg = Message(id="t1", type=MessageType.TEXT, content="create new task")
        result = agent.process(msg)
        assert result is not None
        assert result.type == MessageType.TEXT

    def test_update_task(self, agent):
        msg = Message(id="t2", type=MessageType.TEXT, content="update task status")
        result = agent.process(msg)
        assert result is not None
        assert "updated" in result.content

    def test_query_status(self, agent):
        msg = Message(id="t3", type=MessageType.TEXT, content="check status")
        result = agent.process(msg)
        assert result is not None
        assert result.type == MessageType.TEXT

    def test_general_request(self, agent):
        msg = Message(id="t4", type=MessageType.TEXT, content="hello")
        result = agent.process(msg)
        assert result is not None
        assert result.type == MessageType.TEXT


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
