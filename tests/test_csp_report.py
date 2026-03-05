"""CSP違反レポート永続化のテスト。"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from shared.audit import InMemoryAuditLogWriter
from shared.csp_report import (
    CspSpikeAlertSender,
    SqlAlchemyCspReportWriter,
    build_csp_report_entry,
    create_csp_spike_alert_sender_from_env,
    dispatch_csp_spike_alert,
    get_csp_report_summary,
    persist_csp_report,
)
from shared.database import Base
from shared.tables import CspReportTable


def test_build_csp_report_entry_正常系() -> None:
    """サニタイズ済み辞書から永続化エントリを生成できる。"""
    report = {
        "document-uri": "https://example.com/report",
        "violated-directive": "script-src-elem",
        "effective-directive": "script-src",
        "blocked-uri": "https://cdn.example.com/lib.js",
        "original-policy": "default-src 'self'; report-uri /csp-report",
        "disposition": "report",
        "referrer": "https://example.com",
        "status-code": 200,
    }

    entry = build_csp_report_entry(report)

    assert entry.document_uri == "https://example.com/report"
    assert entry.violated_directive == "script-src-elem"
    assert entry.effective_directive == "script-src"
    assert entry.blocked_uri == "https://cdn.example.com/lib.js"
    assert entry.status_code == 200


def test_sqlalchemy_csp_report_writer_永続化できる() -> None:
    """SQLAlchemyライタでCSPレポートを永続化できる。"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)

    with Session(engine) as session:
        writer = SqlAlchemyCspReportWriter(session=session, auto_commit=True)
        persisted_id = writer.write(
            build_csp_report_entry(
                {
                    "document-uri": "https://example.com/report",
                    "violated-directive": "script-src-elem",
                    "effective-directive": "script-src",
                    "blocked-uri": "https://cdn.example.com/lib.js",
                    "original-policy": "default-src 'self'; report-uri /csp-report",
                    "status-code": 200,
                }
            )
        )

    with Session(engine) as session:
        rows = session.query(CspReportTable).all()

    assert persisted_id > 0
    assert len(rows) == 1
    row = rows[0]
    assert row.document_uri == "https://example.com/report"
    assert row.violated_directive == "script-src-elem"
    assert row.status_code == 200
    assert json.loads(str(row.report_json))["effective-directive"] == "script-src"


def test_persist_csp_report_監査ログ連携できる() -> None:
    """永続化成功時に監査ログへ成功結果を記録する。"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)

    with Session(engine) as session:
        csp_writer = SqlAlchemyCspReportWriter(session=session, auto_commit=False)
        audit_writer = InMemoryAuditLogWriter()

        persisted_id = persist_csp_report(
            report={
                "document-uri": "https://example.com/report",
                "violated-directive": "script-src-elem",
                "effective-directive": "script-src",
                "blocked-uri": "https://cdn.example.com/lib.js",
                "original-policy": "default-src 'self'; report-uri /csp-report",
                "status-code": 200,
            },
            csp_report_writer=csp_writer,
            audit_log_writer=audit_writer,
        )
        session.commit()

    assert persisted_id > 0
    assert len(audit_writer.entries) == 1
    entry = audit_writer.entries[0]
    assert entry.resource == "security"
    assert entry.action == "csp_report_ingest"
    assert entry.result == "success"
    assert entry.target_resource_id == str(persisted_id)


def test_persist_csp_report_永続化失敗時は監査ログ失敗を記録() -> None:
    """永続化失敗時は監査ログへ failure を記録して例外送出する。"""

    class FailingCspReportWriter:
        """常に失敗するテスト用ライタ。"""

        def write(self, _: object) -> int:
            raise RuntimeError("db unavailable")

    audit_writer = InMemoryAuditLogWriter()

    with pytest.raises(RuntimeError, match="db unavailable"):
        persist_csp_report(
            report={
                "document-uri": "https://example.com/report",
                "violated-directive": "script-src-elem",
            },
            csp_report_writer=FailingCspReportWriter(),
            audit_log_writer=audit_writer,
        )

    assert len(audit_writer.entries) == 1
    entry = audit_writer.entries[0]
    assert entry.resource == "security"
    assert entry.action == "csp_report_ingest"
    assert entry.result == "failure"
    assert entry.error_type == "RuntimeError"


def test_get_csp_report_summary_期間別とdirective別を集計できる() -> None:
    """指定期間の件数とdirective別件数を集計できる。"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    now = datetime(2026, 3, 5, 12, 0, tzinfo=timezone.utc)

    with Session(engine) as session:
        writer = SqlAlchemyCspReportWriter(session=session, auto_commit=False)
        writer.write(
            build_csp_report_entry(
                {
                    "document-uri": "https://example.com/report-1",
                    "violated-directive": "script-src-elem",
                    "effective-directive": "script-src",
                    "status-code": 200,
                }
            )
        )
        writer.write(
            build_csp_report_entry(
                {
                    "document-uri": "https://example.com/report-2",
                    "violated-directive": "img-src",
                    "effective-directive": "img-src",
                    "status-code": 200,
                }
            )
        )
        writer.write(
            build_csp_report_entry(
                {
                    "document-uri": "https://example.com/report-old",
                    "violated-directive": "style-src",
                    "effective-directive": "style-src",
                    "status-code": 200,
                }
            )
        )

        latest_row = session.query(CspReportTable).filter(CspReportTable.id == 1).one()
        latest_row.occurred_at = now - timedelta(days=1)
        second_row = session.query(CspReportTable).filter(CspReportTable.id == 2).one()
        second_row.occurred_at = now - timedelta(days=2)
        old_row = session.query(CspReportTable).filter(CspReportTable.id == 3).one()
        old_row.occurred_at = now - timedelta(days=40)
        session.flush()

        summary = get_csp_report_summary(
            session=session,
            days=7,
            top_directives=10,
            spike_threshold=3,
            now=now,
        )

    assert summary["range_days"] == 7
    assert summary["total_reports"] == 2
    assert summary["spike_threshold"] == 3
    assert summary["period_counts"] == [
        {"date": "2026-03-03", "count": 1},
        {"date": "2026-03-04", "count": 1},
    ]
    assert summary["directive_counts"] == [
        {"directive": "img-src", "count": 1},
        {"directive": "script-src-elem", "count": 1},
    ]
    assert summary["spike_directives"] == []


def test_get_csp_report_summary_急増directiveを検知できる() -> None:
    """直近24時間の件数増加がしきい値を超えるdirectiveを検知する。"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    now = datetime(2026, 3, 5, 12, 0, tzinfo=timezone.utc)

    with Session(engine) as session:
        writer = SqlAlchemyCspReportWriter(session=session, auto_commit=False)

        writer.write(
            build_csp_report_entry(
                {
                    "document-uri": "https://example.com/recent-1",
                    "violated-directive": "script-src-elem",
                    "effective-directive": "script-src",
                    "status-code": 200,
                }
            )
        )
        writer.write(
            build_csp_report_entry(
                {
                    "document-uri": "https://example.com/recent-2",
                    "violated-directive": "script-src-elem",
                    "effective-directive": "script-src",
                    "status-code": 200,
                }
            )
        )
        writer.write(
            build_csp_report_entry(
                {
                    "document-uri": "https://example.com/recent-3",
                    "violated-directive": "script-src-elem",
                    "effective-directive": "script-src",
                    "status-code": 200,
                }
            )
        )
        writer.write(
            build_csp_report_entry(
                {
                    "document-uri": "https://example.com/baseline",
                    "violated-directive": "script-src-elem",
                    "effective-directive": "script-src",
                    "status-code": 200,
                }
            )
        )

        row1 = session.query(CspReportTable).filter(CspReportTable.id == 1).one()
        row1.occurred_at = now - timedelta(hours=2)
        row2 = session.query(CspReportTable).filter(CspReportTable.id == 2).one()
        row2.occurred_at = now - timedelta(hours=3)
        row3 = session.query(CspReportTable).filter(CspReportTable.id == 3).one()
        row3.occurred_at = now - timedelta(hours=4)
        row4 = session.query(CspReportTable).filter(CspReportTable.id == 4).one()
        row4.occurred_at = now - timedelta(days=2)
        session.flush()

        summary = get_csp_report_summary(
            session=session,
            days=7,
            top_directives=10,
            spike_threshold=2,
            now=now,
        )

    assert summary["spike_directives"] == [
        {
            "directive": "script-src-elem",
            "recent_count": 3,
            "baseline_daily_avg": 0.17,
            "increase": 2.83,
        }
    ]


def test_dispatch_csp_spike_alert_急増が無い場合は送信しない() -> None:
    """急増が無い場合はWebhook送信しない。"""
    calls: list[dict[str, object]] = []

    sender = CspSpikeAlertSender(
        endpoint_url="https://hooks.example.com/csp",
        transport=lambda endpoint_url, headers, body, timeout: calls.append(
            {
                "endpoint_url": endpoint_url,
                "headers": headers,
                "body": body,
                "timeout": timeout,
            }
        ),
    )

    dispatched = dispatch_csp_spike_alert(
        summary={
            "range_days": 7,
            "total_reports": 12,
            "spike_threshold": 3,
            "spike_directives": [],
        },
        sender=sender,
    )

    assert dispatched is False
    assert calls == []


def test_dispatch_csp_spike_alert_急増がある場合は送信する() -> None:
    """急増がある場合はWebhookへ送信する。"""
    calls: list[dict[str, object]] = []

    sender = CspSpikeAlertSender(
        endpoint_url="https://hooks.example.com/csp",
        bearer_token="secret-token",
        timeout_seconds=4.5,
        transport=lambda endpoint_url, headers, body, timeout: calls.append(
            {
                "endpoint_url": endpoint_url,
                "headers": headers,
                "body": body,
                "timeout": timeout,
            }
        ),
    )

    dispatched = dispatch_csp_spike_alert(
        summary={
            "range_days": 7,
            "total_reports": 20,
            "spike_threshold": 2,
            "spike_directives": [
                {
                    "directive": "script-src-elem",
                    "recent_count": 5,
                    "baseline_daily_avg": 0.5,
                    "increase": 4.5,
                }
            ],
        },
        sender=sender,
    )

    assert dispatched is True
    assert len(calls) == 1
    call = calls[0]
    assert call["endpoint_url"] == "https://hooks.example.com/csp"
    assert call["timeout"] == 4.5
    headers = call["headers"]
    assert isinstance(headers, dict)
    assert headers["Content-Type"] == "application/json"
    assert headers["Authorization"] == "Bearer secret-token"

    body = call["body"]
    assert isinstance(body, bytes)
    payload = json.loads(body.decode("utf-8"))
    assert payload["event"] == "csp_spike_detected"
    assert payload["spike_threshold"] == 2
    assert payload["spike_directives"][0]["directive"] == "script-src-elem"


def test_create_csp_spike_alert_sender_from_env_設定が無い場合はNone() -> None:
    """Webhook URL未設定時は送信設定を生成しない。"""
    sender = create_csp_spike_alert_sender_from_env(environ_get=lambda _: None)
    assert sender is None


def test_create_csp_spike_alert_sender_from_env_設定値から生成できる() -> None:
    """環境変数設定からWebhook送信設定を生成できる。"""
    env = {
        "CSP_SPIKE_ALERT_WEBHOOK_URL": " https://hooks.example.com/csp ",
        "CSP_SPIKE_ALERT_TIMEOUT_SECONDS": "5.5",
        "CSP_SPIKE_ALERT_BEARER_TOKEN": " secret-token ",
    }

    sender = create_csp_spike_alert_sender_from_env(environ_get=env.get)

    assert sender is not None
    assert sender.endpoint_url == "https://hooks.example.com/csp"
    assert sender.timeout_seconds == 5.5
    assert sender.bearer_token == "secret-token"
