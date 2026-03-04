"""CSRF 防御共通ロジックのテスト。"""

from __future__ import annotations

import pytest

from shared.csrf import create_csrf_token, requires_csrf_validation, validate_csrf_tokens
from shared.exceptions import AuthorizationError


class TestCreateCsrfToken:
    """create_csrf_token のテスト。"""

    def test_create_csrf_token_正常系(self) -> None:
        """CSRF トークンを生成できる。"""
        token = create_csrf_token()

        assert isinstance(token, str)
        assert len(token) > 20

    def test_create_csrf_token_不正サイズでエラー(self) -> None:
        """token_size が0以下の場合はエラー。"""
        with pytest.raises(ValueError, match="token_size"):
            create_csrf_token(0)


class TestRequiresCsrfValidation:
    """requires_csrf_validation のテスト。"""

    def test_requires_csrf_validation_getは対象外(self) -> None:
        """GET は CSRF 検証対象外。"""
        assert requires_csrf_validation("GET") is False

    def test_requires_csrf_validation_postは対象(self) -> None:
        """POST は CSRF 検証対象。"""
        assert requires_csrf_validation("POST") is True

    def test_requires_csrf_validation_空文字でエラー(self) -> None:
        """空メソッドはエラー。"""
        with pytest.raises(ValueError, match="method"):
            requires_csrf_validation("")


class TestValidateCsrfTokens:
    """validate_csrf_tokens のテスト。"""

    def test_validate_csrf_tokens_getは検証不要(self) -> None:
        """GET はトークン無しでも通過する。"""
        validate_csrf_tokens(
            method="GET",
            header_token=None,
            cookie_token=None,
        )

    def test_validate_csrf_tokens_post_トークン一致で通過(self) -> None:
        """POST でヘッダとCookieが一致すれば通過する。"""
        token = create_csrf_token()

        validate_csrf_tokens(
            method="POST",
            header_token=token,
            cookie_token=token,
        )

    def test_validate_csrf_tokens_post_ヘッダなしで拒否(self) -> None:
        """POST でヘッダトークンが無い場合は拒否する。"""
        token = create_csrf_token()

        with pytest.raises(AuthorizationError, match="不正なリクエストです"):
            validate_csrf_tokens(
                method="POST",
                header_token=None,
                cookie_token=token,
            )

    def test_validate_csrf_tokens_post_cookieなしで拒否(self) -> None:
        """POST でCookieトークンが無い場合は拒否する。"""
        token = create_csrf_token()

        with pytest.raises(AuthorizationError, match="不正なリクエストです"):
            validate_csrf_tokens(
                method="POST",
                header_token=token,
                cookie_token=None,
            )

    def test_validate_csrf_tokens_post_不一致で拒否(self) -> None:
        """POST でトークン不一致は拒否する。"""
        with pytest.raises(AuthorizationError, match="不正なリクエストです"):
            validate_csrf_tokens(
                method="POST",
                header_token=create_csrf_token(),
                cookie_token=create_csrf_token(),
            )
