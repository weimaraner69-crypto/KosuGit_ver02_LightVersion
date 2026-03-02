# 中小企業向け業務管理システム

日報・売上・人件費・原価管理、シフト作成・出退勤打刻、教育コンテンツ管理を統合した業務管理システムです。

## 対象

- **想定規模**: 中小企業（20人程度）
- **対象業務**:
  - 日報・売上・人件費・原価管理
  - シフト作成・シフト提出・出退勤打刻
  - 子どもたちの教育コンテンツ管理

## 特徴

- **セキュリティ重視**: 個人情報保護、データ保全機能を標準実装
- **軽量設計**: 小規模チーム向けに最適化された構成
- **型安全**: Python 3.11+ の型ヒントと mypy による静的型チェック
- **CI/CD**: 自動テスト、セキュリティチェック、型チェックによる品質保証

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

## クイックスタート

### 1. 環境セットアップ

```bash
# Python 3.11+ が必要
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 依存パッケージのインストール
pip install -e ".[dev]"
```

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

### 3. セキュリティチェック

```bash
# 秘密情報検出
python ci/policy_check.py
```

## 開発

開発の詳細は [docs/development.md](docs/development.md) を参照してください。

セキュリティ・個人情報保護については [docs/security.md](docs/security.md) を参照してください。

## ライセンス

[LICENSE](LICENSE) を参照してください。
