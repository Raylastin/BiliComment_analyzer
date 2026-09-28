"""Shared enums and constant values."""

from __future__ import annotations

from enum import Enum


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    COMPLETED = "completed"
    FAILED = "failed"


class SourceType(str, Enum):
    BV = "bv"
    TAG_SEARCH = "tag_search"


class VipStatus(int, Enum):
    NON_MEMBER = 0
    MEMBER = 1
    UNKNOWN = -1


class EmotionLabel(str, Enum):
    POSITIVE = "正面"
    NEGATIVE = "负面"
    NEUTRAL = "中立"


class AnalysisResultType(str, Enum):
    SENTIMENT_OVERVIEW = "sentiment_overview"
    USER_TRANSITION = "user_transition"
    EXTREME_USERS = "extreme_users"


class CrawlScopeType(str, Enum):
    BV = "bv"
    TAG_SEARCH = "tag_search"


class CrawlStepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class MembershipFilter(str, Enum):
    ALL = "all"
    MEMBER = "member"
    NON_MEMBER = "non_member"
    UNKNOWN = "unknown"


# Play-count buckets as [lower, upper) with upper == None meaning infinity.
PLAY_COUNT_BUCKETS: dict[str, tuple[int | None, int | None]] = {
    "100_1000": (100, 1_000),
    "1000_10000": (1_000, 10_000),
    "10000_100000": (10_000, 100_000),
    "100000_inf": (100_000, None),
}
