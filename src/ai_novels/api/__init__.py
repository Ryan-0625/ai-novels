"""

API模块初始化

@file: api/__init__.py
@date: 2026-03-12
@version: 2.0
@description: 导出API模块的公共接口
"""

from .main import app

from .controllers import (
    task_controller,
    status_controller,
    config_controller,
    health_controller
)

__all__ = [
    'app',
    'task_controller',
    'status_controller',
    'config_controller',
    'health_controller'
]
