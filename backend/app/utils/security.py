"""密码哈希工具。

环境内是独立的 bcrypt 包（没有 passlib），现有 users.hashed_password
是 ``$2b$12$...`` 格式，因此这里统一用 bcrypt + rounds=12。
"""

import bcrypt

# bcrypt 只取密码前 72 字节，超出部分必须显式处理
_MAX_BYTES = 72


def _to_bytes(password: str) -> bytes:
    if not isinstance(password, str):
        raise TypeError("password 必须是 str")
    return password.encode("utf-8")[:_MAX_BYTES]


def hash_password(password: str) -> str:
    """明文 -> 哈希字符串（入库用，禁止存明文）"""
    return bcrypt.hashpw(_to_bytes(password), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """明文与数据库中的哈希比对；哈希损坏或格式不对时返回 False，不抛异常"""
    if not plain_password or not hashed_password:
        return False
    try:
        return bcrypt.checkpw(_to_bytes(plain_password), hashed_password.encode("utf-8"))
    except (ValueError, TypeError):
        return False

