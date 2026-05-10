"""
ConfigEnhancerAgent 单元测试

测试范围:
- Agent 初始化
- process() 使用 LLM 增强配置
- 空/异常 LLM 响应处理
"""

import pytest
from unittest.mock import patch

from deepnovel.agents.implementations import ConfigEnhancerAgent
from deepnovel.agents.base import AgentConfig, Message, MessageType


@pytest.fixture
def agent():
    config = AgentConfig(name="config_enhancer", provider="ollama", model="qwen2.5-7b")
    a = ConfigEnhancerAgent(config)
    a.initialize()
    return a


class TestConfigEnhancerInitialization:
    def test_default_init(self):
        a = ConfigEnhancerAgent()
        a.initialize()
        assert a.name == "config_enhancer"
        assert a.state.value == "ready"


class TestConfigEnhancerProcess:
    def test_process_with_llm_response(self, agent):
        mock_result = '{"genre": "fantasy", "target_audience": "young adult", "style": "descriptive", "tone": "dark", "structure": "three-act", "themes": ["redemption", "friendship"]}'
        with patch.object(agent, '_generate_with_llm', return_value=mock_result):
            msg = Message(id="t1", type=MessageType.TEXT, content="I want a dark fantasy novel")
            result = agent.process(msg)
        assert result is not None
        assert "Configuration enhanced" in result.content

    def test_process_empty_llm_response(self, agent):
        with patch.object(agent, '_generate_with_llm', return_value=None):
            msg = Message(id="t2", type=MessageType.TEXT, content="Generate config")
            result = agent.process(msg)
        assert result is not None
        assert "default settings" in result.content


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
