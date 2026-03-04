"""セッション発行共通処理のテスト。"""

from __future__ import annotations

import pytest

from shared.security_config import get_security_runtime_config
from shared.session import (
    SESSION_COOKIE_NAME,
    build_session_cookie,
    create_session_token,
    is_https_request,
    is_oauth_callback_path,
)


def test_create_session_token_正常系() -> None:
    """セッショントークンを生成できる。"""
    token = create_session_token()

    assert isinstance(token, str)
    assert len(token) > 20


def test_create_session_token_不正サイズでエラー() -> None:
    """トークンサイズが不正な場合はエラー。"""
    with pytest.raises(ValueError, match="token_size"):
        create_session_token(0)


def test_build_session_cookie_デフォルト設定を反映() -> None:
    """security_config のデフォルト値でCookieを構築する。"""
    config = get_security_runtime_config()

    cookie = build_session_cookie("token-001", config=config)

    assert cookie.name == SESSION_COOKIE_NAME
    assert cookie.value == "token-001"
    assert cookie.path == "/"
    assert cookie.max_age == config.cookie.session_ttl_seconds
    assert cookie.secure is True
    assert cookie.http_only is True
    assert cookie.same_site == "Lax"


def test_build_session_cookie_空トークンでエラー() -> None:
    """空トークンはエラー。"""
    with pytest.raises(ValueError, match="session_token"):
        build_session_cookie("")


def test_is_https_request_スキームhttpsは真() -> None:
    """request_scheme が https の場合は真。"""
    assert is_https_request(request_scheme="https", headers={}) is True


def test_is_https_request_forwarded_protoを信頼して真() -> None:
    """X-Forwarded-Proto が https なら真。"""
    assert is_https_request(
        request_scheme="http",
        headers={"X-Forwarded-Proto": "https"},
    ) is True


def test_is_https_request_forwarded_proto不一致は偽() -> None:
    """X-Forwarded-Proto が https 以外なら偽。"""
    assert is_https_request(
        request_scheme="http",
        headers={"X-Forwarded-Proto": "http"},
    ) is False


def test_is_oauth_callback_path_既定パスは真() -> None:
    """既定のOAuthコールバックパスを認識する。"""
    assert is_oauth_callback_path("/auth/google/callback") is True
    assert is_oauth_callback_path("/auth/line/callback") is True


def test_is_oauth_callback_path_対象外は偽() -> None:
    """対象外パスは偽。"""
    assert is_oauth_callback_path("/api/health") is False
