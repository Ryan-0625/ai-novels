"""
API模块初始化

@file: api/__init__.py
@date: 2026-03-12
@version: 1.0
@description: 导出API模块的公共接口
"""

from .main import app
from .legacy_routes import router

# 兼容性导出
api_router = router

from .controllers import (
    task_controller,
    status_controller,
    config_controller,
    health_controller
)

__all__ = [
    'app',
    'api_router',
    'router',
    'task_controller',
    'status_controller',
    'config_controller',
    'health_controller'
]
