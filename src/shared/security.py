"""セキュリティ機能"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass


@dataclass(frozen=True)
class User:
    """ユーザー情報（個人情報は含まない）"""
    user_id: str
    username: str
    role: str
    is_active: bool = True

    def __post_init__(self) -> None:
        """不変条件の検証"""
        if not self.user_id:
            raise ValueError("ユーザーIDは必須です")
        if not self.username:
            raise ValueError("ユーザー名は必須です")
        if not self.role:
            raise ValueError("ロールは必須です")


def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    """
    パスワードをハッシュ化する

    Args:
        password: ハッシュ化するパスワード
        salt: ソルト（指定しない場合は生成される）

    Returns:
        (ハッシュ化されたパスワード, ソルト) のタプル

    Raises:
        ValueError: パスワードが空の場合
    """
    if not password:
        raise ValueError("パスワードは必須です")

    if salt is None:
        salt = secrets.token_hex(32)

    # SHA-256 でハッシュ化（本番環境では bcrypt や argon2 を推奨）
    password_hash = hashlib.sha256((password + salt).encode()).hexdigest()

    return password_hash, salt


def verify_password(password: str, password_hash: str, salt: str) -> bool:
    """
    パスワードを検証する

    Args:
        password: 検証するパスワード
        password_hash: 保存されているハッシュ
        salt: 保存されているソルト

    Returns:
        パスワードが一致する場合は True
    """
    computed_hash, _ = hash_password(password, salt)
    return secrets.compare_digest(computed_hash, password_hash)


def sanitize_input(value: str, max_length: int = 255) -> str:
    """
    入力値をサニタイズする

    Args:
        value: サニタイズする文字列
        max_length: 最大長

    Returns:
        サニタイズされた文字列

    Raises:
        ValueError: 値が空または最大長を超える場合
    """
    if not value:
        raise ValueError("値は必須です")

    # 前後の空白を削除
    sanitized = value.strip()

    # 最大長チェック
    if len(sanitized) > max_length:
        raise ValueError(f"値は{max_length}文字以内である必要があります")

    return sanitized
