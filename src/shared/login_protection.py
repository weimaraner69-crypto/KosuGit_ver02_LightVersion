"""ログイン試行保護（レート制限・一時ロック）。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable


@dataclass(frozen=True)
class LoginProtectionConfig:
    """ログイン試行保護の設定。"""

    max_failed_attempts: int = 5
    lock_minutes: int = 15

    def __post_init__(self) -> None:
        """不変条件の検証。"""
        if self.max_failed_attempts <= 0:
            raise ValueError("max_failed_attempts は正の値である必要があります")
        if self.lock_minutes <= 0:
            raise ValueError("lock_minutes は正の値である必要があります")


@dataclass(frozen=True)
class LoginAttemptState:
    """ユーザーごとのログイン試行状態。"""

    failed_attempts: int
    locked_until: datetime | None = None

    def __post_init__(self) -> None:
        """不変条件の検証。"""
        if self.failed_attempts < 0:
            raise ValueError("failed_attempts は0以上である必要があります")
        if self.locked_until is not None and self.locked_until.tzinfo is None:
            raise ValueError("locked_until はタイムゾーン付き datetime である必要があります")


class LoginProtection:
    """ログイン試行保護インターフェース。"""

    def is_locked(self, username: str) -> bool:
        """ユーザーがロック中か判定する。"""
        raise NotImplementedError

    def register_failure(self, username: str) -> None:
        """失敗試行を記録する。"""
        raise NotImplementedError

    def register_success(self, username: str) -> None:
        """成功試行を記録する。"""
        raise NotImplementedError


@dataclass
class InMemoryLoginProtection(LoginProtection):
    """メモリ内でログイン試行保護を行う実装。"""

    config: LoginProtectionConfig = field(default_factory=LoginProtectionConfig)
    now_provider: Callable[[], datetime] = lambda: datetime.now(timezone.utc)  # noqa: UP017
    _attempt_states: dict[str, LoginAttemptState] = field(
        default_factory=dict,
        init=False,
        repr=False,
    )

    def is_locked(self, username: str) -> bool:
        """ユーザーがロック中か判定する。"""
        normalized_username = _normalize_username(username)
        if not normalized_username:
            return False

        state = self._resolve_state(normalized_username)
        return state.locked_until is not None

    def register_failure(self, username: str) -> None:
        """失敗試行を記録する。"""
        normalized_username = _normalize_username(username)
        if not normalized_username:
            return

        state = self._resolve_state(normalized_username)
        if state.locked_until is not None:
            return

        failed_attempts = state.failed_attempts + 1
        if failed_attempts >= self.config.max_failed_attempts:
            self._attempt_states[normalized_username] = LoginAttemptState(
                failed_attempts=0,
                locked_until=self.now_provider() + timedelta(minutes=self.config.lock_minutes),
            )
            return

        self._attempt_states[normalized_username] = LoginAttemptState(
            failed_attempts=failed_attempts,
            locked_until=None,
        )

    def register_success(self, username: str) -> None:
        """成功試行を記録し、失敗カウントをリセットする。"""
        normalized_username = _normalize_username(username)
        if not normalized_username:
            return

        self._attempt_states.pop(normalized_username, None)

    def _resolve_state(self, normalized_username: str) -> LoginAttemptState:
        """現在時刻基準で有効な状態を返す。"""
        current_state = self._attempt_states.get(
            normalized_username,
            LoginAttemptState(failed_attempts=0, locked_until=None),
        )

        if current_state.locked_until is None:
            return current_state

        if self.now_provider() < current_state.locked_until:
            return current_state

        reset_state = LoginAttemptState(failed_attempts=0, locked_until=None)
        self._attempt_states.pop(normalized_username, None)
        return reset_state


def _normalize_username(username: str) -> str:
    """ログイン試行管理用にユーザー名を正規化する。"""
    return username.strip().lower()
