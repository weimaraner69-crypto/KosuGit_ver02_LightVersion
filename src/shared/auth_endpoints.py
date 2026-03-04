"""認証関連の疑似エンドポイント。"""

from __future__ import annotations

from collections.abc import Callable, Mapping

from shared.api_handlers import ApiResponse
from shared.auth import GENERIC_AUTH_ERROR_MESSAGE
from shared.security import User, sanitize_input
from shared.session import (
    build_session_cookie,
    create_session_token,
    is_https_request,
    is_oauth_callback_path,
)


def login_with_password(
    *,
    request_scheme: str,
    request_headers: Mapping[str, str],
    username: str,
    password: str,
    authenticate: Callable[[str, str], User | None],
) -> ApiResponse:
    """ID/パスワードログインを実行し、セッションCookieを返す。"""
    if not is_https_request(request_scheme=request_scheme, headers=request_headers):
        return ApiResponse(
            status_code=400,
            body={"ok": False, "error": "HTTPS接続が必要です"},
        )

    if not password:
        return ApiResponse(
            status_code=401,
            body={"ok": False, "error": GENERIC_AUTH_ERROR_MESSAGE},
        )

    try:
        sanitized_username = sanitize_input(username, max_length=255)
    except ValueError:
        return ApiResponse(
            status_code=401,
            body={"ok": False, "error": GENERIC_AUTH_ERROR_MESSAGE},
        )

    user = authenticate(sanitized_username, password)
    if user is None or not user.is_active:
        return ApiResponse(
            status_code=401,
            body={"ok": False, "error": GENERIC_AUTH_ERROR_MESSAGE},
        )

    session_token = create_session_token()
    session_cookie = build_session_cookie(session_token)

    return ApiResponse(
        status_code=200,
        body={
            "ok": True,
            "data": {
                "user_id": user.user_id,
                "role": user.role,
            },
        },
        set_cookies=(session_cookie,),
    )


def is_oauth_callback_request(path: str) -> bool:
    """リクエストパスがOAuthコールバック対象か判定する。"""
    return is_oauth_callback_path(path)
