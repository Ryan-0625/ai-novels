"""
CharacterGeneratorAgent 单元测试

测试范围:
- Agent 初始化与配置
- process() 消息处理流程
- LLM 输出解析与持久化调用
- 异常输入处理
"""

import json
from unittest.mock import patch

import pytest

from ai_novels.agents.implementations import CharacterGeneratorAgent
from ai_novels.agents.base import AgentConfig, Message, MessageType


@pytest.fixture
def agent():
    """创建已初始化的 CharacterGeneratorAgent"""
    config = AgentConfig(
        name="character_generator",
        description="Generate character profiles",
        provider="ollama",
        model="qwen2.5-7b",
    )
    a = CharacterGeneratorAgent(config)
    a.initialize()
    return a


class TestCharacterGeneratorInitialization:
    """初始化测试"""

    def test_default_init(self):
        """默认配置初始化"""
        a = CharacterGeneratorAgent()
        a.initialize()
        assert a.name == "character_generator"
        assert a.state.value == "ready"

    def test_custom_config_init(self, agent):
        """自定义配置初始化"""
        assert agent.config.name == "character_generator"
        assert agent.config.provider == "ollama"


class TestCharacterGeneratorProcess:
    """消息处理测试"""

    def test_process_with_mock_llm(self, agent):
        """使用 Mock LLM 测试完整处理流程"""
        # _generate_character_with_llm expects a single JSON object per call
        mock_char = json.dumps({
            "age": 25,
            "gender": "female",
            "personality": ["brave", "curious"],
            "goals": ["Seek the ancient tome"],
            "background": "A wizard apprentice...",
            "weaknesses": ["Trust issues"],
            "secrets": ["A dark secret"]
        })

        with patch.object(agent, '_generate_with_llm', return_value=mock_char):
            msg = Message(
                id="test-1",
                type=MessageType.TEXT,
                content="Generate characters for a fantasy novel. Title: The Lost Tome. Genre: fantasy. Task ID: test-task-001",
            )
            result = agent.process(msg)

        assert result is not None
        assert result.type == MessageType.TEXT
        assert "Generated" in result.content

    def test_process_llm_empty_response(self, agent):
        """LLM 返回空时的处理"""
        with patch.object(agent, '_generate_with_llm', return_value=None):
            msg = Message(
                id="test-2",
                type=MessageType.TEXT,
                content="Generate characters. Genre: sci-fi.",
            )
            result = agent.process(msg)

        assert result is not None
        assert "Generated" in result.content

    def test_process_invalid_json_in_content(self, agent):
        """消息内容不含有效 JSON 时的处理"""
        with patch.object(agent, '_generate_with_llm', return_value="plain text without json"):
            msg = Message(
                id="test-3",
                type=MessageType.TEXT,
                content="Just generate something",
            )
            result = agent.process(msg)

        assert result is not None
        assert result.type == MessageType.TEXT

    def test_extract_user_request(self, agent):
        """测试请求参数提取"""
        content = "Genre: romance"
        req = agent._parse_config(content)
        assert req.get("genre") == "romance"


class TestCharacterGeneratorEdgeCases:
    """边界情况测试"""

    def test_process_empty_message(self, agent):
        """空消息处理"""
        with patch.object(agent, '_generate_with_llm', return_value="[]"):
            msg = Message(
                id="test-empty",
                type=MessageType.TEXT,
                content="",
            )
            result = agent.process(msg)
        assert result is not None

    def test_health_check(self, agent):
        """健康检查"""
        health = agent.health_check()
        assert health["name"] == "character_generator"
        assert "state" in health


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
