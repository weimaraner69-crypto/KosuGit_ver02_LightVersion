"""認証セッション発行とCookie構築の共通処理。"""

from __future__ import annotations

import secrets
from collections.abc import Mapping
from dataclasses import dataclass

from shared.security_config import SecurityRuntimeConfig, get_security_runtime_config


SESSION_COOKIE_NAME = "session_id"


@dataclass(frozen=True)
class SessionCookie:
    """セッションCookieの設定値。"""

    name: str
    value: str
    path: str
    max_age: int
    secure: bool
    http_only: bool
    same_site: str

    def __post_init__(self) -> None:
        """不変条件の検証。"""
        if not self.name:
            raise ValueError("Cookie名は必須です")
        if not self.value:
            raise ValueError("Cookie値は必須です")
        if not self.path.startswith("/"):
            raise ValueError("Cookie path は '/' で始まる必要があります")
        if self.max_age <= 0:
            raise ValueError("Cookie max_age は正の値である必要があります")
        if self.same_site not in {"Lax", "Strict", "None"}:
            raise ValueError("Cookie same_site は Lax / Strict / None のいずれかです")


def create_session_token(token_size: int = 32) -> str:
    """セッションIDとして利用するランダムトークンを生成する。"""
    if token_size <= 0:
        raise ValueError("token_size は正の値である必要があります")

    return secrets.token_urlsafe(token_size)


def build_session_cookie(
    session_token: str,
    *,
    config: SecurityRuntimeConfig | None = None,
    cookie_name: str = SESSION_COOKIE_NAME,
    cookie_path: str = "/",
) -> SessionCookie:
    """security_config に基づいてセッションCookieを構築する。"""
    if not session_token:
        raise ValueError("session_token は必須です")

    runtime_config = config or get_security_runtime_config()

    return SessionCookie(
        name=cookie_name,
        value=session_token,
        path=cookie_path,
        max_age=runtime_config.cookie.session_ttl_seconds,
        secure=runtime_config.cookie.secure,
        http_only=runtime_config.cookie.http_only,
        same_site=runtime_config.cookie.same_site,
    )


def is_https_request(
    *,
    request_scheme: str,
    headers: Mapping[str, str],
    config: SecurityRuntimeConfig | None = None,
) -> bool:
    """リクエストがHTTPS相当かどうかを判定する。"""
    runtime_config = config or get_security_runtime_config()

    normalized_scheme = request_scheme.strip().lower()
    if normalized_scheme == "https":
        return True

    if not runtime_config.trust_x_forwarded_proto:
        return False

    forwarded_proto = headers.get("X-Forwarded-Proto", "").strip().lower()
    return forwarded_proto == "https"


def is_oauth_callback_path(path: str, config: SecurityRuntimeConfig | None = None) -> bool:
    """パスがOAuthコールバック対象かを判定する。"""
    if not path:
        return False

    runtime_config = config or get_security_runtime_config()
    normalized_path = path.strip()
    return normalized_path in runtime_config.oauth_callback_paths
