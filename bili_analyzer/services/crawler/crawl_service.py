"""BV comment crawling orchestration with idempotent storage."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from bili_analyzer.models import Comment, User, Video, task_comments, task_videos
from bili_analyzer.services.crawler.client import BiliClient
from bili_analyzer.services.crawler.parsers import (
    parse_comment,
    parse_comment_list,
    parse_video_info,
)
from bili_analyzer.utils.time_utils import utcnow_naive

ProgressCallback = Callable[[str], None]
CancelCheck = Callable[[], bool]


class CrawlService:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        client: BiliClient | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.client = client or BiliClient()

    def close(self) -> None:
        self.client.close()

    def crawl_bv(
        self,
        bvid: str,
        include_replies: bool = True,
        max_pages: int | None = None,
        task_id: int | None = None,
        page_size: int = 49,
        progress_callback: ProgressCallback | None = None,
        cancel_check: CancelCheck | None = None,
    ) -> dict[str, int]:
        if cancel_check and cancel_check():
            return {"videos": 0, "comments": 0, "replies": 0, "skipped": 0}

        video_data = self.client.get_json("/x/web-interface/view", {"bvid": bvid})
        parsed_video = parse_video_info(video_data)
        if not parsed_video.get("bvid"):
            raise ValueError(f"Video not found for bvid: {bvid}")

        with self.session_factory() as session:
            video = self._upsert_video(session, parsed_video)
            aid = parsed_video["aid"] or video.aid
            if task_id:
                self._link_task_video(session, task_id, video.id)
            session.commit()
        if not aid:
            raise ValueError(f"Video aid missing for bvid: {bvid}")

        stats = {"videos": 1, "comments": 0, "replies": 0, "skipped": 0}
        page = 1
        while True:
            if cancel_check and cancel_check():
                break
            if max_pages is not None and page > max_pages:
                break

            data = self.client.get_json(
                "/x/v2/reply",
                {"type": 1, "oid": aid, "pn": page, "ps": page_size, "sort": 2},
            )
            replies = parse_comment_list(data)
            if not replies:
                break
            self._report(progress_callback, f"主评论第 {page} 页：{len(replies)} 条")

            inserted, skipped = self._store_comments(
                bvid=bvid,
                replies=replies,
                is_reply=False,
                task_id=task_id,
            )
            stats["comments"] += inserted
            stats["skipped"] += skipped

            if include_replies:
                for reply in replies:
                    if cancel_check and cancel_check():
                        break
                    rcount = reply.get("rcount") or 0
                    if not isinstance(rcount, int) or rcount <= 0:
                        continue
                    root_rpid = reply.get("rpid")
                    reply_inserted, reply_skipped = self._crawl_replies(
                        bvid=bvid,
                        aid=aid,
                        root_rpid=root_rpid,
                        task_id=task_id,
                        progress_callback=progress_callback,
                        cancel_check=cancel_check,
                    )
                    stats["replies"] += reply_inserted
                    stats["skipped"] += reply_skipped

            page += 1

        return stats

    def _crawl_replies(
        self,
        bvid: str,
        aid: int,
        root_rpid: int,
        task_id: int | None,
        progress_callback: ProgressCallback | None,
        cancel_check: CancelCheck | None,
    ) -> tuple[int, int]:
        inserted_total = 0
        skipped_total = 0
        page = 1
        while True:
            if cancel_check and cancel_check():
                break
            data = self.client.get_json(
                "/x/v2/reply/reply",
                {"type": 1, "oid": aid, "root": root_rpid, "pn": page, "ps": 20},
            )
            replies = parse_comment_list(data)
            if not replies:
                break
            self._report(
                progress_callback, f"楼中楼 root={root_rpid} 第 {page} 页：{len(replies)} 条"
            )
            inserted, skipped = self._store_comments(
                bvid=bvid,
                replies=replies,
                is_reply=True,
                task_id=task_id,
            )
            inserted_total += inserted
            skipped_total += skipped
            page += 1
        return inserted_total, skipped_total

    def _store_comments(
        self,
        bvid: str,
        replies: list[dict[str, Any]],
        is_reply: bool,
        task_id: int | None,
    ) -> tuple[int, int]:
        inserted = 0
        skipped = 0
        with self.session_factory() as session:
            for raw in replies:
                parsed = parse_comment(raw, is_reply=is_reply)
                rpid = parsed["rpid"]
                if not rpid or not parsed["mid"]:
                    continue
                existing = session.scalar(select(Comment.id).where(Comment.rpid == rpid))
                if existing is not None:
                    skipped += 1
                    continue

                user = self._get_or_create_user(session, parsed["user"])
                comment = Comment(
                    rpid=rpid,
                    bvid=bvid,
                    mid=user.mid,
                    parent_rpid=parsed["parent_rpid"],
                    root_rpid=parsed["root_rpid"],
                    is_reply=is_reply,
                    content=parsed["content"],
                    ctime=parsed["ctime"],
                    like_count=parsed["like_count"],
                )
                session.add(comment)
                session.flush()
                if task_id:
                    self._link_task_comment(session, task_id, comment.id)
                inserted += 1
            session.commit()
        return inserted, skipped

    @staticmethod
    def _upsert_video(session: Session, data: dict[str, Any]) -> Video:
        video = session.scalar(select(Video).where(Video.bvid == data["bvid"]))
        if video is None:
            video = Video()
            session.add(video)
        video.bvid = data["bvid"]
        video.aid = data["aid"] or None
        video.title = data["title"]
        video.tags_json = data.get("tags_json") or _tags_to_json(data.get("tags") or [])
        video.pubdate = data["pubdate"]
        video.play_count = data["play_count"]
        video.like_count = data["like_count"]
        video.reply_count = data["reply_count"]
        video.author_mid = data["author_mid"]
        return video

    @staticmethod
    def _get_or_create_user(session: Session, data: dict[str, Any]) -> User:
        user = session.scalar(select(User).where(User.mid == data["mid"]))
        if user is None:
            user = User(mid=data["mid"])
            session.add(user)
        if data.get("name"):
            user.name = data["name"]
        if data.get("avatar_url"):
            user.avatar_url = data["avatar_url"]
        if data.get("vip_status") is not None:
            user.vip_status = data["vip_status"]
            user.vip_raw_json = data.get("vip_raw_json")
            user.snapshot_at = utcnow_naive()
        return user

    @staticmethod
    def _link_task_video(session: Session, task_id: int, video_id: int) -> None:
        session.execute(
            task_videos.insert().prefix_with("OR IGNORE"),
            {"task_id": task_id, "video_id": video_id},
        )

    @staticmethod
    def _link_task_comment(session: Session, task_id: int, comment_id: int) -> None:
        session.execute(
            task_comments.insert().prefix_with("OR IGNORE"),
            {"task_id": task_id, "comment_id": comment_id},
        )

    @staticmethod
    def _report(callback: ProgressCallback | None, message: str) -> None:
        if callback:
            callback(message)


def _tags_to_json(tags: list[str]) -> str:
    from bili_analyzer.utils.json_utils import dumps

    return dumps(tags)
