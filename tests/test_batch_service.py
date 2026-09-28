from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from bili_analyzer.constants import SourceType, TaskStatus
from bili_analyzer.models import Comment, Task
from bili_analyzer.services.crawler import BatchCrawlService, PlayBucketConfig, TagSearchConfig


class FakeBatchClient:
    def __init__(self):
        self.search_items = [
            {"bvid": "BV100", "aid": 1001, "title": "视频A", "pubdate": 1717200000},
            {"bvid": "BV200", "aid": 1002, "title": "视频B", "pubdate": 1717300000},
            {"bvid": "BV300", "aid": 1003, "title": "视频C", "pubdate": 1717400000},
        ]
        self.details = {
            "BV100": {"bvid": "BV100", "aid": 1001, "title": "视频A", "pubdate": 1717200000, "stat": {"view": 500, "like": 10, "reply": 1}, "owner": {"mid": 9001}},
            "BV200": {"bvid": "BV200", "aid": 1002, "title": "视频B", "pubdate": 1717300000, "stat": {"view": 2000, "like": 20, "reply": 1}, "owner": {"mid": 9002}},
            "BV300": {"bvid": "BV300", "aid": 1003, "title": "视频C", "pubdate": 1717400000, "stat": {"view": 800, "like": 30, "reply": 1}, "owner": {"mid": 9003}},
        }

    def get_json(self, path, params=None):
        if path == "/x/web-interface/search/type":
            return {"result": self.search_items if params.get("page") == 1 else []}
        if path == "/x/web-interface/view":
            return self.details.get(params.get("bvid"), {})
        if path == "/x/v2/reply":
            aid = params.get("oid")
            if params.get("pn") != 1:
                return {"replies": []}
            return {
                "replies": [
                    {
                        "rpid": 300000 + aid,
                        "oid": aid,
                        "mid": 7000 + aid,
                        "member": {"mid": 7000 + aid, "uname": f"用户{aid}"},
                        "content": {"message": f"评论{aid}"},
                        "ctime": 1717500000,
                        "like": 1,
                        "rcount": 0,
                    }
                ]
            }
        if path == "/x/v2/reply/reply":
            return {"replies": []}
        raise AssertionError(f"Unexpected path: {path}")

    def close(self):
        pass


def _config() -> TagSearchConfig:
    return TagSearchConfig(
        keyword="测试标签",
        start_time=datetime(2024, 1, 1),
        end_time=datetime(2024, 12, 31),
        buckets=[PlayBucketConfig(bucket_key="100_1000", count=2, sort_by="play", max_pages=1)],
        include_replies=True,
    )


def test_batch_crawl_selects_by_play_range(engine):
    factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    with factory() as session:
        task = Task(name="批量", source_type=SourceType.TAG_SEARCH.value, status=TaskStatus.RUNNING.value)
        session.add(task)
        session.commit()
        task_id = task.id

    service = BatchCrawlService(factory, client=FakeBatchClient())
    summary = service.crawl_by_tag(_config(), task_id=task_id)

    assert summary["selected_videos"] == 2
    assert summary["comments"] == 2
    assert summary["replies"] == 0
    with factory() as session:
        assert session.query(Comment).count() == 2


def test_batch_crawl_resume_skips_completed(engine):
    factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    with factory() as session:
        task = Task(name="批量续爬", source_type=SourceType.TAG_SEARCH.value, status=TaskStatus.RUNNING.value)
        session.add(task)
        session.commit()
        task_id = task.id

    service = BatchCrawlService(factory, client=FakeBatchClient())
    first = service.crawl_by_tag(_config(), task_id=task_id)
    second = service.crawl_by_tag(_config(), task_id=task_id)

    assert first["selected_videos"] == 2
    assert second["selected_videos"] == 2
    assert second["comments"] == 0
    assert second["replies"] == 0
    assert second["skipped"] == 0
    with factory() as session:
        assert session.query(Comment).count() == 2

