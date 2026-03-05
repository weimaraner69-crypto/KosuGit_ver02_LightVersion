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
    - 補足: 検知対象の詳細は `docs/security.md` の「CI による自動チェック」を参照

### SEC-011 運用Runbook（担当ロール別）

`security-regression` ジョブ失敗時は、`docs/security.md` の一次対応フローに加えて、以下の担当ロール別チェックリストを適用する。

1. 実装担当（Primary Assignee）
    - PRコメントの run URL から失敗ログを確認する
    - 失敗理由を「仕様差分 / 実装不備 / 一時要因」に分類してPRへ記録する
    - 一時要因が明確な場合のみ、再実行は1回まで実施する
2. セキュリティ担当（Reviewer）
    - 認証・CSRF・ヘッダー設定など共通基盤への影響有無を確認する
    - 失敗テストの修正方針（許容 / 追加対策）をレビューコメントで明示する
3. マージ担当（Maintainer）
    - `security-regression` 成功を確認してからマージ判断を行う
    - PR本文またはコメントに、原因・対応・再発防止メモが残っていることを確認する

#### PRコメント雛形（SEC-011失敗時）

```text
SEC-011 security-regression 失敗対応

- 失敗テスト:
- 原因分類: 仕様差分 / 実装不備 / 一時要因
- 対応内容:
- 再実行有無: 実施 / 未実施（理由）
- 再発防止メモ:
```

#### Issue起票テンプレート（SEC-011失敗時）

- GitHub Issue を起票する場合は `.github/ISSUE_TEMPLATE/security_regression.yml` を使用する。
- PRコメント雛形と同じ項目（原因分類 / 対応内容 / 再発防止）を記録し、証跡URLを必ず添付する。

#### 自動トリアージ設定（SEC系）

- `.github/workflows/sec011-issue-triage.yml` は、`[SEC-xxx]` で始まる Issue 作成時に `security` ラベル付与と担当候補アサインを実行する。
- 担当候補は Issue 起票者とし、コラボレーター権限がある場合に自動アサインする。
- 起票者に権限がない場合は Issue へ注意コメントを投稿し、手動アサインへフォールバックする。

#### 週次集計レポート設定（SEC系）

- `.github/workflows/security-issue-triage-report.yml` は週次実行でSEC系Issueのトリアージ結果を集計する。
- Step Summary へ件数（total/open/closed/assigned/unassigned）を出力し、同内容をArtifactとして保存する。
- 未アサインの open Issue は `unassigned_alert_threshold`（既定3）以上のときのみ警告見出しで強調表示する。
- 未アサインの open Issue 一覧（max 10）はStep Summary先頭に出力する。
- しきい値超過時は未アサイン open Issue（max 10）へ自動通知コメントを投稿する。
- 自動通知コメントは週次マーカー（`security-issue-triage-report:<ISO週>`）で同一週の重複投稿を抑止する。
- 自動通知コメントには担当ロール候補として、実装担当（Issue起票者）とレビュー担当（リポジトリオーナー）を追記する。
- 現時点では上記のシンプル運用を標準とし、レビュー担当候補の高度自動選出（直近対応者推定など）は運用課題が顕在化するまで導入しない。
- `ci/policy_check.py` で `docs/sec-triage-spec-freeze.md` の必須セクション・参照先・版表記を検証し、凍結仕様との乖離を検知する。
- `docs/sec-triage-spec-freeze.md` を変更した場合は、変更履歴の版番号増分（例: `v1.0` → `v1.1`）を必須とする。
- 手動実行時は `report_days` 入力で集計期間を指定できる。
- 手動実行時は `unassigned_alert_threshold` 入力で警告しきい値を指定できる。
- 定期実行の既定期間は7日（`workflow_dispatch` 未指定時も同値）とする。

## 環境変数設定

- ローカル開発では `.env.example` をコピーして `.env` を作成し、必要な値を設定する。
- `.env` は機密情報を含むためコミットしない（`.gitignore` で除外済み）。
- CSP通知（SEC-010）の運用値は `docs/security.md` の「CSP違反通知の運用設定（SEC-010）」に従う。
- `docs/security.md` の推奨値と `.env.example` のサンプル値は、変更時に同一PRで必ず同期する。

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
