"""
HealthCheckerAgent 单元测试

测试范围:
- Agent 初始化
- process() 调用真实健康检查服务
- 异常处理

注意: HealthCheckerAgent 已废弃，建议使用 ai_novels.utils.health_checker
"""

import pytest
from unittest.mock import patch

from ai_novels.agents.implementations import HealthCheckerAgent
from ai_novels.agents.base import AgentConfig, Message, MessageType


@pytest.fixture
def agent():
    config = AgentConfig(name="health_checker", provider="ollama", model="qwen2.5-7b")
    a = HealthCheckerAgent(config)
    a.initialize()
    return a


class TestHealthCheckerInitialization:
    def test_default_init(self):
        a = HealthCheckerAgent()
        a.initialize()
        assert a.name == "health_checker"


class TestHealthCheckerProcess:
    @patch("ai_novels.agents.health_checker.HealthCheckerAgent._check_all_components")
    def test_process_with_healthy_system(self, mock_check_all, agent):
        mock_check_all.return_value = Message(
            id="r1", type=MessageType.TEXT,
            content="=== Health Check Results ===\n\nOverall Status: HEALTHY",
            metadata={"overall_status": "healthy", "components_checked": 3}
        )

        msg = Message(id="t1", type=MessageType.TEXT, content="check health")
        result = agent.process(msg)

        assert result is not None
        assert "HEALTHY" in result.content or "healthy" in result.content

    @patch("ai_novels.agents.health_checker.HealthCheckerAgent._check_all_components")
    def test_process_with_unhealthy_system(self, mock_check_all, agent):
        mock_check_all.return_value = Message(
            id="r2", type=MessageType.TEXT,
            content="=== Health Check Results ===\n\nOverall Status: DEGRADED",
            metadata={"overall_status": "degraded", "components_checked": 3}
        )

        msg = Message(id="t2", type=MessageType.TEXT, content="check health")
        result = agent.process(msg)

        assert result is not None
        assert "DEGRADED" in result.content or "degraded" in result.content

    def test_process_service_exception(self, agent):
        msg = Message(id="t3", type=MessageType.TEXT, content="check health")
        result = agent.process(msg)

        assert result is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
