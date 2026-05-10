"""
AppConfig 与基础设施集成测试

测试范围:
- database.engine 从 AppConfig 读取配置
- redis_event_bus 从 AppConfig 读取配置
- structlog_config 从 AppConfig 读取配置
"""

from unittest.mock import patch

import pytest

from deepnovel.config.app_config import reload_config


class TestEngineConfigIntegration:
    """数据库引擎配置集成测试"""

    @pytest.mark.asyncio
    async def test_engine_reads_db_url_from_config(self):
        """引擎必须从 AppConfig 读取数据库 URL"""
        from deepnovel.database.engine import _init_engine, close_db

        await close_db()

        with patch.dict(
            "os.environ",
            {"APP_DATABASE__URL": "postgresql+asyncpg://test:test@localhost:5432/testdb"},
            clear=False,
        ):
            reload_config()
            _init_engine()

            from deepnovel.database.engine import _engine

            assert _engine is not None
            assert "testdb" in str(_engine.url)

        await close_db()

    @pytest.mark.asyncio
    async def test_engine_reads_pool_size_from_config(self):
        """引擎必须从 AppConfig 读取连接池配置"""
        from deepnovel.database.engine import _init_engine, close_db

        await close_db()

        with patch.dict(
            "os.environ",
            {"APP_DATABASE__POOL_SIZE": "25"},
            clear=False,
        ):
            reload_config()
            _init_engine()

            from deepnovel.database.engine import _engine

            assert _engine is not None

        await close_db()


class TestRedisEventBusConfigIntegration:
    """Redis EventBus 配置集成测试"""

    def test_redis_url_from_config(self):
        """RedisEventBus 必须可从 AppConfig 读取 URL"""
        from deepnovel.core.redis_event_bus import _get_redis_url

        url = _get_redis_url()
        assert "redis://" in url

    def test_redis_url_uses_app_config(self):
        """Redis URL 必须反映 AppConfig 的值"""
        from deepnovel.core.redis_event_bus import _get_redis_url

        with patch.dict(
            "os.environ",
            {"APP_REDIS__URL": "redis://custom:6380/1"},
            clear=False,
        ):
            reload_config()
            url = _get_redis_url()
            assert url == "redis://custom:6380/1"


class TestStructlogConfigIntegration:
    """Structlog 配置集成测试"""

    def test_configure_from_app_reads_log_level(self):
        """configure_structlog_from_app 必须读取日志级别"""
        from deepnovel.utils.structlog_config import configure_structlog_from_app

        with patch.dict(
            "os.environ",
            {"APP_LOG__LEVEL": "DEBUG", "APP_LOG__JSON_FORMAT": "true"},
            clear=False,
        ):
            reload_config()
            # 不应抛出异常
            configure_structlog_from_app()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
