"""Application configuration loaded from a local JSON file."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

APP_NAME = "B站评论分析器"
APP_DIR_NAME = "bili_analyzer"


def default_data_dir() -> Path:
    return Path.home() / f".{APP_DIR_NAME}"


@dataclass
class EmotionConfig:
    provider: str = "local"
    positive_threshold: float = 0.6
    negative_threshold: float = 0.4


@dataclass
class CrawlerConfig:
    request_timeout: float = 10.0
    retry_times: int = 3
    rate_limit_interval: float = 0.5
    max_workers: int = 2
    comment_page_size: int = 49
    include_replies: bool = True
    max_reply_pages: int = 5


@dataclass
class AppConfig:
    app_name: str = APP_NAME
    data_dir: Path = field(default_factory=default_data_dir)
    db_path: Path = Path("data/bili_analyzer.db")
    log_dir: Path = Path("logs")
    export_dir: Path = Path("exports")
    mask_mid: bool = True
    emotion: EmotionConfig = field(default_factory=EmotionConfig)
    crawler: CrawlerConfig = field(default_factory=CrawlerConfig)

    def resolve_paths(self, base_dir: Path | None = None) -> None:
        root = base_dir or Path.cwd()
        if not self.db_path.is_absolute():
            self.db_path = root / self.db_path
        if not self.log_dir.is_absolute():
            self.log_dir = root / self.log_dir
        if not self.export_dir.is_absolute():
            self.export_dir = root / self.export_dir

    def ensure_dirs(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.export_dir.mkdir(parents=True, exist_ok=True)


def _as_dict(config: AppConfig) -> dict[str, Any]:
    return {
        "app_name": config.app_name,
        "db_path": str(config.db_path),
        "log_dir": str(config.log_dir),
        "export_dir": str(config.export_dir),
        "mask_mid": config.mask_mid,
        "emotion": {
            "provider": config.emotion.provider,
            "positive_threshold": config.emotion.positive_threshold,
            "negative_threshold": config.emotion.negative_threshold,
        },
        "crawler": {
            "request_timeout": config.crawler.request_timeout,
            "retry_times": config.crawler.retry_times,
            "rate_limit_interval": config.crawler.rate_limit_interval,
            "max_workers": config.crawler.max_workers,
            "comment_page_size": config.crawler.comment_page_size,
            "include_replies": config.crawler.include_replies,
            "max_reply_pages": config.crawler.max_reply_pages,
        },
    }


def load_config(path: Path | None = None, base_dir: Path | None = None) -> AppConfig:
    config = AppConfig()
    if path is None:
        path = Path("config.json")
    if path.exists():
        raw = json.loads(path.read_text(encoding="utf-8"))
        config.db_path = Path(raw.get("db_path", config.db_path))
        config.log_dir = Path(raw.get("log_dir", config.log_dir))
        config.export_dir = Path(raw.get("export_dir", config.export_dir))
        config.mask_mid = raw.get("mask_mid", config.mask_mid)
        config.emotion = EmotionConfig(**raw.get("emotion", {}))
        config.crawler = CrawlerConfig(**raw.get("crawler", {}))
    config.resolve_paths(base_dir)
    return config


def save_config(config: AppConfig, path: Path | None = None) -> None:
    if path is None:
        path = Path("config.json")
    path.write_text(
        json.dumps(_as_dict(config), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

