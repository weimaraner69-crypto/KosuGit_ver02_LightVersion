"""HTTP応答アダプタのテスト。"""

from __future__ import annotations

import pytest

from shared.api_handlers import ApiResponse
from shared.http_response_adapter import (
    HttpHeader,
    adapt_api_response_to_http,
)
from shared.session import SessionCookie


def test_adapt_api_response_to_http_ヘッダーとCookieを転写できる() -> None:
    """ApiResponse の headers / set_cookies を HTTP 応答形式へ転写できる。"""
    response = ApiResponse(
        status_code=200,
        body={"ok": True},
        headers={"X-Test": "value"},
        set_cookies=(
            SessionCookie(
                name="session_id",
                value="token123",
                path="/",
                max_age=3600,
                secure=True,
                http_only=True,
                same_site="Lax",
            ),
        ),
    )

    http_response = adapt_api_response_to_http(response)

    assert http_response.status_code == 200
    assert http_response.body == {"ok": True}
    assert HttpHeader(name="X-Test", value="value") in http_response.headers
    set_cookie_headers = [header for header in http_response.headers if header.name == "Set-Cookie"]
    assert len(set_cookie_headers) == 1
    assert set_cookie_headers[0].value == (
        "session_id=token123; Path=/; Max-Age=3600; SameSite=Lax; Secure; HttpOnly"
    )


def test_adapt_api_response_to_http_複数Cookieを転写できる() -> None:
    """複数 Cookie がある場合も Set-Cookie を複数行で保持する。"""
    response = ApiResponse(
        status_code=200,
        body={"ok": True},
        headers={"X-Test": "value"},
        set_cookies=(
            SessionCookie(
                name="session_id",
                value="token123",
                path="/",
                max_age=3600,
                secure=True,
                http_only=True,
                same_site="Lax",
            ),
            SessionCookie(
                name="refresh_id",
                value="refresh456",
                path="/",
                max_age=7200,
                secure=False,
                http_only=False,
                same_site="Strict",
            ),
        ),
    )

    http_response = adapt_api_response_to_http(response)

    set_cookie_headers = [header for header in http_response.headers if header.name == "Set-Cookie"]
    assert len(set_cookie_headers) == 2
    assert set_cookie_headers[1].value == (
        "refresh_id=refresh456; Path=/; Max-Age=7200; SameSite=Strict"
    )


def test_http_header_改行文字はエラー() -> None:
    """ヘッダー値に改行が含まれる場合はエラー。"""
    with pytest.raises(ValueError, match="改行"):
        HttpHeader(name="X-Test", value="line1\nline2")
