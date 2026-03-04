"""API 層向け認証・認可アダプタ。"""

from __future__ import annotations

from dataclasses import dataclass

from shared.auth import AuthContext
from shared.exceptions import AuthenticationError, AuthorizationError
from shared.rbac import require_permission


@dataclass(frozen=True)
class ApiErrorResponse:
    """API エラーレスポンス情報。"""

    status_code: int
    message: str


def authorize_api_request(
    context: AuthContext | None,
    *,
    resource: str,
    action: str,
) -> AuthContext:
    """API リクエストの認証・認可を実行する。"""
    return require_permission(context, resource=resource, action=action)


def to_api_error_response(error: Exception) -> ApiErrorResponse:
    """認証・認可例外を API レスポンス形式へ変換する。"""
    if isinstance(error, AuthenticationError):
        return ApiErrorResponse(status_code=401, message=str(error))

    if isinstance(error, AuthorizationError):
        return ApiErrorResponse(status_code=403, message=str(error))

    return ApiErrorResponse(
        status_code=500,
        message="処理に失敗しました。時間をおいて再度お試しください",
    )
