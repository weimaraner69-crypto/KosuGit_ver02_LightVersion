"""認証関連の疑似エンドポイント。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from shared.api_handlers import ApiResponse
from shared.auth import GENERIC_AUTH_ERROR_MESSAGE
from shared.login_protection import InMemoryLoginProtection
from shared.security import User, sanitize_input
from shared.session import (
    build_session_cookie,
    create_session_token,
    is_https_request,
    is_oauth_callback_path,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from shared.login_protection import LoginProtection


GENERIC_LOCKOUT_ERROR_MESSAGE = "試行回数が上限を超えました。しばらく待って再度お試しください"
DEFAULT_LOGIN_PROTECTION = InMemoryLoginProtection()


def login_with_password(
    *,
    request_scheme: str,
    request_headers: Mapping[str, str],
    username: str,
    password: str,
    authenticate: Callable[[str, str], User | None],
    login_protection: LoginProtection | None = None,
) -> ApiResponse:
    """ID/パスワードログインを実行し、セッションCookieを返す。"""
    if not is_https_request(request_scheme=request_scheme, headers=request_headers):
        return ApiResponse(
            status_code=400,
            body={"ok": False, "error": "HTTPS接続が必要です"},
        )

    try:
        sanitized_username = sanitize_input(username, max_length=255)
    except ValueError:
        return ApiResponse(
            status_code=401,
            body={"ok": False, "error": GENERIC_AUTH_ERROR_MESSAGE},
        )

    protection = login_protection or DEFAULT_LOGIN_PROTECTION
    if protection.is_locked(sanitized_username):
        return ApiResponse(
            status_code=429,
            body={"ok": False, "error": GENERIC_LOCKOUT_ERROR_MESSAGE},
        )

    if not password:
        protection.register_failure(sanitized_username)
        return ApiResponse(
            status_code=401,
            body={"ok": False, "error": GENERIC_AUTH_ERROR_MESSAGE},
        )

    user = authenticate(sanitized_username, password)
    if user is None or not user.is_active:
        protection.register_failure(sanitized_username)
        return ApiResponse(
            status_code=401,
            body={"ok": False, "error": GENERIC_AUTH_ERROR_MESSAGE},
        )

    protection.register_success(sanitized_username)

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
