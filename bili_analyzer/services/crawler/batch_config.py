"""Configuration structures for tag-based batch crawling."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from bili_analyzer.constants import PLAY_COUNT_BUCKETS


@dataclass
class PlayBucketConfig:
    bucket_key: str
    count: int = 0
    sort_by: str = "play"
    max_pages: int = 1

    def range(self) -> tuple[int | None, int | None]:
        return PLAY_COUNT_BUCKETS[self.bucket_key]


@dataclass
class TagSearchConfig:
    keyword: str
    start_time: datetime | None = None
    end_time: datetime | None = None
    buckets: list[PlayBucketConfig] = field(default_factory=list)
    page_size: int = 20
    include_replies: bool = True

    def enabled_buckets(self) -> list[PlayBucketConfig]:
        return [bucket for bucket in self.buckets if bucket.count > 0]


SEARCH_ORDER_BY_SORT: dict[str, str] = {
    "play": "click",
    "pubdate": "pubdate",
}

