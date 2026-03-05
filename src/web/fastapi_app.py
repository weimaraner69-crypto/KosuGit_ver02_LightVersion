"""FastAPI 最小ルーター雛形。"""

from __future__ import annotations

import importlib.util
from typing import Any

from business.api import export_sales_data
from shared.api_handlers import ApiResponse
from shared.auth import AuthContext
from shared.csrf import CSRF_COOKIE_NAME, CSRF_HEADER_NAME
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
            api_response = ApiResponse(
                status_code=200,
                body={
                    "ok": True,
                    "data": {
                        "accepted": True,
                        "report_fields": sorted(sanitized_report.keys()),
                    },
                },
            )
        except Exception:
            api_response = ApiResponse(
                status_code=400,
                body={
                    "ok": False,
                    "error": "不正なリクエストです",
                },
            )

        return adapt_api_response_to_fastapi(api_response)

    app = FastAPI(title="business-management-system", version="0.1.0")

    app.get("/health")(health_check_handler)
    app.post("/business/sales/export")(export_sales_handler)
    app.post("/csp-report")(csp_report_handler)

    return app
