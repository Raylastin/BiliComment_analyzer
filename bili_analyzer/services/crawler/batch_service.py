"""Tag search batch crawling with resume support."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from bili_analyzer.models import CrawlProgress
from bili_analyzer.services.crawler.batch_config import (
    SEARCH_ORDER_BY_SORT,
    PlayBucketConfig,
    TagSearchConfig,
)
from bili_analyzer.services.crawler.client import BiliClient, BiliClientError
from bili_analyzer.services.crawler.crawl_service import CrawlService
from bili_analyzer.services.crawler.parsers import parse_search_results, parse_video_info

ProgressCallback = Callable[[str], None]
CancelCheck = Callable[[], bool]


class BatchCrawlService:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        client: BiliClient | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.crawl_service = CrawlService(session_factory, client=client)
        self.client = self.crawl_service.client

    def close(self) -> None:
        self.crawl_service.close()

    def crawl_by_tag(
        self,
        config: TagSearchConfig,
        task_id: int | None = None,
        progress_callback: ProgressCallback | None = None,
        cancel_check: CancelCheck | None = None,
    ) -> dict[str, Any]:
        summary: dict[str, Any] = {
            "selected_videos": 0,
            "comments": 0,
            "replies": 0,
            "skipped": 0,
            "failed_videos": [],
        }
        for bucket in config.enabled_buckets():
            if cancel_check and cancel_check():
                break
            self._report(
                progress_callback, f"开始区间 {bucket.bucket_key}，目标 {bucket.count} 个视频"
            )
            selected = self._select_videos_for_bucket(
                config, bucket, task_id, progress_callback, cancel_check
            )
            summary["selected_videos"] += len(selected)

            for video in selected:
                if cancel_check and cancel_check():
                    break
                result = self._crawl_video_with_resume(
                    video=video,
                    task_id=task_id,
                    include_replies=config.include_replies,
                    progress_callback=progress_callback,
                    cancel_check=cancel_check,
                )
                if result is None:
                    summary["failed_videos"].append(video["bvid"])
                else:
                    summary["comments"] += result["comments"]
                    summary["replies"] += result["replies"]
                    summary["skipped"] += result["skipped"]
        return summary

    def _select_videos_for_bucket(
        self,
        config: TagSearchConfig,
        bucket: PlayBucketConfig,
        task_id: int | None,
        progress_callback: ProgressCallback | None,
        cancel_check: CancelCheck | None,
    ) -> list[dict[str, Any]]:
        scope_key = self._search_scope_key(config, bucket)
        saved = self._load_progress(task_id, "tag_search", scope_key)

        if saved and saved.get("done"):
            selected: list[dict[str, Any]] = []
            for item in saved.get("selected", []):
                item = dict(item)
                if item.get("pubdate"):
                    item["pubdate"] = datetime.fromisoformat(item["pubdate"])
                selected.append(item)
            return selected

        page = int((saved or {}).get("page", 1))
        candidates: dict[str, dict[str, Any]] = {}
        order = SEARCH_ORDER_BY_SORT.get(bucket.sort_by, "click")

        while page <= bucket.max_pages:
            if cancel_check and cancel_check():
                break
            data = self.client.get_json(
                "/x/web-interface/search/type",
                {
                    "search_type": "video",
                    "keyword": config.keyword,
                    "page": page,
                    "page_size": config.page_size,
                    "order": order,
                },
            )
            items = parse_search_results(data)
            if not items:
                break
            self._report(progress_callback, f"搜索第 {page} 页：{len(items)} 条")
            for item in items:
                if item.get("bvid"):
                    candidates[item["bvid"]] = item
            page += 1
            self._save_progress(
                task_id, "tag_search", scope_key, {"page": page}, done=False
            )

        matched: list[dict[str, Any]] = []
        for bvid, candidate in candidates.items():
            if cancel_check and cancel_check():
                break
            try:
                detail = self.client.get_json("/x/web-interface/view", {"bvid": bvid})
            except BiliClientError:
                continue
            video_info = parse_video_info(detail)
            video_info["bvid"] = bvid
            if not self._in_time_range(video_info.get("pubdate"), config):
                continue
            if not self._in_play_range(video_info.get("play_count"), bucket):
                continue
            matched.append(video_info)

        matched.sort(
            key=lambda item: item.get(bucket.sort_by, 0) or 0,
            reverse=True,
        )
        selected = matched[: bucket.count]
        selected_serializable = [
            {
                "bvid": item["bvid"],
                "aid": item.get("aid"),
                "title": item.get("title"),
                "tags": item.get("tags") or [],
                "pubdate": item["pubdate"].isoformat() if item.get("pubdate") else None,
                "play_count": item.get("play_count") or 0,
                "like_count": item.get("like_count") or 0,
                "reply_count": item.get("reply_count") or 0,
                "author_mid": item.get("author_mid"),
            }
            for item in selected
        ]
        self._save_progress(
            task_id,
            "tag_search",
            scope_key,
            {"page": page, "done": True, "selected": selected_serializable},
            done=True,
        )
        return selected

    def _crawl_video_with_resume(
        self,
        video: dict[str, Any],
        task_id: int | None,
        include_replies: bool,
        progress_callback: ProgressCallback | None,
        cancel_check: CancelCheck | None,
    ) -> dict[str, int] | None:
        bvid = video["bvid"]
        existing = self._load_progress(task_id, "video", bvid)
        if existing and existing.get("done"):
            self._report(progress_callback, f"跳过已完成视频 {bvid}")
            return {"comments": 0, "replies": 0, "skipped": 0}

        self._report(progress_callback, f"抓取视频 {bvid} 的评论")
        self.crawl_service.upsert_video_data(video, task_id=task_id)
        aid = video.get("aid")
        if not aid:
            self._save_progress(task_id, "video", bvid, {"error": "aid missing"}, done=False)
            return None

        try:
            stats = self.crawl_service.crawl_comments(
                bvid=bvid,
                aid=aid,
                include_replies=include_replies,
                task_id=task_id,
                progress_callback=progress_callback,
                cancel_check=cancel_check,
            )
        except BiliClientError as exc:
            self._save_progress(
                task_id, "video", bvid, {"error": str(exc)}, done=False
            )
            return None

        self._save_progress(task_id, "video", bvid, {"done": True}, done=True)
        return stats

    @staticmethod
    def _in_time_range(pubdate: Any, config: TagSearchConfig) -> bool:
        if pubdate is None:
            return True
        if config.start_time and pubdate < config.start_time:
            return False
        if config.end_time and pubdate > config.end_time:
            return False
        return True

    @staticmethod
    def _in_play_range(play_count: Any, bucket: PlayBucketConfig) -> bool:
        lower, upper = bucket.range()
        count = int(play_count or 0)
        if lower is not None and count < lower:
            return False
        if upper is not None and count >= upper:
            return False
        return True

    @staticmethod
    def _search_scope_key(config: TagSearchConfig, bucket: PlayBucketConfig) -> str:
        raw = json.dumps(
            {
                "keyword": config.keyword,
                "start": config.start_time.isoformat() if config.start_time else "",
                "end": config.end_time.isoformat() if config.end_time else "",
                "bucket": bucket.bucket_key,
                "sort": bucket.sort_by,
                "max_pages": bucket.max_pages,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:20]

    def _load_progress(
        self, task_id: int | None, scope_type: str, scope_key: str
    ) -> dict[str, Any] | None:
        if task_id is None:
            return None
        with self.session_factory() as session:
            row = session.scalar(
                select(CrawlProgress).where(
                    CrawlProgress.task_id == task_id,
                    CrawlProgress.scope_type == scope_type,
                    CrawlProgress.scope_key == scope_key,
                )
            )
            if row is None:
                return None
            return json.loads(row.cursor_json or "{}")

    def _save_progress(
        self,
        task_id: int | None,
        scope_type: str,
        scope_key: str,
        cursor: dict[str, Any],
        done: bool,
    ) -> None:
        if task_id is None:
            return
        with self.session_factory() as session:
            row = session.scalar(
                select(CrawlProgress).where(
                    CrawlProgress.task_id == task_id,
                    CrawlProgress.scope_type == scope_type,
                    CrawlProgress.scope_key == scope_key,
                )
            )
            if row is None:
                row = CrawlProgress(
                    task_id=task_id, scope_type=scope_type, scope_key=scope_key
                )
                session.add(row)
            row.cursor_json = json.dumps(cursor, ensure_ascii=False)
            row.status = "done" if done else "running"
            session.commit()

    @staticmethod
    def _report(callback: ProgressCallback | None, message: str) -> None:
        if callback:
            callback(message)
