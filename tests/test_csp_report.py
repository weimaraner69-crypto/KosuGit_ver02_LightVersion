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
    get_csp_spike_alert_cooldown_minutes_from_env,
    get_csp_spike_alert_priority_increase_ratio_threshold_from_env,
    persist_csp_report,
    should_bypass_csp_spike_alert_cooldown,
    should_suppress_csp_spike_alert,
)
from shared.database import Base
from shared.tables import AuditLogTable, CspReportTable


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


def test_csp_spike_alert_sender_再送で成功する() -> None:
    """一時失敗があっても再送で成功できる。"""
    call_count = 0
    backoff_calls: list[float] = []

    def flaky_transport(_: str, __: dict[str, str], ___: bytes, ____: float) -> None:
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise RuntimeError("temporary network error")

    sender = CspSpikeAlertSender(
        endpoint_url="https://hooks.example.com/csp",
        max_retries=3,
        retry_backoff_seconds=0.25,
        transport=flaky_transport,
        sleeper=backoff_calls.append,
    )

    attempts = sender.send({"event": "csp_spike_detected"})

    assert attempts == 3
    assert call_count == 3
    assert backoff_calls == [0.25, 0.5]


def test_csp_spike_alert_sender_再送上限到達で失敗する() -> None:
    """再送上限まで失敗した場合は例外を送出する。"""
    call_count = 0
    backoff_calls: list[float] = []

    def failing_transport(_: str, __: dict[str, str], ___: bytes, ____: float) -> None:
        nonlocal call_count
        call_count += 1
        raise RuntimeError("network down")

    sender = CspSpikeAlertSender(
        endpoint_url="https://hooks.example.com/csp",
        max_retries=1,
        retry_backoff_seconds=0.2,
        transport=failing_transport,
        sleeper=backoff_calls.append,
    )

    with pytest.raises(RuntimeError, match="network down"):
        sender.send({"event": "csp_spike_detected"})

    assert call_count == 2
    assert backoff_calls == [0.2]


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


def test_dispatch_csp_spike_alert_成功時は監査ログへ記録する() -> None:
    """通知成功時に監査ログを記録する。"""
    audit_writer = InMemoryAuditLogWriter()

    sender = CspSpikeAlertSender(
        endpoint_url="https://hooks.example.com/csp",
        transport=lambda *_: None,
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
        audit_log_writer=audit_writer,
    )

    assert dispatched is True
    assert len(audit_writer.entries) == 1
    entry = audit_writer.entries[0]
    assert entry.action == "csp_spike_alert_dispatch"
    assert entry.result == "success"
    assert entry.metadata["attempt_count"] == "1"


def test_dispatch_csp_spike_alert_失敗時は監査ログへfailureを記録する() -> None:
    """通知失敗時に監査ログへfailureを記録して例外送出する。"""
    audit_writer = InMemoryAuditLogWriter()

    sender = CspSpikeAlertSender(
        endpoint_url="https://hooks.example.com/csp",
        max_retries=1,
        retry_backoff_seconds=0.1,
        transport=lambda *_: (_ for _ in ()).throw(RuntimeError("webhook unavailable")),
        sleeper=lambda _: None,
    )

    with pytest.raises(RuntimeError, match="webhook unavailable"):
        dispatch_csp_spike_alert(
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
            audit_log_writer=audit_writer,
        )

    assert len(audit_writer.entries) == 1
    entry = audit_writer.entries[0]
    assert entry.action == "csp_spike_alert_dispatch"
    assert entry.result == "failure"
    assert entry.error_type == "RuntimeError"
    assert entry.metadata["max_retries"] == "1"


def test_should_suppress_csp_spike_alert_同一directiveは抑制する() -> None:
    """同一directiveがクールダウン内に通知済みなら抑制する。"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    now = datetime(2026, 3, 5, 12, 0, tzinfo=timezone.utc)

    with Session(engine) as session:
        session.add(
            AuditLogTable(
                actor_user_id="system",
                actor_role="system",
                resource="security",
                action="csp_spike_alert_dispatch",
                result="success",
                occurred_at=now - timedelta(minutes=5),
                metadata_json=json.dumps(
                    {
                        "spike_directives": "script-src-elem,img-src",
                    }
                ),
            )
        )
        session.flush()

        suppressed = should_suppress_csp_spike_alert(
            session=session,
            summary={
                "spike_directives": [
                    {"directive": "script-src-elem", "increase": 4.0},
                ]
            },
            cooldown_minutes=30,
            now=now,
        )

    assert suppressed is True


def test_should_bypass_csp_spike_alert_cooldown_高増加率で解除する() -> None:
    """増加率が閾値以上ならクールダウンを解除する。"""
    bypass = should_bypass_csp_spike_alert_cooldown(
        summary={
            "spike_directives": [
                {
                    "directive": "script-src-elem",
                    "recent_count": 12,
                    "baseline_daily_avg": 2.0,
                }
            ]
        },
        priority_increase_ratio_threshold=5.0,
    )

    assert bypass is True


def test_should_bypass_csp_spike_alert_cooldown_閾値未満は解除しない() -> None:
    """増加率が閾値未満ならクールダウン解除しない。"""
    bypass = should_bypass_csp_spike_alert_cooldown(
        summary={
            "spike_directives": [
                {
                    "directive": "script-src-elem",
                    "recent_count": 6,
                    "baseline_daily_avg": 2.0,
                }
            ]
        },
        priority_increase_ratio_threshold=5.0,
    )

    assert bypass is False


def test_dispatch_csp_spike_alert_クールダウン中は送信抑制される() -> None:
    """クールダウン中は送信せず抑制監査ログを残す。"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    now = datetime(2026, 3, 5, 12, 0, tzinfo=timezone.utc)

    with Session(engine) as session:
        session.add(
            AuditLogTable(
                actor_user_id="system",
                actor_role="system",
                resource="security",
                action="csp_spike_alert_dispatch",
                result="success",
                occurred_at=now - timedelta(minutes=3),
                metadata_json=json.dumps({"spike_directives": "script-src-elem"}),
            )
        )
        session.flush()

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
        audit_writer = InMemoryAuditLogWriter()

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
            audit_log_writer=audit_writer,
            session=session,
            cooldown_minutes=30,
            now=now,
        )

    assert dispatched is False
    assert calls == []
    assert len(audit_writer.entries) == 1
    entry = audit_writer.entries[0]
    assert entry.action == "csp_spike_alert_suppressed"
    assert entry.result == "success"
    assert entry.metadata["cooldown_minutes"] == "30"


def test_dispatch_csp_spike_alert_高増加率ならクールダウン解除で送信する() -> None:
    """同一directiveでも高増加率なら抑制を解除して通知する。"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    now = datetime(2026, 3, 5, 12, 0, tzinfo=timezone.utc)

    with Session(engine) as session:
        session.add(
            AuditLogTable(
                actor_user_id="system",
                actor_role="system",
                resource="security",
                action="csp_spike_alert_dispatch",
                result="success",
                occurred_at=now - timedelta(minutes=3),
                metadata_json=json.dumps({"spike_directives": "script-src-elem"}),
            )
        )
        session.flush()

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
        audit_writer = InMemoryAuditLogWriter()

        dispatched = dispatch_csp_spike_alert(
            summary={
                "range_days": 7,
                "total_reports": 20,
                "spike_threshold": 2,
                "spike_directives": [
                    {
                        "directive": "script-src-elem",
                        "recent_count": 12,
                        "baseline_daily_avg": 2.0,
                        "increase": 10.0,
                    }
                ],
            },
            sender=sender,
            audit_log_writer=audit_writer,
            session=session,
            cooldown_minutes=30,
            priority_increase_ratio_threshold=5.0,
            now=now,
        )

    assert dispatched is True
    assert len(calls) == 1
    assert len(audit_writer.entries) == 2
    bypass_entry = audit_writer.entries[0]
    dispatch_entry = audit_writer.entries[1]
    assert bypass_entry.action == "csp_spike_alert_cooldown_bypassed"
    assert dispatch_entry.action == "csp_spike_alert_dispatch"
    assert dispatch_entry.metadata["cooldown_bypassed"] == "true"


def test_create_csp_spike_alert_sender_from_env_設定が無い場合はNone() -> None:
    """Webhook URL未設定時は送信設定を生成しない。"""
    sender = create_csp_spike_alert_sender_from_env(environ_get=lambda _: None)
    assert sender is None


def test_create_csp_spike_alert_sender_from_env_設定値から生成できる() -> None:
    """環境変数設定からWebhook送信設定を生成できる。"""
    env = {
        "CSP_SPIKE_ALERT_WEBHOOK_URL": " https://hooks.example.com/csp ",
        "CSP_SPIKE_ALERT_TIMEOUT_SECONDS": "5.5",
        "CSP_SPIKE_ALERT_MAX_RETRIES": "3",
        "CSP_SPIKE_ALERT_RETRY_BACKOFF_SECONDS": "0.75",
        "CSP_SPIKE_ALERT_BEARER_TOKEN": " secret-token ",
    }

    sender = create_csp_spike_alert_sender_from_env(environ_get=env.get)

    assert sender is not None
    assert sender.endpoint_url == "https://hooks.example.com/csp"
    assert sender.timeout_seconds == 5.5
    assert sender.max_retries == 3
    assert sender.retry_backoff_seconds == 0.75
    assert sender.bearer_token == "secret-token"


def test_create_csp_spike_alert_sender_from_env_不正リトライ値は例外() -> None:
    """max_retries が不正値の場合は例外を送出する。"""
    env = {
        "CSP_SPIKE_ALERT_WEBHOOK_URL": "https://hooks.example.com/csp",
        "CSP_SPIKE_ALERT_MAX_RETRIES": "-1",
    }

    with pytest.raises(ValueError, match="CSP_SPIKE_ALERT_MAX_RETRIES"):
        create_csp_spike_alert_sender_from_env(environ_get=env.get)


def test_get_csp_spike_alert_cooldown_minutes_from_env_正常系() -> None:
    """クールダウン分を環境変数から読み取れる。"""
    env = {"CSP_SPIKE_ALERT_COOLDOWN_MINUTES": "45"}
    value = get_csp_spike_alert_cooldown_minutes_from_env(environ_get=env.get)
    assert value == 45


def test_get_csp_spike_alert_cooldown_minutes_from_env_不正値は例外() -> None:
    """クールダウン分が不正値なら例外を返す。"""
    env = {"CSP_SPIKE_ALERT_COOLDOWN_MINUTES": "-1"}

    with pytest.raises(ValueError, match="CSP_SPIKE_ALERT_COOLDOWN_MINUTES"):
        get_csp_spike_alert_cooldown_minutes_from_env(environ_get=env.get)


def test_get_csp_spike_alert_priority_increase_ratio_threshold_from_env_正常系() -> None:
    """優先通知の増加率閾値を環境変数から読み取れる。"""
    env = {"CSP_SPIKE_ALERT_PRIORITY_INCREASE_RATIO_THRESHOLD": "6.5"}
    value = get_csp_spike_alert_priority_increase_ratio_threshold_from_env(environ_get=env.get)
    assert value == 6.5


def test_get_csp_spike_alert_priority_increase_ratio_threshold_from_env_不正値は例外() -> None:
    """優先通知増加率閾値が不正値なら例外を返す。"""
    env = {"CSP_SPIKE_ALERT_PRIORITY_INCREASE_RATIO_THRESHOLD": "-1"}

    with pytest.raises(ValueError, match="CSP_SPIKE_ALERT_PRIORITY_INCREASE_RATIO_THRESHOLD"):
        get_csp_spike_alert_priority_increase_ratio_threshold_from_env(environ_get=env.get)
