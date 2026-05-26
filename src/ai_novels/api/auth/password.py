"""
密码哈希与验证工具

使用 bcrypt 算法, 自动加盐。
"""

import bcrypt


def hash_password(password: str) -> str:
    """密码哈希 (bcrypt, rounds=12)

    Args:
        password: 明文密码 (至少 6 位)

    Returns:
        bcrypt 哈希字符串

    Raises:
        ValueError: 密码长度不足
    """
    if not password or len(password) < 6:
        raise ValueError("Password must be at least 6 characters")
    if len(password) > 128:
        raise ValueError("Password must be at most 128 characters")
    return bcrypt.hashpw(
        password.encode("utf-8"),
        bcrypt.gensalt(rounds=12),
    ).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    """验证密码

    Args:
        password: 明文密码
        hashed: bcrypt 哈希字符串

    Returns:
        True 如果匹配, 否则 False
    """
    if not password or not hashed:
        return False
    try:
        return bcrypt.checkpw(
            str(password).encode("utf-8"),
            str(hashed).encode("utf-8"),
        )
    except (ValueError, TypeError, AttributeError):
        return False
