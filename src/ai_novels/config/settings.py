"""
全局设置模块

@file: config/settings.py
@date: 2026-03-12
@version: 1.0
@description: 提供全局配置访问
"""

from typing import Optional, Dict, Any
from .manager import ConfigManager, Settings as BaseSettings

# 导出 Settings 类供 config/__init__.py 使用
Settings = BaseSettings

# 全局设置实例
settings: Optional[BaseSettings] = None


def initialize_settings(config_manager: ConfigManager) -> bool:
    """
    初始化全局设置

    Args:
        config_manager: ConfigManager实例

    Returns:
        是否成功
    """
    global settings
    if settings is None:
        settings = BaseSettings()
    return settings.initialize(config_manager)


def get_settings() -> Optional[BaseSettings]:
    """
    获取全局设置实例

    Returns:
        Settings实例
    """
    return settings


def get_config(key: str, default: Any = None) -> Any:
    """
    便捷函数：获取配置值

    Args:
        key: 配置键
        default: 默认值

    Returns:
        配置值
    """
    if settings:
        return settings.get(key, default)
    return default
