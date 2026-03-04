"""認証・アクティブ状態チェックの共通ロジック。"""

from __future__ import annotations

from dataclasses import dataclass

from shared.exceptions import AuthenticationError


GENERIC_AUTH_ERROR_MESSAGE = "ユーザー名またはパスワードが正しくありません"


@dataclass(frozen=True)
class AuthContext:
    """認証済みユーザーの実行コンテキスト。"""

    user_id: str
    role: str
    is_active: bool

    def __post_init__(self) -> None:
        """不変条件の検証。"""
        if not self.user_id:
            raise ValueError("ユーザーIDは必須です")
        if not self.role:
            raise ValueError("ロールは必須です")


def require_authenticated_user(context: AuthContext | None) -> AuthContext:
    """認証済みユーザーを必須とする。"""
    if context is None:
        raise AuthenticationError(GENERIC_AUTH_ERROR_MESSAGE)
    return context


def ensure_active_user(context: AuthContext) -> AuthContext:
    """無効化済みアカウントを拒否する。"""
    if not context.is_active:
        raise AuthenticationError(GENERIC_AUTH_ERROR_MESSAGE)
    return context


def require_active_authenticated_user(context: AuthContext | None) -> AuthContext:
    """認証済みかつ有効なユーザーを必須とする。"""
    authenticated_context = require_authenticated_user(context)
    return ensure_active_user(authenticated_context)
