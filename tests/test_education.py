"""教育アプリモジュールのテスト"""

from datetime import datetime, timezone

import pytest

from education.models import (
    ContentType,
    LearningContent,
    LearningProgress,
    ProgressStatus,
)


class TestLearningContent:
    """LearningContent クラスのテスト"""

    def test_learning_content_creation_正常系(self) -> None:
        """学習コンテンツの正常作成"""
        content = LearningContent(
            content_id="content_001",
            title="算数の基礎",
            content_type=ContentType.VIDEO,
            difficulty_level=2,
            estimated_minutes=30,
        )

        assert content.content_id == "content_001"
        assert content.title == "算数の基礎"
        assert content.difficulty_level == 2

    def test_learning_content_難易度が範囲外でエラー(self) -> None:
        """難易度が1〜5の範囲外の場合はエラー"""
        with pytest.raises(ValueError, match="難易度は1〜5の範囲である必要があります"):
            LearningContent(
                content_id="content_001",
                title="算数の基礎",
                content_type=ContentType.VIDEO,
                difficulty_level=6,
                estimated_minutes=30,
            )

    def test_learning_content_学習時間が0以下でエラー(self) -> None:
        """学習時間が0以下の場合はエラー"""
        with pytest.raises(ValueError, match="学習時間は正の値である必要があります"):
            LearningContent(
                content_id="content_001",
                title="算数の基礎",
                content_type=ContentType.VIDEO,
                difficulty_level=2,
                estimated_minutes=0,
            )


class TestLearningProgress:
    """LearningProgress クラスのテスト"""

    def test_learning_progress_creation_正常系(self) -> None:
        """学習進捗の正常作成"""
        progress = LearningProgress(
            student_id="student_001",
            content_id="content_001",
            status=ProgressStatus.IN_PROGRESS,
            started_at=datetime(2026, 3, 2, 10, 0, tzinfo=timezone.utc),
            completed_at=None,
        )

        assert progress.student_id == "student_001"
        assert progress.status == ProgressStatus.IN_PROGRESS

    def test_learning_progress_開始日時が完了日時より後でエラー(self) -> None:
        """開始日時が完了日時より後の場合はエラー"""
        with pytest.raises(ValueError, match="開始日時は完了日時より前である必要があります"):
            LearningProgress(
                student_id="student_001",
                content_id="content_001",
                status=ProgressStatus.COMPLETED,
                started_at=datetime(2026, 3, 2, 12, 0, tzinfo=timezone.utc),
                completed_at=datetime(2026, 3, 2, 10, 0, tzinfo=timezone.utc),
            )

    def test_learning_progress_スコアが範囲外でエラー(self) -> None:
        """スコアが0〜100の範囲外の場合はエラー"""
        with pytest.raises(ValueError, match="スコアは0〜100の範囲である必要があります"):
            LearningProgress(
                student_id="student_001",
                content_id="content_001",
                status=ProgressStatus.COMPLETED,
                started_at=datetime(2026, 3, 2, 10, 0, tzinfo=timezone.utc),
                completed_at=datetime(2026, 3, 2, 11, 0, tzinfo=timezone.utc),
                score=101,
            )
