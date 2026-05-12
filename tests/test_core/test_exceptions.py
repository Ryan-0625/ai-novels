"""
异常处理模块测试

@file: tests/test_exceptions.py
@date: 2026-04-08
@version: 1.0.0
"""

import pytest
from ai_novels.core.exceptions import (
    AINovelsException,
    ConfigException,
    AgentException,
    LLMException,
    DatabaseException,
    TaskException,
    ValidationException,
    ErrorCode,
    raise_config_error,
    raise_agent_error,
    raise_llm_error
)


class TestExceptions:
    """异常类测试"""
    
    def test_base_exception_creation(self):
        """测试基础异常创建"""
        exc = AINovelsException("Test error", ErrorCode.SYSTEM_ERROR, {"detail": "test"})
        
        assert exc.message == "Test error"
        assert exc.code == ErrorCode.SYSTEM_ERROR
        assert exc.details == {"detail": "test"}
        assert str(exc) == "[SYSTEM_ERROR] Test error"
    
    def test_exception_to_dict(self):
        """测试异常转字典"""
        exc = AINovelsException("Test error", ErrorCode.AGENT_ERROR, {"agent": "test"})
        result = exc.to_dict()
        
        assert result["error"] is True
        assert result["code"] == 2000
        assert result["code_name"] == "AGENT_ERROR"
        assert result["message"] == "Test error"
        assert result["details"] == {"agent": "test"}
    
    def test_exception_with_cause(self):
        """测试带原因的异常"""
        cause = ValueError("Original error")
        exc = AINovelsException("Wrapped error", ErrorCode.SYSTEM_ERROR, cause=cause)
        
        assert "Original error" in str(exc)
    
    def test_config_exception(self):
        """测试配置异常"""
        exc = ConfigException("Config error", ErrorCode.CONFIGURATION_ERROR)
        
        assert exc.code == ErrorCode.CONFIGURATION_ERROR
        assert "Config error" in str(exc)
    
    def test_agent_exception(self):
        """测试Agent异常"""
        exc = AgentException("Agent failed", ErrorCode.AGENT_EXECUTION_ERROR)
        
        assert exc.code == ErrorCode.AGENT_EXECUTION_ERROR
    
    def test_llm_exception(self):
        """测试LLM异常"""
        exc = LLMException("LLM error", ErrorCode.LLM_RATE_LIMIT)
        
        assert exc.code == ErrorCode.LLM_RATE_LIMIT


class TestExceptionHelpers:
    """异常辅助函数测试"""
    
    def test_raise_config_error(self):
        """测试抛出配置错误"""
        with pytest.raises(ConfigException) as exc_info:
            raise_config_error("Invalid config", {"field": "name"})
        
        assert exc_info.value.message == "Invalid config"
        assert exc_info.value.details == {"field": "name"}
    
    def test_raise_agent_error(self):
        """测试抛出Agent错误"""
        with pytest.raises(AgentException) as exc_info:
            raise_agent_error("Agent timeout", ErrorCode.AGENT_TIMEOUT)
        
        assert exc_info.value.code == ErrorCode.AGENT_TIMEOUT
    
    def test_raise_llm_error(self):
        """测试抛出LLM错误"""
        with pytest.raises(LLMException) as exc_info:
            raise_llm_error("Rate limited", ErrorCode.LLM_RATE_LIMIT)
        
        assert exc_info.value.code == ErrorCode.LLM_RATE_LIMIT


class TestErrorCodes:
    """错误码测试"""
    
    def test_error_code_values(self):
        """测试错误码值"""
        assert ErrorCode.SYSTEM_ERROR.value == 1000
        assert ErrorCode.AGENT_ERROR.value == 2000
        assert ErrorCode.LLM_ERROR.value == 3000
        assert ErrorCode.DATABASE_ERROR.value == 4000
        assert ErrorCode.TASK_ERROR.value == 5000
    
    def test_error_code_categories(self):
        """测试错误码分类"""
        # 系统级错误
        assert 1000 <= ErrorCode.SYSTEM_ERROR.value < 2000
        
        # Agent错误
        assert 2000 <= ErrorCode.AGENT_ERROR.value < 3000
        
        # LLM错误
        assert 3000 <= ErrorCode.LLM_ERROR.value < 4000
