# 開発ガイド

## 開発フロー

1. **Issue 作成**: 実装する機能・修正するバグを Issue で定義
2. **ブランチ作成**: `feature/機能名` または `fix/バグ名` でブランチを作成
3. **実装**: コードと単体テストを同時に作成
4. **ローカルテスト**: CI と同じチェックをローカルで実行
5. **PR 作成**: レビュー用に PR を作成
6. **レビュー**: Reviewer エージェントまたは人間がレビュー
7. **マージ**: 承認後に main ブランチにマージ

## コーディング規約

### Python スタイル

- Python 3.11+ の型ヒントを必須とする
- PEP 8 に従う（ruff で自動チェック）
- 行長: 100 文字以内
- インポート順: 標準ライブラリ → サードパーティ → ローカル

### 命名規則

- **クラス**: PascalCase（例: `AttendanceRecord`）
- **関数・変数**: snake_case（例: `get_user_by_id`）
- **定数**: UPPER_CASE（例: `MAX_RETRY_COUNT`）
- **プライベート**: 先頭にアンダースコア（例: `_internal_method`）

### docstring

すべての公開クラス・関数に docstring を記述する：

```python
def calculate_labor_cost(hourly_rate: Decimal, hours: Decimal) -> Decimal:
    """
    人件費を計算する

    Args:
        hourly_rate: 時給
        hours: 労働時間

    Returns:
        人件費

    Raises:
        ValueError: 時給または労働時間が負の値の場合
    """
    if hourly_rate < 0 or hours < 0:
        raise ValueError("時給と労働時間は0以上である必要があります")
    return hourly_rate * hours
```

### Design by Contract

frozen dataclass を使用し、不変条件を `__post_init__` で検証する：

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

## テスト

### テストの種類

- **単体テスト**: 関数・クラス単位のテスト
- **統合テスト**: モジュール間の連携テスト
- **プロパティベーステスト**: Hypothesis を使用したランダムテスト
- **セキュリティテスト**: 秘密情報検出、入力検証テスト

### テストの書き方

AAA パターン（Arrange, Act, Assert）に従う：

```python
def test_calculate_labor_cost_正常系() -> None:
    """人件費計算の正常系テスト"""
    # Arrange
    hourly_rate = Decimal("1500")
    hours = Decimal("8")

    # Act
    result = calculate_labor_cost(hourly_rate, hours)

    # Assert
    assert result == Decimal("12000")


def test_calculate_labor_cost_負の値でエラー() -> None:
    """人件費計算で負の値を指定した場合のエラーテスト"""
    # Arrange
    hourly_rate = Decimal("-1500")
    hours = Decimal("8")

    # Act & Assert
    with pytest.raises(ValueError, match="時給と労働時間は0以上である必要があります"):
        calculate_labor_cost(hourly_rate, hours)
```

### テストカバレッジ

- **目標**: 80% 以上
- **確認方法**: `pytest --cov=src --cov-report=html`

## API仕様参照

OpenAPI相当のAPI仕様は、READMEとコード内の仕様定数を同期して管理する。

- 仕様の説明（ドキュメント）
    - `README.md` の「18. APIレスポンス仕様（OpenAPI相当）」を参照する
- 仕様の実体（コード）
    - 勤怠サマリー取得: `src/attendance/api.py` の `ATTENDANCE_SUMMARY_ENDPOINT_SPEC`
    - 売上データエクスポート: `src/business/api.py` の `EXPORT_SALES_DATA_ENDPOINT_SPEC`
- 仕様変更時の運用ルール
    - 仕様定数とREADMEを同一PRで更新する
    - 仕様定数の必須項目テストを更新し、退行を防ぐ
    - 対象テスト: `tests/test_attendance_api.py`, `tests/test_business_api.py`

## CI/CD

GitHub Actions を使用した自動チェック：

- **Lint**: ruff によるコードスタイルチェック
- **Type**: mypy による型チェック
- **Test**: pytest によるテスト実行
- **Security**: policy_check.py による秘密情報検出

## 環境変数設定

- ローカル開発では `.env.example` をコピーして `.env` を作成し、必要な値を設定する。
- `.env` は機密情報を含むためコミットしない（`.gitignore` で除外済み）。
- CSP通知（SEC-010）の運用値は `docs/security.md` の「CSP違反通知の運用設定（SEC-010）」に従う。

```bash
cp .env.example .env
```

## エージェント

開発を支援する3つのエージェント：

- **Developer**: コード実装と機能開発
- **Tester**: テスト作成と品質保証
- **Reviewer**: コードレビューと品質監査

詳細は [.github/agents/](../.github/agents/) を参照。

## トラブルシューティング

### テストが失敗する

```bash
# 詳細なエラー情報を表示
pytest -vv

# 特定のテストのみ実行
pytest tests/test_attendance.py::test_shift_creation
```

### 型エラーが出る

```bash
# 型エラーの詳細を確認
mypy src --show-error-codes

# 特定のファイルのみチェック
mypy src/attendance/models.py
```

### リントエラーが出る

```bash
# 自動修正可能なエラーを修正
ruff check --fix src tests

# フォーマット
ruff format src tests
```

## ディレクトリ構成

```text
.
├── .github/
│   ├── agents/              # エージェント定義
│   ├── workflows/           # CI/CD ワークフロー
│   └── PULL_REQUEST_TEMPLATE.md
├── ci/
│   └── policy_check.py      # セキュリティチェック
├── docs/
│   ├── README.md           # プロジェクト概要（本ファイル）
│   ├── development.md      # 開発ガイド（本ファイル）
│   └── security.md         # セキュリティガイド
├── src/
│   ├── attendance/         # 出退勤・シフト管理
│   ├── business/           # 日報・売上・人件費・原価管理
│   ├── education/          # 教育コンテンツ管理
│   ├── shared/             # 共通機能
│   └── my_package/         # レガシーコード（移行中）
├── tests/                  # テスト
├── pyproject.toml          # プロジェクト設定
└── README.md              # トップレベル README
```

## 参考資料

- [セキュリティガイド](security.md)
- [PR テンプレート](../.github/PULL_REQUEST_TEMPLATE.md)
- [エージェント定義](../.github/agents/)
