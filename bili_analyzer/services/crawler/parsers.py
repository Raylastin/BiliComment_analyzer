"""Parsers for Bilibili API responses."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from bili_analyzer.utils.json_utils import dumps


def _ts_to_dt(ts: Any) -> datetime | None:
    if ts in (None, "", 0):
        return None
    try:
        value = int(ts)
    except (TypeError, ValueError):
        return None
    if value <= 0:
        return None
    return datetime.fromtimestamp(value, tz=timezone.utc).replace(tzinfo=None)


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def parse_vip_status(member: dict[str, Any]) -> int | None:
    vip = member.get("vip") or {}
    status = vip.get("vipStatus", vip.get("status"))
    if status in (0, 1):
        return int(status)
    return None


def parse_user_from_member(member: dict[str, Any]) -> dict[str, Any]:
    vip_status = parse_vip_status(member)
    return {
        "mid": _as_int(member.get("mid")),
        "name": member.get("uname") or member.get("name"),
        "avatar_url": member.get("avatar"),
        "vip_status": vip_status,
        "vip_raw_json": dumps(member.get("vip") or {}),
    }


def parse_video_info(data: dict[str, Any]) -> dict[str, Any]:
    stat = data.get("stat") or {}
    owner = data.get("owner") or {}
    tags = data.get("tags") if isinstance(data.get("tags"), list) else []
    return {
        "bvid": data.get("bvid"),
        "aid": _as_int(data.get("aid")),
        "title": data.get("title"),
        "tags": [str(tag) for tag in tags],
        "pubdate": _ts_to_dt(data.get("pubdate")),
        "play_count": _as_int(stat.get("view")),
        "like_count": _as_int(stat.get("like")),
        "reply_count": _as_int(stat.get("reply")),
        "author_mid": _as_int(owner.get("mid")) if owner.get("mid") else None,
    }


def parse_comment(reply: dict[str, Any], is_reply: bool = False) -> dict[str, Any]:
    member = reply.get("member") or {}
    content = (reply.get("content") or {}).get("message", "")
    return {
        "rpid": _as_int(reply.get("rpid")),
        "mid": _as_int(member.get("mid")),
        "parent_rpid": _as_int(reply.get("parent")) if is_reply else None,
        "root_rpid": _as_int(reply.get("root")) if is_reply else None,
        "is_reply": is_reply,
        "content": content,
        "ctime": _ts_to_dt(reply.get("ctime")),
        "like_count": _as_int(reply.get("like")),
        "user": parse_user_from_member(member),
    }


def parse_comment_list(data: dict[str, Any]) -> list[dict[str, Any]]:
    replies = data.get("replies")
    if not isinstance(replies, list):
        return []
    return replies

