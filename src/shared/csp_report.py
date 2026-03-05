"""CSP違反レポートの永続化・監査連携ロジック。"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, Protocol

from sqlalchemy import func
from sqlalchemy.orm import Session  # noqa: TC002

from shared.audit import AuditLogWriter, write_audit_log
from shared.tables import CspReportTable

if TYPE_CHECKING:
    from collections.abc import Mapping


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
    now: datetime | None = None,
) -> dict[str, Any]:
    """CSPレポートの期間別件数・directive別件数を集計する。"""
    if days <= 0:
        raise ValueError("days は正の値である必要があります")
    if top_directives <= 0:
        raise ValueError("top_directives は正の値である必要があります")

    current = now or datetime.now(timezone.utc)  # noqa: UP017
    since = current - timedelta(days=days)

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

    return {
        "range_days": days,
        "total_reports": int(total_reports or 0),
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
    }
