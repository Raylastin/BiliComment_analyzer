"""Command line helpers for early-stage verification."""

from __future__ import annotations

import argparse
import logging

from bili_analyzer.config import load_config
from bili_analyzer.db import create_engine, init_db, session_factory
from bili_analyzer.services.crawler import CrawlService
from bili_analyzer.services.crawler.client import BiliClient
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


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
