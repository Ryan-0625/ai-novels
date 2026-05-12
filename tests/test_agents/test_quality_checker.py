"""
QualityCheckerAgent 单元测试

测试范围:
- Agent 初始化
- process() 质量检查流程
- LLM 响应处理
"""

import pytest
from unittest.mock import patch

from ai_novels.agents.implementations import QualityCheckerAgent
from ai_novels.agents.base import AgentConfig, Message, MessageType


@pytest.fixture
def agent():
    config = AgentConfig(name="quality_checker", provider="ollama", model="qwen2.5-7b")
    a = QualityCheckerAgent(config)
    a.initialize()
    return a


class TestQualityCheckerInitialization:
    def test_default_init(self):
        a = QualityCheckerAgent()
        a.initialize()
        assert a.name == "quality_checker"


class TestQualityCheckerProcess:
    def test_process_with_llm_response(self, agent):
        mock_report = """
        Coherence: 85/100
        Grammar: 90/100
        Character Consistency: 88/100
        Plot Logic: 82/100
        Engagement: 87/100
        """
        with patch.object(agent, '_generate_with_llm', return_value=mock_report):
            msg = Message(
                id="t1", type=MessageType.TEXT,
                content="content_id=test-001 The protagonist walked into the dark forest."
            )
            result = agent.process(msg)

        assert result is not None
        assert "Quality Report" in result.content

    def test_process_empty_llm_response(self, agent):
        with patch.object(agent, '_generate_with_llm', return_value=None):
            msg = Message(id="t2", type=MessageType.TEXT, content="content_id=test-002 Check this text")
            result = agent.process(msg)

        assert result is not None
        assert "Quality Report" in result.content


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
