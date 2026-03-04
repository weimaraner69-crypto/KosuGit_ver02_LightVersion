"""business 疑似エンドポイントのテスト。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from business.api import (
    DELETE_DAILY_REPORT_ENDPOINT_SPEC,
    EXPORT_SALES_DATA_ENDPOINT_SPEC,
    REPLACE_DAILY_REPORT_ENDPOINT_SPEC,
    UPDATE_DAILY_REPORT_NOTE_ENDPOINT_SPEC,
    delete_daily_report,
    delete_daily_report_sample,
    export_sales_data,
    export_sales_data_sample,
    replace_daily_report,
    replace_daily_report_sample,
    update_daily_report_note,
    update_daily_report_note_sample,
)
from shared.audit import InMemoryAuditLogWriter
from shared.auth import AuthContext
from shared.csrf import create_csrf_token

if TYPE_CHECKING:
    from collections.abc import Mapping


class TestBusinessApi:
    """business API の認可・応答テスト。"""

    def test_export_sales_data_endpoint_spec_必須項目を持つ(self) -> None:
        """OpenAPI相当の雛形として必須項目を持つ。"""
        assert EXPORT_SALES_DATA_ENDPOINT_SPEC["path"] == "/business/sales/export"
        assert EXPORT_SALES_DATA_ENDPOINT_SPEC["method"] == "POST"
        assert EXPORT_SALES_DATA_ENDPOINT_SPEC["auth"]["resource"] == "business"
        assert EXPORT_SALES_DATA_ENDPOINT_SPEC["auth"]["action"] == "export"
        assert set(EXPORT_SALES_DATA_ENDPOINT_SPEC["responses"].keys()) == {
            "200",
            "401",
            "403",
            "500",
        }

    def test_update_daily_report_note_endpoint_spec_必須項目を持つ(self) -> None:
        """PATCH更新APIの仕様雛形として必須項目を持つ。"""
        assert UPDATE_DAILY_REPORT_NOTE_ENDPOINT_SPEC["path"] == "/business/report/note"
        assert UPDATE_DAILY_REPORT_NOTE_ENDPOINT_SPEC["method"] == "PATCH"
        assert UPDATE_DAILY_REPORT_NOTE_ENDPOINT_SPEC["auth"]["resource"] == "report"
        assert UPDATE_DAILY_REPORT_NOTE_ENDPOINT_SPEC["auth"]["action"] == "update"
        assert set(UPDATE_DAILY_REPORT_NOTE_ENDPOINT_SPEC["responses"].keys()) == {
            "200",
            "401",
            "403",
            "500",
        }

    def test_replace_daily_report_endpoint_spec_必須項目を持つ(self) -> None:
        """PUT更新APIの仕様雛形として必須項目を持つ。"""
        assert REPLACE_DAILY_REPORT_ENDPOINT_SPEC["path"] == "/business/report"
        assert REPLACE_DAILY_REPORT_ENDPOINT_SPEC["method"] == "PUT"
        assert REPLACE_DAILY_REPORT_ENDPOINT_SPEC["auth"]["resource"] == "report"
        assert REPLACE_DAILY_REPORT_ENDPOINT_SPEC["auth"]["action"] == "update"
        assert set(REPLACE_DAILY_REPORT_ENDPOINT_SPEC["responses"].keys()) == {
            "200",
            "401",
            "403",
            "500",
        }

    def test_delete_daily_report_endpoint_spec_必須項目を持つ(self) -> None:
        """DELETE更新APIの仕様雛形として必須項目を持つ。"""
        assert DELETE_DAILY_REPORT_ENDPOINT_SPEC["path"] == "/business/report"
        assert DELETE_DAILY_REPORT_ENDPOINT_SPEC["method"] == "DELETE"
        assert DELETE_DAILY_REPORT_ENDPOINT_SPEC["auth"]["resource"] == "report"
        assert DELETE_DAILY_REPORT_ENDPOINT_SPEC["auth"]["action"] == "delete"
        assert set(DELETE_DAILY_REPORT_ENDPOINT_SPEC["responses"].keys()) == {
            "200",
            "401",
            "403",
            "500",
        }

    def test_export_sales_data_sample_税理士は成功(self) -> None:
        """税理士は売上エクスポートが成功する。"""
        context = AuthContext(user_id="user_001", role="tax_accountant", is_active=True)

        response = export_sales_data_sample(context)

        assert response.status_code == 200
        assert response.body["ok"] is True
        assert response.body["data"]["resource"] == "sales"

    def test_export_sales_data_税理士の許可データセットは成功(self) -> None:
        """税理士の許可データセットのみを含むエクスポートは成功する。"""

        def sales_exporter(_: AuthContext) -> Mapping[str, Any]:
            return {
                "export_id": "export-allowed-001",
                "resource": "sales",
                "datasets": ["sales", "profit_loss", "kpi"],
                "executed_by": "user_001",
            }

        context = AuthContext(user_id="user_001", role="tax_accountant", is_active=True)
        csrf_token = create_csrf_token()

        response = export_sales_data(
            context,
            method="POST",
            csrf_header_token=csrf_token,
            csrf_cookie_token=csrf_token,
            sales_exporter=sales_exporter,
        )

        assert response.status_code == 200
        assert response.body["ok"] is True

    def test_export_sales_data_税理士の禁止データセットは403(self) -> None:
        """税理士が禁止データセットを含む場合は403。"""

        def sales_exporter(_: AuthContext) -> Mapping[str, Any]:
            return {
                "export_id": "export-forbidden-001",
                "resource": "sales",
                "datasets": ["sales", "payroll"],
                "executed_by": "user_001",
            }

        context = AuthContext(user_id="user_001", role="tax_accountant", is_active=True)
        csrf_token = create_csrf_token()

        response = export_sales_data(
            context,
            method="POST",
            csrf_header_token=csrf_token,
            csrf_cookie_token=csrf_token,
            sales_exporter=sales_exporter,
        )

        assert response.status_code == 403
        assert response.body["ok"] is False

    def test_export_sales_data_adminは任意データセットを許可(self) -> None:
        """管理者は任意データセットを含むエクスポートを実行できる。"""

        def sales_exporter(_: AuthContext) -> Mapping[str, Any]:
            return {
                "export_id": "export-admin-001",
                "resource": "sales",
                "datasets": ["sales", "payroll", "attendance"],
                "executed_by": "admin_001",
            }

        context = AuthContext(user_id="admin_001", role="admin", is_active=True)
        csrf_token = create_csrf_token()

        response = export_sales_data(
            context,
            method="POST",
            csrf_header_token=csrf_token,
            csrf_cookie_token=csrf_token,
            sales_exporter=sales_exporter,
        )

        assert response.status_code == 200
        assert response.body["ok"] is True

    def test_export_sales_data_sample_店長は403(self) -> None:
        """店長は売上エクスポート不可。"""
        context = AuthContext(user_id="user_001", role="manager", is_active=True)

        response = export_sales_data_sample(context)

        assert response.status_code == 403
        assert response.body["ok"] is False

    def test_export_sales_data_sample_無効化ユーザーは401(self) -> None:
        """無効化ユーザーは401。"""
        context = AuthContext(user_id="user_001", role="tax_accountant", is_active=False)

        response = export_sales_data_sample(context)

        assert response.status_code == 401
        assert response.body["ok"] is False

    def test_export_sales_data_業務例外は500一般化(self) -> None:
        """業務処理例外は一般化された500で返る。"""

        def sales_exporter(_: AuthContext) -> Mapping[str, Any]:
            raise RuntimeError("internal details")

        context = AuthContext(user_id="user_001", role="tax_accountant", is_active=True)
        csrf_token = create_csrf_token()

        response = export_sales_data(
            context,
            method="POST",
            csrf_header_token=csrf_token,
            csrf_cookie_token=csrf_token,
            sales_exporter=sales_exporter,
        )

        assert response.status_code == 500
        assert response.body["ok"] is False
        assert response.body["error"] == "処理に失敗しました。時間をおいて再度お試しください"

    def test_update_daily_report_note_sample_店長は成功(self) -> None:
        """店長は日報更新が成功する。"""
        context = AuthContext(user_id="user_001", role="manager", is_active=True)

        response = update_daily_report_note_sample(context)

        assert response.status_code == 200
        assert response.body["ok"] is True
        assert response.body["data"]["resource"] == "report"

    def test_update_daily_report_note_sample_税理士は403(self) -> None:
        """税理士は日報更新不可。"""
        context = AuthContext(user_id="user_001", role="tax_accountant", is_active=True)

        response = update_daily_report_note_sample(context)

        assert response.status_code == 403
        assert response.body["ok"] is False

    def test_update_daily_report_note_csrf不一致は403(self) -> None:
        """PATCH更新でCSRF不一致時は403。"""

        def note_updater(_: AuthContext) -> Mapping[str, Any]:
            return {"result": "ok"}

        context = AuthContext(user_id="user_001", role="manager", is_active=True)

        response = update_daily_report_note(
            context,
            method="PATCH",
            csrf_header_token=create_csrf_token(),
            csrf_cookie_token=create_csrf_token(),
            note_updater=note_updater,
        )

        assert response.status_code == 403
        assert response.body["ok"] is False
        assert response.body["error"] == "不正なリクエストです"

    def test_replace_daily_report_sample_店長は成功(self) -> None:
        """店長は日報全体更新が成功する。"""
        context = AuthContext(user_id="user_001", role="manager", is_active=True)

        response = replace_daily_report_sample(context)

        assert response.status_code == 200
        assert response.body["ok"] is True
        assert response.body["data"]["resource"] == "report"

    def test_replace_daily_report_csrf不一致は403(self) -> None:
        """PUT更新でCSRF不一致時は403。"""

        def report_replacer(_: AuthContext) -> Mapping[str, Any]:
            return {"result": "ok"}

        context = AuthContext(user_id="user_001", role="manager", is_active=True)

        response = replace_daily_report(
            context,
            method="PUT",
            csrf_header_token=create_csrf_token(),
            csrf_cookie_token=create_csrf_token(),
            report_replacer=report_replacer,
        )

        assert response.status_code == 403
        assert response.body["ok"] is False
        assert response.body["error"] == "不正なリクエストです"

    def test_delete_daily_report_sample_adminは成功(self) -> None:
        """管理者は日報削除が成功する。"""
        context = AuthContext(user_id="user_001", role="admin", is_active=True)

        response = delete_daily_report_sample(context)

        assert response.status_code == 200
        assert response.body["ok"] is True
        assert response.body["data"]["resource"] == "report"

    def test_delete_daily_report_sample_店長は403(self) -> None:
        """店長は日報削除不可。"""
        context = AuthContext(user_id="user_001", role="manager", is_active=True)

        response = delete_daily_report_sample(context)

        assert response.status_code == 403
        assert response.body["ok"] is False

    def test_delete_daily_report_csrf不一致は403(self) -> None:
        """DELETE更新でCSRF不一致時は403。"""

        def report_deleter(_: AuthContext) -> Mapping[str, Any]:
            return {"result": "ok"}

        context = AuthContext(user_id="user_001", role="admin", is_active=True)

        response = delete_daily_report(
            context,
            method="DELETE",
            csrf_header_token=create_csrf_token(),
            csrf_cookie_token=create_csrf_token(),
            report_deleter=report_deleter,
        )

        assert response.status_code == 403
        assert response.body["ok"] is False
        assert response.body["error"] == "不正なリクエストです"

    def test_export_sales_data_csrfヘッダ欠落は403(self) -> None:
        """更新系でCSRFヘッダ欠落時は403。"""

        def sales_exporter(_: AuthContext) -> Mapping[str, Any]:
            return {"result": "ok"}

        context = AuthContext(user_id="user_001", role="tax_accountant", is_active=True)
        csrf_token = create_csrf_token()

        response = export_sales_data(
            context,
            method="POST",
            csrf_header_token=None,
            csrf_cookie_token=csrf_token,
            sales_exporter=sales_exporter,
        )

        assert response.status_code == 403
        assert response.body["ok"] is False
        assert response.body["error"] == "不正なリクエストです"

    def test_export_sales_data_csrf不一致は403(self) -> None:
        """更新系でCSRFトークン不一致時は403。"""

        def sales_exporter(_: AuthContext) -> Mapping[str, Any]:
            return {"result": "ok"}

        context = AuthContext(user_id="user_001", role="tax_accountant", is_active=True)

        response = export_sales_data(
            context,
            method="POST",
            csrf_header_token=create_csrf_token(),
            csrf_cookie_token=create_csrf_token(),
            sales_exporter=sales_exporter,
        )

        assert response.status_code == 403
        assert response.body["ok"] is False
        assert response.body["error"] == "不正なリクエストです"

    def test_export_sales_data_監査ログへexport_idを記録(self) -> None:
        """売上エクスポート成功時は export_id を監査ログへ記録する。"""

        def sales_exporter(_: AuthContext) -> Mapping[str, Any]:
            return {
                "export_id": "export-001",
                "resource": "sales",
                "executed_by": "user_001",
            }

        context = AuthContext(user_id="user_001", role="tax_accountant", is_active=True)
        csrf_token = create_csrf_token()
        writer = InMemoryAuditLogWriter()

        response = export_sales_data(
            context,
            method="POST",
            csrf_header_token=csrf_token,
            csrf_cookie_token=csrf_token,
            sales_exporter=sales_exporter,
            audit_log_writer=writer,
        )

        assert response.status_code == 200
        assert len(writer.entries) == 1
        assert writer.entries[0].target_resource_id == "export-001"

    def test_update_daily_report_note_監査ログへreport_idを記録(self) -> None:
        """日報更新成功時は report_id を監査ログへ記録する。"""

        def note_updater(_: AuthContext) -> Mapping[str, Any]:
            return {
                "report_id": "report-123",
                "updated": True,
                "resource": "report",
                "executed_by": "user_001",
            }

        context = AuthContext(user_id="user_001", role="manager", is_active=True)
        csrf_token = create_csrf_token()
        writer = InMemoryAuditLogWriter()

        response = update_daily_report_note(
            context,
            method="PATCH",
            csrf_header_token=csrf_token,
            csrf_cookie_token=csrf_token,
            note_updater=note_updater,
            audit_log_writer=writer,
        )

        assert response.status_code == 200
        assert len(writer.entries) == 1
        assert writer.entries[0].target_resource_id == "report-123"
