"""監査ログ共通ロジックのテスト。"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import cast

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from shared.audit import (
    AuditLogEntry,
    CompositeAuditLogWriter,
    HttpAuditLogWriter,
    InMemoryAuditLogWriter,
    SqlAlchemyAuditLogWriter,
    cleanup_expired_audit_logs,
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
    assert json.loads(cast("str", row.metadata_json)) == {"safe_key": "safe-value"}


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


def test_composite_audit_writer_一部失敗でも他ライタへ継続() -> None:
    """複合ライタは一部失敗しても他ライタへの保存を継続する。"""

    class FailingAuditLogWriter:
        """常に失敗するテスト用ライタ。"""

        def write(self, _: AuditLogEntry) -> None:
            raise RuntimeError("simulated failure")

    memory_writer = InMemoryAuditLogWriter()
    composite_writer = CompositeAuditLogWriter(
        writers=(FailingAuditLogWriter(), memory_writer),
    )

    write_audit_log(
        writer=composite_writer,
        actor_user_id="user_001",
        actor_role="admin",
        resource="report",
        action="update",
        result="success",
    )

    assert len(memory_writer.entries) == 1


def test_http_audit_log_writer_外部転送ペイロードを送信できる() -> None:
    """HTTPライタは監査ログを外部基盤向けにJSON送信できる。"""
    captured: dict[str, object] = {}

    def fake_transport(
        endpoint_url: str,
        headers: dict[str, str],
        body: bytes,
        timeout_seconds: float,
    ) -> None:
        captured["endpoint_url"] = endpoint_url
        captured["headers"] = headers
        captured["body"] = body
        captured["timeout_seconds"] = timeout_seconds

    entry = AuditLogEntry(
        actor_user_id="user_001",
        actor_role="manager",
        resource="sales",
        action="export",
        result="success",
        target_resource_id="export-001",
        metadata={"safe_key": "safe-value"},
    )

    writer = HttpAuditLogWriter(
        endpoint_url="https://example.com/audit/logs",
        timeout_seconds=2.0,
        bearer_token="token-123",
        extra_headers={"X-Audit-Source": "kosugit"},
        transport=fake_transport,
    )

    writer.write(entry)

    assert captured["endpoint_url"] == "https://example.com/audit/logs"
    assert captured["timeout_seconds"] == 2.0

    headers = cast("dict[str, str]", captured["headers"])
    assert headers["Content-Type"] == "application/json"
    assert headers["Authorization"] == "Bearer token-123"
    assert headers["X-Audit-Source"] == "kosugit"

    payload = json.loads(cast("bytes", captured["body"]).decode("utf-8"))
    assert payload["actor_user_id"] == "user_001"
    assert payload["resource"] == "sales"
    assert payload["target_resource_id"] == "export-001"
    assert payload["metadata"] == {"safe_key": "safe-value"}


def test_http_audit_log_writer_endpoint_urlが不正ならエラー() -> None:
    """HTTPライタは不正URLを拒否する。"""
    with pytest.raises(ValueError, match="endpoint_url"):
        HttpAuditLogWriter(endpoint_url="audit.internal.local")


def test_cleanup_expired_audit_logs_期限超過のみ削除する() -> None:
    """保持期限を超過した行のみ削除する。"""
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

        deleted_count = cleanup_expired_audit_logs(
            session=session,
            retention_days=30,
            now=now,
        )

        assert deleted_count == 1
        remain_rows = session.query(AuditLogTable).all()

    assert len(remain_rows) == 1
    assert remain_rows[0].actor_user_id == "new-user"


def test_cleanup_expired_audit_logs_アーカイブ成功時に削除する() -> None:
    """アーカイブ成功時は期限超過行を削除する。"""
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
                action="delete",
                result="failure",
                occurred_at=now - timedelta(days=60),
                error_type="AuthorizationError",
            )
        )

        archive_writer = InMemoryAuditLogWriter()
        deleted_count = cleanup_expired_audit_logs(
            session=session,
            retention_days=30,
            now=now,
            archive_writer=archive_writer,
        )

        assert deleted_count == 1
        assert len(archive_writer.entries) == 1
        assert archive_writer.entries[0].actor_user_id == "old-user"
        assert archive_writer.entries[0].error_type == "AuthorizationError"
        remain_rows = session.query(AuditLogTable).all()

    assert len(remain_rows) == 0


def test_cleanup_expired_audit_logs_アーカイブ失敗時は削除しない() -> None:
    """アーカイブ失敗時は安全側で削除をスキップする。"""

    class FailingAuditLogWriter:
        """常に失敗するテスト用ライタ。"""

        def write(self, _: AuditLogEntry) -> None:
            raise RuntimeError("archive failed")

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
                occurred_at=now - timedelta(days=60),
            )
        )

        deleted_count = cleanup_expired_audit_logs(
            session=session,
            retention_days=30,
            now=now,
            archive_writer=FailingAuditLogWriter(),
        )

        assert deleted_count == 0
        remain_rows = session.query(AuditLogTable).all()

    assert len(remain_rows) == 1


def test_cleanup_expired_audit_logs_retention_days不正でエラー() -> None:
    """保持日数が不正な場合はエラー。"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)

    with Session(engine) as session, pytest.raises(ValueError, match="retention_days"):
        cleanup_expired_audit_logs(session=session, retention_days=0)
