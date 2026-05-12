"""
配置管理器

@file: config/manager.py
@date: 2026-03-12
@author: AI-Novels Team
@version: 1.0
@description: 配置管理核心类，整合加载、验证和访问
"""

import os
from typing import Any, Dict, List, Optional
from pathlib import Path

from .loader import ConfigLoader, EnvironmentVariableResolver
from .validator import ConfigValidator, SchemaBuilder, AINovelsSchemas
from ai_novels.utils import log_error, log_info, get_logger


class ConfigNotFoundError(Exception):
    """配置文件未找到异常"""
    pass


class ConfigValidationError(Exception):
    """配置验证异常"""
    pass


class ConfigManager:
    """
    配置管理器

    统一管理配置的加载、验证、访问
    """

    # 默认配置文件路径
    DEFAULT_CONFIG_PATHS = [
        "config/config.json",
        "config/config.yaml",
        "config/config.yml"
    ]

    # 环境配置文件路径
    ENV_CONFIG_PATHS = {
        "development": "config/config.dev.json",
        "test": "config/config.test.json",
        "production": "config/config.prod.json"
    }

    def __init__(self, base_dir: str = None, env: str = "development"):
        """
        初始化配置管理器

        Args:
            base_dir: 基础目录
            env: 环境名称 (development, test, production)
        """
        self._base_dir = base_dir or os.getcwd()
        self._env = env
        self._loader = ConfigLoader(self._base_dir)
        self._validator = ConfigValidator()
        self._resolver = EnvironmentVariableResolver(self._loader)
        self._config: Dict[str, Any] = {}
        self._initialized = False

        # 注册内置schema
        self._register_schemas()

    def _register_schemas(self):
        """注册内置schema"""
        self._validator.register_schema("llm", AINovelsSchemas.get_llm_config_schema())
        self._validator.register_schema("database", AINovelsSchemas.get_database_config_schema())
        self._validator.register_schema("agents", AINovelsSchemas.get_agent_config_schema())
        self._validator.register_schema("settings", AINovelsSchemas.get_settings_schema())

    def initialize(self, config_paths: List[str] = None, validate: bool = True) -> bool:
        """
        初始化配置

        Args:
            config_paths: 配置文件路径列表，None则使用默认路径
            validate: 是否验证配置

        Returns:
            是否成功
        """
        try:
            logger = get_logger()

            # 优先从 AppConfig 获取已合并的配置（统一入口）
            try:
                from .app_config import get_config
                app_cfg = get_config()
                raw = getattr(app_cfg, "_raw", None)
                if raw:
                    self._config = raw
                    self._initialized = True
                    if validate:
                        is_valid, errors = self._validator.validate(self._config, AINovelsSchemas.get_settings_schema())
                        if not is_valid:
                            logger.config_error("Config validation failed", errors=errors)
                            raise ConfigValidationError(f"Config validation failed: {errors}")
                    logger.config("Configuration manager initialized from AppConfig")
                    return True
            except Exception:
                pass

            # 降级：直接加载 JSON 文件（旧行为）
            if config_paths is None:
                config_paths = self.DEFAULT_CONFIG_PATHS.copy()

                # 添加环境特定配置
                if self._env in self.ENV_CONFIG_PATHS:
                    config_paths.append(self.ENV_CONFIG_PATHS[self._env])

                # 移除不存在的路径
                config_paths = [p for p in config_paths if os.path.exists(self._loader._resolve_path(p))]

            # 加载并合并配置
            for config_file in config_paths:
                logger.config_loading(config_file)

            self._config = self._loader.load_multiple(config_paths)
            logger.config("All configuration files loaded and merged", count=len(config_paths))

            # 解析环境变量
            self._config = self._resolver.resolve(self._config)
            logger.config("Environment variables resolved")

            # 验证配置
            if validate:
                is_valid, errors = self._validator.validate(self._config, AINovelsSchemas.get_settings_schema())
                if not is_valid:
                    logger.config_error("Config validation failed", errors=errors)
                    raise ConfigValidationError(f"Config validation failed: {errors}")
                logger.config("Config validation passed")

            self._initialized = True
            logger.config("Configuration manager initialized successfully", paths=config_paths)
            return True

        except Exception as e:
            self._initialized = False
            log_error(f"Failed to initialize config: {e}")
            return False

    def reload(self) -> bool:
        """
        重新加载配置

        Returns:
            是否成功
        """
        return self.initialize()

    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置值（支持嵌套路径）

        Args:
            key: 配置键（如 "llm.provider"）
            default: 默认值

        Returns:
            配置值
        """
        keys = key.split(".")
        value = self._config

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def get_required(self, key: str) -> Any:
        """
        获取必需的配置值

        Args:
            key: 配置键

        Returns:
            配置值

        Raises:
            ConfigNotFoundError: 配置不存在
        """
        value = self.get(key)
        if value is None:
            raise ConfigNotFoundError(f"Required config '{key}' not found")
        return value

    def get_llm(self, provider: str = None) -> Dict[str, Any]:
        """
        获取LLM配置

        Args:
            provider: 提供商名称，None则获取默认提供商

        Returns:
            LLM配置字典
        """
        llm_config = self.get("llm", {})
        if provider:
            return llm_config.get(provider, llm_config.get("default", {}))
        return llm_config.get("default", llm_config)

    def get_database(self, name: str) -> Dict[str, Any]:
        """
        获取数据库配置

        Args:
            name: 数据库名称 (mysql, neo4j, mongodb, chromadb)

        Returns:
            数据库配置字典
        """
        return self.get(f"database.{name}", {})

    def get_agent(self, name: str) -> Dict[str, Any]:
        """
        获取Agent配置

        Args:
            name: Agent名称

        Returns:
            Agent配置字典
        """
        agents = self.get("agents", {})
        return agents.get(name, agents.get("default", {}))

    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典

        Returns:
            完整配置字典
        """
        return self._config.copy()

    def to_json(self, indent: int = 2) -> str:
        """
        转换为JSON字符串

        Args:
            indent: 缩进空格数

        Returns:
            JSON字符串
        """
        import json
        return json.dumps(self._config, indent=indent, ensure_ascii=False)

    def save(self, path: str) -> bool:
        """
        保存配置到文件

        Args:
            path: 保存路径

        Returns:
            是否成功
        """
        try:
            import json
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(self._config, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            log_error(f"Failed to save config: {e}")
            return False

    def is_initialized(self) -> bool:
        """
        检查是否已初始化

        Returns:
            是否已初始化
        """
        return self._initialized

    @property
    def config(self) -> Dict[str, Any]:
        """配置字典（只读）"""
        return self._config


class Settings:
    """
    全局设置访问器

    提供便捷的全局配置访问
    """

    _instance: Optional['Settings'] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._manager = None
        return cls._instance

    def initialize(self, config_manager: ConfigManager) -> bool:
        """
        初始化全局设置

        Args:
            config_manager: ConfigManager实例

        Returns:
            是否成功
        """
        self._manager = config_manager
        return config_manager.is_initialized()

    @property
    def language(self) -> Dict[str, Any]:
        """获取语言配置"""
        return self.get("language", {"name": "English", "code": "en-US", "description": "English"})

    @property
    def language_name(self) -> str:
        """获取语言名称"""
        return self.language.get("name", "English")

    @property
    def language_code(self) -> str:
        """获取语言代码"""
        return self.language.get("code", "en-US")

    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值"""
        if self._manager:
            return self._manager.get(key, default)
        return default

    def get_required(self, key: str) -> Any:
        """获取必需配置值"""
        if self._manager:
            return self._manager.get_required(key)
        raise ConfigNotFoundError(f"Required config '{key}' not found - Settings not initialized")

    def _lazy_init(self) -> bool:
        """懒加载 ConfigManager（从 AppConfig 读取）"""
        try:
            config_manager = ConfigManager()
            if config_manager.initialize(validate=False):
                self._manager = config_manager
                return True
        except Exception:
            pass
        return False

    def get_llm(self, provider: str = None) -> Dict[str, Any]:
        """获取LLM配置"""
        if self._manager:
            return self._manager.get_llm(provider)
        self._lazy_init()
        return self._manager.get_llm(provider) if self._manager else {}

    def get_database(self, name: str) -> Dict[str, Any]:
        """获取数据库配置"""
        if not self._manager:
            self._lazy_init()
        return self._manager.get_database(name) if self._manager else {}

    def get_agent(self, name: str) -> Dict[str, Any]:
        """获取Agent配置"""
        if not self._manager:
            self._lazy_init()
        return self._manager.get_agent(name) if self._manager else {}


# 全局设置访问器
settings = Settings()
