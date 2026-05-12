"""
Tests for health_checker utility functions.

@file: tests/test_utils/test_health_checker.py
"""

from unittest.mock import patch, MagicMock
import pytest

from ai_novels.utils.health_checker import check_component_health, check_system_health


class TestCheckComponentHealth:
    """Tests for check_component_health()"""

    @patch("ai_novels.utils.health_checker.get_health_service")
    def test_component_healthy(self, mock_get_service):
        mock_service = MagicMock()
        mock_health = MagicMock()
        mock_health.to_dict.return_value = {
            "name": "mysql",
            "status": "healthy",
            "latency_ms": 12,
            "type": "database",
            "details": {},
            "last_check": 1000.0,
        }
        mock_service.check_single.return_value = mock_health
        mock_get_service.return_value = mock_service

        result = check_component_health("mysql")
        assert result["status"] == "healthy"
        assert result["name"] == "mysql"
        mock_service.check_single.assert_called_once_with("mysql")

    @patch("ai_novels.utils.health_checker.get_health_service")
    def test_component_unhealthy(self, mock_get_service):
        mock_service = MagicMock()
        mock_health = MagicMock()
        mock_health.to_dict.return_value = {
            "name": "neo4j",
            "status": "unhealthy",
            "latency_ms": 3000,
            "type": "database",
            "details": {"error": "Connection refused"},
            "last_check": 1000.0,
        }
        mock_service.check_single.return_value = mock_health
        mock_get_service.return_value = mock_service

        result = check_component_health("neo4j")
        assert result["status"] == "unhealthy"
        assert "error" in result["details"]

    @patch("ai_novels.utils.health_checker.get_health_service")
    def test_component_without_to_dict(self, mock_get_service):
        """Fallback: check_single returns object without to_dict()"""
        mock_service = MagicMock()

        class NoToDict:
            def __str__(self):
                return "unknown status"

        mock_service.check_single.return_value = NoToDict()
        mock_get_service.return_value = mock_service

        result = check_component_health("unknown")
        assert result["name"] == "unknown"
        assert "status" in result

    @patch("ai_novels.utils.health_checker.get_health_service")
    def test_service_exception(self, mock_get_service):
        mock_get_service.side_effect = RuntimeError("HealthService unavailable")

        with pytest.raises(RuntimeError):
            check_component_health("mysql")


class TestCheckSystemHealth:
    """Tests for check_system_health()"""

    @patch("ai_novels.utils.health_checker.get_health_service")
    def test_healthy_system(self, mock_get_service):
        mock_service = MagicMock()
        mock_service.check_all.return_value = {
            "overall_status": "healthy",
            "components": {"mysql": {"status": "healthy"}},
            "healthy_count": 1,
            "degraded_count": 0,
            "unhealthy_count": 0,
        }
        mock_get_service.return_value = mock_service

        result = check_system_health()
        assert result["overall_status"] == "healthy"
        assert result["healthy_count"] == 1

    @patch("ai_novels.utils.health_checker.get_health_service")
    def test_unhealthy_system(self, mock_get_service):
        mock_service = MagicMock()
        mock_service.check_all.return_value = {
            "overall_status": "unhealthy",
            "components": {"mysql": {"status": "unhealthy"}},
            "healthy_count": 0,
            "degraded_count": 0,
            "unhealthy_count": 1,
        }
        mock_get_service.return_value = mock_service

        result = check_system_health()
        assert result["overall_status"] == "unhealthy"
        assert result["unhealthy_count"] == 1
