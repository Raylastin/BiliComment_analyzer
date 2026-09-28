"""Main application window."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from PySide6.QtWidgets import QListWidget, QListWidgetItem, QMainWindow, QMessageBox, QStackedWidget
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from bili_analyzer.config import AppConfig, save_config
from bili_analyzer.constants import SourceType, TaskStatus
from bili_analyzer.models import Comment, Task, User, Video, task_comments
from bili_analyzer.services.analysis.emotion import EmotionService, LocalLexiconAnalyzer
from bili_analyzer.services.analysis.statistics import StatisticsService
from bili_analyzer.services.crawler import BatchCrawlService, CrawlService, PlayBucketConfig, TagSearchConfig
from bili_analyzer.services.crawler.client import BiliClient
from bili_analyzer.services.task_service import TaskService
from bili_analyzer.ui.pages import (
    CrawlConfigPage,
    DetailPage,
    HomePage,
    ProgressPage,
    ResultPage,
    SettingsPage,
)
from bili_analyzer.ui.workers import AnalyzeWorker, CrawlWorker
from bili_analyzer.utils.json_utils import dumps
from bili_analyzer.utils.mid_mask import mask_mid


class MainWindow(QMainWindow):
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        config: AppConfig,
    ) -> None:
        super().__init__()
        self.setWindowTitle(config.app_name)
        self.resize(1100, 760)

        self.session_factory = session_factory
        self.config = config
        self.task_service = TaskService(
            session_factory, config.export_dir, mask_mid=config.mask_mid
        )
        self.statistics_service = StatisticsService(session_factory)
        self.current_task_id: int | None = None
        self.current_worker: CrawlWorker | AnalyzeWorker | None = None

        self.sidebar = QListWidget()
        self.stack = QStackedWidget()
        self.pages: dict[str, Any] = {}
        self._build_pages()

        self._build_central()
        self.sidebar.currentRowChanged.connect(self.stack.setCurrentIndex)

        self.refresh_tasks()

    def _build_pages(self) -> None:
        self.home_page = HomePage()
        self.crawl_page = CrawlConfigPage()
        self.progress_page = ProgressPage()
        self.result_page = ResultPage()
        self.detail_page = DetailPage()
        self.settings_page = SettingsPage()

        self.pages = {
            "首页": self.home_page,
            "采集配置": self.crawl_page,
            "进度": self.progress_page,
            "分析结果": self.result_page,
            "详情": self.detail_page,
            "设置": self.settings_page,
        }
        for name, page in self.pages.items():
            self.sidebar.addItem(QListWidgetItem(name))
            self.stack.addWidget(page)

        self.home_page.refresh_requested.connect(self.refresh_tasks)
        self.home_page.new_task_requested.connect(lambda: self.sidebar.setCurrentRow(1))
        self.home_page.open_task_requested.connect(self.open_task)
        self.home_page.delete_task_requested.connect(self.delete_task)
        self.home_page.export_csv_requested.connect(lambda task_id: self.export_task(task_id, "csv"))
        self.home_page.export_xlsx_requested.connect(lambda task_id: self.export_task(task_id, "xlsx"))

        self.crawl_page.start_bv.connect(self.start_bv_crawl)
        self.crawl_page.start_tag.connect(self.start_tag_crawl)
        self.progress_page.pause_requested.connect(self.pause_worker)
        self.progress_page.resume_requested.connect(self.resume_worker)
        self.progress_page.stop_requested.connect(self.stop_worker)

        self.result_page.analyze_requested.connect(self.analyze_task)
        self.result_page.refresh_requested.connect(self.refresh_stats)
        self.result_page.detail_requested.connect(self.show_detail)
        self.detail_page.back_requested.connect(lambda: self.sidebar.setCurrentRow(3))

        self.settings_page.set_settings(
            {
                "positive_threshold": self.config.emotion.positive_threshold,
                "negative_threshold": self.config.emotion.negative_threshold,
                "rate_limit_interval": self.config.crawler.rate_limit_interval,
                "export_dir": str(self.config.export_dir),
                "mask_mid": self.config.mask_mid,
            }
        )
        self.settings_page.save_requested.connect(self.save_settings)

    def _build_central(self) -> None:
        from PySide6.QtWidgets import QHBoxLayout, QWidget

        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.addWidget(self.sidebar, 1)
        layout.addWidget(self.stack, 4)
        self.setCentralWidget(widget)

    def refresh_tasks(self) -> None:
        self.home_page.set_tasks(self.task_service.list_tasks())

    def open_task(self, task_id: int) -> None:
        task = self.task_service.get_task(task_id)
        if not task:
            return
        self.current_task_id = task_id
        self.result_page.set_task(task_id, task.get("name", ""))
        self.sidebar.setCurrentRow(3)
        self.refresh_stats(task_id, self.result_page.membership.currentData())

    def delete_task(self, task_id: int) -> None:
        self.task_service.delete_task(task_id)
        self.refresh_tasks()

    def export_task(self, task_id: int, fmt: str) -> None:
        try:
            path = self.task_service.export_task(task_id, fmt)
            QMessageBox.information(self, "导出成功", f"已导出到：\n{path}")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "导出失败", str(exc))

    def start_bv_crawl(self, params: dict) -> None:
        bvid = params["bvid"]
        if not bvid:
            QMessageBox.warning(self, "参数错误", "请输入 BV 号")
            return
        task_id = self._create_task(f"BV采集:{bvid}", SourceType.BV.value, params)
        service = CrawlService(
            self.session_factory,
            client=BiliClient(
                cookie=params.get("cookie"),
                timeout=self.config.crawler.request_timeout,
                retry_times=self.config.crawler.retry_times,
                rate_limit_interval=self.config.crawler.rate_limit_interval,
            ),
        )
        worker = CrawlWorker(
            service.crawl_bv,
            bvid,
            include_replies=params["include_replies"],
            max_pages=params["max_pages"],
            task_id=task_id,
        )
        self._start_worker(worker)

    def start_tag_crawl(self, params: dict) -> None:
        keyword = params["keyword"]
        if not keyword:
            QMessageBox.warning(self, "参数错误", "请输入标签关键词")
            return
        task_id = self._create_task(f"标签采集:{keyword}", SourceType.TAG_SEARCH.value, params)
        tag_config = TagSearchConfig(
            keyword=keyword,
            start_time=datetime.fromisoformat(params["start_time"]),
            end_time=datetime.fromisoformat(params["end_time"]),
            buckets=[
                PlayBucketConfig(
                    bucket_key=params["bucket_key"],
                    count=params["count"],
                    sort_by=params["sort_by"],
                    max_pages=params["max_pages"],
                )
            ],
            include_replies=params["include_replies"],
        )
        service = BatchCrawlService(
            self.session_factory,
            client=BiliClient(
                cookie=params.get("cookie"),
                timeout=self.config.crawler.request_timeout,
                retry_times=self.config.crawler.retry_times,
                rate_limit_interval=self.config.crawler.rate_limit_interval,
            ),
        )
        worker = CrawlWorker(service.crawl_by_tag, tag_config, task_id=task_id)
        self._start_worker(worker)

    def _create_task(self, name: str, source_type: str, params: dict) -> int:
        with self.session_factory() as session:
            task = Task(
                name=name,
                source_type=source_type,
                status=TaskStatus.RUNNING.value,
                config_json=dumps(params),
            )
            session.add(task)
            session.commit()
            return task.id

    def _start_worker(self, worker: CrawlWorker) -> None:
        self.current_worker = worker
        self.progress_page.log.clear()
        self.progress_page.set_running(True)
        self.sidebar.setCurrentRow(2)
        worker.progress.connect(self.progress_page.append_log)
        worker.result.connect(self._on_crawl_finished)
        worker.error.connect(self._on_worker_error)
        worker.finished.connect(lambda: self._on_worker_finished(worker))
        worker.start()

    def _on_crawl_finished(self, result: object) -> None:
        self.progress_page.append_log(f"采集完成：{result}")
        self.progress_page.set_running(False)
        self.refresh_tasks()
        if self.current_task_id:
            self._finish_task(self.current_task_id, TaskStatus.COMPLETED.value)

    def _on_worker_error(self, message: str) -> None:
        self.progress_page.append_log(f"错误：{message}")
        self.progress_page.set_running(False)
        if self.current_task_id:
            self._finish_task(self.current_task_id, TaskStatus.FAILED.value, message)
        QMessageBox.warning(self, "执行失败", message)

    def _on_worker_finished(self, worker: object) -> None:
        if self.current_worker is worker:
            self.current_worker = None

    def _finish_task(self, task_id: int, status: str, error: str | None = None) -> None:
        with self.session_factory() as session:
            task = session.get(Task, task_id)
            if task and task.status not in (TaskStatus.STOPPED.value,):
                task.status = status
                task.error_message = error
                task.finished_at = datetime.utcnow()
                session.commit()

    def pause_worker(self) -> None:
        if isinstance(self.current_worker, CrawlWorker):
            self.current_worker.pause()
            self.progress_page.append_log("已暂停")

    def resume_worker(self) -> None:
        if isinstance(self.current_worker, CrawlWorker):
            self.current_worker.resume()
            self.progress_page.append_log("已继续")

    def stop_worker(self) -> None:
        if self.current_worker is not None:
            self.current_worker.cancel()
            self.progress_page.append_log("正在停止...")
            if self.current_task_id:
                self._finish_task(self.current_task_id, TaskStatus.STOPPED.value)

    def analyze_task(self, task_id: int, force: bool) -> None:
        analyzer = LocalLexiconAnalyzer(
            positive_threshold=self.config.emotion.positive_threshold,
            negative_threshold=self.config.emotion.negative_threshold,
        )
        service = EmotionService(self.session_factory, analyzer=analyzer)
        worker = AnalyzeWorker(service.analyze_task, task_id, force=force)
        self.current_worker = worker
        self.progress_page.log.clear()
        self.progress_page.set_running(True)
        self.sidebar.setCurrentRow(2)
        worker.progress.connect(self.progress_page.append_log)
        worker.result.connect(self._on_analyze_finished)
        worker.error.connect(self._on_worker_error)
        worker.finished.connect(lambda: self._on_worker_finished(worker))
        worker.start()

    def _on_analyze_finished(self, result: object) -> None:
        self.progress_page.append_log(f"分析完成：{result}")
        self.progress_page.set_running(False)
        if self.current_task_id:
            self.refresh_stats(
                self.current_task_id, self.result_page.membership.currentData()
            )

    def refresh_stats(self, task_id: int, membership: str) -> None:
        overview = self.statistics_service.compute_overview(task_id, membership)
        transition = self.statistics_service.compute_transition(task_id, membership)
        extremes = self.statistics_service.compute_extremes(task_id, membership)
        self.result_page.show_overview(overview)
        self.result_page.show_transition(transition)
        self.result_page.show_extremes(extremes)

    def show_detail(self, task_id: int, mid: int) -> None:
        rows = self._user_comments(task_id, mid)
        self.detail_page.title.setText(
            f"用户 {mask_mid(mid) if self.config.mask_mid else mid} 的评论详情"
        )
        self.detail_page.set_comments(rows)
        self.sidebar.setCurrentRow(4)

    def _user_comments(self, task_id: int, mid: int) -> list[list]:
        with self.session_factory() as session:
            stmt = (
                select(Comment, Video.title, User.vip_status)
                .join(task_comments, task_comments.c.comment_id == Comment.id)
                .outerjoin(Video, Video.bvid == Comment.bvid)
                .outerjoin(User, User.mid == Comment.mid)
                .where(task_comments.c.task_id == task_id, Comment.mid == mid)
                .order_by(Comment.ctime)
            )
            rows = session.execute(stmt).all()
        result = []
        for comment, title, vip_status in rows:
            vip_text = {0: "非大会员", 1: "大会员"}.get(vip_status, "未知")
            result.append(
                [
                    comment.ctime.strftime("%Y-%m-%d %H:%M:%S") if comment.ctime else "",
                    comment.bvid,
                    title or "",
                    comment.content or "",
                    comment.like_count or 0,
                    comment.emotion_label or "",
                    round(comment.confidence, 4) if comment.confidence is not None else "",
                    vip_text,
                ]
            )
        return result

    def save_settings(self, settings: dict) -> None:
        self.config.emotion.positive_threshold = settings["positive_threshold"]
        self.config.emotion.negative_threshold = settings["negative_threshold"]
        self.config.crawler.rate_limit_interval = settings["rate_limit_interval"]
        self.config.export_dir = Path(settings["export_dir"])
        self.config.mask_mid = settings["mask_mid"]
        self.config.ensure_dirs()
        self.task_service.export_dir = self.config.export_dir
        self.task_service.mask_mid = self.config.mask_mid
        save_config(self.config)
        QMessageBox.information(self, "已保存", "设置已保存")
