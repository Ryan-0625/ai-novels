"""
工具函数模块初始化

@file: utils/__init__.py
@date: 2026-03-12
@version: 1.0.0
@description: 导出工具函数
"""

from .logger import (
    logger,
    log_info,
    log_warn,
    log_error,
    log_debug,
    log_llm_call,
    get_logger,
    HierarchicalLogger,
    LogContext
)

from .health_checker import (
    check_component_health,
    check_system_health,
)

from .id_utils import (
    generate_id,
    generate_task_id,
    generate_chapter_id,
    generate_char_id,
    generate_hook_id,
    generate_conflict_id,
    generate_entity_id
)

__all__ = [
    # Logger
    'logger',
    'log_info',
    'log_warn',
    'log_error',
    'log_debug',
    'log_llm_call',
    'get_logger',
    'HierarchicalLogger',
    'LogContext',
    # Health checker
    'check_component_health',
    'check_system_health',
    # ID Utils
    'generate_id',
    'generate_task_id',
    'generate_chapter_id',
    'generate_char_id',
    'generate_hook_id',
    'generate_conflict_id',
    'generate_entity_id',
]
