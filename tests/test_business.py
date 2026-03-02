"""日報・売上・人件費・原価管理モジュールのテスト"""

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from business.models import DailyReport, LaborCost, ReportStatus, SalesRecord


class TestDailyReport:
    """DailyReport クラスのテスト"""

    def test_daily_report_creation_正常系(self) -> None:
        """日報の正常作成"""
        report = DailyReport(
            employee_id="emp_001",
            date=datetime(2026, 3, 2, tzinfo=timezone.utc),
            content="本日の業務内容",
            status=ReportStatus.DRAFT,
            work_hours=Decimal("8.0"),
        )

        assert report.employee_id == "emp_001"
        assert report.content == "本日の業務内容"
        assert report.work_hours == Decimal("8.0")

    def test_daily_report_空の従業員IDでエラー(self) -> None:
        """従業員IDが空の場合はエラー"""
        with pytest.raises(ValueError, match="従業員IDは必須です"):
            DailyReport(
                employee_id="",
                date=datetime(2026, 3, 2, tzinfo=timezone.utc),
                content="本日の業務内容",
                status=ReportStatus.DRAFT,
                work_hours=Decimal("8.0"),
            )

    def test_daily_report_作業時間が負の値でエラー(self) -> None:
        """作業時間が負の値の場合はエラー"""
        with pytest.raises(ValueError, match="作業時間は0以上である必要があります"):
            DailyReport(
                employee_id="emp_001",
                date=datetime(2026, 3, 2, tzinfo=timezone.utc),
                content="本日の業務内容",
                status=ReportStatus.DRAFT,
                work_hours=Decimal("-1.0"),
            )


class TestSalesRecord:
    """SalesRecord クラスのテスト"""

    def test_sales_record_creation_正常系(self) -> None:
        """売上記録の正常作成"""
        record = SalesRecord(
            record_id="sale_001",
            date=datetime(2026, 3, 2, tzinfo=timezone.utc),
            amount=Decimal("10000"),
            customer_name="山田商店",
            product_name="商品A",
        )

        assert record.record_id == "sale_001"
        assert record.amount == Decimal("10000")
        assert record.customer_name == "山田商店"

    def test_sales_record_売上金額が0以下でエラー(self) -> None:
        """売上金額が0以下の場合はエラー"""
        with pytest.raises(ValueError, match="売上金額は正の値である必要があります"):
            SalesRecord(
                record_id="sale_001",
                date=datetime(2026, 3, 2, tzinfo=timezone.utc),
                amount=Decimal("0"),
                customer_name="山田商店",
                product_name="商品A",
            )


class TestLaborCost:
    """LaborCost クラスのテスト"""

    def test_labor_cost_creation_正常系(self) -> None:
        """人件費の正常作成"""
        cost = LaborCost(
            employee_id="emp_001",
            period_start=datetime(2026, 3, 1, tzinfo=timezone.utc),
            period_end=datetime(2026, 3, 31, tzinfo=timezone.utc),
            hourly_rate=Decimal("1500"),
            total_hours=Decimal("160"),
            total_cost=Decimal("240000"),
        )

        assert cost.employee_id == "emp_001"
        assert cost.hourly_rate == Decimal("1500")
        assert cost.total_cost == Decimal("240000")

    def test_labor_cost_開始日が終了日より後でエラー(self) -> None:
        """開始日が終了日より後の場合はエラー"""
        with pytest.raises(ValueError, match="開始日は終了日より前である必要があります"):
            LaborCost(
                employee_id="emp_001",
                period_start=datetime(2026, 3, 31, tzinfo=timezone.utc),
                period_end=datetime(2026, 3, 1, tzinfo=timezone.utc),
                hourly_rate=Decimal("1500"),
                total_hours=Decimal("160"),
                total_cost=Decimal("240000"),
            )
