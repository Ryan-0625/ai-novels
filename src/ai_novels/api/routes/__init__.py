"""
API路由模块

Step 11: API网关层重构
按领域拆分的API路由模块

@file: api/routes/__init__.py
@date: 2026-04-29
"""

from .task_routes import router as task_router
from .agent_routes import router as agent_router
from .config_routes import router as config_router

__all__ = ["task_router", "agent_router", "config_router"]
