"""
JWT 工具函数

职责: 访问令牌的创建、验证、解析。
安全: 支持 HS256(默认) 和 RS256, 令牌过期自动拒验。
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import jwt as pyjwt

from ai_novels.core.exceptions import AINovelsException, ErrorCode


# 运行时配置 (应用启动时由 configure_jwt 设置)
_JWT_SECRET: str = ""
_JWT_ALGORITHM: str = "HS256"
_JWT_EXPIRE_MINUTES: int = 1440  # 24h

# 允许的算法白名单 (防止算法混淆攻击)
_ALLOWED_ALGORITHMS = {"HS256", "HS384", "HS512", "RS256", "RS384", "RS512"}


class JWTException(AINovelsException):
    def __init__(self, message: str, details: Optional[Dict] = None,
                 cause: Optional[Exception] = None):
        super().__init__(message, ErrorCode.AUTH_INVALID_TOKEN, details, cause)


class JWTExpired(JWTException):
    def __init__(self):
        super().__init__("Token expired", details={"code": "TOKEN_EXPIRED"})


class JWTMalformed(JWTException):
    def __init__(self, cause: Optional[Exception] = None):
        super().__init__("Malformed token", details={"code": "TOKEN_MALFORMED"}, cause=cause)


def configure_jwt(secret: str, algorithm: str = "HS256",
                  expire_minutes: int = 1440) -> None:
    """配置 JWT 参数 (应用启动时调用, 线程安全)"""
    global _JWT_SECRET, _JWT_ALGORITHM, _JWT_EXPIRE_MINUTES
    if algorithm not in _ALLOWED_ALGORITHMS:
        raise ValueError(f"Unsupported algorithm '{algorithm}'. "
                         f"Allowed: {_ALLOWED_ALGORITHMS}")
    if not secret or len(secret) < 16:
        raise ValueError("JWT secret must be at least 16 characters")
    _JWT_SECRET = secret
    _JWT_ALGORITHM = algorithm
    _JWT_EXPIRE_MINUTES = expire_minutes


async def create_access_token(data: Dict[str, Any],
                              expires_delta: Optional[int] = None) -> str:
    """创建访问令牌

    Args:
        data: 令牌载荷, 必须包含 sub(user_id) 和 tenant_id
        expires_delta: 过期时间(分钟), None 则使用默认值

    Returns:
        编码后的 JWT 字符串
    """
    if not _JWT_SECRET:
        raise JWTException("JWT not configured. Call configure_jwt() first.")

    payload = data.copy()
    now = datetime.now(timezone.utc)
    expire_min = expires_delta if expires_delta is not None else _JWT_EXPIRE_MINUTES
    payload["iat"] = now
    payload["exp"] = now + timedelta(minutes=expire_min)
    if "sub" not in payload:
        payload["sub"] = payload.get("user_id", "anonymous")
    if "tenant_id" not in payload:
        payload["tenant_id"] = "default"

    token = pyjwt.encode(payload, _JWT_SECRET, algorithm=_JWT_ALGORITHM)
    return token


async def verify_jwt(token: str) -> Optional[Dict[str, Any]]:
    """验证并解析 JWT

    Args:
        token: JWT 字符串

    Returns:
        验证成功返回 payload dict, 失败返回 None
    """
    if not _JWT_SECRET:
        return None
    if not token:
        return None

    try:
        payload = pyjwt.decode(
            token,
            _JWT_SECRET,
            algorithms=[_JWT_ALGORITHM],
            options={
                "verify_exp": True,
                "verify_iat": True,
                "require": ["sub", "tenant_id"],
            },
        )
        return payload
    except pyjwt.ExpiredSignatureError:
        return None
    except pyjwt.InvalidTokenError:
        return None
