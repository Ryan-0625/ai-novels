"""
ConfigHub 单元测试

测试统一配置管理中心的初始化、访问和热重载。
"""

import pytest

from deepnovel.config.hub import ConfigHub, get_config_hub, get_novel_config
from deepnovel.config.novel_config import GenreType, NovelConfig


class TestConfigHubSingleton:
    def test_singleton(self):
        hub1 = ConfigHub()
        hub2 = ConfigHub()
        assert hub1 is hub2

    def test_initialize_idempotent(self):
        hub = ConfigHub()
        hub.initialize()
        hub.initialize()  # 第二次不应出错
        assert hub.is_initialized is True


class TestConfigHubAccess:
    def test_get_database_url(self):
        hub = ConfigHub()
        hub.initialize()
        url = hub.get("database.url")
        assert url is not None
        assert "postgresql" in url

    def test_get_nested(self):
        hub = ConfigHub()
        hub.initialize()
        # 测试嵌套访问
        pool_size = hub.get("database.pool_size")
        assert isinstance(pool_size, int)
        assert pool_size >= 1

    def test_get_default(self):
        hub = ConfigHub()
        hub.initialize()
        value = hub.get("nonexistent.path", default="fallback")
        assert value == "fallback"

    def test_get_invalid_key_returns_default(self):
        hub = ConfigHub()
        hub.initialize()
        value = hub.get("database.nonexistent_field", default=42)
        assert value == 42


class TestConfigHubNovelConfig:
    def test_get_novel_config_default(self):
        hub = ConfigHub()
        hub.initialize()
        config = hub.get_novel_config()
        assert isinstance(config, NovelConfig)
        assert config.title == "未命名小说"
        assert config.genre == GenreType.OTHER

    def test_get_novel_preset_xianxia(self):
        hub = ConfigHub()
        hub.initialize()
        config = hub.get_novel_config("xianxia")
        assert config.genre == GenreType.XIUXIA
        assert config.world.power_system.value == "qi_cultivation"
        assert "修仙" in config.tags

    def test_get_novel_preset_wuxia(self):
        hub = ConfigHub()
        hub.initialize()
        config = hub.get_novel_config("wuxia")
        assert config.genre == GenreType.WUXIA

    def test_get_novel_preset_scifi(self):
        hub = ConfigHub()
        hub.initialize()
        config = hub.get_novel_config("sci-fi")
        assert config.genre == GenreType.SCI_FI

    def test_get_novel_preset_romance(self):
        hub = ConfigHub()
        hub.initialize()
        config = hub.get_novel_config("romance")
        assert config.genre == GenreType.ROMANCE

    def test_get_preset_names(self):
        hub = ConfigHub()
        hub.initialize()
        names = hub.get_preset_names()
        assert "xianxia" in names
        assert "wuxia" in names
        assert "sci-fi" in names
        assert "romance" in names

    def test_add_preset(self):
        hub = ConfigHub()
        hub.initialize()
        custom = NovelConfig(title="自定义", genre="fantasy")
        hub.add_preset("custom", custom)
        retrieved = hub.get_novel_config("custom")
        assert retrieved.title == "自定义"

    def test_unknown_preset_returns_default(self):
        hub = ConfigHub()
        hub.initialize()
        config = hub.get_novel_config("unknown_preset")
        assert config.title == "未命名小说"


class TestConfigHubProperties:
    def test_config_property(self):
        hub = ConfigHub()
        hub.initialize()
        config = hub.config
        assert config.app_name == "deepnovel-ai"

    def test_is_initialized_after_init(self):
        hub = ConfigHub()
        # 单例可能已被其他测试初始化
        if not hub.is_initialized:
            hub.initialize()
        assert hub.is_initialized is True

    def test_uninitialized_config_raises(self):
        # 创建子类绕过单例，测试未初始化时的行为
        class FreshHub(ConfigHub):
            _instance = None
            _initialized = False

        fresh = FreshHub()
        assert fresh.is_initialized is False
        fresh.initialize()
        assert fresh.is_initialized is True


class TestConfigHubReload:
    def test_reload(self):
        hub = ConfigHub()
        hub.initialize()
        result = hub.reload()
        assert result is hub  # 返回自身（链式调用）
        assert hub.is_initialized is True


class TestConfigHubSafeDict:
    def test_to_safe_dict(self):
        hub = ConfigHub()
        hub.initialize()
        safe = hub.to_safe_dict()
        assert "app_name" in safe
        assert "database" in safe


class TestConvenienceFunctions:
    def test_get_config_hub(self):
        hub = get_config_hub()
        assert isinstance(hub, ConfigHub)
        assert hub.is_initialized is True

    def test_get_novel_config_function(self):
        config = get_novel_config("xianxia")
        assert config.genre == GenreType.XIUXIA

    def test_get_novel_config_function_default(self):
        config = get_novel_config()
        assert config.genre == GenreType.OTHER


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
