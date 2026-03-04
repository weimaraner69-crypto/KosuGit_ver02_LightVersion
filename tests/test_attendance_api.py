"""attendance 疑似エンドポイントのテスト。"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from attendance.api import (
    ATTENDANCE_SUMMARY_ENDPOINT_SPEC,
    get_attendance_summary,
    get_attendance_summary_sample,
)
from shared.audit import InMemoryAuditLogWriter
from shared.auth import AuthContext


class TestAttendanceApi:
    """attendance API の認可・応答テスト。"""

    def test_attendance_summary_endpoint_spec_必須項目を持つ(self) -> None:
        """OpenAPI相当の雛形として必須項目を持つ。"""
        assert ATTENDANCE_SUMMARY_ENDPOINT_SPEC["path"] == "/attendance/summary"
        assert ATTENDANCE_SUMMARY_ENDPOINT_SPEC["method"] == "GET"
        assert ATTENDANCE_SUMMARY_ENDPOINT_SPEC["auth"]["resource"] == "attendance"
        assert ATTENDANCE_SUMMARY_ENDPOINT_SPEC["auth"]["action"] == "read"
        assert set(ATTENDANCE_SUMMARY_ENDPOINT_SPEC["responses"].keys()) == {
            "200",
            "401",
            "403",
            "500",
        }

    def test_get_attendance_summary_sample_社労士は成功(self) -> None:
        """社労士は勤怠参照が成功する。"""
        context = AuthContext(user_id="user_001", role="labor_consultant", is_active=True)

        response = get_attendance_summary_sample(context)

        assert response.status_code == 200
        assert response.body["ok"] is True
        assert response.body["data"]["resource"] == "attendance"

    def test_get_attendance_summary_sample_税理士は403(self) -> None:
        """税理士は勤怠参照不可。"""
        context = AuthContext(user_id="user_001", role="tax_accountant", is_active=True)

        response = get_attendance_summary_sample(context)

        assert response.status_code == 403
        assert response.body["ok"] is False

    def test_get_attendance_summary_sample_未認証は401(self) -> None:
        """未認証は401。"""
        response = get_attendance_summary_sample(None)

        assert response.status_code == 401
        assert response.body["ok"] is False

    def test_get_attendance_summary_業務例外は500一般化(self) -> None:
        """業務処理例外は一般化された500で返る。"""

        def attendance_reader(_: AuthContext) -> Mapping[str, Any]:
            raise RuntimeError("internal details")

        context = AuthContext(user_id="user_001", role="labor_consultant", is_active=True)

        response = get_attendance_summary(context, attendance_reader=attendance_reader)

        assert response.status_code == 500
        assert response.body["ok"] is False
        assert response.body["error"] == "処理に失敗しました。時間をおいて再度お試しください"

    def test_get_attendance_summary_監査ログへrecord_idを記録(self) -> None:
        """勤怠参照成功時は record_id を監査ログへ記録する。"""

        def attendance_reader(_: AuthContext) -> Mapping[str, Any]:
            return {
                "record_id": "attendance-record-001",
                "total_records": 1,
                "resource": "attendance",
                "executed_by": "user_001",
            }

        context = AuthContext(user_id="user_001", role="labor_consultant", is_active=True)
        writer = InMemoryAuditLogWriter()

        response = get_attendance_summary(
            context,
            attendance_reader=attendance_reader,
            audit_log_writer=writer,
        )

        assert response.status_code == 200
        assert len(writer.entries) == 1
        assert writer.entries[0].target_resource_id == "attendance-record-001"
