"""
HealthCheckerAgent 单元测试

测试范围:
- Agent 初始化
- process() 调用真实健康检查服务
- 异常处理
"""

import pytest
from unittest.mock import patch, MagicMock

from deepnovel.agents.implementations import HealthCheckerAgent
from deepnovel.agents.base import AgentConfig, Message, MessageType


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
    @patch("deepnovel.services.health_service.get_health_service")
    def test_process_with_healthy_system(self, mock_get_service, agent):
        mock_service = MagicMock()
        mock_service.check_system_health.return_value = {
            "overall_status": "healthy",
            "components": {
                "database": {"status": "healthy", "latency_ms": 12},
                "llm": {"status": "healthy", "latency_ms": 45},
            }
        }
        mock_get_service.return_value = mock_service

        msg = Message(id="t1", type=MessageType.TEXT, content="check health")
        result = agent.process(msg)

        assert result is not None
        assert "HEALTHY" in result.content or "healthy" in result.content
        assert "database" in result.content

    @patch("deepnovel.services.health_service.get_health_service")
    def test_process_with_unhealthy_system(self, mock_get_service, agent):
        mock_service = MagicMock()
        mock_service.check_system_health.return_value = {
            "overall_status": "degraded",
            "components": {
                "database": {"status": "unhealthy", "latency_ms": 5000},
            }
        }
        mock_get_service.return_value = mock_service

        msg = Message(id="t2", type=MessageType.TEXT, content="check health")
        result = agent.process(msg)

        assert result is not None
        assert "degraded" in result.content or "DEGRADED" in result.content

    def test_process_service_exception(self, agent):
        with patch("deepnovel.services.health_service.get_health_service", side_effect=RuntimeError("Service not available")):
            msg = Message(id="t3", type=MessageType.TEXT, content="check health")
            result = agent.process(msg)

        assert result is not None
        assert "failed" in result.content


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
