"""監査ログの共通ロジック。"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from sqlalchemy.orm import Session  # noqa: TC002

from shared.tables import AuditLogTable


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
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
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
