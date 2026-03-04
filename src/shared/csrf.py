"""CSRF 防御の共通ロジック。"""

from __future__ import annotations

import secrets

from shared.exceptions import AuthorizationError


CSRF_HEADER_NAME = "X-CSRF-Token"
CSRF_COOKIE_NAME = "csrf_token"
GENERIC_CSRF_ERROR_MESSAGE = "不正なリクエストです"

SAFE_HTTP_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}


def create_csrf_token(token_size: int = 32) -> str:
    """CSRF トークンを生成する。"""
    if token_size <= 0:
        raise ValueError("token_size は正の値である必要があります")

    return secrets.token_urlsafe(token_size)


def requires_csrf_validation(method: str) -> bool:
    """HTTP メソッドが CSRF 検証対象か判定する。"""
    normalized_method = method.strip().upper()
    if not normalized_method:
        raise ValueError("method は必須です")

    return normalized_method not in SAFE_HTTP_METHODS


def validate_csrf_tokens(
    *,
    method: str,
    header_token: str | None,
    cookie_token: str | None,
) -> None:
    """更新系リクエストの CSRF トークンを検証する。"""
    if not requires_csrf_validation(method):
        return

    if not header_token or not cookie_token:
        raise AuthorizationError(GENERIC_CSRF_ERROR_MESSAGE)

    if not secrets.compare_digest(header_token, cookie_token):
        raise AuthorizationError(GENERIC_CSRF_ERROR_MESSAGE)
