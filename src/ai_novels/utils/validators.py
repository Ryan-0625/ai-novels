"""
数据验证工具模块

@file: utils/validators.py
@date: 2026-04-08
@version: 1.0.0
@description: 统一的数据验证工具
"""

import re
from typing import Any, Dict, List, Optional, Callable, Union
from dataclasses import dataclass
from enum import Enum


class ValidationResult:
    """验证结果"""
    
    def __init__(self, is_valid: bool = True, errors: List[str] = None):
        self.is_valid = is_valid
        self.errors = errors or []
    
    def add_error(self, error: str):
        """添加错误信息"""
        self.errors.append(error)
        self.is_valid = False
    
    def merge(self, other: 'ValidationResult'):
        """合并另一个验证结果"""
        if not other.is_valid:
            self.is_valid = False
            self.errors.extend(other.errors)


class FieldValidator:
    """字段验证器"""
    
    @staticmethod
    def required(value: Any, field_name: str = "field") -> ValidationResult:
        """验证必填"""
        result = ValidationResult()
        if value is None or (isinstance(value, str) and not value.strip()):
            result.add_error(f"{field_name} is required")
        return result
    
    @staticmethod
    def string(
        value: Any,
        field_name: str = "field",
        min_length: int = None,
        max_length: int = None,
        pattern: str = None,
        allow_empty: bool = True
    ) -> ValidationResult:
        """验证字符串"""
        result = ValidationResult()
        
        if value is None:
            return result
        
        if not isinstance(value, str):
            result.add_error(f"{field_name} must be a string")
            return result
        
        if not allow_empty and not value.strip():
            result.add_error(f"{field_name} cannot be empty")
        
        if min_length is not None and len(value) < min_length:
            result.add_error(f"{field_name} must be at least {min_length} characters")
        
        if max_length is not None and len(value) > max_length:
            result.add_error(f"{field_name} must be at most {max_length} characters")
        
        if pattern and not re.match(pattern, value):
            result.add_error(f"{field_name} format is invalid")
        
        return result
    
    @staticmethod
    def integer(
        value: Any,
        field_name: str = "field",
        min_value: int = None,
        max_value: int = None
    ) -> ValidationResult:
        """验证整数"""
        result = ValidationResult()
        
        if value is None:
            return result
        
        try:
            num = int(value)
        except (TypeError, ValueError):
            result.add_error(f"{field_name} must be an integer")
            return result
        
        if min_value is not None and num < min_value:
            result.add_error(f"{field_name} must be at least {min_value}")
        
        if max_value is not None and num > max_value:
            result.add_error(f"{field_name} must be at most {max_value}")
        
        return result
    
    @staticmethod
    def float(
        value: Any,
        field_name: str = "field",
        min_value: float = None,
        max_value: float = None
    ) -> ValidationResult:
        """验证浮点数"""
        result = ValidationResult()
        
        if value is None:
            return result
        
        try:
            num = float(value)
        except (TypeError, ValueError):
            result.add_error(f"{field_name} must be a number")
            return result
        
        if min_value is not None and num < min_value:
            result.add_error(f"{field_name} must be at least {min_value}")
        
        if max_value is not None and num > max_value:
            result.add_error(f"{field_name} must be at most {max_value}")
        
        return result
    
    @staticmethod
    def enum(
        value: Any,
        allowed_values: List[Any],
        field_name: str = "field"
    ) -> ValidationResult:
        """验证枚举值"""
        result = ValidationResult()
        
        if value is None:
            return result
        
        if value not in allowed_values:
            result.add_error(
                f"{field_name} must be one of: {', '.join(map(str, allowed_values))}"
            )
        
        return result
    
    @staticmethod
    def list(
        value: Any,
        field_name: str = "field",
        min_items: int = None,
        max_items: int = None,
        item_validator: Callable = None
    ) -> ValidationResult:
        """验证列表"""
        result = ValidationResult()
        
        if value is None:
            return result
        
        if not isinstance(value, list):
            result.add_error(f"{field_name} must be a list")
            return result
        
        if min_items is not None and len(value) < min_items:
            result.add_error(f"{field_name} must have at least {min_items} items")
        
        if max_items is not None and len(value) > max_items:
            result.add_error(f"{field_name} must have at most {max_items} items")
        
        if item_validator:
            for i, item in enumerate(value):
                item_result = item_validator(item, f"{field_name}[{i}]")
                result.merge(item_result)
        
        return result
    
    @staticmethod
    def dict(
        value: Any,
        field_name: str = "field",
        required_keys: List[str] = None,
        schema: Dict[str, Callable] = None
    ) -> ValidationResult:
        """验证字典"""
        result = ValidationResult()
        
        if value is None:
            return result
        
        if not isinstance(value, dict):
            result.add_error(f"{field_name} must be an object")
            return result
        
        if required_keys:
            for key in required_keys:
                if key not in value:
                    result.add_error(f"{field_name}.{key} is required")
        
        if schema:
            for key, validator in schema.items():
                if key in value:
                    field_result = validator(value[key], f"{field_name}.{key}")
                    result.merge(field_result)
        
        return result


class SchemaValidator:
    """模式验证器"""
    
    def __init__(self, schema: Dict[str, Callable]):
        """
        初始化
        
        Args:
            schema: 验证模式 {字段名: 验证函数}
        """
        self.schema = schema
    
    def validate(self, data: Dict[str, Any]) -> ValidationResult:
        """
        验证数据
        
        Args:
            data: 待验证数据
            
        Returns:
            验证结果
        """
        result = ValidationResult()
        
        for field_name, validator in self.schema.items():
            value = data.get(field_name)
            field_result = validator(value, field_name)
            result.merge(field_result)
        
        return result


# 预定义的验证模式
class CommonSchemas:
    """常用验证模式"""
    
    @staticmethod
    def task_request() -> SchemaValidator:
        """任务请求验证"""
        return SchemaValidator({
            "prompt": lambda v, n: FieldValidator.string(v, n, min_length=1, max_length=10000),
            "genre": lambda v, n: FieldValidator.string(v, n, max_length=50),
            "style": lambda v, n: FieldValidator.string(v, n, max_length=50),
            "chapters": lambda v, n: FieldValidator.integer(v, n, min_value=1, max_value=1000),
            "words_per_chapter": lambda v, n: FieldValidator.integer(v, n, min_value=100, max_value=100000)
        })
    
    @staticmethod
    def agent_config() -> SchemaValidator:
        """Agent配置验证"""
        return SchemaValidator({
            "name": lambda v, n: FieldValidator.required(v, n),
            "provider": lambda v, n: FieldValidator.enum(v, ["ollama", "openai", "qwen", "gemini"], n),
            "model": lambda v, n: FieldValidator.string(v, n, min_length=1),
            "temperature": lambda v, n: FieldValidator.float(v, n, min_value=0, max_value=2),
            "max_tokens": lambda v, n: FieldValidator.integer(v, n, min_value=1, max_value=100000)
        })
    
    @staticmethod
    def database_config() -> SchemaValidator:
        """数据库配置验证"""
        return SchemaValidator({
            "host": lambda v, n: FieldValidator.string(v, n, min_length=1),
            "port": lambda v, n: FieldValidator.integer(v, n, min_value=1, max_value=65535),
            "database": lambda v, n: FieldValidator.string(v, n, min_length=1),
            "user": lambda v, n: FieldValidator.string(v, n, min_length=1)
        })


# 便捷函数
def validate_task_request(data: Dict[str, Any]) -> ValidationResult:
    """验证任务请求"""
    return CommonSchemas.task_request().validate(data)


def validate_agent_config(data: Dict[str, Any]) -> ValidationResult:
    """验证Agent配置"""
    return CommonSchemas.agent_config().validate(data)


def validate_database_config(data: Dict[str, Any]) -> ValidationResult:
    """验证数据库配置"""
    return CommonSchemas.database_config().validate(data)
