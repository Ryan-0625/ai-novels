"""
安全工具模块

@file: core/security.py
@date: 2026-04-08
@version: 1.0.0
@description: 安全相关工具，包括加密、验证、敏感数据处理等
"""

import os
import re
import hashlib
import hmac
import secrets
import base64
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from dataclasses import dataclass

from ai_novels.utils import log_info, log_warn, log_error, get_logger


class SecurityUtils:
    """安全工具类"""
    
    @staticmethod
    def generate_secure_token(length: int = 32) -> str:
        """
        生成安全随机令牌
        
        Args:
            length: 令牌长度
            
        Returns:
            安全随机字符串
        """
        return secrets.token_urlsafe(length)
    
    @staticmethod
    def hash_password(password: str, salt: Optional[str] = None) -> Dict[str, str]:
        """
        密码哈希（PBKDF2）
        
        Args:
            password: 原始密码
            salt: 盐值，None则自动生成
            
        Returns:
            包含hash和salt的字典
        """
        if salt is None:
            salt = secrets.token_hex(16)
        
        # 使用PBKDF2进行哈希
        hash_value = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt.encode('utf-8'),
            iterations=100000
        )
        
        return {
            "hash": base64.b64encode(hash_value).decode('utf-8'),
            "salt": salt
        }
    
    @staticmethod
    def verify_password(password: str, hash_value: str, salt: str) -> bool:
        """
        验证密码
        
        Args:
            password: 原始密码
            hash_value: 存储的哈希值
            salt: 盐值
            
        Returns:
            是否匹配
        """
        result = SecurityUtils.hash_password(password, salt)
        return hmac.compare_digest(result["hash"], hash_value)
    
    @staticmethod
    def hash_sensitive_data(data: str) -> str:
        """
        敏感数据哈希（用于日志记录）
        
        Args:
            data: 敏感数据
            
        Returns:
            哈希值
        """
        return hashlib.sha256(data.encode()).hexdigest()[:16]
    
    @staticmethod
    def mask_string(value: str, visible_chars: int = 4) -> str:
        """
        字符串掩码
        
        Args:
            value: 原始字符串
            visible_chars: 可见字符数
            
        Returns:
            掩码后的字符串
        """
        if len(value) <= visible_chars * 2:
            return "*" * len(value)
        
        return value[:visible_chars] + "*" * (len(value) - visible_chars * 2) + value[-visible_chars:]
    
    @staticmethod
    def mask_email(email: str) -> str:
        """
        邮箱掩码
        
        Args:
            email: 邮箱地址
            
        Returns:
            掩码后的邮箱
        """
        if "@" not in email:
            return SecurityUtils.mask_string(email)
        
        local, domain = email.split("@", 1)
        masked_local = local[:2] + "*" * (len(local) - 2) if len(local) > 2 else "*" * len(local)
        return f"{masked_local}@{domain}"
    
    @staticmethod
    def sanitize_input(value: str, max_length: int = 1000) -> str:
        """
        输入清理
        
        Args:
            value: 输入值
            max_length: 最大长度
            
        Returns:
            清理后的值
        """
        if not value:
            return value
        
        # 截断长度
        if len(value) > max_length:
            value = value[:max_length]
        
        # 移除控制字符
        value = ''.join(char for char in value if ord(char) >= 32 or char in '\n\r\t')
        
        return value
    
    @staticmethod
    def validate_api_key(key: str) -> bool:
        """
        验证API Key格式
        
        Args:
            key: API Key
            
        Returns:
            是否有效
        """
        if not key:
            return False
        
        # 最小长度检查
        if len(key) < 16:
            return False
        
        # 字符集检查（只允许字母数字和特定符号）
        if not re.match(r'^[a-zA-Z0-9_-]+$', key):
            return False
        
        return True
    
    @staticmethod
    def generate_api_key(prefix: str = "ak") -> str:
        """
        生成API Key
        
        Args:
            prefix: 前缀
            
        Returns:
            API Key
        """
        random_part = secrets.token_urlsafe(32)
        return f"{prefix}_{random_part}"


class SensitiveDataFilter:
    """敏感数据过滤器"""
    
    # 敏感字段名模式
    SENSITIVE_PATTERNS = [
        r'password',
        r'secret',
        r'token',
        r'key',
        r'api_key',
        r'private',
        r'credential',
        r'auth',
        r'passwd',
        r'pwd'
    ]
    
    @classmethod
    def is_sensitive_field(cls, field_name: str) -> bool:
        """
        检查是否为敏感字段
        
        Args:
            field_name: 字段名
            
        Returns:
            是否敏感
        """
        field_lower = field_name.lower()
        return any(re.search(pattern, field_lower) for pattern in cls.SENSITIVE_PATTERNS)
    
    @classmethod
    def filter_dict(cls, data: Dict[str, Any], mask: str = "***") -> Dict[str, Any]:
        """
        过滤字典中的敏感数据
        
        Args:
            data: 原始数据
            mask: 掩码值
            
        Returns:
            过滤后的数据
        """
        result = {}
        for key, value in data.items():
            if cls.is_sensitive_field(key):
                if isinstance(value, str) and len(value) > 0:
                    result[key] = mask
                else:
                    result[key] = mask
            elif isinstance(value, dict):
                result[key] = cls.filter_dict(value, mask)
            elif isinstance(value, list):
                result[key] = cls.filter_list(value, mask)
            else:
                result[key] = value
        return result
    
    @classmethod
    def filter_list(cls, data: List[Any], mask: str = "***") -> List[Any]:
        """
        过滤列表中的敏感数据
        
        Args:
            data: 原始数据
            mask: 掩码值
            
        Returns:
            过滤后的数据
        """
        result = []
        for item in data:
            if isinstance(item, dict):
                result.append(cls.filter_dict(item, mask))
            elif isinstance(item, list):
                result.append(cls.filter_list(item, mask))
            else:
                result.append(item)
        return result


class ConfigEncryption:
    """配置加密工具"""
    
    def __init__(self, key: Optional[str] = None):
        """
        初始化
        
        Args:
            key: 加密密钥，None则从环境变量获取
        """
        self._key = key or os.environ.get('AI_NOVELS_CONFIG_KEY')
        if not self._key:
            self._logger = get_logger()
            self._logger.warn("Config encryption key not set, using default (INSECURE!)")
            self._key = "default_insecure_key_do_not_use_in_production"
        
        # 确保密钥长度正确（32字节用于AES-256）
        self._key_bytes = hashlib.sha256(self._key.encode()).digest()
    
    def encrypt(self, plaintext: str) -> str:
        """
        加密文本
        
        Args:
            plaintext: 明文
            
        Returns:
            密文（base64编码）
        """
        try:
            from cryptography.fernet import Fernet
            
            # 使用密钥生成Fernet密钥
            key = base64.urlsafe_b64encode(self._key_bytes)
            f = Fernet(key)
            
            encrypted = f.encrypt(plaintext.encode('utf-8'))
            return base64.b64encode(encrypted).decode('utf-8')
        except ImportError:
            log_error("cryptography library not installed, cannot encrypt")
            raise
    
    def decrypt(self, ciphertext: str) -> str:
        """
        解密文本
        
        Args:
            ciphertext: 密文（base64编码）
            
        Returns:
            明文
        """
        try:
            from cryptography.fernet import Fernet
            
            key = base64.urlsafe_b64encode(self._key_bytes)
            f = Fernet(key)
            
            encrypted = base64.b64decode(ciphertext.encode('utf-8'))
            decrypted = f.decrypt(encrypted)
            return decrypted.decode('utf-8')
        except ImportError:
            log_error("cryptography library not installed, cannot decrypt")
            raise
    
    def encrypt_value(self, value: Any) -> Any:
        """
        加密值（支持嵌套结构）
        
        Args:
            value: 值
            
        Returns:
            加密后的值
        """
        if isinstance(value, str):
            return f"ENC:{self.encrypt(value)}"
        elif isinstance(value, dict):
            return {k: self.encrypt_value(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [self.encrypt_value(item) for item in value]
        return value
    
    def decrypt_value(self, value: Any) -> Any:
        """
        解密值（支持嵌套结构）
        
        Args:
            value: 值
            
        Returns:
            解密后的值
        """
        if isinstance(value, str) and value.startswith("ENC:"):
            return self.decrypt(value[4:])
        elif isinstance(value, dict):
            return {k: self.decrypt_value(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [self.decrypt_value(item) for item in value]
        return value


class RequestValidator:
    """请求验证器"""
    
    @staticmethod
    def validate_string(
        value: str,
        min_length: int = 1,
        max_length: int = 1000,
        pattern: Optional[str] = None,
        allow_empty: bool = False
    ) -> tuple[bool, Optional[str]]:
        """
        验证字符串
        
        Args:
            value: 值
            min_length: 最小长度
            max_length: 最大长度
            pattern: 正则表达式模式
            allow_empty: 是否允许空值
            
        Returns:
            (是否有效, 错误信息)
        """
        if value is None:
            if allow_empty:
                return True, None
            return False, "Value is required"
        
        if not isinstance(value, str):
            return False, "Value must be a string"
        
        if len(value) < min_length:
            return False, f"Value must be at least {min_length} characters"
        
        if len(value) > max_length:
            return False, f"Value must be at most {max_length} characters"
        
        if pattern and not re.match(pattern, value):
            return False, "Value format is invalid"
        
        return True, None
    
    @staticmethod
    def validate_integer(
        value: Any,
        min_value: Optional[int] = None,
        max_value: Optional[int] = None
    ) -> tuple[bool, Optional[str]]:
        """
        验证整数
        
        Args:
            value: 值
            min_value: 最小值
            max_value: 最大值
            
        Returns:
            (是否有效, 错误信息)
        """
        try:
            num = int(value)
        except (TypeError, ValueError):
            return False, "Value must be an integer"
        
        if min_value is not None and num < min_value:
            return False, f"Value must be at least {min_value}"
        
        if max_value is not None and num > max_value:
            return False, f"Value must be at most {max_value}"
        
        return True, None
    
    @staticmethod
    def validate_enum(
        value: Any,
        allowed_values: List[Any]
    ) -> tuple[bool, Optional[str]]:
        """
        验证枚举值
        
        Args:
            value: 值
            allowed_values: 允许的值列表
            
        Returns:
            (是否有效, 错误信息)
        """
        if value not in allowed_values:
            return False, f"Value must be one of: {', '.join(map(str, allowed_values))}"
        
        return True, None


# 便捷函数
def mask_sensitive_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """掩码敏感数据"""
    return SensitiveDataFilter.filter_dict(data)


def hash_password(password: str) -> Dict[str, str]:
    """哈希密码"""
    return SecurityUtils.hash_password(password)


def verify_password(password: str, hash_value: str, salt: str) -> bool:
    """验证密码"""
    return SecurityUtils.verify_password(password, hash_value, salt)


def generate_api_key(prefix: str = "ak") -> str:
    """生成API Key"""
    return SecurityUtils.generate_api_key(prefix)


def sanitize_input(value: str, max_length: int = 1000) -> str:
    """清理输入"""
    return SecurityUtils.sanitize_input(value, max_length)
