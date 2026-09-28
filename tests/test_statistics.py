from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.orm import sessionmaker

from bili_analyzer.models import Comment, Task, User, task_comments
from bili_analyzer.services.analysis.statistics import StatisticsService


def _make_dataset(factory) -> int:
    base = datetime(2024, 1, 1, 12, 0, 0)
    with factory() as session:
        task = Task(name="统计任务", source_type="bv", status="completed")
        session.add(task)
        session.flush()

        users = [
            User(mid=1, name="u1", vip_status=1),
            User(mid=2, name="u2", vip_status=0),
            User(mid=3, name="u3", vip_status=None),
            User(mid=4, name="u4", vip_status=1),
        ]
        session.add_all(users)
        session.flush()

        rows = [
            (101, 1, "正面", 0.9, base),
            (102, 1, "负面", 0.8, base + timedelta(minutes=1)),
            (103, 1, "负面", 0.7, base + timedelta(minutes=2)),
            (104, 2, "正面", 0.9, base),
            (105, 2, "正面", 0.8, base + timedelta(minutes=1)),
            (106, 3, "正面", 0.8, base),
            (107, 3, "中立", 0.6, base + timedelta(minutes=1)),
            (108, 3, "负面", 0.9, base + timedelta(minutes=2)),
            (109, 4, "负面", 0.7, base),
            (110, 4, "负面", 0.8, base + timedelta(minutes=1)),
        ]
        comments = []
        for rpid, mid, label, confidence, ctime in rows:
            comments.append(
                Comment(
                    rpid=rpid,
                    bvid="BVSTAT",
                    mid=mid,
                    content="x",
                    ctime=ctime,
                    emotion_label=label,
                    confidence=confidence,
                )
            )
        session.add_all(comments)
        session.flush()
        for comment in comments:
            session.execute(
                task_comments.insert(),
                {"task_id": task.id, "comment_id": comment.id},
            )
        session.commit()
        return task.id


def test_overview_all(engine):
    factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    task_id = _make_dataset(factory)
    service = StatisticsService(factory)
    result = service.compute_overview(task_id)

    assert result["total_comments"] == 10
    assert result["total_users"] == 4
    assert result["by_comment"]["正面"]["count"] == 4
    assert result["by_comment"]["负面"]["count"] == 5
    assert result["by_comment"]["中立"]["count"] == 1
    assert result["by_user"]["负面"]["count"] == 3
    assert result["by_user"]["正面"]["count"] == 1


def test_overview_membership_filter(engine):
    factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    task_id = _make_dataset(factory)
    service = StatisticsService(factory)
    result = service.compute_overview(task_id, membership="member")
    assert result["total_comments"] == 5
    assert result["total_users"] == 2
    assert result["by_user"]["负面"]["count"] == 2


def test_transition_and_extremes(engine):
    factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    task_id = _make_dataset(factory)
    service = StatisticsService(factory)

    transition = service.compute_transition(task_id)
    assert transition["eligible_users"] == 4
    assert transition["multiple_conversions"] == 1
    assert transition["six_transitions"]["正面→负面"] == 1
    assert transition["final_tendency"]["负面"] == 1

    extremes = service.compute_extremes(task_id)
    assert extremes["always_positive"][0]["mid"] == 2
    assert extremes["always_negative"][0]["mid"] == 4

    member_extremes = service.compute_extremes(task_id, membership="member")
    assert member_extremes["always_positive"] == []
    assert member_extremes["always_negative"][0]["mid"] == 4

