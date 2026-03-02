"""共通セキュリティ機能のテスト"""

import pytest

from shared.exceptions import (
    AuthenticationError,
    AuthorizationError,
    ValidationError,
)
from shared.security import (
    User,
    hash_password,
    sanitize_input,
    verify_password,
)


class TestUser:
    """User クラスのテスト"""

    def test_user_creation_正常系(self) -> None:
        """ユーザーの正常作成"""
        user = User(
            user_id="user_001",
            username="john_doe",
            role="admin",
        )

        assert user.user_id == "user_001"
        assert user.username == "john_doe"
        assert user.role == "admin"
        assert user.is_active is True

    def test_user_空のユーザーIDでエラー(self) -> None:
        """ユーザーIDが空の場合はエラー"""
        with pytest.raises(ValueError, match="ユーザーIDは必須です"):
            User(user_id="", username="john_doe", role="admin")


class TestPasswordHashing:
    """パスワードハッシュ化のテスト"""

    def test_hash_password_正常系(self) -> None:
        """パスワードのハッシュ化"""
        password = "my_secret_password"
        password_hash, salt = hash_password(password)

        # ハッシュは平文とは異なる
        assert password_hash != password
        # ハッシュは固定長（SHA-256 の16進数表現）
        assert len(password_hash) == 64
        # ソルトは生成される
        assert len(salt) > 0

    def test_hash_password_空のパスワードでエラー(self) -> None:
        """空のパスワードはエラー"""
        with pytest.raises(ValueError, match="パスワードは必須です"):
            hash_password("")

    def test_verify_password_正常系(self) -> None:
        """パスワードの検証が成功する"""
        password = "my_secret_password"
        password_hash, salt = hash_password(password)

        # 正しいパスワードは検証成功
        assert verify_password(password, password_hash, salt) is True

    def test_verify_password_誤ったパスワードで失敗(self) -> None:
        """誤ったパスワードは検証失敗"""
        password = "my_secret_password"
        password_hash, salt = hash_password(password)

        # 誤ったパスワードは検証失敗
        assert verify_password("wrong_password", password_hash, salt) is False


class TestSanitizeInput:
    """入力サニタイゼーションのテスト"""

    def test_sanitize_input_正常系(self) -> None:
        """入力値のサニタイズ"""
        value = "  hello world  "
        sanitized = sanitize_input(value)

        # 前後の空白が削除される
        assert sanitized == "hello world"

    def test_sanitize_input_空の値でエラー(self) -> None:
        """空の値はエラー"""
        with pytest.raises(ValueError, match="値は必須です"):
            sanitize_input("")

    def test_sanitize_input_最大長超過でエラー(self) -> None:
        """最大長を超える値はエラー"""
        value = "a" * 256
        with pytest.raises(ValueError, match="値は255文字以内である必要があります"):
            sanitize_input(value, max_length=255)


class TestExceptions:
    """例外クラスのテスト"""

    def test_authentication_error(self) -> None:
        """AuthenticationError の送出"""
        with pytest.raises(AuthenticationError):
            raise AuthenticationError("認証に失敗しました")

    def test_authorization_error(self) -> None:
        """AuthorizationError の送出"""
        with pytest.raises(AuthorizationError):
            raise AuthorizationError("権限がありません")

    def test_validation_error(self) -> None:
        """ValidationError の送出"""
        with pytest.raises(ValidationError):
            raise ValidationError("バリデーションエラー")
