"""RBAC 共通ロジックのテスト。"""

import pytest

from shared.auth import AuthContext
from shared.exceptions import AuthenticationError, AuthorizationError
from shared.rbac import has_permission, require_permission


class TestHasPermission:
    """has_permission のテスト。"""

    def test_admin_全操作が許可される(self) -> None:
        """管理者ロールは全リソース全操作が許可される。"""
        assert has_permission("admin", "payroll", "read") is True
        assert has_permission("admin", "sales", "export") is True
        assert has_permission("admin", "attendance", "delete") is True

    def test_manager_日報作成が許可される(self) -> None:
        """店長は日報の作成が許可される。"""
        assert has_permission("manager", "report", "create") is True

    def test_manager_給与明細参照は拒否される(self) -> None:
        """店長は給与明細へのアクセスが拒否される。"""
        assert has_permission("manager", "payroll", "read") is False

    def test_labor_consultant_勤怠給与kpiの参照出力が許可される(self) -> None:
        """社労士ロールは勤怠・給与・KPIの参照/出力のみ許可される。"""
        assert has_permission("labor_consultant", "attendance", "read") is True
        assert has_permission("labor_consultant", "attendance", "export") is True
        assert has_permission("labor_consultant", "payroll", "read") is True
        assert has_permission("labor_consultant", "payroll", "export") is True
        assert has_permission("labor_consultant", "kpi", "read") is True
        assert has_permission("labor_consultant", "kpi", "export") is True

    def test_labor_consultant_売上更新は拒否される(self) -> None:
        """社労士ロールは売上更新を実行できない。"""
        assert has_permission("labor_consultant", "sales", "update") is False

    def test_tax_accountant_会計データ参照出力が許可される(self) -> None:
        """税理士ロールは会計データの参照/出力が許可される。"""
        assert has_permission("tax_accountant", "sales", "read") is True
        assert has_permission("tax_accountant", "sales", "export") is True
        assert has_permission("tax_accountant", "expense", "read") is True
        assert has_permission("tax_accountant", "profit_loss", "export") is True

    def test_tax_accountant_勤怠参照は拒否される(self) -> None:
        """税理士ロールは勤怠データを参照できない。"""
        assert has_permission("tax_accountant", "attendance", "read") is False

    def test_不正な操作種別でエラー(self) -> None:
        """不正な操作種別は ValueError。"""
        with pytest.raises(ValueError, match="不正な操作種別です"):
            has_permission("admin", "sales", "invalid")


class TestRequirePermission:
    """require_permission のテスト。"""

    def test_未認証は認証エラー(self) -> None:
        """未認証コンテキストは AuthenticationError。"""
        with pytest.raises(AuthenticationError, match="ユーザー名またはパスワードが正しくありません"):
            require_permission(None, resource="sales", action="read")

    def test_無効化ユーザーは認証エラー(self) -> None:
        """無効化ユーザーは AuthenticationError。"""
        context = AuthContext(user_id="u001", role="manager", is_active=False)

        with pytest.raises(AuthenticationError, match="ユーザー名またはパスワードが正しくありません"):
            require_permission(context, resource="sales", action="read")

    def test_権限不足は認可エラー(self) -> None:
        """権限不足は AuthorizationError。"""
        context = AuthContext(user_id="u001", role="tax_accountant", is_active=True)

        with pytest.raises(AuthorizationError, match="この操作を実行する権限がありません"):
            require_permission(context, resource="attendance", action="read")

    def test_権限ありは通過(self) -> None:
        """権限がある場合はコンテキストを返す。"""
        context = AuthContext(user_id="u001", role="labor_consultant", is_active=True)

        result = require_permission(context, resource="payroll", action="export")

        assert result == context
