"""Task history, export and deletion."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from bili_analyzer.models import Comment, Task, User, Video, task_comments
from bili_analyzer.utils.mid_mask import mask_mid


class TaskService:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        export_dir: Path,
        mask_mid: bool = True,
    ) -> None:
        self.session_factory = session_factory
        self.export_dir = export_dir
        self.mask_mid = mask_mid
        self.export_dir.mkdir(parents=True, exist_ok=True)

    def list_tasks(self) -> list[dict]:
        with self.session_factory() as session:
            tasks = session.scalars(select(Task).order_by(Task.created_at.desc())).all()
            return [
                {
                    "id": task.id,
                    "name": task.name,
                    "status": task.status,
                    "source_type": task.source_type,
                    "created_at": task.created_at.strftime("%Y-%m-%d %H:%M:%S")
                    if task.created_at
                    else "",
                }
                for task in tasks
            ]

    def get_task(self, task_id: int) -> dict:
        with self.session_factory() as session:
            task = session.get(Task, task_id)
            if task is None:
                return {}
            return {
                "id": task.id,
                "name": task.name,
                "status": task.status,
                "source_type": task.source_type,
                "config_json": task.config_json,
                "created_at": task.created_at.strftime("%Y-%m-%d %H:%M:%S")
                if task.created_at
                else "",
                "error_message": task.error_message,
            }

    def delete_task(self, task_id: int) -> None:
        with self.session_factory() as session:
            task = session.get(Task, task_id)
            if task is not None:
                session.delete(task)
                session.commit()

    def export_task(self, task_id: int, fmt: str = "csv") -> Path:
        rows = self._task_comment_rows(task_id)
        df = pd.DataFrame(
            rows,
            columns=[
                "评论时间", "BV号", "视频标题", "评论原文", "点赞数",
                "情感", "置信度", "大会员状态", "用户(mid)",
            ],
        )
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if fmt == "xlsx":
            path = self.export_dir / f"task_{task_id}_comments_{timestamp}.xlsx"
            df.to_excel(path, index=False)
        else:
            path = self.export_dir / f"task_{task_id}_comments_{timestamp}.csv"
            df.to_csv(path, index=False, encoding="utf-8-sig")
        return path

    def _task_comment_rows(self, task_id: int) -> list[list]:
        with self.session_factory() as session:
            stmt = (
                select(
                    Comment.ctime,
                    Comment.bvid,
                    Video.title,
                    Comment.content,
                    Comment.like_count,
                    Comment.emotion_label,
                    Comment.confidence,
                    Comment.mid,
                    User.vip_status,
                )
                .join(task_comments, task_comments.c.comment_id == Comment.id)
                .outerjoin(Video, Video.bvid == Comment.bvid)
                .outerjoin(User, User.mid == Comment.mid)
                .where(task_comments.c.task_id == task_id)
                .order_by(Comment.ctime)
            )
            result = session.execute(stmt).all()

        rows: list[list] = []
        for item in result:
            vip_text = {0: "非大会员", 1: "大会员"}.get(item.vip_status, "未知")
            mid = mask_mid(item.mid) if self.mask_mid else str(item.mid)
            rows.append(
                [
                    item.ctime.strftime("%Y-%m-%d %H:%M:%S") if item.ctime else "",
                    item.bvid or "",
                    item.title or "",
                    item.content or "",
                    item.like_count or 0,
                    item.emotion_label or "",
                    round(item.confidence, 4) if item.confidence is not None else "",
                    vip_text,
                    mid,
                ]
            )
        return rows

