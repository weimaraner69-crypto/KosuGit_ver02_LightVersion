"""認証共通ロジックのテスト。"""

import pytest

from shared.auth import (
    AuthContext,
    ensure_active_user,
    require_active_authenticated_user,
    require_authenticated_user,
)
from shared.exceptions import AuthenticationError


class TestAuthContext:
    """AuthContext のテスト。"""

    def test_auth_context_正常作成(self) -> None:
        """認証コンテキストを正常に作成できる。"""
        context = AuthContext(user_id="user_001", role="manager", is_active=True)

        assert context.user_id == "user_001"
        assert context.role == "manager"
        assert context.is_active is True

    def test_auth_context_ユーザーID空でエラー(self) -> None:
        """ユーザーIDが空の場合はエラー。"""
        with pytest.raises(ValueError, match="ユーザーIDは必須です"):
            AuthContext(user_id="", role="manager", is_active=True)

    def test_auth_context_ロール空でエラー(self) -> None:
        """ロールが空の場合はエラー。"""
        with pytest.raises(ValueError, match="ロールは必須です"):
            AuthContext(user_id="user_001", role="", is_active=True)


class TestAuthenticationGuard:
    """認証ガード関数のテスト。"""

    def test_require_authenticated_user_未認証でエラー(self) -> None:
        """認証コンテキストがない場合はエラー。"""
        with pytest.raises(AuthenticationError, match="ユーザー名またはパスワードが正しくありません"):
            require_authenticated_user(None)

    def test_require_authenticated_user_認証済みは通過(self) -> None:
        """認証済みコンテキストは通過する。"""
        context = AuthContext(user_id="user_001", role="manager", is_active=True)

        result = require_authenticated_user(context)

        assert result == context

    def test_ensure_active_user_無効化ユーザーでエラー(self) -> None:
        """無効化ユーザーはエラー。"""
        context = AuthContext(user_id="user_001", role="manager", is_active=False)

        with pytest.raises(AuthenticationError, match="ユーザー名またはパスワードが正しくありません"):
            ensure_active_user(context)

    def test_ensure_active_user_有効ユーザーは通過(self) -> None:
        """有効ユーザーは通過する。"""
        context = AuthContext(user_id="user_001", role="manager", is_active=True)

        result = ensure_active_user(context)

        assert result == context

    def test_require_active_authenticated_user_未認証でエラー(self) -> None:
        """未認証ユーザーはエラー。"""
        with pytest.raises(AuthenticationError, match="ユーザー名またはパスワードが正しくありません"):
            require_active_authenticated_user(None)

    def test_require_active_authenticated_user_無効化ユーザーでエラー(self) -> None:
        """無効化ユーザーはエラー。"""
        context = AuthContext(user_id="user_001", role="manager", is_active=False)

        with pytest.raises(AuthenticationError, match="ユーザー名またはパスワードが正しくありません"):
            require_active_authenticated_user(context)

    def test_require_active_authenticated_user_有効ユーザーは通過(self) -> None:
        """認証済みかつ有効ユーザーは通過する。"""
        context = AuthContext(user_id="user_001", role="manager", is_active=True)

        result = require_active_authenticated_user(context)

        assert result == context
