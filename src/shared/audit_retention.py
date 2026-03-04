"""監査ログRetention運用の共通ロジック。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

from shared.audit import cleanup_expired_audit_logs
from shared.tables import AuditLogTable


@dataclass(frozen=True)
class AuditRetentionResult:
    """Retention実行結果。"""

    executed_at: datetime
    cutoff: datetime
    retention_days: int
    batch_size: int
    target_count: int
    deleted_count: int
    dry_run: bool

    def __post_init__(self) -> None:
        """不変条件の検証。"""
        if self.retention_days <= 0:
            raise ValueError("retention_days は正の値である必要があります")
        if self.batch_size <= 0:
            raise ValueError("batch_size は正の値である必要があります")
        if self.target_count < 0:
            raise ValueError("target_count は0以上である必要があります")
        if self.deleted_count < 0:
            raise ValueError("deleted_count は0以上である必要があります")
        if self.deleted_count > self.target_count:
            raise ValueError("deleted_count は target_count を超えられません")

    def to_dict(self) -> dict[str, object]:
        """JSON出力向け辞書へ変換する。"""
        return {
            "executed_at": self.executed_at.isoformat(),
            "cutoff": self.cutoff.isoformat(),
            "retention_days": self.retention_days,
            "batch_size": self.batch_size,
            "target_count": self.target_count,
            "deleted_count": self.deleted_count,
            "dry_run": self.dry_run,
        }


def run_audit_log_retention(
    *,
    session: Session,
    retention_days: int,
    batch_size: int = 500,
    now: datetime | None = None,
    dry_run: bool = False,
) -> AuditRetentionResult:
    """監査ログRetentionを実行し、結果を返す。"""
    if retention_days <= 0:
        raise ValueError("retention_days は正の値である必要があります")
    if batch_size <= 0:
        raise ValueError("batch_size は正の値である必要があります")

    executed_at = now or datetime.now(timezone.utc)  # noqa: UP017
    cutoff = executed_at - timedelta(days=retention_days)

    target_count = session.query(AuditLogTable).filter(AuditLogTable.occurred_at <= cutoff).count()

    if dry_run:
        deleted_count = 0
    else:
        deleted_count = cleanup_expired_audit_logs(
            session=session,
            retention_days=retention_days,
            now=executed_at,
            batch_size=batch_size,
            auto_commit=True,
        )

    return AuditRetentionResult(
        executed_at=executed_at,
        cutoff=cutoff,
        retention_days=retention_days,
        batch_size=batch_size,
        target_count=target_count,
        deleted_count=deleted_count,
        dry_run=dry_run,
    )
