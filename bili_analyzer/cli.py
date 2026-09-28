"""Command line helpers for early-stage verification."""

from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime

from bili_analyzer.config import load_config
from bili_analyzer.constants import SourceType, TaskStatus
from bili_analyzer.db import create_engine, init_db, session_factory
from bili_analyzer.models import Task
from bili_analyzer.services.analysis.emotion import EmotionService, LocalLexiconAnalyzer
from bili_analyzer.services.analysis.statistics import StatisticsService
from bili_analyzer.services.crawler import BatchCrawlService, CrawlService, PlayBucketConfig, TagSearchConfig
from bili_analyzer.services.crawler.client import BiliClient
from bili_analyzer.utils.json_utils import dumps
from bili_analyzer.utils.logging_setup import setup_logging


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bili-analyzer", description="B站评论分析器 CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("initdb", help="初始化数据库")
    init_parser.set_defaults(func=_cmd_initdb)

    crawl_parser = subparsers.add_parser("crawl", help="抓取单个 BV 的评论")
    crawl_parser.add_argument("bvid")
    crawl_parser.add_argument("--no-replies", action="store_true", help="不抓取楼中楼")
    crawl_parser.add_argument("--max-pages", type=int, default=None)
    crawl_parser.add_argument("--cookie", default=None, help="可选 Cookie，仅本机使用")
    crawl_parser.set_defaults(func=_cmd_crawl)

    tag_parser = subparsers.add_parser("crawl-tag", help="按标签批量搜索并抓取评论")
    tag_parser.add_argument("--config-file", required=True, help="批量采集 JSON 配置路径")
    tag_parser.add_argument("--task-id", type=int, default=None, help="续爬时指定已有任务 ID")
    tag_parser.add_argument("--cookie", default=None, help="可选 Cookie，仅本机使用")
    tag_parser.set_defaults(func=_cmd_crawl_tag)

    analyze_parser = subparsers.add_parser("analyze", help="对任务评论做情感分析")
    analyze_parser.add_argument("--task-id", type=int, required=True)
    analyze_parser.add_argument("--force", action="store_true", help="忽略缓存重新分析")
    analyze_parser.set_defaults(func=_cmd_analyze)

    stats_parser = subparsers.add_parser("stats", help="输出任务统计结果")
    stats_parser.add_argument("--task-id", type=int, required=True)
    stats_parser.add_argument("--type", choices=["overview", "transition", "extremes"], required=True)
    stats_parser.add_argument("--membership", default="all", choices=["all", "member", "non_member", "unknown"])
    stats_parser.set_defaults(func=_cmd_stats)
    return parser


def _cmd_initdb(args: argparse.Namespace) -> None:
    config = load_config()
    engine = create_engine(config.db_path)
    init_db(engine)
    print(f"数据库已初始化：{config.db_path}")


def _cmd_crawl(args: argparse.Namespace) -> None:
    config = load_config()
    config.ensure_dirs()
    logger = setup_logging(config.log_dir, logging.INFO)
    engine = create_engine(config.db_path)
    init_db(engine)

    client = BiliClient(
        cookie=args.cookie,
        timeout=config.crawler.request_timeout,
        retry_times=config.crawler.retry_times,
        rate_limit_interval=config.crawler.rate_limit_interval,
    )
    service = CrawlService(session_factory(engine), client=client)

    def progress(message: str) -> None:
        print(message)
        logger.info(message)

    try:
        stats = service.crawl_bv(
            args.bvid,
            include_replies=not args.no_replies,
            max_pages=args.max_pages,
            progress_callback=progress,
        )
        print("统计结果：", stats)
    finally:
        service.close()


def _cmd_crawl_tag(args: argparse.Namespace) -> None:
    raw = json.loads(open(args.config_file, encoding="utf-8").read())
    config = load_config()
    config.ensure_dirs()
    logger = setup_logging(config.log_dir, logging.INFO)
    engine = create_engine(config.db_path)
    init_db(engine)

    buckets = [
        PlayBucketConfig(
            bucket_key=item["bucket_key"],
            count=int(item.get("count", 0)),
            sort_by=item.get("sort_by", "play"),
            max_pages=int(item.get("max_pages", 1)),
        )
        for item in raw.get("buckets", [])
    ]
    tag_config = TagSearchConfig(
        keyword=raw["keyword"],
        start_time=_parse_time(raw.get("start_time")),
        end_time=_parse_time(raw.get("end_time")),
        buckets=buckets,
        page_size=int(raw.get("page_size", 20)),
        include_replies=bool(raw.get("include_replies", True)),
    )

    factory = session_factory(engine)
    if args.task_id:
        task_id = args.task_id
    else:
        with factory() as session:
            task = Task(
                name=f"标签:{raw['keyword']}",
                source_type=SourceType.TAG_SEARCH.value,
                config_json=dumps(raw),
                status=TaskStatus.RUNNING.value,
            )
            session.add(task)
            session.commit()
            task_id = task.id

    client = BiliClient(
        cookie=args.cookie,
        timeout=config.crawler.request_timeout,
        retry_times=config.crawler.retry_times,
        rate_limit_interval=config.crawler.rate_limit_interval,
    )
    service = BatchCrawlService(factory, client=client)

    def progress(message: str) -> None:
        print(message)
        logger.info(message)

    try:
        summary = service.crawl_by_tag(
            tag_config,
            task_id=task_id,
            progress_callback=progress,
        )
        print("统计结果：", summary)
        with factory() as session:
            task = session.get(Task, task_id)
            if task:
                task.status = TaskStatus.COMPLETED.value
                session.commit()
    except Exception:
        logger.exception("批量抓取失败")
        with factory() as session:
            task = session.get(Task, task_id)
            if task:
                task.status = TaskStatus.FAILED.value
                session.commit()
        raise
    finally:
        service.close()


def _cmd_analyze(args: argparse.Namespace) -> None:
    config = load_config()
    config.ensure_dirs()
    logger = setup_logging(config.log_dir, logging.INFO)
    engine = create_engine(config.db_path)
    init_db(engine)

    analyzer = LocalLexiconAnalyzer(
        positive_threshold=config.emotion.positive_threshold,
        negative_threshold=config.emotion.negative_threshold,
    )
    service = EmotionService(session_factory(engine), analyzer=analyzer)

    def progress(message: str) -> None:
        print(message)
        logger.info(message)

    result = service.analyze_task(args.task_id, force=args.force, progress_callback=progress)
    print("统计结果：", result)


def _cmd_stats(args: argparse.Namespace) -> None:
    config = load_config()
    engine = create_engine(config.db_path)
    init_db(engine)
    service = StatisticsService(session_factory(engine))

    if args.type == "overview":
        result = service.compute_overview(args.task_id, membership=args.membership)
    elif args.type == "transition":
        result = service.compute_transition(args.task_id, membership=args.membership)
    else:
        result = service.compute_extremes(args.task_id, membership=args.membership)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
