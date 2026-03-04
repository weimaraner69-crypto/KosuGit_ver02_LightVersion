"""business ドメインの疑似エンドポイント。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from shared.api_handlers import ApiResponse, execute_authorized_mutation
from shared.csrf import create_csrf_token
from shared.exceptions import AuthorizationError
from shared.rbac import AUTHORIZATION_ERROR_MESSAGE

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from shared.audit import AuditLogWriter
    from shared.auth import AuthContext

EXPORT_SALES_DATA_ENDPOINT_SPEC: dict[str, Any] = {
    "path": "/business/sales/export",
    "method": "POST",
    "summary": "売上データエクスポート",
    "auth": {
        "resource": "business",
        "action": "export",
    },
    "responses": {
        "200": {
            "description": "エクスポート成功",
            "body": {
                "ok": True,
                "data": {
                    "message": "string",
                    "resource": "sales",
                    "executed_by": "string",
                },
            },
        },
        "401": {
            "description": "未認証または無効化ユーザー",
            "body": {"ok": False, "error": "ユーザー名またはパスワードが正しくありません"},
        },
        "403": {
            "description": "権限不足またはCSRF検証失敗",
            "body": {"ok": False, "error": "string"},
        },
        "500": {
            "description": "内部エラー",
            "body": {"ok": False, "error": "処理に失敗しました。時間をおいて再度お試しください"},
        },
    },
}

UPDATE_DAILY_REPORT_NOTE_ENDPOINT_SPEC: dict[str, Any] = {
    "path": "/business/report/note",
    "method": "PATCH",
    "summary": "日報メモ更新",
    "auth": {
        "resource": "report",
        "action": "update",
    },
    "responses": {
        "200": {
            "description": "更新成功",
            "body": {
                "ok": True,
                "data": {
                    "report_id": "string",
                    "updated": "boolean",
                    "resource": "report",
                    "executed_by": "string",
                },
            },
        },
        "401": {
            "description": "未認証または無効化ユーザー",
            "body": {"ok": False, "error": "ユーザー名またはパスワードが正しくありません"},
        },
        "403": {
            "description": "権限不足またはCSRF検証失敗",
            "body": {"ok": False, "error": "string"},
        },
        "500": {
            "description": "内部エラー",
            "body": {"ok": False, "error": "処理に失敗しました。時間をおいて再度お試しください"},
        },
    },
}

REPLACE_DAILY_REPORT_ENDPOINT_SPEC: dict[str, Any] = {
    "path": "/business/report",
    "method": "PUT",
    "summary": "日報更新（全体置換）",
    "auth": {
        "resource": "report",
        "action": "update",
    },
    "responses": {
        "200": {
            "description": "更新成功",
            "body": {
                "ok": True,
                "data": {
                    "report_id": "string",
                    "replaced": "boolean",
                    "resource": "report",
                    "executed_by": "string",
                },
            },
        },
        "401": {
            "description": "未認証または無効化ユーザー",
            "body": {"ok": False, "error": "ユーザー名またはパスワードが正しくありません"},
        },
        "403": {
            "description": "権限不足またはCSRF検証失敗",
            "body": {"ok": False, "error": "string"},
        },
        "500": {
            "description": "内部エラー",
            "body": {"ok": False, "error": "処理に失敗しました。時間をおいて再度お試しください"},
        },
    },
}

DELETE_DAILY_REPORT_ENDPOINT_SPEC: dict[str, Any] = {
    "path": "/business/report",
    "method": "DELETE",
    "summary": "日報削除",
    "auth": {
        "resource": "report",
        "action": "delete",
    },
    "responses": {
        "200": {
            "description": "削除成功",
            "body": {
                "ok": True,
                "data": {
                    "report_id": "string",
                    "deleted": "boolean",
                    "resource": "report",
                    "executed_by": "string",
                },
            },
        },
        "401": {
            "description": "未認証または無効化ユーザー",
            "body": {"ok": False, "error": "ユーザー名またはパスワードが正しくありません"},
        },
        "403": {
            "description": "権限不足またはCSRF検証失敗",
            "body": {"ok": False, "error": "string"},
        },
        "500": {
            "description": "内部エラー",
            "body": {"ok": False, "error": "処理に失敗しました。時間をおいて再度お試しください"},
        },
    },
}

SALES_EXPORT_ALLOWED_DATASETS_BY_ROLE: dict[str, set[str]] = {
    "admin": {"*"},
    "tax_accountant": {
        "sales",
        "expense",
        "petty_cash",
        "purchase",
        "labor_cost_summary",
        "profit_loss",
        "kpi",
    },
}


def _extract_target_resource_id(result: Mapping[str, Any], *, keys: tuple[str, ...]) -> str | None:
    """業務処理結果から監査ログ対象IDを抽出する。"""
    for key in keys:
        value = result.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _normalize_export_datasets(result: Mapping[str, Any]) -> set[str]:
    """エクスポート結果のデータセット一覧を正規化する。"""
    raw_datasets = result.get("datasets")
    if raw_datasets is None:
        return {"sales"}

    if isinstance(raw_datasets, str):
        candidates: tuple[object, ...] = (raw_datasets,)
    elif isinstance(raw_datasets, (list, tuple, set)):
        candidates = tuple(raw_datasets)
    else:
        raise AuthorizationError(AUTHORIZATION_ERROR_MESSAGE)

    normalized: set[str] = set()
    for candidate in candidates:
        if not isinstance(candidate, str):
            raise AuthorizationError(AUTHORIZATION_ERROR_MESSAGE)
        dataset = candidate.strip().lower()
        if not dataset:
            raise AuthorizationError(AUTHORIZATION_ERROR_MESSAGE)
        normalized.add(dataset)

    if not normalized:
        raise AuthorizationError(AUTHORIZATION_ERROR_MESSAGE)

    return normalized


def _enforce_sales_export_dataset_scope(role: str, result: Mapping[str, Any]) -> None:
    """ロールごとの売上エクスポート対象制約を検証する。"""
    allowed = SALES_EXPORT_ALLOWED_DATASETS_BY_ROLE.get(role.strip().lower())
    if allowed is None:
        raise AuthorizationError(AUTHORIZATION_ERROR_MESSAGE)

    if "*" in allowed:
        return

    datasets = _normalize_export_datasets(result)
    if not datasets.issubset(allowed):
        raise AuthorizationError(AUTHORIZATION_ERROR_MESSAGE)


def export_sales_data(
    context: AuthContext | None,
    *,
    method: str,
    csrf_header_token: str | None,
    csrf_cookie_token: str | None,
    sales_exporter: Callable[[AuthContext], Mapping[str, Any]],
    audit_log_writer: AuditLogWriter | None = None,
) -> ApiResponse:
    """売上エクスポートの疑似エンドポイント。"""

    def operation(authorized_context: AuthContext) -> Mapping[str, Any]:
        result = dict(sales_exporter(authorized_context))
        _enforce_sales_export_dataset_scope(authorized_context.role, result)
        return result

    return execute_authorized_mutation(
        context,
        resource="sales",
        action="export",
        method=method,
        csrf_header_token=csrf_header_token,
        csrf_cookie_token=csrf_cookie_token,
        operation=operation,
        audit_log_writer=audit_log_writer,
        target_resource_id_getter=lambda result: _extract_target_resource_id(
            result,
            keys=("export_id", "target_resource_id", "report_id"),
        ),
    )


def export_sales_data_sample(context: AuthContext | None) -> ApiResponse:
    """売上エクスポートのサンプル実装。"""

    def sales_exporter(authorized_context: AuthContext) -> Mapping[str, Any]:
        return {
            "export_id": "sample-export-001",
            "resource": "sales",
            "executed_by": authorized_context.user_id,
        }

    csrf_token = create_csrf_token()

    return export_sales_data(
        context,
        method="POST",
        csrf_header_token=csrf_token,
        csrf_cookie_token=csrf_token,
        sales_exporter=sales_exporter,
    )


def update_daily_report_note(
    context: AuthContext | None,
    *,
    method: str,
    csrf_header_token: str | None,
    csrf_cookie_token: str | None,
    note_updater: Callable[[AuthContext], Mapping[str, Any]],
    audit_log_writer: AuditLogWriter | None = None,
) -> ApiResponse:
    """日報メモ更新の疑似エンドポイント。"""
    return execute_authorized_mutation(
        context,
        resource="report",
        action="update",
        method=method,
        csrf_header_token=csrf_header_token,
        csrf_cookie_token=csrf_cookie_token,
        operation=lambda authorized_context: dict(note_updater(authorized_context)),
        audit_log_writer=audit_log_writer,
        target_resource_id_getter=lambda result: _extract_target_resource_id(
            result,
            keys=("report_id", "target_resource_id"),
        ),
    )


def update_daily_report_note_sample(context: AuthContext | None) -> ApiResponse:
    """日報メモ更新のサンプル実装。"""

    def note_updater(authorized_context: AuthContext) -> Mapping[str, Any]:
        return {
            "report_id": "report-001",
            "updated": True,
            "resource": "report",
            "executed_by": authorized_context.user_id,
        }

    csrf_token = create_csrf_token()

    return update_daily_report_note(
        context,
        method="PATCH",
        csrf_header_token=csrf_token,
        csrf_cookie_token=csrf_token,
        note_updater=note_updater,
    )


def replace_daily_report(
    context: AuthContext | None,
    *,
    method: str,
    csrf_header_token: str | None,
    csrf_cookie_token: str | None,
    report_replacer: Callable[[AuthContext], Mapping[str, Any]],
    audit_log_writer: AuditLogWriter | None = None,
) -> ApiResponse:
    """日報更新（全体置換）の疑似エンドポイント。"""
    return execute_authorized_mutation(
        context,
        resource="report",
        action="update",
        method=method,
        csrf_header_token=csrf_header_token,
        csrf_cookie_token=csrf_cookie_token,
        operation=lambda authorized_context: dict(report_replacer(authorized_context)),
        audit_log_writer=audit_log_writer,
        target_resource_id_getter=lambda result: _extract_target_resource_id(
            result,
            keys=("report_id", "target_resource_id"),
        ),
    )


def replace_daily_report_sample(context: AuthContext | None) -> ApiResponse:
    """日報更新（全体置換）のサンプル実装。"""

    def report_replacer(authorized_context: AuthContext) -> Mapping[str, Any]:
        return {
            "report_id": "report-001",
            "replaced": True,
            "resource": "report",
            "executed_by": authorized_context.user_id,
        }

    csrf_token = create_csrf_token()

    return replace_daily_report(
        context,
        method="PUT",
        csrf_header_token=csrf_token,
        csrf_cookie_token=csrf_token,
        report_replacer=report_replacer,
    )


def delete_daily_report(
    context: AuthContext | None,
    *,
    method: str,
    csrf_header_token: str | None,
    csrf_cookie_token: str | None,
    report_deleter: Callable[[AuthContext], Mapping[str, Any]],
    audit_log_writer: AuditLogWriter | None = None,
) -> ApiResponse:
    """日報削除の疑似エンドポイント。"""
    return execute_authorized_mutation(
        context,
        resource="report",
        action="delete",
        method=method,
        csrf_header_token=csrf_header_token,
        csrf_cookie_token=csrf_cookie_token,
        operation=lambda authorized_context: dict(report_deleter(authorized_context)),
        audit_log_writer=audit_log_writer,
        target_resource_id_getter=lambda result: _extract_target_resource_id(
            result,
            keys=("report_id", "target_resource_id"),
        ),
    )


def delete_daily_report_sample(context: AuthContext | None) -> ApiResponse:
    """日報削除のサンプル実装。"""

    def report_deleter(authorized_context: AuthContext) -> Mapping[str, Any]:
        return {
            "report_id": "report-001",
            "deleted": True,
            "resource": "report",
            "executed_by": authorized_context.user_id,
        }

    csrf_token = create_csrf_token()

    return delete_daily_report(
        context,
        method="DELETE",
        csrf_header_token=csrf_token,
        csrf_cookie_token=csrf_token,
        report_deleter=report_deleter,
    )
