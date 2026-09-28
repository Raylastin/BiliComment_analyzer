from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from bili_analyzer.models import Comment, Task, task_comments
from bili_analyzer.services.analysis.emotion import (
    LocalLexiconAnalyzer,
    EmotionService,
    map_score_to_emotion,
)


def test_map_score_to_emotion():
    assert map_score_to_emotion(0.9).label == "正面"
    assert map_score_to_emotion(0.1).label == "负面"
    assert map_score_to_emotion(0.5).label == "中立"


def test_local_lexicon_analyzer():
    analyzer = LocalLexiconAnalyzer()
    assert analyzer.analyze("很好，很棒").label == "正面"
    assert analyzer.analyze("太垃圾了").label == "负面"
    assert analyzer.analyze("今天天气如何").label == "中立"


def _make_task_with_comments(factory) -> int:
    with factory() as session:
        task = Task(name="情感分析任务", source_type="bv", status="completed")
        session.add(task)
        session.flush()
        comments = [
            Comment(rpid=1001, bvid="BV100", mid=1, content="很好很棒", ctime=datetime.now()),
            Comment(rpid=1002, bvid="BV100", mid=2, content="太垃圾了", ctime=datetime.now()),
            Comment(rpid=1003, bvid="BV100", mid=3, content="随便看看", ctime=datetime.now()),
        ]
        session.add_all(comments)
        session.flush()
        for comment in comments:
            session.execute(
                task_comments.insert(),
                {"task_id": task.id, "comment_id": comment.id},
            )
        session.commit()
        return task.id


def test_emotion_service_analyzes_and_caches(engine):
    factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    task_id = _make_task_with_comments(factory)
    service = EmotionService(factory, analyzer=LocalLexiconAnalyzer())

    first = service.analyze_task(task_id)
    assert first == {"analyzed": 3, "cached": 0, "total": 3}

    with factory() as session:
        labels = set(session.scalars(select(Comment.emotion_label)))
    assert labels == {"正面", "负面", "中立"}

    second = service.analyze_task(task_id)
    assert second == {"analyzed": 0, "cached": 3, "total": 3}

    forced = service.analyze_task(task_id, force=True)
    assert forced == {"analyzed": 3, "cached": 0, "total": 3}

