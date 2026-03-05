"""FastAPI 最小ルーター雛形。"""

from __future__ import annotations

import importlib.util
from typing import Any

from business.api import export_sales_data
from shared.api_handlers import ApiResponse
from shared.audit import SqlAlchemyAuditLogWriter
from shared.auth import AuthContext
from shared.csp_report import (
    SqlAlchemyCspReportWriter,
    get_csp_report_summary,
    persist_csp_report,
)
from shared.csrf import CSRF_COOKIE_NAME, CSRF_HEADER_NAME
from shared.database import init_db
from shared.database.connection import get_session_factory
from shared.error_handling import PUBLIC_INTERNAL_ERROR_MESSAGE, log_internal_error
from shared.fastapi_response_adapter import adapt_api_response_to_fastapi
from shared.security import sanitize_input

AUTH_USER_ID_HEADER_NAME = "X-User-Id"
AUTH_ROLE_HEADER_NAME = "X-User-Role"
AUTH_IS_ACTIVE_HEADER_NAME = "X-User-Active"
CSP_REPORT_BODY_KEY = "csp-report"


def _is_fastapi_available() -> bool:
    """FastAPI 依存が導入済みか判定する。"""
    try:
        return importlib.util.find_spec("fastapi") is not None
    except ModuleNotFoundError:
        return False


def _parse_is_active(value: str | None) -> bool:
    """ヘッダーの有効フラグを bool へ変換する。"""
    if value is None:
        return True

    normalized = sanitize_input(value, max_length=10).lower()
    if normalized in {"true", "1"}:
        return True
    if normalized in {"false", "0"}:
        return False

    raise ValueError("X-User-Active ヘッダーの値が不正です")


def _build_auth_context(
    *,
    user_id_value: str | None,
    role_value: str | None,
    is_active_value: str | None,
) -> AuthContext | None:
    """認証ヘッダーから AuthContext を生成する。"""
    if user_id_value is None or role_value is None:
        return None

    try:
        user_id = sanitize_input(user_id_value, max_length=64)
        role = sanitize_input(role_value, max_length=64)
        is_active = _parse_is_active(is_active_value)
        return AuthContext(user_id=user_id, role=role, is_active=is_active)
    except ValueError:
        return None


def _sales_exporter(authorized_context: AuthContext) -> dict[str, Any]:
    """売上エクスポートのサンプル業務処理。"""
    return {
        "export_id": "fastapi-export-001",
        "resource": "sales",
        "datasets": ["sales"],
        "executed_by": authorized_context.user_id,
    }


def _sanitize_csp_report_payload(payload: Any) -> dict[str, Any]:
    """CSPレポートJSONを最小限サニタイズする。"""
    if not isinstance(payload, dict):
        raise ValueError("CSPレポート形式が不正です")

    raw_report = payload.get(CSP_REPORT_BODY_KEY)
    if not isinstance(raw_report, dict):
        raise ValueError("CSPレポート形式が不正です")

    sanitized_report: dict[str, Any] = {}
    string_fields = {
        "document-uri": 1024,
        "violated-directive": 256,
        "effective-directive": 256,
        "blocked-uri": 1024,
        "original-policy": 2048,
        "disposition": 32,
        "referrer": 1024,
    }
    for field_name, max_length in string_fields.items():
        value = raw_report.get(field_name)
        if isinstance(value, str):
            sanitized_report[field_name] = sanitize_input(value, max_length=max_length)

    status_code_value = raw_report.get("status-code")
    if isinstance(status_code_value, int):
        sanitized_report["status-code"] = status_code_value

    return sanitized_report


def _parse_positive_query_parameter(
    value: str | None,
    *,
    parameter_name: str,
    default: int,
    max_value: int,
) -> int:
    """クエリパラメータを正の整数へ変換する。"""
    if value is None:
        return default

    normalized = sanitize_input(value, max_length=16)
    try:
        parsed = int(normalized)
    except ValueError as error:
        raise ValueError(f"{parameter_name} は整数で指定してください") from error

    if parsed <= 0:
        raise ValueError(f"{parameter_name} は正の値で指定してください")
    if parsed > max_value:
        raise ValueError(f"{parameter_name} は {max_value} 以下で指定してください")
    return parsed


def _persist_csp_report_to_database(sanitized_report: dict[str, Any]) -> int:
    """CSPレポートをDBへ永続化し、監査ログへ記録する。"""
    try:
        session_factory = get_session_factory()
    except RuntimeError:
        init_db()
        session_factory = get_session_factory()

    with session_factory() as session:
        csp_report_writer = SqlAlchemyCspReportWriter(session=session, auto_commit=False)
        audit_log_writer = SqlAlchemyAuditLogWriter(session=session, auto_commit=False)
        row_id = persist_csp_report(
            report=sanitized_report,
            csp_report_writer=csp_report_writer,
            audit_log_writer=audit_log_writer,
        )
        session.commit()

    return row_id


def _summarize_csp_reports_from_database(
    *,
    days: int,
    top_directives: int,
    spike_threshold: int,
) -> dict[str, Any]:
    """CSPレポート集計をデータベースから取得する。"""
    try:
        session_factory = get_session_factory()
    except RuntimeError:
        init_db()
        session_factory = get_session_factory()

    with session_factory() as session:
        return get_csp_report_summary(
            session=session,
            days=days,
            top_directives=top_directives,
            spike_threshold=spike_threshold,
        )


def create_fastapi_app() -> Any:
    """FastAPI アプリを生成する。"""
    if not _is_fastapi_available():
        raise RuntimeError(
            "fastapi がインストールされていません。`pip install '.[web]'` を実行してください"
        )

    from fastapi import FastAPI  # type: ignore[import-not-found]

    def health_check_handler() -> Any:
        """ヘルスチェックのサンプルエンドポイント。"""
        api_response = ApiResponse(
            status_code=200,
            body={
                "ok": True,
                "data": {
                    "status": "healthy",
                },
            },
        )
        return adapt_api_response_to_fastapi(api_response)

    def export_sales_handler(request: Any) -> Any:
        """売上エクスポートAPIの最小ルーター。"""
        context = _build_auth_context(
            user_id_value=request.headers.get(AUTH_USER_ID_HEADER_NAME),
            role_value=request.headers.get(AUTH_ROLE_HEADER_NAME),
            is_active_value=request.headers.get(AUTH_IS_ACTIVE_HEADER_NAME),
        )

        api_response = export_sales_data(
            context,
            method=request.method,
            csrf_header_token=request.headers.get(CSRF_HEADER_NAME),
            csrf_cookie_token=request.cookies.get(CSRF_COOKIE_NAME),
            sales_exporter=_sales_exporter,
        )
        return adapt_api_response_to_fastapi(api_response)

    async def csp_report_handler(request: Any) -> Any:
        """CSP違反レポートの受信エンドポイント。"""
        try:
            payload = await request.json()
            sanitized_report = _sanitize_csp_report_payload(payload)
            persisted_id = _persist_csp_report_to_database(sanitized_report)
            api_response = ApiResponse(
                status_code=200,
                body={
                    "ok": True,
                    "data": {
                        "accepted": True,
                        "persisted_id": persisted_id,
                        "report_fields": sorted(sanitized_report.keys()),
                    },
                },
            )
        except ValueError:
            api_response = ApiResponse(
                status_code=400,
                body={
                    "ok": False,
                    "error": "不正なリクエストです",
                },
            )
        except Exception as error:
            log_internal_error(
                error,
                context={
                    "component": "csp_report_handler",
                },
            )
            api_response = ApiResponse(
                status_code=500,
                body={
                    "ok": False,
                    "error": PUBLIC_INTERNAL_ERROR_MESSAGE,
                },
            )

        return adapt_api_response_to_fastapi(api_response)

    def csp_report_summary_handler(request: Any) -> Any:
        """CSP違反レポートの集計ビュー。"""
        try:
            days = _parse_positive_query_parameter(
                request.query_params.get("days"),
                parameter_name="days",
                default=7,
                max_value=365,
            )
            top_directives = _parse_positive_query_parameter(
                request.query_params.get("top"),
                parameter_name="top",
                default=10,
                max_value=100,
            )
            spike_threshold = _parse_positive_query_parameter(
                request.query_params.get("spike_threshold"),
                parameter_name="spike_threshold",
                default=3,
                max_value=1000,
            )

            summary = _summarize_csp_reports_from_database(
                days=days,
                top_directives=top_directives,
                spike_threshold=spike_threshold,
            )
            api_response = ApiResponse(
                status_code=200,
                body={
                    "ok": True,
                    "data": summary,
                },
            )
        except ValueError:
            api_response = ApiResponse(
                status_code=400,
                body={
                    "ok": False,
                    "error": "不正なリクエストです",
                },
            )
        except Exception as error:
            log_internal_error(
                error,
                context={
                    "component": "csp_report_summary_handler",
                },
            )
            api_response = ApiResponse(
                status_code=500,
                body={
                    "ok": False,
                    "error": PUBLIC_INTERNAL_ERROR_MESSAGE,
                },
            )

        return adapt_api_response_to_fastapi(api_response)

    app = FastAPI(title="business-management-system", version="0.1.0")

    app.get("/health")(health_check_handler)
    app.post("/business/sales/export")(export_sales_handler)
    app.post("/csp-report")(csp_report_handler)
    app.get("/csp-report/summary")(csp_report_summary_handler)

    return app
