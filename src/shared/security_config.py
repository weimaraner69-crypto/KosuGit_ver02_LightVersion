"""セキュリティ設定値の共通定義。"""

from __future__ import annotations

import os
from dataclasses import dataclass


def _parse_bool(value: str | None, *, default: bool, setting_name: str) -> bool:
    """環境変数から真偽値を読み取る。"""
    if value is None:
        return default

    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False

    raise ValueError(f"{setting_name} は真偽値で指定してください")


def _parse_positive_int(value: str | None, *, default: int, setting_name: str) -> int:
    """環境変数から正の整数を読み取る。"""
    if value is None:
        return default

    try:
        parsed = int(value)
    except ValueError as error:
        raise ValueError(f"{setting_name} は整数で指定してください") from error

    if parsed <= 0:
        raise ValueError(f"{setting_name} は正の整数である必要があります")
    return parsed


def _normalize_same_site(value: str | None) -> str:
    """SameSite 設定値を正規化する。"""
    if value is None:
        return "Lax"

    normalized = value.strip().capitalize()
    if normalized not in {"Lax", "Strict", "None"}:
        raise ValueError("COOKIE_SAMESITE は Lax / Strict / None のいずれかで指定してください")
    return normalized


def _parse_oauth_callback_paths(value: str | None) -> tuple[str, ...]:
    """OAuth コールバック対象パスを読み取る。"""
    raw_value = value or "/auth/google/callback,/auth/line/callback"
    paths = tuple(path.strip() for path in raw_value.split(",") if path.strip())

    if not paths:
        raise ValueError("OAUTH_CALLBACK_PATHS は1つ以上指定する必要があります")

    for path in paths:
        if not path.startswith("/"):
            raise ValueError("OAUTH_CALLBACK_PATHS の各パスは '/' で始まる必要があります")

    return paths


@dataclass(frozen=True)
class CookieSettings:
    """認証Cookie設定。"""

    secure: bool
    http_only: bool
    same_site: str
    session_ttl_seconds: int
    idle_timeout_seconds: int

    def __post_init__(self) -> None:
        """不変条件の検証。"""
        if self.same_site not in {"Lax", "Strict", "None"}:
            raise ValueError("same_site は Lax / Strict / None のいずれかである必要があります")
        if self.session_ttl_seconds <= 0:
            raise ValueError("session_ttl_seconds は正の値である必要があります")
        if self.idle_timeout_seconds <= 0:
            raise ValueError("idle_timeout_seconds は正の値である必要があります")
        if self.idle_timeout_seconds > self.session_ttl_seconds:
            raise ValueError("idle_timeout_seconds は session_ttl_seconds 以下である必要があります")


@dataclass(frozen=True)
class SecurityRuntimeConfig:
    """SEC-001 で利用する実行時セキュリティ設定。"""

    trust_x_forwarded_proto: bool
    cookie: CookieSettings
    oauth_callback_paths: tuple[str, ...]
    key_rotation_days: int

    def __post_init__(self) -> None:
        """不変条件の検証。"""
        if not self.oauth_callback_paths:
            raise ValueError("oauth_callback_paths は1つ以上必要です")
        if self.key_rotation_days <= 0:
            raise ValueError("key_rotation_days は正の値である必要があります")


def get_security_runtime_config() -> SecurityRuntimeConfig:
    """環境変数から SEC-001 用の設定を構築する。"""
    trust_x_forwarded_proto = _parse_bool(
        os.getenv("TRUST_X_FORWARDED_PROTO"),
        default=True,
        setting_name="TRUST_X_FORWARDED_PROTO",
    )

    cookie_secure = _parse_bool(
        os.getenv("COOKIE_SECURE"),
        default=True,
        setting_name="COOKIE_SECURE",
    )
    cookie_http_only = _parse_bool(
        os.getenv("COOKIE_HTTP_ONLY"),
        default=True,
        setting_name="COOKIE_HTTP_ONLY",
    )
    cookie_same_site = _normalize_same_site(os.getenv("COOKIE_SAMESITE"))

    session_ttl_hours = _parse_positive_int(
        os.getenv("SESSION_TTL_HOURS"),
        default=12,
        setting_name="SESSION_TTL_HOURS",
    )
    idle_timeout_minutes = _parse_positive_int(
        os.getenv("IDLE_TIMEOUT_MINUTES"),
        default=120,
        setting_name="IDLE_TIMEOUT_MINUTES",
    )
    key_rotation_days = _parse_positive_int(
        os.getenv("KEY_ROTATION_DAYS"),
        default=90,
        setting_name="KEY_ROTATION_DAYS",
    )

    cookie_settings = CookieSettings(
        secure=cookie_secure,
        http_only=cookie_http_only,
        same_site=cookie_same_site,
        session_ttl_seconds=session_ttl_hours * 60 * 60,
        idle_timeout_seconds=idle_timeout_minutes * 60,
    )

    callback_paths = _parse_oauth_callback_paths(os.getenv("OAUTH_CALLBACK_PATHS"))

    return SecurityRuntimeConfig(
        trust_x_forwarded_proto=trust_x_forwarded_proto,
        cookie=cookie_settings,
        oauth_callback_paths=callback_paths,
        key_rotation_days=key_rotation_days,
    )
