"""日報・売上・人件費・原価管理のデータモデル"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime


class ReportStatus(Enum):
    """日報状態"""
    DRAFT = "draft"  # 下書き
    SUBMITTED = "submitted"  # 提出済み
    APPROVED = "approved"  # 承認済み


@dataclass(frozen=True)
class DailyReport:
    """日報"""
    employee_id: str
    date: datetime
    content: str
    status: ReportStatus
    work_hours: Decimal
    notes: str | None = None

    def __post_init__(self) -> None:
        """不変条件の検証"""
        if not self.employee_id:
            raise ValueError("従業員IDは必須です")
        if not self.content:
            raise ValueError("日報内容は必須です")
        if self.work_hours < Decimal("0"):
            raise ValueError("作業時間は0以上である必要があります")


@dataclass(frozen=True)
class SalesRecord:
    """売上記録"""
    record_id: str
    date: datetime
    amount: Decimal
    customer_name: str
    product_name: str
    notes: str | None = None

    def __post_init__(self) -> None:
        """不変条件の検証"""
        if not self.record_id:
            raise ValueError("記録IDは必須です")
        if self.amount <= Decimal("0"):
            raise ValueError("売上金額は正の値である必要があります")
        if not self.customer_name:
            raise ValueError("顧客名は必須です")


@dataclass(frozen=True)
class LaborCost:
    """人件費"""
    employee_id: str
    period_start: datetime
    period_end: datetime
    hourly_rate: Decimal
    total_hours: Decimal
    total_cost: Decimal

    def __post_init__(self) -> None:
        """不変条件の検証"""
        if not self.employee_id:
            raise ValueError("従業員IDは必須です")
        if self.period_start >= self.period_end:
            raise ValueError("開始日は終了日より前である必要があります")
        if self.hourly_rate < Decimal("0"):
            raise ValueError("時給は0以上である必要があります")
        if self.total_hours < Decimal("0"):
            raise ValueError("総労働時間は0以上である必要があります")
        if self.total_cost < Decimal("0"):
            raise ValueError("総人件費は0以上である必要があります")
