"""
配置验证器

@file: config/validator.py
@date: 2026-03-12
@author: AI-Novels Team
@version: 1.0
@description: 配置合法性验证
"""

import json
import os
from typing import Any, Dict, List, Optional
from jsonschema import validate, ValidationError, Draft7Validator
import yaml

from ai_novels.utils import log_error


class ConfigValidator:
    """
    配置验证器

    使用JSON Schema进行配置验证
    """

    def __init__(self):
        """
        初始化验证器
        """
        self._schemas: Dict[str, Dict[str, Any]] = {}

    def register_schema(self, name: str, schema: Dict[str, Any]) -> bool:
        """
        注册配置schema

        Args:
            name: schema名称
            schema: JSON Schema定义

        Returns:
            是否成功
        """
        try:
            Draft7Validator.check_schema(schema)
            self._schemas[name] = schema
            return True
        except Exception as e:
            log_error(f"Failed to register schema '{name}': {e}")
            return False

    def validate(self, config: Dict[str, Any], schema: Dict[str, Any]) -> tuple[bool, List[str]]:
        """
        验证配置是否符合schema

        Args:
            config: 配置字典
            schema: JSON Schema定义

        Returns:
            (是否有效, 错误信息列表)
        """
        errors = []

        try:
            validate(instance=config, schema=schema)
            return True, []
        except ValidationError as e:
            errors.append(self._format_error(e))
            return False, errors

    def validate_named(self, config: Dict[str, Any], schema_name: str) -> tuple[bool, List[str]]:
        """
        使用已注册的schema验证配置

        Args:
            config: 配置字典
            schema_name: schema名称

        Returns:
            (是否有效, 错误信息列表)
        """
        if schema_name not in self._schemas:
            return False, [f"Schema '{schema_name}' not found"]

        return self.validate(config, self._schemas[schema_name])

    def validate_file(self, config_path: str, schema: Dict[str, Any]) -> tuple[bool, List[str]]:
        """
        从文件验证配置

        Args:
            config_path: 配置文件路径
            schema: JSON Schema定义

        Returns:
            (是否有效, 错误信息列表)
        """
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            return self.validate(config, schema)
        except Exception as e:
            return False, [str(e)]

    def _format_error(self, error: ValidationError) -> str:
        """
        格式化验证错误信息

        Args:
            error: ValidationError对象

        Returns:
            格式化后的错误信息
        """
        path = ".".join([str(p) for p in error.path])
        return f"{'[ROOT]' if not path else path}: {error.message}"


class SchemaBuilder:
    """
    JSON Schema构建器

    提供链式调用构建schema
    """

    def __init__(self):
        """
        初始化构建器
        """
        self._schema: Dict[str, Any] = {}

    def object(self) -> 'SchemaBuilder':
        """设置类型为object"""
        self._schema = {"type": "object", "properties": {}, "required": []}
        return self

    def string(self, **kwargs) -> 'SchemaBuilder':
        """设置类型为string"""
        self._schema = {"type": "string", **kwargs}
        return self

    def integer(self, **kwargs) -> 'SchemaBuilder':
        """设置类型为integer"""
        self._schema = {"type": "integer", **kwargs}
        return self

    def number(self, **kwargs) -> 'SchemaBuilder':
        """设置类型为number"""
        self._schema = {"type": "number", **kwargs}
        return self

    def boolean(self, **kwargs) -> 'SchemaBuilder':
        """设置类型为boolean"""
        self._schema = {"type": "boolean", **kwargs}
        return self

    def array(self, **kwargs) -> 'SchemaBuilder':
        """设置类型为array"""
        self._schema = {"type": "array", **kwargs}
        return self

    def anyOf(self, schemas: List[Dict[str, Any]]) -> 'SchemaBuilder':
        """设置为anyOf类型"""
        self._schema = {"anyOf": schemas}
        return self

    def add_property(self, name: str, schema: Dict[str, Any], required: bool = False) -> 'SchemaBuilder':
        """
        添加属性

        Args:
            name: 属性名
            schema: 属性schema
            required: 是否必填

        Returns:
            self
        """
        if "properties" not in self._schema:
            self._schema["properties"] = {}

        self._schema["properties"][name] = schema

        if required:
            if "required" not in self._schema:
                self._schema["required"] = []
            if name not in self._schema["required"]:
                self._schema["required"].append(name)

        return self

    def add_nested(self, name: str, builder: 'SchemaBuilder', required: bool = False) -> 'SchemaBuilder':
        """
        添加嵌套对象

        Args:
            name: 属性名
            builder: 子SchemaBuilder
            required: 是否必填

        Returns:
            self
        """
        return self.add_property(name, builder.build(), required)

    def build(self) -> Dict[str, Any]:
        """
        构建schema

        Returns:
            JSON Schema字典
        """
        return self._schema.copy()


# AI-Novels内置Schema定义
class AINovelsSchemas:
    """AI-Novels内置schema定义"""

    @staticmethod
    def get_llm_config_schema() -> Dict[str, Any]:
        """获取LLM配置schema"""
        return {
            "type": "object",
            "properties": {
                "provider": {
                    "type": "string",
                    "enum": ["openai", "ollama", "qwen", "gemini", "minimax"]
                },
                "api_key": {
                    "type": "string"
                },
                "base_url": {
                    "type": "string"
                },
                "model": {
                    "type": "string"
                },
                "temperature": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 2
                },
                "max_tokens": {
                    "type": "integer",
                    "minimum": 1
                }
            },
            "required": ["provider", "model"]
        }

    @staticmethod
    def get_database_config_schema() -> Dict[str, Any]:
        """获取数据库配置schema"""
        return {
            "type": "object",
            "properties": {
                "mysql": {
                    "type": "object",
                    "properties": {
                        "host": {"type": "string"},
                        "port": {"type": "integer"},
                        "user": {"type": "string"},
                        "password": {"type": "string"},
                        "database": {"type": "string"}
                    },
                    "required": ["host", "user", "password", "database"]
                },
                "neo4j": {
                    "type": "object",
                    "properties": {
                        "uri": {"type": "string"},
                        "user": {"type": "string"},
                        "password": {"type": "string"}
                    },
                    "required": ["uri", "user", "password"]
                },
                "mongodb": {
                    "type": "object",
                    "properties": {
                        "host": {"type": "string"},
                        "port": {"type": "integer"},
                        "user": {"type": "string"},
                        "password": {"type": "string"},
                        "database": {"type": "string"}
                    },
                    "required": ["host", "database"]
                },
                "chromadb": {
                    "type": "object",
                    "properties": {
                        "host": {"type": "string"},
                        "port": {"type": "integer"},
                        "path": {"type": "string"}
                    }
                }
            },
            "required": ["mysql", "neo4j", "mongodb", "chromadb"]
        }

    @staticmethod
    def get_agent_config_schema() -> Dict[str, Any]:
        """获取agent配置schema"""
        return {
            "type": "object",
            "properties": {
                "coordinator": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "description": {"type": "string"},
                        "provider": {"type": "string"},
                        "model": {"type": "string"}
                    }
                },
                "task_manager": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "description": {"type": "string"},
                        "provider": {"type": "string"},
                        "model": {"type": "string"}
                    }
                },
                "content_generator": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "description": {"type": "string"},
                        "provider": {"type": "string"},
                        "model": {"type": "string"}
                    }
                },
                "quality_checker": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "description": {"type": "string"},
                        "provider": {"type": "string"},
                        "model": {"type": "string"}
                    }
                },
                "default_model": {"type": "string"}
            },
            "required": ["coordinator", "content_generator", "quality_checker"]
        }

    @staticmethod
    def get_settings_schema() -> Dict[str, Any]:
        """获取完整settings配置schema"""
        return {
            "type": "object",
            "properties": {
                "llm": AINovelsSchemas.get_llm_config_schema(),
                "database": AINovelsSchemas.get_database_config_schema(),
                "agents": AINovelsSchemas.get_agent_config_schema(),
                "generation": {
                    "type": "object",
                    "properties": {
                        "output_dir": {"type": "string"},
                        "default_word_count": {"type": "integer"},
                        "max_retries": {"type": "integer"}
                    },
                    "required": ["output_dir"]
                },
                "messaging": {
                    "type": "object",
                    "properties": {
                        "rocketmq": {
                            "type": "object",
                            "properties": {
                                "name_server": {"type": "string"},
                                "producer_group": {"type": "string"},
                                "consumer_group": {"type": "string"}
                            },
                            "required": ["name_server"]
                        }
                    },
                    "required": ["rocketmq"]
                }
            },
            "required": ["llm", "database", "agents", "generation", "messaging"]
        }
