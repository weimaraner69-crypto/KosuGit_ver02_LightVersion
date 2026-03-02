# Copilot Repository Instructions

## Language（最優先）

- すべての成果物（PR タイトル/本文、Issue 本文、コメント）は日本語で書く。
- コードの識別子は英語でよいが、コメント・docstring・説明文は日本語で書く。

## Security & Privacy（最優先）

### 絶対禁止事項

- **P-001**: API キー/トークン/認証情報/個人情報/実データをコミットしない。`.env` はローカルのみ。
- **P-002**: 個人情報をログに出力しない。
- **P-003**: パスワードを平文で保存しない（必ずハッシュ化）。
- **P-004**: 入力値は必ずサニタイズする。

詳細は `docs/security.md` を参照。

## Development Workflow

1. **Issue 作成**: 実装する機能・修正するバグを Issue で定義
2. **ブランチ作成**: `feature/機能名` または `fix/バグ名` でブランチを作成
3. **実装**: コードと単体テストを同時に作成
4. **ローカルテスト**: CI と同じチェックをローカルで実行
   ```bash
   pytest --cov=src
   mypy src
   ruff check src tests
   python ci/policy_check.py
   ```
5. **PR 作成**: レビュー用に PR を作成
6. **レビュー**: Reviewer エージェントまたは人間がレビュー
7. **マージ**: 承認後に main ブランチにマージ

## Coding Standards

### Python スタイル

- Python 3.11+ の型ヒントを必須とする
- PEP 8 に従う（ruff で自動チェック）
- frozen dataclass を使用し、不変条件を `__post_init__` で検証

### Design by Contract

```python
@dataclass(frozen=True)
class User:
    user_id: str
    username: str

    def __post_init__(self) -> None:
        if not self.user_id:
            raise ValueError("ユーザーIDは必須です")
        if len(self.username) < 3:
            raise ValueError("ユーザー名は3文字以上である必要があります")
```

### セキュリティ

- 入力値のサニタイズ: `shared.security.sanitize_input` を使用
- パスワードのハッシュ化: `shared.security.hash_password` を使用
- トランザクション処理: データベース操作は必ずトランザクション内で行う
- 論理削除: データ削除は論理削除を優先する

## Testing

- AAA パターン（Arrange, Act, Assert）に従う
- テスト名は日本語で意図を明確に記述
- カバレッジ 80% 以上を目標
- セキュリティテストを必ず含める

```python
def test_hash_password_正常系() -> None:
    """パスワードのハッシュ化"""
    password = "my_secret_password"
    password_hash, salt = hash_password(password)

    assert password_hash != password
    assert len(password_hash) == 64
```

## Documentation

- `docs/README.md`: プロジェクト概要
- `docs/development.md`: 開発ガイド
- `docs/security.md`: セキュリティ・個人情報保護ガイド

## Agents

開発を支援する3つのエージェント：

- **Developer**: コード実装と機能開発
- **Tester**: テスト作成と品質保証
- **Reviewer**: コードレビューと品質監査

詳細は `.github/agents/` を参照。

