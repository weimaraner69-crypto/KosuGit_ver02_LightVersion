"""出退勤・シフト管理モジュールのテスト"""

from datetime import datetime, timezone

import pytest

from attendance.models import AttendanceRecord, AttendanceStatus, Shift, ShiftStatus


class TestShift:
    """Shift クラスのテスト"""

    def test_shift_creation_正常系(self) -> None:
        """シフトの正常作成"""
        shift = Shift(
            employee_id="emp_001",
            date=datetime(2026, 3, 2, tzinfo=timezone.utc),
            start_time=datetime(2026, 3, 2, 9, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 3, 2, 18, 0, tzinfo=timezone.utc),
            status=ShiftStatus.DRAFT,
        )

        assert shift.employee_id == "emp_001"
        assert shift.status == ShiftStatus.DRAFT

    def test_shift_空の従業員IDでエラー(self) -> None:
        """従業員IDが空の場合はエラー"""
        with pytest.raises(ValueError, match="従業員IDは必須です"):
            Shift(
                employee_id="",
                date=datetime(2026, 3, 2, tzinfo=timezone.utc),
                start_time=datetime(2026, 3, 2, 9, 0, tzinfo=timezone.utc),
                end_time=datetime(2026, 3, 2, 18, 0, tzinfo=timezone.utc),
                status=ShiftStatus.DRAFT,
            )

    def test_shift_開始時刻が終了時刻より後でエラー(self) -> None:
        """開始時刻が終了時刻より後の場合はエラー"""
        with pytest.raises(ValueError, match="開始時刻は終了時刻より前である必要があります"):
            Shift(
                employee_id="emp_001",
                date=datetime(2026, 3, 2, tzinfo=timezone.utc),
                start_time=datetime(2026, 3, 2, 18, 0, tzinfo=timezone.utc),
                end_time=datetime(2026, 3, 2, 9, 0, tzinfo=timezone.utc),
                status=ShiftStatus.DRAFT,
            )


class TestAttendanceRecord:
    """AttendanceRecord クラスのテスト"""

    def test_attendance_record_creation_正常系(self) -> None:
        """勤怠記録の正常作成"""
        record = AttendanceRecord(
            employee_id="emp_001",
            date=datetime(2026, 3, 2, tzinfo=timezone.utc),
            clock_in=datetime(2026, 3, 2, 9, 0, tzinfo=timezone.utc),
            clock_out=datetime(2026, 3, 2, 18, 0, tzinfo=timezone.utc),
            status=AttendanceStatus.CLOCKED_OUT,
        )

        assert record.employee_id == "emp_001"
        assert record.status == AttendanceStatus.CLOCKED_OUT

    def test_attendance_record_空の従業員IDでエラー(self) -> None:
        """従業員IDが空の場合はエラー"""
        with pytest.raises(ValueError, match="従業員IDは必須です"):
            AttendanceRecord(
                employee_id="",
                date=datetime(2026, 3, 2, tzinfo=timezone.utc),
                clock_in=None,
                clock_out=None,
                status=AttendanceStatus.PENDING,
            )

    def test_attendance_record_出勤時刻が退勤時刻より後でエラー(self) -> None:
        """出勤時刻が退勤時刻より後の場合はエラー"""
        with pytest.raises(ValueError, match="出勤時刻は退勤時刻より前である必要があります"):
            AttendanceRecord(
                employee_id="emp_001",
                date=datetime(2026, 3, 2, tzinfo=timezone.utc),
                clock_in=datetime(2026, 3, 2, 18, 0, tzinfo=timezone.utc),
                clock_out=datetime(2026, 3, 2, 9, 0, tzinfo=timezone.utc),
                status=AttendanceStatus.CLOCKED_OUT,
            )
