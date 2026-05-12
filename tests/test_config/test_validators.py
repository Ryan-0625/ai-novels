"""
验证器模块测试

@file: tests/test_validators.py
@date: 2026-04-08
@version: 1.0.0
"""

import pytest
from ai_novels.utils.validators import (
    FieldValidator,
    SchemaValidator,
    ValidationResult,
    CommonSchemas,
    validate_task_request,
    validate_agent_config
)


class TestValidationResult:
    """验证结果测试"""
    
    def test_default_valid(self):
        """测试默认有效"""
        result = ValidationResult()
        assert result.is_valid is True
        assert result.errors == []
    
    def test_add_error(self):
        """测试添加错误"""
        result = ValidationResult()
        result.add_error("Field is required")
        
        assert result.is_valid is False
        assert "Field is required" in result.errors
    
    def test_merge_results(self):
        """测试合并结果"""
        result1 = ValidationResult()
        result1.add_error("Error 1")
        
        result2 = ValidationResult()
        result2.add_error("Error 2")
        
        result1.merge(result2)
        
        assert result1.is_valid is False
        assert len(result1.errors) == 2


class TestFieldValidator:
    """字段验证器测试"""
    
    def test_required_with_value(self):
        """测试必填-有值"""
        result = FieldValidator.required("test", "name")
        assert result.is_valid is True
    
    def test_required_with_none(self):
        """测试必填-None值"""
        result = FieldValidator.required(None, "name")
        assert result.is_valid is False
        assert "name is required" in result.errors
    
    def test_required_with_empty_string(self):
        """测试必填-空字符串"""
        result = FieldValidator.required("   ", "name")
        assert result.is_valid is False
    
    def test_string_valid(self):
        """测试字符串-有效"""
        result = FieldValidator.string("test", "name")
        assert result.is_valid is True
    
    def test_string_min_length(self):
        """测试字符串-最小长度"""
        result = FieldValidator.string("ab", "name", min_length=3)
        assert result.is_valid is False
        assert "at least 3 characters" in result.errors[0]
    
    def test_string_max_length(self):
        """测试字符串-最大长度"""
        result = FieldValidator.string("abcdef", "name", max_length=5)
        assert result.is_valid is False
        assert "at most 5 characters" in result.errors[0]
    
    def test_string_pattern(self):
        """测试字符串-模式匹配"""
        result = FieldValidator.string("test123", "name", pattern=r"^[a-z]+$")
        assert result.is_valid is False
        assert "format is invalid" in result.errors[0]
    
    def test_integer_valid(self):
        """测试整数-有效"""
        result = FieldValidator.integer(42, "age")
        assert result.is_valid is True
    
    def test_integer_invalid_type(self):
        """测试整数-无效类型"""
        result = FieldValidator.integer("abc", "age")
        assert result.is_valid is False
        assert "must be an integer" in result.errors[0]
    
    def test_integer_min_value(self):
        """测试整数-最小值"""
        result = FieldValidator.integer(5, "age", min_value=18)
        assert result.is_valid is False
        assert "at least 18" in result.errors[0]
    
    def test_integer_max_value(self):
        """测试整数-最大值"""
        result = FieldValidator.integer(150, "age", max_value=120)
        assert result.is_valid is False
        assert "at most 120" in result.errors[0]
    
    def test_float_valid(self):
        """测试浮点数-有效"""
        result = FieldValidator.float(3.14, "price")
        assert result.is_valid is True
    
    def test_float_range(self):
        """测试浮点数-范围"""
        result = FieldValidator.float(1.5, "ratio", min_value=0.0, max_value=1.0)
        assert result.is_valid is False
    
    def test_enum_valid(self):
        """测试枚举-有效"""
        result = FieldValidator.enum("active", ["active", "inactive"], "status")
        assert result.is_valid is True
    
    def test_enum_invalid(self):
        """测试枚举-无效"""
        result = FieldValidator.enum("deleted", ["active", "inactive"], "status")
        assert result.is_valid is False
        assert "must be one of" in result.errors[0]
    
    def test_list_valid(self):
        """测试列表-有效"""
        result = FieldValidator.list([1, 2, 3], "items", min_items=1, max_items=5)
        assert result.is_valid is True
    
    def test_list_min_items(self):
        """测试列表-最小项数"""
        result = FieldValidator.list([], "items", min_items=1)
        assert result.is_valid is False
        assert "at least 1 items" in result.errors[0]
    
    def test_list_max_items(self):
        """测试列表-最大项数"""
        result = FieldValidator.list([1, 2, 3], "items", max_items=2)
        assert result.is_valid is False
    
    def test_dict_valid(self):
        """测试字典-有效"""
        result = FieldValidator.dict(
            {"name": "test", "age": 25},
            "user",
            required_keys=["name"]
        )
        assert result.is_valid is True
    
    def test_dict_missing_required(self):
        """测试字典-缺少必填项"""
        result = FieldValidator.dict(
            {"age": 25},
            "user",
            required_keys=["name"]
        )
        assert result.is_valid is False
        assert "name is required" in result.errors[0]


class TestSchemaValidator:
    """模式验证器测试"""
    
    def test_validate_valid_data(self):
        """测试验证有效数据"""
        schema = SchemaValidator({
            "name": lambda v, n: FieldValidator.string(v, n, min_length=1),
            "age": lambda v, n: FieldValidator.integer(v, n, min_value=0)
        })
        
        result = schema.validate({"name": "John", "age": 25})
        assert result.is_valid is True
    
    def test_validate_invalid_data(self):
        """测试验证无效数据"""
        schema = SchemaValidator({
            "name": lambda v, n: FieldValidator.string(v, n, min_length=3),
            "age": lambda v, n: FieldValidator.integer(v, n, min_value=18)
        })
        
        result = schema.validate({"name": "Jo", "age": 16})
        assert result.is_valid is False
        assert len(result.errors) == 2


class TestCommonSchemas:
    """常用模式测试"""
    
    def test_task_request_valid(self):
        """测试任务请求-有效"""
        data = {
            "prompt": "Write a story",
            "genre": "fantasy",
            "chapters": 10,
            "words_per_chapter": 3000
        }
        result = validate_task_request(data)
        assert result.is_valid is True
    
    def test_task_request_invalid_prompt(self):
        """测试任务请求-无效prompt"""
        data = {"prompt": "", "chapters": 10}
        result = validate_task_request(data)
        assert result.is_valid is False
    
    def test_task_request_invalid_chapters(self):
        """测试任务请求-无效chapters"""
        data = {"prompt": "Test", "chapters": 0}
        result = validate_task_request(data)
        assert result.is_valid is False
    
    def test_agent_config_valid(self):
        """测试Agent配置-有效"""
        data = {
            "name": "test_agent",
            "provider": "ollama",
            "model": "qwen2.5-14b",
            "temperature": 0.7,
            "max_tokens": 8192
        }
        result = validate_agent_config(data)
        assert result.is_valid is True
    
    def test_agent_config_invalid_provider(self):
        """测试Agent配置-无效provider"""
        data = {
            "name": "test_agent",
            "provider": "invalid",
            "model": "test"
        }
        result = validate_agent_config(data)
        assert result.is_valid is False
    
    def test_agent_config_invalid_temperature(self):
        """测试Agent配置-无效temperature"""
        data = {
            "name": "test_agent",
            "provider": "ollama",
            "model": "test",
            "temperature": 3.0
        }
        result = validate_agent_config(data)
        assert result.is_valid is False
