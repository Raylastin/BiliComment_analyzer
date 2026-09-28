from __future__ import annotations

from sqlalchemy import select

from bili_analyzer.models import Comment, User, Video
from bili_analyzer.services.crawler import CrawlService


class FakeBiliClient:
    def __init__(self):
        self.video_data = {
            "bvid": "BV1xx411c7mD",
            "aid": 170001,
            "title": "示例视频",
            "tags": ["测试"],
            "pubdate": 1700000000,
            "stat": {"view": 12345, "like": 678, "reply": 20},
            "owner": {"mid": 9001, "name": "UP主"},
        }
        self.main_replies = [
            {
                "rpid": 1001,
                "oid": 170001,
                "mid": 101,
                "member": {
                    "mid": 101,
                    "uname": "用户A",
                    "avatar": "http://avatar/a",
                    "vip": {"vipStatus": 1},
                },
                "content": {"message": "很好"},
                "ctime": 1700000001,
                "like": 5,
                "rcount": 2,
            },
            {
                "rpid": 1002,
                "oid": 170001,
                "mid": 102,
                "member": {"mid": 102, "uname": "用户B"},
                "content": {"message": "一般"},
                "ctime": 1700000002,
                "like": 2,
                "rcount": 0,
            },
        ]
        self.sub_replies = [
            {
                "rpid": 2001,
                "oid": 170001,
                "mid": 103,
                "member": {"mid": 103, "uname": "用户C"},
                "content": {"message": "回复"},
                "ctime": 1700000003,
                "like": 1,
                "parent": 1001,
                "root": 1001,
            }
        ]

    def get_json(self, path, params=None):
        if path == "/x/web-interface/view":
            return self.video_data
        if path == "/x/v2/reply":
            return {"replies": self.main_replies if params.get("pn") == 1 else []}
        if path == "/x/v2/reply/reply":
            return {"replies": self.sub_replies if params.get("pn") == 1 else []}
        raise AssertionError(f"Unexpected path: {path}")

    def close(self):
        pass


def test_crawl_bv_stores_and_deduplicates(engine):
    from sqlalchemy.orm import sessionmaker

    factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    service = CrawlService(factory, client=FakeBiliClient())

    stats = service.crawl_bv("BV1xx411c7mD", include_replies=True)
    assert stats == {"videos": 1, "comments": 2, "replies": 1, "skipped": 0}

    with factory() as session:
        assert session.scalar(select(Video).where(Video.bvid == "BV1xx411c7mD")) is not None
        assert session.query(User).count() == 3
        assert session.query(Comment).count() == 3

    stats2 = service.crawl_bv("BV1xx411c7mD", include_replies=True)
    assert stats2 == {"videos": 1, "comments": 0, "replies": 0, "skipped": 3}

