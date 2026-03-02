"""教育アプリのデータモデル"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime


class ContentType(Enum):
    """学習コンテンツ種別"""
    VIDEO = "video"  # 動画
    QUIZ = "quiz"  # クイズ
    READING = "reading"  # 読み物
    EXERCISE = "exercise"  # 演習問題


class ProgressStatus(Enum):
    """学習進捗状態"""
    NOT_STARTED = "not_started"  # 未開始
    IN_PROGRESS = "in_progress"  # 学習中
    COMPLETED = "completed"  # 完了


@dataclass(frozen=True)
class LearningContent:
    """学習コンテンツ"""
    content_id: str
    title: str
    content_type: ContentType
    difficulty_level: int
    estimated_minutes: int
    description: str | None = None

    def __post_init__(self) -> None:
        """不変条件の検証"""
        if not self.content_id:
            raise ValueError("コンテンツIDは必須です")
        if not self.title:
            raise ValueError("タイトルは必須です")
        if not 1 <= self.difficulty_level <= 5:
            raise ValueError("難易度は1〜5の範囲である必要があります")
        if self.estimated_minutes <= 0:
            raise ValueError("学習時間は正の値である必要があります")


@dataclass(frozen=True)
class LearningProgress:
    """学習進捗"""
    student_id: str
    content_id: str
    status: ProgressStatus
    started_at: datetime | None
    completed_at: datetime | None
    score: int | None = None

    def __post_init__(self) -> None:
        """不変条件の検証"""
        if not self.student_id:
            raise ValueError("生徒IDは必須です")
        if not self.content_id:
            raise ValueError("コンテンツIDは必須です")
        if self.started_at and self.completed_at and self.started_at > self.completed_at:
            raise ValueError("開始日時は完了日時より前である必要があります")
        if self.score is not None and not 0 <= self.score <= 100:
            raise ValueError("スコアは0〜100の範囲である必要があります")
