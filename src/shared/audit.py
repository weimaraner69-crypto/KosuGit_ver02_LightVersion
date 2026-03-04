"""監査ログの共通ロジック。"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Protocol, cast
from urllib.request import Request, urlopen

from sqlalchemy.orm import Session  # noqa: TC002

from shared.tables import AuditLogTable

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

PII_RELATED_KEYS = {
    "name",
    "full_name",
    "email",
    "phone",
    "address",
    "password",
    "passwd",
    "token",
    "salary",
    "wage",
}


@dataclass(frozen=True)
class AuditLogEntry:
    """監査ログ1件の表現。"""

    actor_user_id: str
    actor_role: str
    resource: str
    action: str
    result: str
    occurred_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),  # noqa: UP017
    )
    target_resource_id: str | None = None
    error_type: str | None = None
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """不変条件の検証。"""
        if not self.actor_user_id:
            raise ValueError("actor_user_id は必須です")
        if not self.actor_role:
            raise ValueError("actor_role は必須です")
        if not self.resource:
            raise ValueError("resource は必須です")
        if not self.action:
            raise ValueError("action は必須です")
        if self.result not in {"success", "failure"}:
            raise ValueError("result は success / failure のいずれかです")


class AuditLogWriter(Protocol):
    """監査ログ保存の抽象インターフェース。"""

    def write(self, entry: AuditLogEntry) -> None:
        """監査ログを保存する。"""


@dataclass
class InMemoryAuditLogWriter:
    """テスト向けのメモリ保存実装。"""

    entries: list[AuditLogEntry] = field(default_factory=list)

    def write(self, entry: AuditLogEntry) -> None:
        """監査ログをメモリに追加する。"""
        self.entries.append(entry)


@dataclass
class CompositeAuditLogWriter:
    """複数ライタへ監査ログを書き込む実装。"""

    writers: tuple[AuditLogWriter, ...]

    def write(self, entry: AuditLogEntry) -> None:
        """登録済みライタへ順次書き込み、失敗ライタはスキップする。"""
        for writer in self.writers:
            try:
                writer.write(entry)
            except Exception:
                continue


@dataclass
class SqlAlchemyAuditLogWriter:
    """SQLAlchemy を利用した監査ログ永続化実装。"""

    session: Session
    auto_commit: bool = False

    def write(self, entry: AuditLogEntry) -> None:
        """監査ログをデータベースへ保存する。"""
        row = AuditLogTable(
            actor_user_id=entry.actor_user_id,
            actor_role=entry.actor_role,
            resource=entry.resource,
            action=entry.action,
            result=entry.result,
            occurred_at=entry.occurred_at,
            target_resource_id=entry.target_resource_id,
            error_type=entry.error_type,
            metadata_json=json.dumps(dict(entry.metadata), ensure_ascii=False, sort_keys=True),
        )
        self.session.add(row)
        self.session.flush()

        if self.auto_commit:
            self.session.commit()


def _default_http_transport(
    endpoint_url: str,
    headers: Mapping[str, str],
    body: bytes,
    timeout_seconds: float,
) -> None:
    """HTTP POST で監査ログを外部基盤へ転送する。"""
    request = Request(
        endpoint_url,
        data=body,
        headers=dict(headers),
        method="POST",
    )
    with urlopen(request, timeout=timeout_seconds):
        return


def build_audit_log_payload(entry: AuditLogEntry) -> dict[str, object | None]:
    """監査ログエントリを外部転送向けJSONペイロードへ変換する。"""
    return {
        "actor_user_id": entry.actor_user_id,
        "actor_role": entry.actor_role,
        "resource": entry.resource,
        "action": entry.action,
        "result": entry.result,
        "occurred_at": entry.occurred_at.isoformat(),
        "target_resource_id": entry.target_resource_id,
        "error_type": entry.error_type,
        "metadata": dict(entry.metadata),
    }


@dataclass
class HttpAuditLogWriter:
    """HTTPで監査ログを外部ログ基盤へ転送する実装。"""

    endpoint_url: str
    timeout_seconds: float = 3.0
    bearer_token: str | None = None
    extra_headers: Mapping[str, str] = field(default_factory=dict)
    transport: Callable[[str, Mapping[str, str], bytes, float], None] | None = None

    def __post_init__(self) -> None:
        """不変条件の検証。"""
        if not self.endpoint_url:
            raise ValueError("endpoint_url は必須です")
        if not (
            self.endpoint_url.startswith("https://")
            or self.endpoint_url.startswith("http://")
        ):
            raise ValueError("endpoint_url は http:// または https:// で始まる必要があります")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds は正の値である必要があります")

    def write(self, entry: AuditLogEntry) -> None:
        """監査ログをHTTP転送する。"""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            **dict(self.extra_headers),
        }
        if self.bearer_token:
            headers["Authorization"] = f"Bearer {self.bearer_token}"

        body = json.dumps(
            build_audit_log_payload(entry),
            ensure_ascii=False,
            sort_keys=True,
        ).encode("utf-8")

        transport = self.transport or _default_http_transport
        transport(
            self.endpoint_url,
            headers,
            body,
            self.timeout_seconds,
        )


def _row_to_audit_log_entry(row: AuditLogTable) -> AuditLogEntry:
    """テーブル行を監査ログエントリへ変換する。"""
    metadata: dict[str, str]
    metadata_json = cast("str | None", row.metadata_json)
    if not metadata_json:
        metadata = {}
    else:
        try:
            parsed = json.loads(metadata_json)
        except json.JSONDecodeError:
            parsed = {}

        if isinstance(parsed, dict):
            metadata = {str(key): str(value) for key, value in parsed.items()}
        else:
            metadata = {}

    return AuditLogEntry(
        actor_user_id=cast("str", row.actor_user_id),
        actor_role=cast("str", row.actor_role),
        resource=cast("str", row.resource),
        action=cast("str", row.action),
        result=cast("str", row.result),
        occurred_at=cast("datetime", row.occurred_at),
        target_resource_id=cast("str | None", row.target_resource_id),
        error_type=cast("str | None", row.error_type),
        metadata=metadata,
    )


def cleanup_expired_audit_logs(
    *,
    session: Session,
    retention_days: int,
    now: datetime | None = None,
    archive_writer: AuditLogWriter | None = None,
    batch_size: int = 500,
    auto_commit: bool = False,
) -> int:
    """保持期限を超過した監査ログをアーカイブ後に削除する。"""
    if retention_days <= 0:
        raise ValueError("retention_days は正の値である必要があります")
    if batch_size <= 0:
        raise ValueError("batch_size は正の値である必要があります")

    current = now or datetime.now(timezone.utc)  # noqa: UP017
    cutoff = current - timedelta(days=retention_days)

    expired_rows = (
        session.query(AuditLogTable)
        .filter(AuditLogTable.occurred_at <= cutoff)
        .order_by(AuditLogTable.occurred_at.asc(), AuditLogTable.id.asc())
        .limit(batch_size)
        .all()
    )

    deleted_count = 0
    for row in expired_rows:
        if archive_writer is not None:
            entry = _row_to_audit_log_entry(row)
            try:
                archive_writer.write(entry)
            except Exception:
                continue

        session.delete(row)
        deleted_count += 1

    session.flush()
    if auto_commit:
        session.commit()

    return deleted_count


def sanitize_audit_metadata(metadata: Mapping[str, str] | None) -> dict[str, str]:
    """監査ログ用メタデータから機微情報キーを除外する。"""
    if metadata is None:
        return {}

    sanitized: dict[str, str] = {}
    for key, value in metadata.items():
        normalized_key = key.strip().lower()
        if normalized_key in PII_RELATED_KEYS:
            continue
        sanitized[key] = value

    return sanitized


def write_audit_log(
    *,
    writer: AuditLogWriter | None,
    actor_user_id: str,
    actor_role: str,
    resource: str,
    action: str,
    result: str,
    target_resource_id: str | None = None,
    error_type: str | None = None,
    metadata: Mapping[str, str] | None = None,
) -> None:
    """監査ログを書き込む。書き込み失敗は業務処理へ影響させない。"""
    if writer is None:
        return

    entry = AuditLogEntry(
        actor_user_id=actor_user_id,
        actor_role=actor_role,
        resource=resource,
        action=action,
        result=result,
        target_resource_id=target_resource_id,
        error_type=error_type,
        metadata=sanitize_audit_metadata(metadata),
    )

    try:
        writer.write(entry)
    except Exception:
        return
