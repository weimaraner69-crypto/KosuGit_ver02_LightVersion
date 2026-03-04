"""ログイン試行保護ロジックのテスト。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from shared.login_protection import InMemoryLoginProtection, LoginProtectionConfig


def test_in_memory_login_protection_失敗回数閾値でロック() -> None:
    """失敗回数が閾値に達するとロックされる。"""
    protection = InMemoryLoginProtection(
        config=LoginProtectionConfig(max_failed_attempts=3, lock_minutes=15),
    )

    protection.register_failure("john_doe")
    protection.register_failure("john_doe")
    assert protection.is_locked("john_doe") is False

    protection.register_failure("john_doe")
    assert protection.is_locked("john_doe") is True


def test_in_memory_login_protection_成功で失敗回数をリセット() -> None:
    """成功試行で失敗回数がリセットされる。"""
    protection = InMemoryLoginProtection(
        config=LoginProtectionConfig(max_failed_attempts=2, lock_minutes=15),
    )

    protection.register_failure("john_doe")
    protection.register_success("john_doe")
    protection.register_failure("john_doe")

    assert protection.is_locked("john_doe") is False


def test_in_memory_login_protection_ロック期限経過で解除() -> None:
    """ロック期限を過ぎると自動解除される。"""
    now = datetime(2026, 3, 5, 12, 0, tzinfo=timezone.utc)

    def now_provider() -> datetime:
        return now

    protection = InMemoryLoginProtection(
        config=LoginProtectionConfig(max_failed_attempts=2, lock_minutes=10),
        now_provider=now_provider,
    )

    protection.register_failure("john_doe")
    protection.register_failure("john_doe")
    assert protection.is_locked("john_doe") is True

    now = now + timedelta(minutes=11)
    assert protection.is_locked("john_doe") is False
