"""Emotion analysis orchestration with database caching."""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from bili_analyzer.models import Comment, task_comments
from bili_analyzer.services.analysis.emotion.base import EmotionAnalyzer
from bili_analyzer.services.analysis.emotion.local_model import LocalLexiconAnalyzer
from bili_analyzer.utils.time_utils import utcnow_naive

ProgressCallback = Callable[[str], None]
CancelCheck = Callable[[], bool]


class EmotionService:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        analyzer: EmotionAnalyzer | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.analyzer = analyzer or LocalLexiconAnalyzer()

    def analyze_task(
        self,
        task_id: int,
        force: bool = False,
        progress_callback: ProgressCallback | None = None,
        cancel_check: CancelCheck | None = None,
    ) -> dict[str, int]:
        comment_ids = self._task_comment_ids(task_id)
        analyzed = 0
        cached = 0
        for index, comment_id in enumerate(comment_ids, start=1):
            if cancel_check and cancel_check():
                break
            if self.analyze_comment(comment_id, force=force):
                analyzed += 1
            else:
                cached += 1
            if progress_callback and index % 10 == 0:
                progress_callback(f"情感分析进度：{index}/{len(comment_ids)}")
        if progress_callback:
            progress_callback(f"情感分析完成：分析 {analyzed}，复用缓存 {cached}")
        return {"analyzed": analyzed, "cached": cached, "total": len(comment_ids)}

    def analyze_comment(self, comment_id: int, force: bool = False) -> bool:
        with self.session_factory() as session:
            comment = session.get(Comment, comment_id)
            if comment is None:
                return False
            if not force and comment.emotion_label is not None:
                return False

            result = self.analyzer.analyze(comment.content)
            comment.emotion_label = result.label
            comment.confidence = result.confidence
            comment.emotion_analyzed_at = utcnow_naive()
            session.commit()
            return True

    def _task_comment_ids(self, task_id: int) -> list[int]:
        with self.session_factory() as session:
            stmt = (
                select(Comment.id)
                .join(task_comments, task_comments.c.comment_id == Comment.id)
                .where(task_comments.c.task_id == task_id)
                .order_by(Comment.id)
            )
            return list(session.scalars(stmt))

