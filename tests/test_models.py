from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy.exc import IntegrityError

from bili_analyzer.models import Comment, Task, User, Video


def test_task_and_video_roundtrip(session):
    task = Task(name="测试任务", source_type="bv", config_json="{}")
    video = Video(bvid="BV1xx411c7mD", aid=1, title="示例视频", play_count=123)
    session.add_all([task, video])
    session.commit()

    assert session.query(Task).count() == 1
    assert session.query(Video).filter_by(bvid="BV1xx411c7mD").one().title == "示例视频"


def test_video_bvid_unique(session):
    session.add(Video(bvid="BV1xx411c7mD"))
    session.commit()
    session.add(Video(bvid="BV1xx411c7mD"))
    with pytest.raises(IntegrityError):
        session.commit()


def test_comment_rpid_unique(session):
    session.add_all(
        [
            Comment(rpid=1, bvid="BV1xx411c7mD", mid=100, content="a", ctime=datetime.now()),
            Comment(rpid=2, bvid="BV1xx411c7mD", mid=101, content="b", ctime=datetime.now()),
        ]
    )
    session.commit()
    session.add(
        Comment(rpid=1, bvid="BV1xx411c7mD", mid=102, content="dup", ctime=datetime.now())
    )
    with pytest.raises(IntegrityError):
        session.commit()


def test_user_mid_unique_and_vip_null(session):
    session.add(User(mid=100, name="用户A", vip_status=None))
    session.commit()
    assert session.query(User).filter_by(mid=100).one().vip_status is None

    session.add(User(mid=100, name="重复"))
    with pytest.raises(IntegrityError):
        session.commit()

