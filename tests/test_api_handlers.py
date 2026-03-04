"""API ハンドラテンプレートのテスト。"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from shared.api_handlers import (
    execute_authorized_action,
    execute_authorized_mutation,
    handle_attendance_read_request,
    handle_sales_export_request,
)
from shared.audit import InMemoryAuditLogWriter
from shared.auth import AuthContext
from shared.csrf import create_csrf_token


class TestSampleHandlers:
    """サンプルハンドラの認可挙動テスト。"""

    def test_handle_sales_export_request_税理士は成功(self) -> None:
        """税理士ロールは売上エクスポート可能。"""
        context = AuthContext(user_id="user_001", role="tax_accountant", is_active=True)

        response = handle_sales_export_request(context)

        assert response.status_code == 200
        assert response.body["ok"] is True
        assert response.body["data"]["resource"] == "sales"

    def test_handle_sales_export_request_店長は権限不足(self) -> None:
        """店長は売上エクスポート不可。"""
        context = AuthContext(user_id="user_001", role="manager", is_active=True)

        response = handle_sales_export_request(context)

        assert response.status_code == 403
        assert response.body["ok"] is False

    def test_handle_attendance_read_request_社労士は成功(self) -> None:
        """社労士ロールは勤怠参照可能。"""
        context = AuthContext(user_id="user_001", role="labor_consultant", is_active=True)

        response = handle_attendance_read_request(context)

        assert response.status_code == 200
        assert response.body["ok"] is True
        assert response.body["data"]["resource"] == "attendance"

    def test_handle_attendance_read_request_税理士は権限不足(self) -> None:
        """税理士ロールは勤怠参照不可。"""
        context = AuthContext(user_id="user_001", role="tax_accountant", is_active=True)

        response = handle_attendance_read_request(context)

        assert response.status_code == 403
        assert response.body["ok"] is False

    def test_handle_sales_export_request_未認証は401(self) -> None:
        """未認証ユーザーは401。"""
        response = handle_sales_export_request(None)

        assert response.status_code == 401
        assert response.body["ok"] is False

    def test_handle_sales_export_request_無効化ユーザーは401(self) -> None:
        """無効化ユーザーは401。"""
        context = AuthContext(user_id="user_001", role="tax_accountant", is_active=False)

        response = handle_sales_export_request(context)

        assert response.status_code == 401
        assert response.body["ok"] is False


class TestExecuteAuthorizedAction:
    """共通テンプレートのテスト。"""

    def test_execute_authorized_action_想定外例外は500一般化(self) -> None:
        """業務処理例外は一般化された500で返る。"""

        def operation(_: AuthContext) -> Mapping[str, Any]:
            raise RuntimeError("internal details")

        context = AuthContext(user_id="user_001", role="admin", is_active=True)

        response = execute_authorized_action(
            context,
            resource="sales",
            action="read",
            operation=operation,
        )

        assert response.status_code == 500
        assert response.body["ok"] is False
        assert response.body["error"] == "処理に失敗しました。時間をおいて再度お試しください"

    def test_execute_authorized_action_成功時に監査ログ記録(self) -> None:
        """成功時は監査ログへ success を記録する。"""

        def operation(_: AuthContext) -> Mapping[str, Any]:
            return {"result": "ok"}

        context = AuthContext(user_id="user_001", role="admin", is_active=True)
        writer = InMemoryAuditLogWriter()

        response = execute_authorized_action(
            context,
            resource="sales",
            action="export",
            operation=operation,
            audit_log_writer=writer,
            target_resource_id="sales-export-001",
        )

        assert response.status_code == 200
        assert len(writer.entries) == 1
        entry = writer.entries[0]
        assert entry.actor_user_id == "user_001"
        assert entry.actor_role == "admin"
        assert entry.resource == "sales"
        assert entry.action == "export"
        assert entry.result == "success"
        assert entry.target_resource_id == "sales-export-001"

    def test_execute_authorized_action_失敗時に監査ログ記録(self) -> None:
        """失敗時は監査ログへ failure を記録する。"""

        def operation(_: AuthContext) -> Mapping[str, Any]:
            raise RuntimeError("internal details")

        context = AuthContext(user_id="user_001", role="admin", is_active=True)
        writer = InMemoryAuditLogWriter()

        response = execute_authorized_action(
            context,
            resource="sales",
            action="read",
            operation=operation,
            audit_log_writer=writer,
        )

        assert response.status_code == 500
        assert len(writer.entries) == 1
        entry = writer.entries[0]
        assert entry.result == "failure"
        assert entry.error_type == "RuntimeError"

    def test_execute_authorized_action_成功時に結果から対象ID抽出(self) -> None:
        """成功時は業務結果から target_resource_id を抽出できる。"""

        def operation(_: AuthContext) -> Mapping[str, Any]:
            return {"report_id": "report-001", "updated": True}

        context = AuthContext(user_id="user_001", role="admin", is_active=True)
        writer = InMemoryAuditLogWriter()

        response = execute_authorized_action(
            context,
            resource="report",
            action="update",
            operation=operation,
            audit_log_writer=writer,
            target_resource_id_getter=lambda result: str(result.get("report_id")),
        )

        assert response.status_code == 200
        assert len(writer.entries) == 1
        entry = writer.entries[0]
        assert entry.target_resource_id == "report-001"


class TestExecuteAuthorizedMutation:
    """CSRF付き更新系テンプレートのテスト。"""

    def test_execute_authorized_mutation_csrf一致で成功(self) -> None:
        """CSRF一致時は更新系処理が実行される。"""

        def operation(_: AuthContext) -> Mapping[str, Any]:
            return {"result": "ok"}

        context = AuthContext(user_id="user_001", role="tax_accountant", is_active=True)
        csrf_token = create_csrf_token()

        response = execute_authorized_mutation(
            context,
            resource="sales",
            action="export",
            method="POST",
            csrf_header_token=csrf_token,
            csrf_cookie_token=csrf_token,
            operation=operation,
        )

        assert response.status_code == 200
        assert response.body["ok"] is True

    def test_execute_authorized_mutation_csrf欠落で403(self) -> None:
        """CSRFトークン欠落時は403。"""

        def operation(_: AuthContext) -> Mapping[str, Any]:
            return {"result": "ok"}

        context = AuthContext(user_id="user_001", role="tax_accountant", is_active=True)

        response = execute_authorized_mutation(
            context,
            resource="sales",
            action="export",
            method="POST",
            csrf_header_token=None,
            csrf_cookie_token=create_csrf_token(),
            operation=operation,
        )

        assert response.status_code == 403
        assert response.body["ok"] is False
        assert response.body["error"] == "不正なリクエストです"

    def test_execute_authorized_mutation_csrf失敗時に監査ログ記録(self) -> None:
        """CSRF失敗時は failure で監査ログ記録する。"""

        def operation(_: AuthContext) -> Mapping[str, Any]:
            return {"result": "ok"}

        context = AuthContext(user_id="user_001", role="tax_accountant", is_active=True)
        writer = InMemoryAuditLogWriter()

        response = execute_authorized_mutation(
            context,
            resource="sales",
            action="export",
            method="POST",
            csrf_header_token=None,
            csrf_cookie_token=create_csrf_token(),
            operation=operation,
            audit_log_writer=writer,
        )

        assert response.status_code == 403
        assert len(writer.entries) == 1
        entry = writer.entries[0]
        assert entry.result == "failure"
        assert entry.error_type == "AuthorizationError"
