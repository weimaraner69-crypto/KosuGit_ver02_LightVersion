# セキュリティ・個人情報保護ガイド

## はじめに

このシステムは中小企業の業務管理を目的としており、従業員の個人情報、勤怠情報、売上データなど機密性の高い情報を扱います。データ漏洩や不正アクセスを防ぐため、セキュリティと個人情報保護を最優先事項としています。

## セキュリティポリシー

### 絶対禁止事項

以下の行為は**絶対に禁止**です。違反した場合、即座に開発を中止します。

#### 1. 秘密情報のハードコーディング

❌ **禁止**:

```python
# 絶対にやってはいけない
API_KEY = "AKIA1234567890ABCDEF"
PASSWORD = "my_password"
DATABASE_URL = "postgresql://user:pass@localhost/db"
```

✅ **正しい方法**:

```python
# 環境変数から読み込む
import os
API_KEY = os.environ.get("API_KEY")
```

#### 2. 個人情報のログ出力

❌ **禁止**:

```python
# 個人情報をログに出力してはいけない
logger.info(f"User: {user.name}, Email: {user.email}")
```

✅ **正しい方法**:

```python
# ユーザーIDのみをログに出力
logger.info(f"User ID: {user.user_id}")
```

#### 3. 平文パスワードの保存

❌ **禁止**:

```python
# パスワードを平文で保存してはいけない
user.password = "my_password"
```

✅ **正しい方法**:

```python
from shared.security import hash_password

# パスワードをハッシュ化して保存
password_hash, salt = hash_password("my_password")
```

### CI による自動チェック

`ci/policy_check.py` が以下のパターンを自動検出します：

- API キー: `AKIA*`, `AIza*`
- GitHub トークン: `ghp_*`, `gho_*`
- JWT トークン: `eyJ*`
- プライベートキー: `-----BEGIN PRIVATE KEY-----`
- パスワード: `password = "..."`, `passwd = "..."`

## 個人情報保護

### 個人情報の定義

このシステムで扱う個人情報：

- **識別情報**: 氏名、メールアドレス、電話番号
- **勤怠情報**: 出退勤時刻、労働時間、シフト
- **財務情報**: 給与、時給、人件費
- **教育情報**: 学習進捗、成績

### 個人情報の取り扱い原則

#### 1. 最小限の収集

必要最小限の個人情報のみを収集する。

#### 2. 暗号化

機密性の高い情報は暗号化して保存する。

```python
from cryptography.fernet import Fernet

# 暗号化
key = Fernet.generate_key()
cipher = Fernet(key)
encrypted_data = cipher.encrypt(b"sensitive data")

# 復号化
decrypted_data = cipher.decrypt(encrypted_data)
```

#### 3. アクセス制御

個人情報へのアクセスは権限を持つユーザーのみに制限する。

```python
from shared.exceptions import AuthorizationError

def get_employee_salary(user: User, employee_id: str) -> Decimal:
    """従業員の給与を取得（管理者のみ）"""
    if user.role != "admin":
        raise AuthorizationError("給与情報へのアクセス権限がありません")

    # 給与情報を取得
    ...
```

#### 4. 論理削除

データ削除は物理削除ではなく、論理削除を優先する。

```python
@dataclass
class Employee:
    employee_id: str
    name: str
    is_deleted: bool = False  # 論理削除フラグ
    deleted_at: Optional[datetime] = None
```

#### 5. 監査ログ

重要な操作は監査ログに記録する（ただし個人情報は含めない）。

```python
logger.info(f"Action: update_salary, User: {user.user_id}, Target: {employee_id}")
```

## 認証・認可

### パスワード管理

パスワードは必ずハッシュ化して保存する：

```python
from shared.security import hash_password, verify_password

# パスワードのハッシュ化
password_hash, salt = hash_password("my_password")

# パスワードの検証
is_valid = verify_password("my_password", password_hash, salt)
```

### 認証

```python
from shared.exceptions import AuthenticationError

def authenticate(username: str, password: str) -> User:
    """ユーザー認証"""
    user = get_user_by_username(username)
    if not user:
        raise AuthenticationError("ユーザー名またはパスワードが正しくありません")

    if not verify_password(password, user.password_hash, user.salt):
        raise AuthenticationError("ユーザー名またはパスワードが正しくありません")

    return user
```

### 認可

```python
from shared.exceptions import AuthorizationError

def require_role(user: User, required_role: str) -> None:
    """ロールチェック"""
    if user.role != required_role:
        raise AuthorizationError(f"{required_role} ロールが必要です")
```

## 入力検証

### サニタイゼーション

すべての入力値は必ずサニタイズする：

```python
from shared.security import sanitize_input

def create_user(username: str, email: str) -> User:
    """ユーザー作成"""
    # 入力値をサニタイズ
    username = sanitize_input(username, max_length=50)
    email = sanitize_input(email, max_length=255)

    # バリデーション
    if not is_valid_email(email):
        raise ValidationError("メールアドレスの形式が正しくありません")

    # ユーザー作成
    ...
```

### SQL インジェクション対策

プリペアドステートメントを使用する：

```python
# ❌ 禁止: 文字列連結
query = f"SELECT * FROM users WHERE username = '{username}'"

# ✅ 正しい方法: プリペアドステートメント
query = "SELECT * FROM users WHERE username = ?"
cursor.execute(query, (username,))
```

### XSS 対策

出力時にエスケープ処理を行う：

```python
import html

# HTMLエスケープ
safe_content = html.escape(user_input)
```

## データ保全

### トランザクション

データベース操作は必ずトランザクション内で行う：

```python
def transfer_funds(from_account: str, to_account: str, amount: Decimal) -> None:
    """資金移動（トランザクション処理）"""
    with db.transaction():
        # 出金
        debit(from_account, amount)
        # 入金
        credit(to_account, amount)
        # コミット（成功時）または ロールバック（失敗時）
```

### バックアップ

重要なデータは定期的にバックアップする：

```bash
# データベースバックアップ
pg_dump mydb > backup_$(date +%Y%m%d).sql

# バックアップの暗号化
gpg --encrypt backup_20260302.sql
```

### データ整合性

データベース制約を定義する：

```sql
-- NOT NULL 制約
CREATE TABLE employees (
    employee_id VARCHAR(50) NOT NULL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE
);

-- 外部キー制約
CREATE TABLE attendance_records (
    record_id VARCHAR(50) NOT NULL PRIMARY KEY,
    employee_id VARCHAR(50) NOT NULL,
    FOREIGN KEY (employee_id) REFERENCES employees(employee_id)
);

-- CHECK 制約
CREATE TABLE shifts (
    shift_id VARCHAR(50) NOT NULL PRIMARY KEY,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP NOT NULL,
    CHECK (end_time > start_time)
);
```

## セキュリティテスト

### テスト項目

- 未認証アクセスの拒否
- 権限外の操作の拒否
- SQL インジェクション防御
- XSS 防御
- CSRF 防御
- パスワードハッシュ化
- 個人情報のログ出力がないこと

### テスト例

```python
def test_未認証アクセスは拒否される() -> None:
    """未認証ユーザーは機密情報にアクセスできない"""
    with pytest.raises(AuthenticationError):
        get_employee_salary(None, "employee_001")


def test_権限外の操作は拒否される() -> None:
    """一般ユーザーは給与情報にアクセスできない"""
    user = User(user_id="user_001", username="john", role="employee")

    with pytest.raises(AuthorizationError):
        get_employee_salary(user, "employee_001")


def test_パスワードはハッシュ化される() -> None:
    """パスワードは平文で保存されない"""
    password = "my_secret_password"
    password_hash, salt = hash_password(password)

    # ハッシュは平文とは異なる
    assert password_hash != password
    # ハッシュは固定長
    assert len(password_hash) == 64
    # 検証は成功する
    assert verify_password(password, password_hash, salt)
```

## インシデント対応

### セキュリティインシデントの定義

- 秘密情報の漏洩
- 個人情報の不正アクセス
- データベースの改ざん
- 不正ログイン

### 対応手順

1. **検知**: ログ、アラート、報告
2. **隔離**: 影響範囲の特定と隔離
3. **調査**: 原因の特定
4. **復旧**: データ復旧、パッチ適用
5. **報告**: 関係者への報告
6. **再発防止**: 対策の実施

### 連絡先

セキュリティインシデントを発見した場合は、直ちに以下に報告してください：

- **緊急連絡先**: [担当者のメールアドレス]
- **報告内容**: インシデントの内容、発生日時、影響範囲

## チェックリスト

開発時のセキュリティチェックリスト：

- [ ] 秘密情報をハードコーディングしていない
- [ ] 個人情報をログに出力していない
- [ ] パスワードをハッシュ化している
- [ ] 入力値をサニタイズしている
- [ ] SQL インジェクション対策をしている
- [ ] XSS 対策をしている
- [ ] 認証・認可を実装している
- [ ] トランザクション処理を実装している
- [ ] データバックアップ機能を実装している
- [ ] セキュリティテストを作成している
- [ ] CI でセキュリティチェックが成功している

## 参考資料

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [個人情報保護法](https://www.ppc.go.jp/)
- [Python Security Best Practices](https://python.readthedocs.io/en/stable/library/security_warnings.html)
