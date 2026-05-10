"""
ConfigHub — 统一配置管理中心

所有模块通过 ConfigHub 获取配置，禁止直接读取环境变量或配置文件。

特性:
- 单例模式（线程安全）
- 统一访问 AppConfig（含 NovelConfig）
- 热重载支持
- 向后兼容旧配置访问方式

@file: config/hub.py
@date: 2026-04-29
"""

import threading
from typing import Any, Dict, Optional

from deepnovel.config.app_config import AppConfig, get_config, reload_config
from deepnovel.config.novel_config import NovelConfig
from deepnovel.utils.logger import get_logger

_logger = get_logger()


class ConfigHub:
    """
    统一配置管理中心

    作为所有配置的唯一入口，封装 AppConfig 并提供便捷访问方法。

    使用方式:
        hub = ConfigHub()
        hub.initialize()  # 首次调用时加载配置

        # 访问配置
        db_url = hub.config.database.url
        llm_provider = hub.config.llm.default_provider

        # 便捷方法
        hub.get("database.url", default="...")
        hub.get_novel_config()  # 获取默认 NovelConfig

        # 热重载
        hub.reload()
    """

    _instance: Optional["ConfigHub"] = None
    _lock = threading.Lock()
    _initialized: bool = False

    def __new__(cls) -> "ConfigHub":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        # 避免重复初始化
        if hasattr(self, "_config"):
            return

        self._config: Optional[AppConfig] = None
        self._novel_presets: Dict[str, NovelConfig] = {}

    def initialize(self) -> "ConfigHub":
        """初始化配置中心

        加载 AppConfig（从环境变量和 .env 文件）。
        幂等操作：多次调用无影响。
        """
        if self._initialized and self._config is not None:
            return self

        with self._lock:
            if self._initialized and self._config is not None:
                return self

            try:
                self._config = get_config()
                self._register_default_presets()
                self._initialized = True
                _logger.agent("ConfigHub initialized successfully")
            except Exception as e:
                _logger.agent_error(f"ConfigHub initialization failed: {e}")
                # 使用默认配置作为fallback
                self._config = AppConfig()
                self._initialized = True

        return self

    def _register_default_presets(self) -> None:
        """注册默认小说配置预设"""
        # 修仙预设
        self._novel_presets["xianxia"] = NovelConfig(
            title="修仙小说",
            genre="xianxia",
            world={
                "world_name": "青云界",
                "power_system": "qi_cultivation",
                "power_system_details": "灵气修炼体系，分为练气、筑基、金丹、元婴、化神...",
            },
            themes=["成长", "逆天改命", "道法自然"],
            tags=["修仙", "东方玄幻"],
            preset_name="xianxia",
        )

        # 武侠预设
        self._novel_presets["wuxia"] = NovelConfig(
            title="武侠小说",
            genre="wuxia",
            world={
                "world_name": "江湖",
                "power_system": "none",
                "power_system_details": "内功、外功、轻功、暗器",
            },
            themes=["侠义", "江湖恩怨", "正邪之争"],
            tags=["武侠", "江湖"],
            preset_name="wuxia",
        )

        # 科幻预设
        self._novel_presets["sci-fi"] = NovelConfig(
            title="科幻小说",
            genre="sci-fi",
            world={
                "world_name": "未来地球",
                "power_system": "technology",
                "technology_level": "星际文明",
            },
            themes=["科技与人性", "未来探索", "文明冲突"],
            tags=["科幻", "未来"],
            preset_name="sci-fi",
        )

        # 言情预设
        self._novel_presets["romance"] = NovelConfig(
            title="言情小说",
            genre="romance",
            world={
                "world_name": "现代都市",
                "power_system": "none",
            },
            themes=["爱情", "成长", "命运"],
            tags=["言情", "现代"],
            preset_name="romance",
        )

    @property
    def config(self) -> AppConfig:
        """获取当前 AppConfig 实例

        Raises:
            RuntimeError: 如果 ConfigHub 尚未初始化
        """
        if self._config is None:
            raise RuntimeError(
                "ConfigHub not initialized. Call initialize() first."
            )
        return self._config

    @property
    def is_initialized(self) -> bool:
        """检查是否已初始化"""
        return self._initialized and self._config is not None

    # ---- 便捷访问方法 ----

    def get(self, key: str, default: Any = None) -> Any:
        """通过点分隔路径获取配置值

        Args:
            key: 配置路径，如 "database.url"、"llm.default_provider"
            default: 默认值

        Returns:
            配置值或默认值

        Example:
            hub.get("database.pool_size")  # -> 10
            hub.get("llm.providers.openai.model")  # -> "gpt-4"
        """
        try:
            parts = key.split(".")
            value: Any = self.config
            for part in parts:
                if hasattr(value, part):
                    value = getattr(value, part)
                elif isinstance(value, dict) and part in value:
                    value = value[part]
                else:
                    return default
            return value
        except Exception:
            return default

    def get_novel_config(self, preset: Optional[str] = None) -> NovelConfig:
        """获取小说配置

        Args:
            preset: 预设名称，如 "xianxia"、"wuxia"
                   为 None 时返回默认空配置

        Returns:
            NovelConfig 实例
        """
        if preset and preset in self._novel_presets:
            return self._novel_presets[preset]
        return NovelConfig(
            title="未命名小说",
            genre="other",
        )

    def get_preset_names(self) -> list:
        """获取所有可用的预设名称"""
        return list(self._novel_presets.keys())

    def add_preset(self, name: str, config: NovelConfig) -> None:
        """添加自定义预设"""
        self._novel_presets[name] = config

    # ---- 热重载 ----

    def reload(self) -> "ConfigHub":
        """热重载配置

        重新从环境变量和 .env 文件加载配置。
        保持单例身份不变。
        """
        with self._lock:
            _logger.agent("ConfigHub reloading configuration...")
            self._config = reload_config()
            # 预设不需要重新注册（它们是代码中定义的）
            _logger.agent("ConfigHub reloaded successfully")
        return self

    def to_safe_dict(self) -> Dict[str, Any]:
        """导出脱敏配置字典（用于日志/监控）"""
        return self.config.to_safe_dict()

    def __repr__(self) -> str:
        if self._config:
            return f"ConfigHub({self._config!r})"
        return "ConfigHub(uninitialized)"


# ---- 便捷函数 ----

_hub_instance: Optional[ConfigHub] = None


def get_config_hub() -> ConfigHub:
    """获取 ConfigHub 实例（已初始化）

    这是推荐的获取方式：自动初始化。
    """
    global _hub_instance
    if _hub_instance is None:
        _hub_instance = ConfigHub()
        _hub_instance.initialize()
    return _hub_instance


def get_novel_config(preset: Optional[str] = None) -> NovelConfig:
    """便捷函数：获取 NovelConfig"""
    return get_config_hub().get_novel_config(preset)
