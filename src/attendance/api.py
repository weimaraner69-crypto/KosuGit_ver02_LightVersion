"""attendance ドメインの疑似エンドポイント。"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from shared.api_handlers import ApiResponse, execute_authorized_action
from shared.audit import AuditLogWriter
from shared.auth import AuthContext


ATTENDANCE_SUMMARY_ENDPOINT_SPEC: dict[str, Any] = {
    "path": "/attendance/summary",
    "method": "GET",
    "summary": "勤怠サマリー取得",
    "auth": {
        "resource": "attendance",
        "action": "read",
    },
    "responses": {
        "200": {
            "description": "取得成功",
            "body": {
                "ok": True,
                "data": {
                    "total_records": "integer",
                    "resource": "attendance",
                    "executed_by": "string",
                },
            },
        },
        "401": {
            "description": "未認証または無効化ユーザー",
            "body": {"ok": False, "error": "ユーザー名またはパスワードが正しくありません"},
        },
        "403": {
            "description": "権限不足",
            "body": {"ok": False, "error": "この操作を実行する権限がありません"},
        },
        "500": {
            "description": "内部エラー",
            "body": {"ok": False, "error": "処理に失敗しました。時間をおいて再度お試しください"},
        },
    },
}


def _extract_target_resource_id(result: Mapping[str, Any]) -> str | None:
    """勤怠系の業務処理結果から監査ログ対象IDを抽出する。"""
    for key in ("attendance_id", "record_id", "target_resource_id"):
        value = result.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def get_attendance_summary(
    context: AuthContext | None,
    *,
    attendance_reader: Callable[[AuthContext], Mapping[str, Any]],
    audit_log_writer: AuditLogWriter | None = None,
) -> ApiResponse:
    """勤怠サマリー参照の疑似エンドポイント。"""
    return execute_authorized_action(
        context,
        resource="attendance",
        action="read",
        operation=lambda authorized_context: dict(attendance_reader(authorized_context)),
        audit_log_writer=audit_log_writer,
        target_resource_id_getter=_extract_target_resource_id,
    )


def get_attendance_summary_sample(context: AuthContext | None) -> ApiResponse:
    """勤怠サマリー参照のサンプル実装。"""

    def attendance_reader(authorized_context: AuthContext) -> Mapping[str, Any]:
        return {
            "total_records": 0,
            "resource": "attendance",
            "executed_by": authorized_context.user_id,
        }

    return get_attendance_summary(context, attendance_reader=attendance_reader)
