"""フレームワーク非依存の API ハンドラテンプレート。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from shared.api_auth import authorize_api_request, to_api_error_response
from shared.audit import AuditLogWriter, write_audit_log
from shared.csrf import validate_csrf_tokens
from shared.error_handling import log_internal_error
from shared.security_config import build_security_headers, get_security_runtime_config

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from shared.auth import AuthContext
    from shared.session import SessionCookie


def _build_default_response_headers() -> dict[str, str]:
    """APIレスポンスへ付与する既定ヘッダーを構築する。"""
    try:
        return build_security_headers(get_security_runtime_config())
    except Exception as error:
        log_internal_error(
            error,
            context={"component": "api_response_headers"},
        )
        return {}


@dataclass(frozen=True)
class ApiResponse:
    """API 応答の共通表現。"""

    status_code: int
    body: dict[str, Any]
    set_cookies: tuple[SessionCookie, ...] = ()
    headers: dict[str, str] = field(default_factory=_build_default_response_headers)

    def __post_init__(self) -> None:
        """不変条件の検証。"""
        if self.status_code < 100 or self.status_code > 599:
            raise ValueError("status_code は 100〜599 である必要があります")
        if not self.body:
            raise ValueError("body は必須です")
        for key, value in self.headers.items():
            if not key:
                raise ValueError("headers のキーは必須です")
            if "\n" in key or "\r" in key or "\n" in value or "\r" in value:
                raise ValueError("headers に改行は指定できません")


def _resolve_target_resource_id(
    *,
    target_resource_id: str | None,
    target_resource_id_getter: Callable[[Mapping[str, Any]], str | None] | None,
    operation_result: Mapping[str, Any] | None,
) -> str | None:
    """監査ログへ記録する対象IDを解決する。"""
    if operation_result is None or target_resource_id_getter is None:
        return target_resource_id

    try:
        resolved = target_resource_id_getter(operation_result)
    except Exception:
        return target_resource_id

    if resolved:
        return resolved
    return target_resource_id


def execute_authorized_action(
    context: AuthContext | None,
    *,
    resource: str,
    action: str,
    operation: Callable[[AuthContext], Mapping[str, Any]],
    audit_log_writer: AuditLogWriter | None = None,
    target_resource_id: str | None = None,
    target_resource_id_getter: Callable[[Mapping[str, Any]], str | None] | None = None,
) -> ApiResponse:
    """認証・認可後に業務処理を実行する共通テンプレート。"""
    try:
        authorized_context = authorize_api_request(
            context,
            resource=resource,
            action=action,
        )

        result = dict(operation(authorized_context))
        resolved_target_resource_id = _resolve_target_resource_id(
            target_resource_id=target_resource_id,
            target_resource_id_getter=target_resource_id_getter,
            operation_result=result,
        )
        write_audit_log(
            writer=audit_log_writer,
            actor_user_id=authorized_context.user_id,
            actor_role=authorized_context.role,
            resource=resource,
            action=action,
            result="success",
            target_resource_id=resolved_target_resource_id,
        )
        return ApiResponse(status_code=200, body={"ok": True, "data": result})
    except Exception as error:
        log_internal_error(
            error,
            context={
                "resource": resource,
                "action": action,
                "actor_user_id": context.user_id if context is not None else "anonymous",
            },
        )
        api_error = to_api_error_response(error)
        write_audit_log(
            writer=audit_log_writer,
            actor_user_id=context.user_id if context is not None else "anonymous",
            actor_role=context.role if context is not None else "anonymous",
            resource=resource,
            action=action,
            result="failure",
            target_resource_id=target_resource_id,
            error_type=type(error).__name__,
        )
        return ApiResponse(
            status_code=api_error.status_code,
            body={"ok": False, "error": api_error.message},
        )


def execute_authorized_mutation(
    context: AuthContext | None,
    *,
    resource: str,
    action: str,
    method: str,
    csrf_header_token: str | None,
    csrf_cookie_token: str | None,
    operation: Callable[[AuthContext], Mapping[str, Any]],
    audit_log_writer: AuditLogWriter | None = None,
    target_resource_id: str | None = None,
    target_resource_id_getter: Callable[[Mapping[str, Any]], str | None] | None = None,
) -> ApiResponse:
    """CSRF 検証付きで更新系業務処理を実行するテンプレート。"""
    try:
        validate_csrf_tokens(
            method=method,
            header_token=csrf_header_token,
            cookie_token=csrf_cookie_token,
        )
        return execute_authorized_action(
            context,
            resource=resource,
            action=action,
            operation=operation,
            audit_log_writer=audit_log_writer,
            target_resource_id=target_resource_id,
            target_resource_id_getter=target_resource_id_getter,
        )
    except Exception as error:
        log_internal_error(
            error,
            context={
                "resource": resource,
                "action": action,
                "actor_user_id": context.user_id if context is not None else "anonymous",
            },
        )
        api_error = to_api_error_response(error)
        write_audit_log(
            writer=audit_log_writer,
            actor_user_id=context.user_id if context is not None else "anonymous",
            actor_role=context.role if context is not None else "anonymous",
            resource=resource,
            action=action,
            result="failure",
            target_resource_id=target_resource_id,
            error_type=type(error).__name__,
        )
        return ApiResponse(
            status_code=api_error.status_code,
            body={"ok": False, "error": api_error.message},
        )


def handle_sales_export_request(context: AuthContext | None) -> ApiResponse:
    """売上エクスポート用のサンプルハンドラ。"""

    def operation(authorized_context: AuthContext) -> Mapping[str, Any]:
        return {
            "resource": "sales",
            "action": "export",
            "executed_by": authorized_context.user_id,
        }

    return execute_authorized_action(
        context,
        resource="sales",
        action="export",
        operation=operation,
    )


def handle_attendance_read_request(context: AuthContext | None) -> ApiResponse:
    """勤怠参照用のサンプルハンドラ。"""

    def operation(authorized_context: AuthContext) -> Mapping[str, Any]:
        return {
            "resource": "attendance",
            "action": "read",
            "executed_by": authorized_context.user_id,
        }

    return execute_authorized_action(
        context,
        resource="attendance",
        action="read",
        operation=operation,
    )
