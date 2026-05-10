"""
配置模块初始化

@file: config/__init__.py
@date: 2026-04-29
@author: AI-Novels Team
@version: 2.0
@description: 导出配置模块的公共接口
"""

# 新版配置系统（推荐）
from .app_config import AppConfig, get_config, reload_config
from .hub import ConfigHub, get_config_hub, get_novel_config
from .novel_config import NovelConfig

# 旧版兼容（deprecated，将在 Phase 5 移除）
from .loader import ConfigLoader
from .manager import ConfigManager
from .settings import Settings
from .validator import ConfigValidator

__all__ = [
    # 新版
    'AppConfig',
    'ConfigHub',
    'NovelConfig',
    'get_config',
    'get_config_hub',
    'get_novel_config',
    'reload_config',
    # 旧版兼容
    'ConfigLoader',
    'ConfigValidator',
    'ConfigManager',
    'Settings',
]
