# 監査ログ Retention 運用 Runbook

最終更新: 2026年3月

## 目的

監査ログの保持期間運用（Retention）を安全に実施し、期限超過データの削除またはアーカイブを手順化する。

## 対象

- 監査ログテーブル: `audit_logs`
- 実装関数: `shared.audit.cleanup_expired_audit_logs`
- アーカイブ転送（任意）: `shared.audit.HttpAuditLogWriter` または複合ライタ

## 事前確認（必須）

1. 本番実行前にデータベースバックアップを取得していること
1. 保持日数（`retention_days`）が運用ポリシーに一致していること
1. アーカイブ先を使用する場合は疎通確認済みであること
1. 誤削除防止のため、対象件数の事前確認を実施すること

## 実行手順

### 1. 仮想環境を有効化

```bash
source .venv/bin/activate
```

### 2. 削除対象件数を事前確認（推奨）

```python
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session

from shared.database.connection import engine
from shared.tables import AuditLogTable

retention_days = 30
cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)

with Session(engine) as session:
    target_count = (
        session.query(AuditLogTable)
        .filter(AuditLogTable.occurred_at <= cutoff)
        .count()
    )

print({"cutoff": cutoff.isoformat(), "target_count": target_count})
```

### 3. Retention 処理を実行

```bash
uv run python scripts/run_audit_retention.py --retention-days 30 --batch-size 500
```

`--dry-run` を付与すると削除せず対象件数のみ確認できる。

```bash
uv run python scripts/run_audit_retention.py --retention-days 30 --batch-size 500 --dry-run
```

### 4. GitHub Actions 定期実行

- ワークフロー: `.github/workflows/audit-retention.yml`
- 実行タイミング: 毎日 02:15 UTC（`cron: 15 2 * * *`）
- 手動実行: `workflow_dispatch` から `retention_days` / `batch_size` / `dry_run` を指定可能

#### Repository Variables（任意）

- `AUDIT_RETENTION_DAYS`（未設定時は `30`）
- `AUDIT_RETENTION_BATCH_SIZE`（未設定時は `500`）

実行結果JSONは Artifact（`audit-retention-result-<run_id>`）として保存され、実行日時・cutoff・対象件数・削除件数を確認できる。

### 5. 事後チェック項目（承認用）

1. Actions の `Audit Retention` 実行が成功していること
1. Artifact `audit-retention-result-<run_id>` が保存されていること
1. JSON内の `retention_days` / `batch_size` / `dry_run` が想定値であること
1. JSON内の `target_count` と `deleted_count` が運用想定と乖離していないこと
1. 乖離がある場合、即時に定期実行を停止し「障害時対応」に従って調査すること

## アーカイブ併用時の注意

- `archive_writer` を指定した場合、アーカイブ失敗レコードは安全側で削除しない
- 一部削除に留まるため、失敗件数を運用ログで確認し、再実行する
- 外部転送のタイムアウトや認証情報（Bearer Token）の期限切れに注意する

## 障害時対応

### ケース1: 途中失敗（例外発生）

- 直近バックアップの取得時刻を確認
- 失敗ログを確認し、再実行可能か判定
- 再実行時は `batch_size` を小さくして段階実行する

### ケース2: 想定より削除件数が多い

- 即時に定期実行を停止
- 事前確認結果（target_count）と実削除件数を突合
- 必要に応じてバックアップから復旧し、保持日数設定を見直す

## 監査証跡として残す情報

- 実行者
- 実行日時
- retention_days
- 事前確認件数（target_count）
- 実削除件数（deleted_count）
- 失敗件数（アーカイブ失敗含む）

## 参考

- セキュリティガイド: `docs/security.md`
- 実装: `src/shared/audit.py`
