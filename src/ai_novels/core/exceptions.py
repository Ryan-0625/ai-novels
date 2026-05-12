"""
统一异常处理模块

@file: core/exceptions.py
@date: 2026-04-08
@version: 1.0.0
@description: 定义项目统一的异常体系和错误处理机制
"""

from typing import Any, Dict, Optional
from enum import Enum


class ErrorCode(Enum):
    """错误码枚举"""
    # 系统级错误 (1000-1999)
    SYSTEM_ERROR = 1000
    INITIALIZATION_ERROR = 1001
    CONFIGURATION_ERROR = 1002
    RESOURCE_NOT_FOUND = 1003
    PERMISSION_DENIED = 1004
    
    # Agent相关错误 (2000-2999)
    AGENT_ERROR = 2000
    AGENT_NOT_FOUND = 2001
    AGENT_INITIALIZATION_FAILED = 2002
    AGENT_EXECUTION_ERROR = 2003
    AGENT_TIMEOUT = 2004
    
    # LLM相关错误 (3000-3999)
    LLM_ERROR = 3000
    LLM_PROVIDER_NOT_FOUND = 3001
    LLM_GENERATION_FAILED = 3002
    LLM_RATE_LIMIT = 3003
    LLM_INVALID_RESPONSE = 3004
    
    # 数据库相关错误 (4000-4999)
    DATABASE_ERROR = 4000
    DATABASE_CONNECTION_FAILED = 4001
    DATABASE_QUERY_ERROR = 4002
    DATABASE_VALIDATION_ERROR = 4003
    
    # 任务相关错误 (5000-5999)
    TASK_ERROR = 5000
    TASK_NOT_FOUND = 5001
    TASK_EXECUTION_FAILED = 5002
    TASK_VALIDATION_ERROR = 5003
    TASK_CANCELLED = 5004
    
    # 消息队列相关错误 (6000-6999)
    MESSAGING_ERROR = 6000
    MESSAGING_CONNECTION_FAILED = 6001
    MESSAGING_PUBLISH_ERROR = 6002
    MESSAGING_CONSUME_ERROR = 6003
    
    # 验证错误 (7000-7999)
    VALIDATION_ERROR = 7000
    INVALID_INPUT = 7001
    MISSING_REQUIRED_FIELD = 7002
    INVALID_FORMAT = 7003


class AINovelsException(Exception):
    """
    项目基础异常类
    
    所有自定义异常都应继承此类
    """
    
    def __init__(
        self,
        message: str,
        code: ErrorCode = ErrorCode.SYSTEM_ERROR,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}
        self.cause = cause
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "error": True,
            "code": self.code.value,
            "code_name": self.code.name,
            "message": self.message,
            "details": self.details
        }
    
    def __str__(self) -> str:
        if self.cause:
            return f"[{self.code.name}] {self.message} (caused by: {self.cause})"
        return f"[{self.code.name}] {self.message}"


class ConfigException(AINovelsException):
    """配置相关异常"""
    
    def __init__(
        self,
        message: str,
        code: ErrorCode = ErrorCode.CONFIGURATION_ERROR,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        super().__init__(message, code, details, cause)


class AgentException(AINovelsException):
    """Agent相关异常"""
    
    def __init__(
        self,
        message: str,
        code: ErrorCode = ErrorCode.AGENT_ERROR,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        super().__init__(message, code, details, cause)


class LLMException(AINovelsException):
    """LLM相关异常"""
    
    def __init__(
        self,
        message: str,
        code: ErrorCode = ErrorCode.LLM_ERROR,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        super().__init__(message, code, details, cause)


class DatabaseException(AINovelsException):
    """数据库相关异常"""
    
    def __init__(
        self,
        message: str,
        code: ErrorCode = ErrorCode.DATABASE_ERROR,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        super().__init__(message, code, details, cause)


class TaskException(AINovelsException):
    """任务相关异常"""
    
    def __init__(
        self,
        message: str,
        code: ErrorCode = ErrorCode.TASK_ERROR,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        super().__init__(message, code, details, cause)


class ValidationException(AINovelsException):
    """验证相关异常"""
    
    def __init__(
        self,
        message: str,
        code: ErrorCode = ErrorCode.VALIDATION_ERROR,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        super().__init__(message, code, details, cause)


class MessagingException(AINovelsException):
    """消息队列相关异常"""
    
    def __init__(
        self,
        message: str,
        code: ErrorCode = ErrorCode.MESSAGING_ERROR,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        super().__init__(message, code, details, cause)


# 便捷函数
def raise_config_error(message: str, details: Optional[Dict[str, Any]] = None):
    """抛出配置错误"""
    raise ConfigException(message, ErrorCode.CONFIGURATION_ERROR, details)


def raise_agent_error(
    message: str,
    code: ErrorCode = ErrorCode.AGENT_ERROR,
    details: Optional[Dict[str, Any]] = None
):
    """抛出Agent错误"""
    raise AgentException(message, code, details)


def raise_llm_error(
    message: str,
    code: ErrorCode = ErrorCode.LLM_ERROR,
    details: Optional[Dict[str, Any]] = None
):
    """抛出LLM错误"""
    raise LLMException(message, code, details)


def raise_database_error(
    message: str,
    code: ErrorCode = ErrorCode.DATABASE_ERROR,
    details: Optional[Dict[str, Any]] = None
):
    """抛出数据库错误"""
    raise DatabaseException(message, code, details)


def raise_task_error(
    message: str,
    code: ErrorCode = ErrorCode.TASK_ERROR,
    details: Optional[Dict[str, Any]] = None
):
    """抛出任务错误"""
    raise TaskException(message, code, details)


def raise_validation_error(
    message: str,
    code: ErrorCode = ErrorCode.VALIDATION_ERROR,
    details: Optional[Dict[str, Any]] = None
):
    """抛出验证错误"""
    raise ValidationException(message, code, details)
