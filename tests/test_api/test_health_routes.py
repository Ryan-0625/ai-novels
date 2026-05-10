"""
健康检查与指标端点测试

测试范围:
- /health 综合健康检查
- /health/live 存活探针
- /health/ready 就绪探针
- /metrics 指标端点
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from deepnovel.api.health_routes import (
    health_check,
    liveness_probe,
    metrics,
    readiness_probe,
)
from deepnovel.config.app_config import AppConfig


class TestLivenessProbe:
    """存活探针测试"""

    @pytest.mark.asyncio
    async def test_returns_alive(self):
        """liveness_probe 必须返回 alive"""
        result = await liveness_probe()
        assert result["status"] == "alive"


class TestHealthCheck:
    """综合健康检查测试"""

    @pytest.mark.asyncio
    async def test_health_all_ok(self):
        """所有组件健康时必须返回 healthy"""
        session = AsyncMock(spec=AsyncSession)
        config = MagicMock(spec=AppConfig)
        config.app_version = "2.0.0"
        config.environment = "test"

        result = await health_check(session, config)

        assert result["status"] == "healthy"
        assert result["version"] == "2.0.0"
        assert result["environment"] == "test"
        assert result["checks"]["database"] == "ok"
        assert "timestamp" in result

    @pytest.mark.asyncio
    async def test_health_db_error(self):
        """数据库异常时必须返回 degraded"""
        session = AsyncMock(spec=AsyncSession)
        session.execute.side_effect = Exception("connection refused")
        config = MagicMock(spec=AppConfig)
        config.app_version = "2.0.0"
        config.environment = "test"

        result = await health_check(session, config)

        assert result["status"] == "degraded"
        assert "error" in result["checks"]["database"]


class TestReadinessProbe:
    """就绪探针测试"""

    @pytest.mark.asyncio
    async def test_ready_when_db_ok(self):
        """数据库连接正常时必须返回 ready"""
        session = AsyncMock(spec=AsyncSession)

        result = await readiness_probe(session)

        assert result["status"] == "ready"
        assert result["database"] == "connected"

    @pytest.mark.asyncio
    async def test_not_ready_when_db_error(self):
        """数据库异常时必须返回 not_ready"""
        session = AsyncMock(spec=AsyncSession)
        session.execute.side_effect = Exception("timeout")

        result = await readiness_probe(session)

        assert result["status"] == "not_ready"
        assert "error" in result["database"]


class TestMetrics:
    """指标端点测试"""

    @pytest.mark.asyncio
    async def test_metrics_returns_data(self):
        """metrics 必须返回指标数据"""
        result = await metrics()

        assert "app" in result
        assert "system" in result
        assert "uptime_seconds" in result["app"]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
