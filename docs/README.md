# 中小企業向け業務管理システム

日報・売上・人件費・原価管理、シフト作成・出退勤打刻、教育コンテンツ管理を統合した業務管理システムです。

このドキュメントは「導入ガイド（セットアップ・実行手順）」です。仕様の正本は [../README.md](../README.md) を参照してください。

## 目次

- [対象](#docs-spec-01)
- [特徴](#docs-spec-02)
- [システム構成](#docs-spec-03)
- [クイックスタート](#docs-spec-04)
  - [1. 環境セットアップ](#docs-spec-05)
  - [2. テストの実行](#docs-spec-06)
  - [3. セキュリティチェック](#docs-spec-07)
- [開発](#docs-spec-08)
- [ライセンス](#docs-spec-09)

<a id="docs-spec-01"></a>
## 対象

- **想定規模**: 中小企業（20人程度）
- **対象業務**:
  - 日報・売上・人件費・原価管理
  - シフト作成・シフト提出・出退勤打刻
  - 子どもたちの教育コンテンツ管理

<a id="docs-spec-02"></a>
## 特徴

- **セキュリティ重視**: 個人情報保護、データ保全機能を標準実装
- **軽量設計**: 小規模チーム向けに最適化された構成
- **型安全**: Python 3.11+ の型ヒントと mypy による静的型チェック
- **CI/CD**: 自動テスト、セキュリティチェック、型チェックによる品質保証

<a id="docs-spec-03"></a>
## システム構成

```text
src/
├── attendance/      # 出退勤・シフト管理
│   ├── models.py    # データモデル（Shift, AttendanceRecord）
│   └── ...
├── business/        # 日報・売上・人件費・原価管理
│   ├── models.py    # データモデル（DailyReport, SalesRecord, LaborCost）
│   └── ...
├── education/       # 教育コンテンツ管理
│   ├── models.py    # データモデル（LearningContent, LearningProgress）
│   └── ...
└── shared/          # 共通機能
    ├── security.py  # 認証・セキュリティ機能
    ├── exceptions.py # 共通例外
    └── ...
```

<a id="docs-spec-04"></a>
## クイックスタート

<a id="docs-spec-05"></a>
### 1. 環境セットアップ

```bash
# Python 3.11+ が必要
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 依存パッケージのインストール
pip install -e ".[dev]"

# ローカル環境変数ファイルを作成
cp .env.example .env
```

<a id="docs-spec-06"></a>
### 2. テストの実行

```bash
# すべてのテストを実行
pytest

# カバレッジ付きで実行
pytest --cov=src --cov-report=html

# 型チェック
mypy src

# リント
ruff check src tests
```

<a id="docs-spec-07"></a>
### 3. セキュリティチェック

```bash
# 秘密情報検出
python ci/policy_check.py
```

`policy_check.py` は `.env.example` の機密キー（`TOKEN` / `SECRET` / `PASSWORD` / `PASSWD` / `API_KEY`）に非空値がある状態も検知します。

<a id="docs-spec-08"></a>
## 開発

業務運用仕様（管理者ダッシュボード・日報・シフト・打刻）の詳細は [operations-spec.md](operations-spec.md) を参照してください。

開発の詳細は [development.md](development.md) を参照してください。

セキュリティ・個人情報保護については [security.md](security.md) を参照してください。

監査ログ保持期間運用の手順は [runbook_audit_retention.md](runbook_audit_retention.md) を参照してください。

<a id="docs-spec-09"></a>
## ライセンス

[../LICENSE](../LICENSE) を参照してください。
