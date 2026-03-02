"""共通例外クラス"""


class ApplicationError(Exception):
    """アプリケーション基底例外"""
    pass


class AuthenticationError(ApplicationError):
    """認証エラー"""
    pass


class AuthorizationError(ApplicationError):
    """認可エラー"""
    pass


class ValidationError(ApplicationError):
    """バリデーションエラー"""
    pass


class DatabaseError(ApplicationError):
    """データベースエラー"""
    pass


class SecurityError(ApplicationError):
    """セキュリティエラー（個人情報流出リスク等）"""
    pass
