"""
配置加载与验证工具函数

@file: utils/config_loader.py
@date: 2026-03-13
@version: 1.0.0
@description: 配置文件加载、验证与合并
"""

import json
import os
from typing import Any, Dict, List, Optional
from pathlib import Path


def load_config(config_path: str) -> Dict[str, Any]:
    """
    加载JSON配置文件

    Args:
        config_path: 配置文件路径

    Returns:
        配置字典
    """
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def validate_config(config: Dict[str, Any], schema: Dict[str, Any]) -> bool:
    """
    验证配置合法性

    Args:
        config: 配置字典
        schema: JSON Schema校验规则

    Returns:
        是否合法
    """
    required_fields = schema.get('required', [])

    for field in required_fields:
        if field not in config:
            return False

    # 类型验证
    properties = schema.get('properties', {})
    for key, value in config.items():
        if key in properties:
            prop_type = properties[key].get('type')
            if prop_type == 'string' and not isinstance(value, str):
                return False
            elif prop_type == 'number' and not isinstance(value, (int, float)):
                return False
            elif prop_type == 'boolean' and not isinstance(value, bool):
                return False
            elif prop_type == 'object' and not isinstance(value, dict):
                return False
            elif prop_type == 'array' and not isinstance(value, list):
                return False

    return True


def load_nested_config(base_path: str, overlay_paths: List[str] = None) -> Dict[str, Any]:
    """
    多配置文件深度合并

    Args:
        base_path: 基础配置路径
        overlay_paths: 覆盖配置路径列表（按优先级排序，后加载的覆盖先加载的）

    Returns:
        合并后的配置字典
    """
    # 加载基础配置
    config = load_config(base_path)

    # 如果没有覆盖配置，直接返回
    if not overlay_paths:
        return config

    # 依次加载覆盖配置
    for overlay_path in overlay_paths:
        if os.path.exists(overlay_path):
            overlay_config = load_config(overlay_path)
            config = merge_nested_dict(config, overlay_config)

    return config


def merge_nested_dict(base: Dict[str, Any], overlay: Dict[str, Any]) -> Dict[str, Any]:
    """
    深度合并字典

    Args:
        base: 基础字典
        overlay: 覆盖字典

    Returns:
        合并后的字典
    """
    result = base.copy()

    for key, value in overlay.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_nested_dict(result[key], value)
        else:
            result[key] = value

    return result


def deep_merge(base: Dict[str, Any], overlay: Dict[str, Any],
               override_lists: bool = True) -> Dict[str, Any]:
    """
    深度合并两个字典，支持列表合并

    Args:
        base: 基础字典
        overlay: 覆盖字典
        override_lists: 是否覆盖列表（True：完全替换；False：合并列表）

    Returns:
        合并后的字典
    """
    result = base.copy()

    for key, value in overlay.items():
        if key not in result:
            result[key] = value
        elif isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value, override_lists)
        elif isinstance(result[key], list) and isinstance(value, list):
            if override_lists:
                result[key] = value
            else:
                result[key] = result[key] + value
        else:
            result[key] = value

    return result


def get_nested_value(data: Dict[str, Any], path: str, default: Any = None) -> Any:
    """
    获取嵌套字典的值

    Args:
        data: 字典
        path: 路径，如 "database.mysql.host"
        default: 默认值

    Returns:
        值或默认值
    """
    keys = path.split('.')
    current = data

    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return default

    return current


def set_nested_value(data: Dict[str, Any], path: str, value: Any) -> Dict[str, Any]:
    """
    设置嵌套字典的值

    Args:
        data: 字典
        path: 路径，如 "database.mysql.host"
        value: 值

    Returns:
        修改后的字典
    """
    keys = path.split('.')
    current = data

    for key in keys[:-1]:
        if key not in current:
            current[key] = {}
        current = current[key]

    current[keys[-1]] = value
    return data


def normalize_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    规范化配置，转换为标准格式

    Args:
        config: 原始配置

    Returns:
        规范化后的配置
    """
    normalized = {}

    for key, value in config.items():
        # 转换为小写下划线格式
        norm_key = key.lower().replace('-', '_')

        if isinstance(value, dict):
            normalized[norm_key] = normalize_config(value)
        elif isinstance(value, list):
            normalized[norm_key] = [
                item.lower().replace('-', '_') if isinstance(item, str) else item
                for item in value
            ]
        else:
            normalized[norm_key] = value

    return normalized


def expand_env_vars(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    展开配置中的环境变量

    Args:
        config: 配置字典

    Returns:
        展开环境变量后的配置
    """
    import re

    result = {}

    for key, value in config.items():
        if isinstance(value, str):
            # 查找${ENV_VAR}格式的环境变量
            pattern = r'\$\{([^}]+)\}'
            matches = re.findall(pattern, value)

            if matches:
                expanded = value
                for var in matches:
                    env_value = os.environ.get(var, '')
                    expanded = expanded.replace(f'${{{var}}}', env_value)
                result[key] = expanded
            else:
                result[key] = value
        elif isinstance(value, dict):
            result[key] = expand_env_vars(value)
        elif isinstance(value, list):
            result[key] = [
                expand_env_vars(item) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            result[key] = value

    return result


if __name__ == "__main__":
    # 示例用法
    print("Config loader module loaded successfully!")

    # 测试深合并
    base = {"a": 1, "b": {"c": 2, "d": [1, 2]}}
    overlay = {"b": {"c": 3, "e": 4}, "f": 5}
    merged = deep_merge(base, overlay)
    print(f"Merged config: {merged}")
