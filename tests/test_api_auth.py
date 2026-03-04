"""API 認証・認可アダプタのテスト。"""

from __future__ import annotations

import pytest

from shared.api_auth import authorize_api_request, to_api_error_response
from shared.auth import AuthContext
from shared.exceptions import AuthenticationError, AuthorizationError


class TestAuthorizeApiRequest:
    """authorize_api_request のテスト。"""

    def test_authorize_api_request_権限ありは通過(self) -> None:
        """権限がある場合はコンテキストが返る。"""
        context = AuthContext(user_id="user_001", role="tax_accountant", is_active=True)

        result = authorize_api_request(context, resource="sales", action="read")

        assert result == context

    def test_authorize_api_request_未認証は認証エラー(self) -> None:
        """未認証は AuthenticationError。"""
        with pytest.raises(AuthenticationError, match="ユーザー名またはパスワードが正しくありません"):
            authorize_api_request(None, resource="sales", action="read")

    def test_authorize_api_request_権限不足は認可エラー(self) -> None:
        """権限不足は AuthorizationError。"""
        context = AuthContext(user_id="user_001", role="tax_accountant", is_active=True)

        with pytest.raises(AuthorizationError, match="この操作を実行する権限がありません"):
            authorize_api_request(context, resource="attendance", action="read")


class TestToApiErrorResponse:
    """to_api_error_response のテスト。"""

    def test_to_api_error_response_認証エラーを401に変換(self) -> None:
        """AuthenticationError を 401 に変換する。"""
        error = AuthenticationError("ユーザー名またはパスワードが正しくありません")

        response = to_api_error_response(error)

        assert response.status_code == 401
        assert response.message == "ユーザー名またはパスワードが正しくありません"

    def test_to_api_error_response_認可エラーを403に変換(self) -> None:
        """AuthorizationError を 403 に変換する。"""
        error = AuthorizationError("この操作を実行する権限がありません")

        response = to_api_error_response(error)

        assert response.status_code == 403
        assert response.message == "この操作を実行する権限がありません"

    def test_to_api_error_response_想定外例外を500に変換(self) -> None:
        """想定外例外を一般化メッセージ付き 500 に変換する。"""
        response = to_api_error_response(RuntimeError("internal details"))

        assert response.status_code == 500
        assert response.message == "処理に失敗しました。時間をおいて再度お試しください"
