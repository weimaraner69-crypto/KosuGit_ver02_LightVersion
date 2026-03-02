"""出退勤・シフト管理のデータモデル"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime


class ShiftStatus(Enum):
    """シフト状態"""
    DRAFT = "draft"  # 下書き
    SUBMITTED = "submitted"  # 提出済み
    APPROVED = "approved"  # 承認済み
    REJECTED = "rejected"  # 却下


class AttendanceStatus(Enum):
    """勤怠状態"""
    PENDING = "pending"  # 未打刻
    CLOCKED_IN = "clocked_in"  # 出勤済み
    CLOCKED_OUT = "clocked_out"  # 退勤済み
    ABSENT = "absent"  # 欠勤


@dataclass(frozen=True)
class Shift:
    """シフト情報"""
    employee_id: str
    date: datetime
    start_time: datetime
    end_time: datetime
    status: ShiftStatus
    notes: str | None = None

    def __post_init__(self) -> None:
        """不変条件の検証"""
        if not self.employee_id:
            raise ValueError("従業員IDは必須です")
        if self.start_time >= self.end_time:
            raise ValueError("開始時刻は終了時刻より前である必要があります")


@dataclass(frozen=True)
class AttendanceRecord:
    """勤怠記録"""
    employee_id: str
    date: datetime
    clock_in: datetime | None
    clock_out: datetime | None
    status: AttendanceStatus
    notes: str | None = None

    def __post_init__(self) -> None:
        """不変条件の検証"""
        if not self.employee_id:
            raise ValueError("従業員IDは必須です")
        if self.clock_in and self.clock_out and self.clock_in >= self.clock_out:
            raise ValueError("出勤時刻は退勤時刻より前である必要があります")
