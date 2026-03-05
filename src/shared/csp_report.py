"""CSP違反レポートの永続化・監査連携ロジック。"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from time import sleep
from typing import TYPE_CHECKING, Any, Protocol
from urllib.request import Request, urlopen

from sqlalchemy import func
from sqlalchemy.orm import Session  # noqa: TC002

from shared.audit import AuditLogWriter, write_audit_log
from shared.tables import CspReportTable

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping


def _parse_non_negative_int(value: str | None, *, default: int, setting_name: str) -> int:
    """環境変数から0以上の整数を読み取る。"""
    if value is None:
        return default

    normalized = value.strip()
    if not normalized:
        return default

    try:
        parsed = int(normalized)
    except ValueError as error:
        raise ValueError(f"{setting_name} は整数で指定してください") from error

    if parsed < 0:
        raise ValueError(f"{setting_name} は0以上である必要があります")
    return parsed


@dataclass(frozen=True)
class CspReportEntry:
    """CSP違反レポート1件の表現。"""

    report_json: Mapping[str, Any]
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))  # noqa: UP017
    document_uri: str | None = None
    violated_directive: str | None = None
    effective_directive: str | None = None
    blocked_uri: str | None = None
    original_policy: str | None = None
    disposition: str | None = None
    referrer: str | None = None
    status_code: int | None = None

    def __post_init__(self) -> None:
        """不変条件の検証。"""
        if not self.report_json:
            raise ValueError("report_json は必須です")
        if self.status_code is not None and self.status_code < 0:
            raise ValueError("status_code は0以上である必要があります")


class CspReportWriter(Protocol):
    """CSPレポート保存の抽象インターフェース。"""

    def write(self, entry: CspReportEntry) -> int:
        """CSPレポートを保存し、採番IDを返す。"""


def _parse_positive_float(value: str | None, *, default: float, setting_name: str) -> float:
    """環境変数から正の実数を読み取る。"""
    if value is None:
        return default

    normalized = value.strip()
    if not normalized:
        return default

    try:
        parsed = float(normalized)
    except ValueError as error:
        raise ValueError(f"{setting_name} は実数で指定してください") from error

    if parsed <= 0:
        raise ValueError(f"{setting_name} は正の値である必要があります")
    return parsed


def _default_alert_transport(
    endpoint_url: str,
    headers: Mapping[str, str],
    body: bytes,
    timeout_seconds: float,
) -> None:
    """Webhook へHTTP POSTで通知する。"""
    request = Request(
        endpoint_url,
        data=body,
        headers=dict(headers),
        method="POST",
    )
    with urlopen(request, timeout=timeout_seconds):
        return


@dataclass
class CspSpikeAlertSender:
    """CSP急増検知通知をWebhookへ送信する実装。"""

    endpoint_url: str
    timeout_seconds: float = 3.0
    max_retries: int = 0
    retry_backoff_seconds: float = 0.5
    bearer_token: str | None = None
    extra_headers: Mapping[str, str] = field(default_factory=dict)
    transport: Callable[[str, Mapping[str, str], bytes, float], None] | None = None
    sleeper: Callable[[float], None] = sleep

    def __post_init__(self) -> None:
        """不変条件の検証。"""
        if not self.endpoint_url:
            raise ValueError("endpoint_url は必須です")
        if not (
            self.endpoint_url.startswith("https://") or self.endpoint_url.startswith("http://")
        ):
            raise ValueError("endpoint_url は http:// または https:// で始まる必要があります")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds は正の値である必要があります")
        if self.max_retries < 0:
            raise ValueError("max_retries は0以上である必要があります")
        if self.retry_backoff_seconds <= 0:
            raise ValueError("retry_backoff_seconds は正の値である必要があります")

    def send(self, payload: Mapping[str, Any]) -> int:
        """Webhookへ通知を送信し、試行回数を返す。"""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            **dict(self.extra_headers),
        }
        if self.bearer_token:
            headers["Authorization"] = f"Bearer {self.bearer_token}"

        body = json.dumps(
            dict(payload),
            ensure_ascii=False,
            sort_keys=True,
        ).encode("utf-8")

        transport = self.transport or _default_alert_transport

        attempt_count = self.max_retries + 1
        for attempt_index in range(attempt_count):
            try:
                transport(self.endpoint_url, headers, body, self.timeout_seconds)
                return attempt_index + 1
            except Exception:
                if attempt_index >= self.max_retries:
                    raise

                backoff_seconds = self.retry_backoff_seconds * (2**attempt_index)
                self.sleeper(backoff_seconds)

        return attempt_count


def build_csp_spike_alert_payload(summary: Mapping[str, Any]) -> dict[str, Any]:
    """CSP急増検知結果をWebhook通知用ペイロードへ変換する。"""
    return {
        "event": "csp_spike_detected",
        "range_days": summary.get("range_days"),
        "total_reports": summary.get("total_reports"),
        "spike_threshold": summary.get("spike_threshold"),
        "spike_directives": summary.get("spike_directives", []),
    }


def dispatch_csp_spike_alert(
    *,
    summary: Mapping[str, Any],
    sender: CspSpikeAlertSender,
    audit_log_writer: AuditLogWriter | None = None,
) -> bool:
    """急増directiveが存在する場合のみ通知する。"""
    spikes = summary.get("spike_directives")
    if not isinstance(spikes, list) or len(spikes) == 0:
        return False

    payload = build_csp_spike_alert_payload(summary)

    try:
        attempt_count = sender.send(payload)
        write_audit_log(
            writer=audit_log_writer,
            actor_user_id="system",
            actor_role="system",
            resource="security",
            action="csp_spike_alert_dispatch",
            result="success",
            metadata={
                "spike_directive_count": str(len(spikes)),
                "attempt_count": str(attempt_count),
                "max_retries": str(sender.max_retries),
            },
        )
        return True
    except Exception as error:
        write_audit_log(
            writer=audit_log_writer,
            actor_user_id="system",
            actor_role="system",
            resource="security",
            action="csp_spike_alert_dispatch",
            result="failure",
            error_type=type(error).__name__,
            metadata={
                "spike_directive_count": str(len(spikes)),
                "max_retries": str(sender.max_retries),
            },
        )
        raise


def create_csp_spike_alert_sender_from_env(
    *,
    environ_get: Callable[[str], str | None] | None = None,
) -> CspSpikeAlertSender | None:
    """環境変数からWebhook通知送信設定を構築する。"""
    get_value = environ_get or os.getenv

    endpoint_url = (get_value("CSP_SPIKE_ALERT_WEBHOOK_URL") or "").strip()
    if not endpoint_url:
        return None

    timeout_seconds = _parse_positive_float(
        get_value("CSP_SPIKE_ALERT_TIMEOUT_SECONDS"),
        default=3.0,
        setting_name="CSP_SPIKE_ALERT_TIMEOUT_SECONDS",
    )
    max_retries = _parse_non_negative_int(
        get_value("CSP_SPIKE_ALERT_MAX_RETRIES"),
        default=2,
        setting_name="CSP_SPIKE_ALERT_MAX_RETRIES",
    )
    retry_backoff_seconds = _parse_positive_float(
        get_value("CSP_SPIKE_ALERT_RETRY_BACKOFF_SECONDS"),
        default=0.5,
        setting_name="CSP_SPIKE_ALERT_RETRY_BACKOFF_SECONDS",
    )

    bearer_token_raw = get_value("CSP_SPIKE_ALERT_BEARER_TOKEN")
    bearer_token = bearer_token_raw.strip() if isinstance(bearer_token_raw, str) else None
    if bearer_token == "":
        bearer_token = None

    return CspSpikeAlertSender(
        endpoint_url=endpoint_url,
        timeout_seconds=timeout_seconds,
        max_retries=max_retries,
        retry_backoff_seconds=retry_backoff_seconds,
        bearer_token=bearer_token,
    )


@dataclass
class SqlAlchemyCspReportWriter:
    """SQLAlchemyを利用したCSPレポート永続化実装。"""

    session: Session
    auto_commit: bool = False

    def write(self, entry: CspReportEntry) -> int:
        """CSPレポートをデータベースへ保存する。"""
        row = CspReportTable(
            occurred_at=entry.occurred_at,
            document_uri=entry.document_uri,
            violated_directive=entry.violated_directive,
            effective_directive=entry.effective_directive,
            blocked_uri=entry.blocked_uri,
            original_policy=entry.original_policy,
            disposition=entry.disposition,
            referrer=entry.referrer,
            status_code=entry.status_code,
            report_json=json.dumps(dict(entry.report_json), ensure_ascii=False, sort_keys=True),
        )
        self.session.add(row)
        self.session.flush()

        if self.auto_commit:
            self.session.commit()

        return int(row.id)


def build_csp_report_entry(report: Mapping[str, Any]) -> CspReportEntry:
    """サニタイズ済みCSPレポートから永続化エントリを組み立てる。"""
    document_uri = report.get("document-uri")
    violated_directive = report.get("violated-directive")
    effective_directive = report.get("effective-directive")
    blocked_uri = report.get("blocked-uri")
    original_policy = report.get("original-policy")
    disposition = report.get("disposition")
    referrer = report.get("referrer")
    status_code = report.get("status-code")

    return CspReportEntry(
        report_json=dict(report),
        document_uri=document_uri if isinstance(document_uri, str) else None,
        violated_directive=violated_directive if isinstance(violated_directive, str) else None,
        effective_directive=effective_directive if isinstance(effective_directive, str) else None,
        blocked_uri=blocked_uri if isinstance(blocked_uri, str) else None,
        original_policy=original_policy if isinstance(original_policy, str) else None,
        disposition=disposition if isinstance(disposition, str) else None,
        referrer=referrer if isinstance(referrer, str) else None,
        status_code=status_code if isinstance(status_code, int) else None,
    )


def _build_audit_metadata(entry: CspReportEntry) -> dict[str, str]:
    """監査ログへ保存するメタデータを構築する。"""
    metadata: dict[str, str] = {}
    if entry.document_uri:
        metadata["document_uri"] = entry.document_uri
    if entry.violated_directive:
        metadata["violated_directive"] = entry.violated_directive
    if entry.effective_directive:
        metadata["effective_directive"] = entry.effective_directive
    if entry.blocked_uri:
        metadata["blocked_uri"] = entry.blocked_uri
    if entry.disposition:
        metadata["disposition"] = entry.disposition
    if entry.status_code is not None:
        metadata["status_code"] = str(entry.status_code)
    return metadata


def persist_csp_report(
    *,
    report: Mapping[str, Any],
    csp_report_writer: CspReportWriter,
    audit_log_writer: AuditLogWriter | None = None,
) -> int:
    """CSPレポートを永続化し、監査ログへ記録する。"""
    try:
        entry = build_csp_report_entry(report)
        row_id = csp_report_writer.write(entry)
        write_audit_log(
            writer=audit_log_writer,
            actor_user_id="system",
            actor_role="system",
            resource="security",
            action="csp_report_ingest",
            result="success",
            target_resource_id=str(row_id),
            metadata=_build_audit_metadata(entry),
        )
        return row_id
    except Exception as error:
        write_audit_log(
            writer=audit_log_writer,
            actor_user_id="system",
            actor_role="system",
            resource="security",
            action="csp_report_ingest",
            result="failure",
            error_type=type(error).__name__,
        )
        raise


def get_csp_report_summary(
    *,
    session: Session,
    days: int,
    top_directives: int,
    spike_threshold: int,
    now: datetime | None = None,
) -> dict[str, Any]:
    """CSPレポートの期間別件数・directive別件数を集計する。"""
    if days <= 0:
        raise ValueError("days は正の値である必要があります")
    if top_directives <= 0:
        raise ValueError("top_directives は正の値である必要があります")
    if spike_threshold <= 0:
        raise ValueError("spike_threshold は正の値である必要があります")

    current = now or datetime.now(timezone.utc)  # noqa: UP017
    since = current - timedelta(days=days)
    recent_since = current - timedelta(days=1)

    total_reports = (
        session.query(func.count(CspReportTable.id))
        .filter(CspReportTable.occurred_at >= since)
        .scalar()
    )

    period_rows = (
        session.query(
            func.date(CspReportTable.occurred_at),
            func.count(CspReportTable.id),
        )
        .filter(CspReportTable.occurred_at >= since)
        .group_by(func.date(CspReportTable.occurred_at))
        .order_by(func.date(CspReportTable.occurred_at).asc())
        .all()
    )

    directive_rows = (
        session.query(
            CspReportTable.violated_directive,
            func.count(CspReportTable.id),
        )
        .filter(
            CspReportTable.occurred_at >= since,
            CspReportTable.violated_directive.isnot(None),
            CspReportTable.violated_directive != "",
        )
        .group_by(CspReportTable.violated_directive)
        .order_by(func.count(CspReportTable.id).desc(), CspReportTable.violated_directive.asc())
        .limit(top_directives)
        .all()
    )

    recent_rows = (
        session.query(
            CspReportTable.violated_directive,
            func.count(CspReportTable.id),
        )
        .filter(
            CspReportTable.occurred_at >= recent_since,
            CspReportTable.occurred_at <= current,
            CspReportTable.violated_directive.isnot(None),
            CspReportTable.violated_directive != "",
        )
        .group_by(CspReportTable.violated_directive)
        .all()
    )

    baseline_rows = (
        session.query(
            CspReportTable.violated_directive,
            func.count(CspReportTable.id),
        )
        .filter(
            CspReportTable.occurred_at >= since,
            CspReportTable.occurred_at < recent_since,
            CspReportTable.violated_directive.isnot(None),
            CspReportTable.violated_directive != "",
        )
        .group_by(CspReportTable.violated_directive)
        .all()
    )

    recent_counts: dict[str, int] = {
        str(directive): int(report_count)
        for directive, report_count in recent_rows
    }
    baseline_counts: dict[str, int] = {
        str(directive): int(report_count)
        for directive, report_count in baseline_rows
    }
    baseline_days = max(days - 1, 1)

    spike_directives: list[dict[str, Any]] = []
    for directive, recent_count in recent_counts.items():
        baseline_daily_avg = baseline_counts.get(directive, 0) / baseline_days
        increase = recent_count - baseline_daily_avg
        if increase >= spike_threshold:
            spike_directives.append(
                {
                    "directive": directive,
                    "recent_count": recent_count,
                    "baseline_daily_avg": round(baseline_daily_avg, 2),
                    "increase": round(increase, 2),
                }
            )

    spike_directives.sort(
        key=lambda item: (float(item["increase"]), int(item["recent_count"])),
        reverse=True,
    )

    return {
        "range_days": days,
        "total_reports": int(total_reports or 0),
        "spike_threshold": spike_threshold,
        "period_counts": [
            {
                "date": str(bucket),
                "count": int(report_count),
            }
            for bucket, report_count in period_rows
        ],
        "directive_counts": [
            {
                "directive": str(directive),
                "count": int(report_count),
            }
            for directive, report_count in directive_rows
        ],
        "spike_directives": spike_directives,
    }
