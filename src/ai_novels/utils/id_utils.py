"""
ID生成工具函数

@file: utils/id_utils.py
@date: 2026-03-12
@version: 1.0.0
@description: ID生成函数
"""

import uuid
from datetime import datetime


def generate_id(prefix: str = '') -> str:
    """
    生成唯一ID

    Args:
        prefix: ID前缀

    Returns:
        str: 格式化ID字符串
    """
    unique_id = uuid.uuid4().hex[:12]
    if prefix:
        return f'{prefix}_{unique_id}'
    return unique_id


def generate_task_id() -> str:
    """
    生成任务ID

    Returns:
        str: task_xxxx_xxx格式ID
    """
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    unique_id = uuid.uuid4().hex[:8]
    return f'task_{timestamp}_{unique_id}'


def generate_chapter_id(outline_id: str) -> str:
    """
    生成章节ID

    Args:
        outline_id: 关联大纲ID

    Returns:
        str: ch_xxx格式ID
    """
    unique_id = uuid.uuid4().hex[:6]
    return f'ch_{outline_id}_{unique_id}'


def generate_char_id() -> str:
    """
    生成角色ID

    Returns:
        str: char_xxx格式ID
    """
    unique_id = uuid.uuid4().hex[:6]
    return f'char_{unique_id}'


def generate_hook_id() -> str:
    """
    生成钩子ID

    Returns:
        str: hook_xxx格式ID
    """
    unique_id = uuid.uuid4().hex[:6]
    return f'hook_{unique_id}'


def generate_conflict_id() -> str:
    """
    生成冲突ID

    Returns:
        str: conflict_xxx格式ID
    """
    unique_id = uuid.uuid4().hex[:6]
    return f'conflict_{unique_id}'


def generate_entity_id(entity_type: str) -> str:
    """
    生成实体ID

    Args:
        entity_type: 实体类型

    Returns:
        str: type_xxx格式ID
    """
    unique_id = uuid.uuid4().hex[:6]
    return f'{entity_type}_{unique_id}'
