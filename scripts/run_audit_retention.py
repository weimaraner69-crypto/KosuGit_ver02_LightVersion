#!/usr/bin/env python3
"""監査ログRetentionを実行するスクリプト。"""

from __future__ import annotations

import argparse
import json
import logging
import sys

from shared.audit_retention import run_audit_log_retention
from shared.database import init_db
from shared.database.connection import get_session_factory

# テーブル定義をロードしてから init_db() を実行するための import
from shared.tables import AuditLogTable  # noqa: F401

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    """コマンドライン引数を解析する。"""
    parser = argparse.ArgumentParser(description="監査ログRetention実行")
    parser.add_argument(
        "--retention-days",
        type=int,
        default=30,
        help="保持日数（デフォルト: 30）",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=500,
        help="1回の処理件数上限（デフォルト: 500）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="削除せず対象件数のみ確認する",
    )
    return parser.parse_args()


def main() -> int:
    """Retention処理を実行する。"""
    args = parse_args()
    try:
        init_db()
        session_factory = get_session_factory()

        with session_factory() as session:
            result = run_audit_log_retention(
                session=session,
                retention_days=args.retention_days,
                batch_size=args.batch_size,
                dry_run=args.dry_run,
            )

        logger.info(
            "Retention完了: target=%s deleted=%s dry_run=%s cutoff=%s",
            result.target_count,
            result.deleted_count,
            result.dry_run,
            result.cutoff.isoformat(),
        )
        print(json.dumps(result.to_dict(), ensure_ascii=False, sort_keys=True))
        return 0
    except Exception as error:
        logger.exception("Retention実行に失敗しました: %s", error)
        return 1


if __name__ == "__main__":
    sys.exit(main())
