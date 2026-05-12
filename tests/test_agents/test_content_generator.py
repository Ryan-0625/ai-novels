"""
ContentGeneratorAgent 单元测试

测试范围:
- Agent 初始化
- process() 内容生成流程
- 风格配置管理
- 混沌事件注入
"""

import pytest
from unittest.mock import patch

from ai_novels.agents.content_generator import ContentGeneratorAgent, WritingMode, StyleConfig
from ai_novels.agents.base import AgentConfig, Message, MessageType


@pytest.fixture
def agent():
    config = AgentConfig(name="content_generator", provider="ollama", model="qwen2.5-7b")
    a = ContentGeneratorAgent(config)
    a.initialize()
    return a


class TestContentGeneratorInitialization:
    def test_default_init(self):
        a = ContentGeneratorAgent()
        a.initialize()
        assert a.name == "content_generator"

    def test_default_style(self, agent):
        style = agent.get_style()
        assert style.vocabulary_level == 5
        assert style.pacing == "normal"


class TestContentGeneratorProcess:
    def test_generate_content_command(self, agent):
        mock_text = "The morning sun rose over the ancient city..."
        with patch.object(agent, '_generate_with_llm', return_value=mock_text):
            msg = Message(
                id="t1", type=MessageType.TEXT,
                content="generate content chapter_id=chapter_1 outline=A test chapter beats=intro;conflict;resolution words=500 mode=balanced"
            )
            result = agent.process(msg)
        assert result is not None
        assert "Generated Content" in result.content

    def test_style_show_command(self, agent):
        msg = Message(id="t2", type=MessageType.TEXT, content="show style")
        result = agent.process(msg)
        assert result is not None
        assert "Vocabulary" in result.content

    def test_set_preset_style(self, agent):
        # 使用不包含 "set" 的消息以命中 preset 分支
        msg = Message(id="t3", type=MessageType.TEXT, content="style preset=poetic")
        result = agent.process(msg)
        assert result is not None
        style = agent.get_style()
        assert style.metaphor_frequency == 8

    def test_chaos_library_commands(self, agent):
        msg = Message(id="t4", type=MessageType.TEXT, content="add chaos event event_id=chaos_001 type=dramatic description=A fire breaks out impact=80")
        result = agent.process(msg)
        assert result is not None
        assert "chaos_001" in result.content

        msg2 = Message(id="t5", type=MessageType.TEXT, content="inject chaos chapter_id=chapter_1 max=1")
        result2 = agent.process(msg2)
        assert result2 is not None

        msg3 = Message(id="t6", type=MessageType.TEXT, content="show chaos library")
        result3 = agent.process(msg3)
        assert result3 is not None
        assert "dramatic" in result3.content

    def test_history_stats_commands(self, agent):
        msg = Message(id="t7", type=MessageType.TEXT, content="show stats history")
        result = agent.process(msg)
        assert result is not None
        assert "Total Words" in result.content

    def test_general_help(self, agent):
        msg = Message(id="t8", type=MessageType.TEXT, content="help")
        result = agent.process(msg)
        assert result is not None
        # 未识别命令默认走内容生成
        assert result.type == MessageType.TEXT


class TestContentGeneratorExternalApi:
    def test_generate_content_api(self, agent):
        with patch.object(agent, '_generate_with_llm', return_value="Test chapter content here."):
            result = agent.generate_content(
                chapter_id="chapter_1",
                outline="Test chapter",
                target_words=200,
                writing_mode="fast",
            )
        assert result is not None
        assert result.chapter_id == "chapter_1"

    def test_set_style_api(self, agent):
        style = agent.set_style(vocabulary_level=8, pacing="slow")
        assert style.vocabulary_level == 8
        assert style.pacing == "slow"

    def test_reset(self, agent):
        agent.reset()
        assert len(agent.get_all_contents()) == 0
        assert len(agent.get_chaos_library()) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
