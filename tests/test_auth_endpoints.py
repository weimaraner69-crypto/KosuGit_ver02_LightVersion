"""認証疑似エンドポイントのテスト。"""

from __future__ import annotations

import pytest

from shared.auth import GENERIC_AUTH_ERROR_MESSAGE
from shared.auth_endpoints import is_oauth_callback_request, login_with_password
from shared.security import User


def test_login_with_password_正常系_cookieが発行される() -> None:
    """HTTPSアクセスかつ認証成功時にCookieが発行される。"""

    def authenticate(username: str, password: str) -> User | None:
        if username == "john_doe" and password == "password":
            return User(user_id="user_001", username="john_doe", role="manager", is_active=True)
        return None

    response = login_with_password(
        request_scheme="https",
        request_headers={},
        username="john_doe",
        password="password",
        authenticate=authenticate,
    )

    assert response.status_code == 200
    assert response.body["ok"] is True
    assert response.body["data"]["user_id"] == "user_001"
    assert len(response.set_cookies) == 1
    cookie = response.set_cookies[0]
    assert cookie.secure is True
    assert cookie.http_only is True
    assert cookie.same_site == "Lax"


def test_login_with_password_httpアクセスは拒否() -> None:
    """HTTPアクセスは拒否される。"""

    def authenticate(_: str, __: str) -> User | None:
        return User(user_id="user_001", username="john_doe", role="manager", is_active=True)

    response = login_with_password(
        request_scheme="http",
        request_headers={},
        username="john_doe",
        password="password",
        authenticate=authenticate,
    )

    assert response.status_code == 400
    assert response.body["ok"] is False
    assert response.body["error"] == "HTTPS接続が必要です"
    assert response.set_cookies == ()


def test_login_with_password_forwarded_proto_httpsは許可() -> None:
    """X-Forwarded-Proto=https の場合は許可される。"""

    def authenticate(_: str, __: str) -> User | None:
        return User(user_id="user_001", username="john_doe", role="manager", is_active=True)

    response = login_with_password(
        request_scheme="http",
        request_headers={"X-Forwarded-Proto": "https"},
        username="john_doe",
        password="password",
        authenticate=authenticate,
    )

    assert response.status_code == 200
    assert response.body["ok"] is True


def test_login_with_password_認証失敗は401() -> None:
    """認証失敗時は一般化メッセージで401。"""

    def authenticate(_: str, __: str) -> User | None:
        return None

    response = login_with_password(
        request_scheme="https",
        request_headers={},
        username="john_doe",
        password="wrong",
        authenticate=authenticate,
    )

    assert response.status_code == 401
    assert response.body["ok"] is False
    assert response.body["error"] == GENERIC_AUTH_ERROR_MESSAGE


def test_login_with_password_無効化ユーザーは401() -> None:
    """無効化ユーザーは401。"""

    def authenticate(_: str, __: str) -> User | None:
        return User(user_id="user_001", username="john_doe", role="manager", is_active=False)

    response = login_with_password(
        request_scheme="https",
        request_headers={},
        username="john_doe",
        password="password",
        authenticate=authenticate,
    )

    assert response.status_code == 401
    assert response.body["ok"] is False
    assert response.body["error"] == GENERIC_AUTH_ERROR_MESSAGE


def test_login_with_password_ユーザー名はtrimされる() -> None:
    """ユーザー名の前後空白が除去されて認証される。"""
    captured_username = ""

    def authenticate(username: str, password: str) -> User | None:
        nonlocal captured_username
        captured_username = username
        if username == "john_doe" and password == "password":
            return User(user_id="user_001", username="john_doe", role="manager", is_active=True)
        return None

    response = login_with_password(
        request_scheme="https",
        request_headers={},
        username="  john_doe  ",
        password="password",
        authenticate=authenticate,
    )

    assert response.status_code == 200
    assert captured_username == "john_doe"


def test_login_with_password_空パスワードは401() -> None:
    """空パスワードは401。"""

    def authenticate(_: str, __: str) -> User | None:
        pytest.fail("authenticate は呼び出されない想定")

    response = login_with_password(
        request_scheme="https",
        request_headers={},
        username="john_doe",
        password="",
        authenticate=authenticate,
    )

    assert response.status_code == 401
    assert response.body["ok"] is False
    assert response.body["error"] == GENERIC_AUTH_ERROR_MESSAGE


def test_is_oauth_callback_request_対象パス() -> None:
    """OAuthコールバックパスを認識できる。"""
    assert is_oauth_callback_request("/auth/google/callback") is True
    assert is_oauth_callback_request("/auth/line/callback") is True


def test_is_oauth_callback_request_対象外パス() -> None:
    """対象外パスは偽。"""
    assert is_oauth_callback_request("/api/health") is False
