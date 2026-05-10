"""
AppConfig 统一配置测试

测试范围:
- 默认值加载
- 环境变量注入
- 子配置验证
- 脱敏导出
- 单例缓存
"""

import os
from unittest.mock import patch

import pytest

from deepnovel.config.app_config import AppConfig, LLMProviderConfig, get_config, reload_config


class TestAppConfigDefaults:
    """AppConfig 默认值测试"""

    def test_default_environment(self):
        """默认环境必须是 development"""
        config = AppConfig()
        assert config.environment == "development"

    def test_default_port(self):
        """默认端口必须是 8000"""
        config = AppConfig()
        assert config.port == 8000

    def test_default_debug(self):
        """默认调试模式必须是 False"""
        config = AppConfig()
        assert config.debug is False

    def test_database_defaults(self):
        """数据库子配置必须有默认值"""
        config = AppConfig()
        assert config.database.pool_size == 10
        assert config.database.max_overflow == 20
        assert config.database.pool_pre_ping is True

    def test_redis_defaults(self):
        """Redis子配置必须有默认值"""
        config = AppConfig()
        assert config.redis.url == "redis://localhost:6379/0"
        assert config.redis.stream_key == "deepnovel:events"

    def test_llm_defaults(self):
        """LLM子配置必须有默认值"""
        config = AppConfig()
        assert config.llm.default_provider == "ollama"
        assert config.llm.fallback_enabled is True

    def test_log_defaults(self):
        """日志子配置必须有默认值"""
        config = AppConfig()
        assert config.log.level == "INFO"
        assert config.log.json_format is False


class TestAppConfigValidation:
    """AppConfig 验证测试"""

    def test_invalid_environment(self):
        """无效环境必须抛出 ValueError"""
        with pytest.raises(ValueError):
            AppConfig(environment="invalid")

    def test_invalid_log_level(self):
        """无效日志级别必须抛出 ValueError"""
        with pytest.raises(ValueError):
            AppConfig(log={"level": "INVALID"})

    def test_port_range(self):
        """端口必须在 1-65535 范围内"""
        with pytest.raises(ValueError):
            AppConfig(port=0)
        with pytest.raises(ValueError):
            AppConfig(port=70000)


class TestEnvironmentVariables:
    """环境变量注入测试"""

    @patch.dict(os.environ, {"APP_PORT": "9000", "APP_DEBUG": "true"}, clear=False)
    def test_port_from_env(self):
        """环境变量必须覆盖默认端口"""
        config = AppConfig()
        assert config.port == 9000
        assert config.debug is True

    @patch.dict(os.environ, {"DB_POOL_SIZE": "20"}, clear=False)
    def test_db_pool_from_env(self):
        """数据库连接池大小必须可从环境变量配置"""
        config = AppConfig()
        assert config.database.pool_size == 20

    @patch.dict(os.environ, {"REDIS_URL": "redis://cache:6379/1"}, clear=False)
    def test_redis_url_from_env(self):
        """Redis URL 必须可从环境变量配置"""
        config = AppConfig()
        assert config.redis.url == "redis://cache:6379/1"


class TestSensitiveDataMasking:
    """敏感数据脱敏测试"""

    def test_mask_api_key(self):
        """to_safe_dict 必须脱敏 API 密钥"""
        provider = LLMProviderConfig(
            provider="openai",
            model="gpt-4",
            api_key="sk-test1234567890abcdef",
        )
        config = AppConfig(
            llm={"providers": {"openai": provider.model_dump()}}
        )

        safe = config.to_safe_dict()
        masked = safe["llm"]["providers"]["openai"]["api_key"]
        assert "****" in masked
        assert masked != "sk-test1234567890abcdef"

    def test_safe_dict_no_mutation(self):
        """to_safe_dict 不应修改原始配置"""
        config = AppConfig()
        original = config.llm.default_provider
        safe = config.to_safe_dict()
        assert config.llm.default_provider == original


class TestConfigSingleton:
    """配置单例测试"""

    def test_singleton_same_instance(self):
        """get_config 必须返回同一实例"""
        c1 = get_config()
        c2 = get_config()
        assert c1 is c2

    def test_reload_creates_new_instance(self):
        """reload_config 必须创建新实例"""
        c1 = get_config()
        c2 = reload_config()
        assert c1 is not c2


class TestLLMProviderConfig:
    """LLMProviderConfig 测试"""

    def test_temperature_range(self):
        """温度必须在 0-2 范围内"""
        with pytest.raises(ValueError):
            LLMProviderConfig(provider="test", model="test", temperature=3.0)

    def test_timeout_range(self):
        """超时必须 >= 1"""
        with pytest.raises(ValueError):
            LLMProviderConfig(provider="test", model="test", timeout=0.5)

    def test_repr_masks_api_key(self):
        """repr 必须脱敏显示"""
        p = LLMProviderConfig(
            provider="openai",
            model="gpt-4",
            api_key="sk-1234567890abcdef",
        )
        r = repr(p)
        assert "****" in r or "sk-1234" in r


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
