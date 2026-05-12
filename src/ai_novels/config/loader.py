"""
配置加载器

@file: config/loader.py
@date: 2026-03-12
@author: AI-Novels Team
@version: 1.0
@description: 配置文件加载与解析
"""

import json
import os
from typing import Any, Dict, List, Optional
from pathlib import Path
import yaml

from ai_novels.utils import log_warn


class ConfigLoader:
    """
    配置加载器

    支持多种配置格式:
    - JSON
    - YAML/YML
    - Python字典

    功能:
    - 单文件加载
    - 多配置合并
    - 环境变量替换
    - 默认值覆盖
    """

    def __init__(self, base_dir: str = None):
        """
        初始化配置加载器

        Args:
            base_dir: 基础目录路径
        """
        self._base_dir = base_dir or os.getcwd()

    def load(self, config_path: str) -> Dict[str, Any]:
        """
        加载单个配置文件

        Args:
            config_path: 配置文件路径

        Returns:
            配置字典

        Raises:
            FileNotFoundError: 文件不存在
            ValueError: 格式不支持或解析错误
        """
        full_path = self._resolve_path(config_path)

        if not os.path.exists(full_path):
            raise FileNotFoundError(f"Config file not found: {full_path}")

        ext = os.path.splitext(full_path)[1].lower()

        with open(full_path, 'r', encoding='utf-8') as f:
            content = f.read()

        try:
            if ext in ['.json']:
                return self._load_json(content)
            elif ext in ['.yaml', '.yml']:
                return self._load_yaml(content)
            else:
                # 尝试JSON，失败则尝试YAML
                try:
                    return self._load_json(content)
                except json.JSONDecodeError:
                    return self._load_yaml(content)
        except Exception as e:
            raise ValueError(f"Failed to parse config file {full_path}: {str(e)}")

    def load_multiple(self, paths: List[str]) -> Dict[str, Any]:
        """
        加载多个配置文件并合并

        后面的配置会覆盖前面的配置

        Args:
            paths: 配置文件路径列表

        Returns:
            合并后的配置字典
        """
        result = {}

        for path in paths:
            try:
                config = self.load(path)
                result = self._deep_merge(result, config)
            except FileNotFoundError:
                # 忽略不存在的文件
                continue
            except Exception as e:
                log_warn(f"Failed to load {path}: {e}")

        return result

    def load_from_dict(self, config_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        从字典加载配置（用于测试）

        Args:
            config_dict: 配置字典

        Returns:
            配置字典
        """
        return config_dict.copy()

    def _resolve_path(self, path: str) -> str:
        """
        解析路径

        Args:
            path: 相对或绝对路径

        Returns:
            绝对路径
        """
        if os.path.isabs(path):
            return path
        return os.path.join(self._base_dir, path)

    def _load_json(self, content: str) -> Dict[str, Any]:
        """
        加载JSON格式配置

        Args:
            content: JSON字符串

        Returns:
            配置字典
        """
        return json.loads(content)

    def _load_yaml(self, content: str) -> Dict[str, Any]:
        """
        加载YAML格式配置

        Args:
            content: YAML字符串

        Returns:
            配置字典
        """
        try:
            return yaml.safe_load(content)
        except yaml.YAMLError as e:
            raise ValueError(f"YAML parse error: {str(e)}")

    def _deep_merge(self, base: Dict[str, Any], overlay: Dict[str, Any]) -> Dict[str, Any]:
        """
        深度合并两个字典，overlay优先级更高

        Args:
            base: 基础字典
            overlay: 覆盖字典

        Returns:
            合并后的字典
        """
        result = base.copy()

        for key, value in overlay.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value

        return result


class EnvironmentVariableResolver:
    """
    环境变量解析器

    在配置中使用 ${VARIABLE_NAME} 或 $VARIABLE_NAME 格式引用环境变量
    """

    def __init__(self, loader: ConfigLoader = None):
        """
        初始化解析器

        Args:
            loader: ConfigLoader实例
        """
        self._loader = loader or ConfigLoader()

    def resolve(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        解析配置中的环境变量引用

        Args:
            config: 配置字典

        Returns:
            替换环境变量后的配置字典
        """
        return self._process_value(config)

    def _process_value(self, value: Any) -> Any:
        """
        处理单个值中的环境变量

        Args:
            value: 值（可以是任意类型）

        Returns:
            替换后的值
        """
        if isinstance(value, str):
            return self._replace_env_vars(value)
        elif isinstance(value, dict):
            return {k: self._process_value(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [self._process_value(item) for item in value]
        else:
            return value

    def _replace_env_vars(self, text: str) -> str:
        """
        替换字符串中的环境变量

        支持格式:
        - ${VARIABLE_NAME} - 推荐格式
        - $VARIABLE_NAME - 简单格式

        Args:
            text: 原始字符串

        Returns:
            替换后的字符串
        """
        import re

        # 替换 ${VARIABLE_NAME} 格式
        pattern1 = r'\$\{([^}]+)\}'

        def replace1(match):
            var_name = match.group(1)
            return os.environ.get(var_name, match.group(0))

        result = re.sub(pattern1, replace1, text)

        # 替换 $VARIABLE_NAME 格式（不跟随字母数字下划线）
        pattern2 = r'\$([A-Za-z_][A-Za-z0-9_]*)\b'

        def replace2(match):
            var_name = match.group(1)
            return os.environ.get(var_name, match.group(0))

        result = re.sub(pattern2, replace2, result)

        return result


# 全局函数
def load_config(config_path: str, base_dir: str = None) -> Dict[str, Any]:
    """
    加载配置文件（全局函数）

    Args:
        config_path: 配置文件路径
        base_dir: 基础目录

    Returns:
        配置字典
    """
    loader = ConfigLoader(base_dir)
    return loader.load(config_path)


def load_configs(config_paths: List[str], base_dir: str = None) -> Dict[str, Any]:
    """
    加载多个配置文件并合并（全局函数）

    Args:
        config_paths: 配置文件路径列表
        base_dir: 基础目录

    Returns:
        合并后的配置字典
    """
    loader = ConfigLoader(base_dir)
    return loader.load_multiple(config_paths)
