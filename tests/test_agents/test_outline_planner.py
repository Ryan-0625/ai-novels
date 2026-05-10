"""
OutlinePlannerAgent 单元测试

测试范围:
- Agent 初始化与默认配置
- process() 大纲生成流程
- 用户请求参数提取
- LLM 空响应处理
"""

import json
import pytest
from unittest.mock import patch

from deepnovel.agents.implementations import OutlinePlannerAgent
from deepnovel.agents.base import AgentConfig, Message, MessageType


@pytest.fixture
def agent():
    config = AgentConfig(name="outline_planner", provider="ollama", model="qwen2.5-7b")
    a = OutlinePlannerAgent(config)
    a.initialize()
    return a


class TestOutlinePlannerInitialization:
    def test_default_init(self):
        a = OutlinePlannerAgent()
        a.initialize()
        assert a.name == "outline_planner"
        assert a.config.system_prompt is not None

    def test_custom_config(self, agent):
        assert agent.config.max_tokens >= 4096


class TestOutlinePlannerProcess:
    def test_process_with_llm_response(self, agent):
        mock_outline = json.dumps([
            {"chapter": 1, "title": "The Beginning", "events": ["Meet protagonist"]},
            {"chapter": 2, "title": "The Conflict", "events": ["Inciting incident"]},
        ], ensure_ascii=False)

        with patch.object(agent, '_generate_with_llm', return_value=mock_outline):
            msg = Message(
                id="t1", type=MessageType.TEXT,
                content='{"title": "Test Novel", "genre": "fantasy", "chapters": 2, "style": "standard", "task_id": "task-001"}'
            )
            result = agent.process(msg)

        assert result is not None
        assert result.type == MessageType.TEXT

    def test_process_empty_llm_response(self, agent):
        with patch.object(agent, '_generate_with_llm', return_value=None):
            msg = Message(id="t2", type=MessageType.TEXT, content="Plan outline for my novel")
            result = agent.process(msg)

        assert result is not None
        assert result.type == MessageType.TEXT

    def test_extract_user_request(self, agent):
        content = 'Genre: sci-fi'
        req = agent._parse_config(content)
        assert req.get("genre") == "sci-fi"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
