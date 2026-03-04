"""監査ログRetention実行ロジックのテスト。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from shared.audit import AuditLogEntry, SqlAlchemyAuditLogWriter
from shared.audit_retention import run_audit_log_retention
from shared.database import Base
from shared.tables import AuditLogTable


def test_run_audit_log_retention_dry_run_削除せず対象件数のみ返す() -> None:
    """dry-run では削除せず対象件数のみ返す。"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    now = datetime.now(timezone.utc)

    with Session(engine) as session:
        writer = SqlAlchemyAuditLogWriter(session=session, auto_commit=False)
        writer.write(
            AuditLogEntry(
                actor_user_id="old-user",
                actor_role="admin",
                resource="report",
                action="update",
                result="success",
                occurred_at=now - timedelta(days=40),
            )
        )

        result = run_audit_log_retention(
            session=session,
            retention_days=30,
            batch_size=500,
            now=now,
            dry_run=True,
        )
        remain_count = session.query(AuditLogTable).count()

    assert result.target_count == 1
    assert result.deleted_count == 0
    assert remain_count == 1


def test_run_audit_log_retention_期限超過分を削除する() -> None:
    """dry-run なしでは期限超過分を削除する。"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    now = datetime.now(timezone.utc)

    with Session(engine) as session:
        writer = SqlAlchemyAuditLogWriter(session=session, auto_commit=False)
        writer.write(
            AuditLogEntry(
                actor_user_id="old-user",
                actor_role="admin",
                resource="report",
                action="update",
                result="success",
                occurred_at=now - timedelta(days=40),
            )
        )
        writer.write(
            AuditLogEntry(
                actor_user_id="new-user",
                actor_role="manager",
                resource="sales",
                action="read",
                result="success",
                occurred_at=now - timedelta(days=1),
            )
        )

        result = run_audit_log_retention(
            session=session,
            retention_days=30,
            batch_size=500,
            now=now,
            dry_run=False,
        )
        remain_rows = session.query(AuditLogTable).all()

    assert result.target_count == 1
    assert result.deleted_count == 1
    assert len(remain_rows) == 1
    assert remain_rows[0].actor_user_id == "new-user"


def test_run_audit_log_retention_retention_days不正でエラー() -> None:
    """保持日数が不正な場合はエラー。"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)

    with Session(engine) as session, pytest.raises(ValueError, match="retention_days"):
        run_audit_log_retention(
            session=session,
            retention_days=0,
        )
