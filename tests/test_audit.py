"""監査ログ共通ロジックのテスト。"""

from __future__ import annotations

import json
from typing import cast

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from shared.audit import (
    AuditLogEntry,
    InMemoryAuditLogWriter,
    SqlAlchemyAuditLogWriter,
    sanitize_audit_metadata,
    write_audit_log,
)
from shared.database import Base
from shared.tables import AuditLogTable


def test_audit_log_entry_正常作成() -> None:
    """必須項目があれば監査ログを作成できる。"""
    entry = AuditLogEntry(
        actor_user_id="user_001",
        actor_role="admin",
        resource="report",
        action="update",
        result="success",
    )

    assert entry.actor_user_id == "user_001"
    assert entry.result == "success"


def test_sanitize_audit_metadata_個人情報キーを除外() -> None:
    """個人情報・機微情報キーを除外する。"""
    metadata = {
        "target_id": "report-001",
        "email": "secret@example.com",
        "password": "secret",
    }

    sanitized = sanitize_audit_metadata(metadata)

    assert sanitized == {"target_id": "report-001"}


def test_write_audit_log_メモリライタへ保存() -> None:
    """監査ログを書き込むとライタへ保存される。"""
    writer = InMemoryAuditLogWriter()

    write_audit_log(
        writer=writer,
        actor_user_id="user_001",
        actor_role="manager",
        resource="sales",
        action="export",
        result="success",
        target_resource_id="sales-export-001",
    )

    assert len(writer.entries) == 1
    entry = writer.entries[0]
    assert entry.resource == "sales"
    assert entry.action == "export"
    assert entry.target_resource_id == "sales-export-001"


def test_write_audit_log_writer未指定は何もしない() -> None:
    """ライタ未指定時は例外なく処理される。"""
    write_audit_log(
        writer=None,
        actor_user_id="user_001",
        actor_role="manager",
        resource="sales",
        action="export",
        result="success",
    )


def test_write_audit_log_sqlalchemyライタへ永続化() -> None:
    """SQLAlchemyライタで監査ログを永続化できる。"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)

    with Session(engine) as session:
        writer = SqlAlchemyAuditLogWriter(session=session, auto_commit=True)

        write_audit_log(
            writer=writer,
            actor_user_id="user_001",
            actor_role="admin",
            resource="report",
            action="update",
            result="success",
            target_resource_id="report-001",
            metadata={
                "email": "secret@example.com",
                "safe_key": "safe-value",
            },
        )

    with Session(engine) as session:
        stored = session.query(AuditLogTable).all()

    assert len(stored) == 1
    row = stored[0]
    assert row.actor_user_id == "user_001"
    assert row.actor_role == "admin"
    assert row.resource == "report"
    assert row.action == "update"
    assert row.result == "success"
    assert row.target_resource_id == "report-001"
    assert json.loads(cast(str, row.metadata_json)) == {"safe_key": "safe-value"}


def test_sqlalchemy_audit_writer_auto_commit_falseでもflushされる() -> None:
    """auto_commit=False でも同一トランザクション内では参照できる。"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)

    with Session(engine) as session:
        writer = SqlAlchemyAuditLogWriter(session=session, auto_commit=False)
        entry = AuditLogEntry(
            actor_user_id="user_001",
            actor_role="manager",
            resource="sales",
            action="export",
            result="success",
        )

        writer.write(entry)
        stored = session.query(AuditLogTable).all()

        assert len(stored) == 1
