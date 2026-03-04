"""セキュリティ設定モジュールのテスト。"""

from __future__ import annotations

import pytest

from shared.security_config import get_security_runtime_config


def test_get_security_runtime_config_デフォルト値() -> None:
    """環境変数未指定時は初期確定値が適用される。"""
    config = get_security_runtime_config()

    assert config.trust_x_forwarded_proto is True
    assert config.cookie.secure is True
    assert config.cookie.http_only is True
    assert config.cookie.same_site == "Lax"
    assert config.cookie.session_ttl_seconds == 12 * 60 * 60
    assert config.cookie.idle_timeout_seconds == 120 * 60
    assert config.oauth_callback_paths == ("/auth/google/callback", "/auth/line/callback")
    assert config.key_rotation_days == 90


def test_get_security_runtime_config_環境変数上書き(monkeypatch: pytest.MonkeyPatch) -> None:
    """環境変数で設定を上書きできる。"""
    monkeypatch.setenv("TRUST_X_FORWARDED_PROTO", "true")
    monkeypatch.setenv("COOKIE_SECURE", "true")
    monkeypatch.setenv("COOKIE_HTTP_ONLY", "true")
    monkeypatch.setenv("COOKIE_SAMESITE", "Strict")
    monkeypatch.setenv("SESSION_TTL_HOURS", "8")
    monkeypatch.setenv("IDLE_TIMEOUT_MINUTES", "60")
    monkeypatch.setenv("OAUTH_CALLBACK_PATHS", "/auth/google/callback,/auth/line/callback")
    monkeypatch.setenv("KEY_ROTATION_DAYS", "30")

    config = get_security_runtime_config()

    assert config.cookie.same_site == "Strict"
    assert config.cookie.session_ttl_seconds == 8 * 60 * 60
    assert config.cookie.idle_timeout_seconds == 60 * 60
    assert config.key_rotation_days == 30


def test_get_security_runtime_config_same_site不正値でエラー(monkeypatch: pytest.MonkeyPatch) -> None:
    """SameSite が不正値ならエラー。"""
    monkeypatch.setenv("COOKIE_SAMESITE", "Invalid")

    with pytest.raises(ValueError, match="COOKIE_SAMESITE"):
        get_security_runtime_config()


def test_get_security_runtime_config_oauth_path不正でエラー(monkeypatch: pytest.MonkeyPatch) -> None:
    """OAuth パスが '/' で始まらない場合はエラー。"""
    monkeypatch.setenv("OAUTH_CALLBACK_PATHS", "auth/google/callback")

    with pytest.raises(ValueError, match="OAUTH_CALLBACK_PATHS"):
        get_security_runtime_config()


def test_get_security_runtime_config_idleがttl超過でエラー(monkeypatch: pytest.MonkeyPatch) -> None:
    """アイドルタイムアウトがTTLを超える場合はエラー。"""
    monkeypatch.setenv("SESSION_TTL_HOURS", "1")
    monkeypatch.setenv("IDLE_TIMEOUT_MINUTES", "120")

    with pytest.raises(ValueError, match="idle_timeout_seconds"):
        get_security_runtime_config()
