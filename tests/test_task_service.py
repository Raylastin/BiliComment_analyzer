from __future__ import annotations

from datetime import datetime

import pandas as pd
from sqlalchemy.orm import sessionmaker

from bili_analyzer.models import Comment, Task, User, Video, task_comments
from bili_analyzer.services.task_service import TaskService


def _make_export_dataset(factory, export_dir):
    with factory() as session:
        task = Task(name="导出任务", source_type="bv", status="completed")
        session.add(task)
        session.flush()
        video = Video(bvid="BVEXPORT", aid=1, title="导出视频")
        user = User(mid=123456, name="用户", vip_status=1)
        session.add_all([video, user])
        session.flush()
        comment = Comment(
            rpid=9001,
            bvid="BVEXPORT",
            mid=123456,
            content="很好",
            ctime=datetime(2024, 1, 1, 12, 0, 0),
            emotion_label="正面",
            confidence=0.9,
        )
        session.add(comment)
        session.flush()
        session.execute(
            task_comments.insert(), {"task_id": task.id, "comment_id": comment.id}
        )
        session.commit()
        return task.id


def test_export_csv_and_delete(engine, tmp_path):
    factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    task_id = _make_export_dataset(factory, tmp_path)
    service = TaskService(factory, tmp_path, mask_mid=True)

    csv_path = service.export_task(task_id, "csv")
    assert csv_path.exists()
    df = pd.read_csv(csv_path)
    assert df["情感"].iloc[0] == "正面"
    assert df["用户(mid)"].iloc[0] == "123****56"

    xlsx_path = service.export_task(task_id, "xlsx")
    assert xlsx_path.exists()

    service.delete_task(task_id)
    assert service.get_task(task_id) == {}

