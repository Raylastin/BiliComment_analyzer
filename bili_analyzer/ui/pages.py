"""Application pages."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateTimeEdit,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QProgressBar,
    QSpinBox,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

try:
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
except ImportError:  # pragma: no cover
    from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

from bili_analyzer.services.analysis.charts import (
    extremes_figure,
    overview_figure,
    transition_figure,
)


class HomePage(QWidget):
    new_task_requested = Signal()
    open_task_requested = Signal(int)
    delete_task_requested = Signal(int)
    export_csv_requested = Signal(int)
    export_xlsx_requested = Signal(int)
    refresh_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["ID", "名称", "状态", "类型", "创建时间"])
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)

        buttons = QHBoxLayout()
        self.new_btn = QPushButton("新建任务")
        self.refresh_btn = QPushButton("刷新")
        self.open_btn = QPushButton("打开")
        self.export_csv_btn = QPushButton("导出CSV")
        self.export_xlsx_btn = QPushButton("导出Excel")
        self.delete_btn = QPushButton("删除")
        for button in [
            self.new_btn,
            self.refresh_btn,
            self.open_btn,
            self.export_csv_btn,
            self.export_xlsx_btn,
            self.delete_btn,
        ]:
            buttons.addWidget(button)
        layout.addLayout(buttons)

        self.new_btn.clicked.connect(self.new_task_requested.emit)
        self.refresh_btn.clicked.connect(self.refresh_requested.emit)
        self.open_btn.clicked.connect(self._emit_open)
        self.export_csv_btn.clicked.connect(lambda: self._emit_export("csv"))
        self.export_xlsx_btn.clicked.connect(lambda: self._emit_export("xlsx"))
        self.delete_btn.clicked.connect(self._emit_delete)

    def set_tasks(self, tasks: list[dict]) -> None:
        self.table.setRowCount(len(tasks))
        for row, task in enumerate(tasks):
            values = [
                str(task.get("id", "")),
                task.get("name", ""),
                task.get("status", ""),
                task.get("source_type", ""),
                task.get("created_at", ""),
            ]
            for col, value in enumerate(values):
                self.table.setItem(row, col, QTableWidgetItem(value))

    def selected_task_id(self) -> int | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return int(item.text()) if item else None

    def _emit_open(self) -> None:
        task_id = self.selected_task_id()
        if task_id is not None:
            self.open_task_requested.emit(task_id)

    def _emit_export(self, fmt: str) -> None:
        task_id = self.selected_task_id()
        if task_id is None:
            return
        if fmt == "csv":
            self.export_csv_requested.emit(task_id)
        else:
            self.export_xlsx_requested.emit(task_id)

    def _emit_delete(self) -> None:
        task_id = self.selected_task_id()
        if task_id is not None:
            self.delete_task_requested.emit(task_id)


class CrawlConfigPage(QWidget):
    start_bv = Signal(dict)
    start_tag = Signal(dict)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        self.tabs.addTab(self._build_bv_tab(), "BV采集")
        self.tabs.addTab(self._build_tag_tab(), "标签批量")

    def _build_bv_tab(self) -> QWidget:
        widget = QWidget()
        form = QFormLayout(widget)
        self.bvid_input = QLineEdit()
        self.cookie_input = QLineEdit()
        self.cookie_input.setEchoMode(QLineEdit.Password)
        self.include_replies = QCheckBox("包含楼中楼")
        self.include_replies.setChecked(True)
        self.max_pages = QSpinBox()
        self.max_pages.setRange(1, 1000)
        self.max_pages.setValue(0)
        self.max_pages.setSpecialValueText("不限制")
        form.addRow("BV号", self.bvid_input)
        form.addRow("Cookie(可选)", self.cookie_input)
        form.addRow("", self.include_replies)
        form.addRow("最大页数", self.max_pages)
        self.start_bv_btn = QPushButton("开始采集")
        form.addRow("", self.start_bv_btn)
        self.start_bv_btn.clicked.connect(self._emit_bv)
        return widget

    def _build_tag_tab(self) -> QWidget:
        widget = QWidget()
        form = QFormLayout(widget)
        self.keyword_input = QLineEdit()
        self.start_time = QDateTimeEdit()
        self.end_time = QDateTimeEdit()
        self.tag_cookie_input = QLineEdit()
        self.tag_cookie_input.setEchoMode(QLineEdit.Password)
        self.tag_include_replies = QCheckBox("包含楼中楼")
        self.tag_include_replies.setChecked(True)
        self.bucket_count = QSpinBox()
        self.bucket_count.setRange(0, 10000)
        self.bucket_count.setValue(5)
        self.bucket_pages = QSpinBox()
        self.bucket_pages.setRange(1, 100)
        self.bucket_pages.setValue(2)
        self.bucket_combo = QComboBox()
        self.bucket_combo.addItems(["100_1000", "1000_10000", "10000_100000", "100000_inf"])
        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["play", "pubdate"])
        form.addRow("标签关键词", self.keyword_input)
        form.addRow("开始时间", self.start_time)
        form.addRow("结束时间", self.end_time)
        form.addRow("Cookie(可选)", self.tag_cookie_input)
        form.addRow("", self.tag_include_replies)
        form.addRow("区间", self.bucket_combo)
        form.addRow("选取数量", self.bucket_count)
        form.addRow("最大页数", self.bucket_pages)
        form.addRow("排序方式", self.sort_combo)
        self.start_tag_btn = QPushButton("开始批量采集")
        form.addRow("", self.start_tag_btn)
        self.start_tag_btn.clicked.connect(self._emit_tag)
        return widget

    def _emit_bv(self) -> None:
        self.start_bv.emit(
            {
                "bvid": self.bvid_input.text().strip(),
                "cookie": self.cookie_input.text().strip() or None,
                "include_replies": self.include_replies.isChecked(),
                "max_pages": self.max_pages.value() or None,
            }
        )

    def _emit_tag(self) -> None:
        self.start_tag.emit(
            {
                "keyword": self.keyword_input.text().strip(),
                "cookie": self.tag_cookie_input.text().strip() or None,
                "include_replies": self.tag_include_replies.isChecked(),
                "bucket_key": self.bucket_combo.currentText(),
                "count": self.bucket_count.value(),
                "max_pages": self.bucket_pages.value(),
                "sort_by": self.sort_combo.currentText(),
                "start_time": self.start_time.dateTime().toString("yyyy-MM-ddTHH:mm:ss"),
                "end_time": self.end_time.dateTime().toString("yyyy-MM-ddTHH:mm:ss"),
            }
        )


class ProgressPage(QWidget):
    pause_requested = Signal()
    resume_requested = Signal()
    stop_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        layout.addWidget(self.progress)
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        layout.addWidget(self.log)
        buttons = QHBoxLayout()
        self.pause_btn = QPushButton("暂停")
        self.resume_btn = QPushButton("继续")
        self.stop_btn = QPushButton("停止")
        buttons.addWidget(self.pause_btn)
        buttons.addWidget(self.resume_btn)
        buttons.addWidget(self.stop_btn)
        layout.addLayout(buttons)
        self.pause_btn.clicked.connect(self.pause_requested.emit)
        self.resume_btn.clicked.connect(self.resume_requested.emit)
        self.stop_btn.clicked.connect(self.stop_requested.emit)

    def append_log(self, message: str) -> None:
        self.log.append(message)

    def set_running(self, running: bool) -> None:
        self.progress.setRange(0, 0 if running else 100)
        self.progress.setValue(100 if not running else 0)


class ResultPage(QWidget):
    analyze_requested = Signal(int, bool)
    refresh_requested = Signal(int, str)
    detail_requested = Signal(int, int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        self.task_label = QLabel("任务：未选择")
        self.membership = QComboBox()
        self.membership.addItem("全部", "all")
        self.membership.addItem("大会员", "member")
        self.membership.addItem("非大会员", "non_member")
        self.membership.addItem("未知", "unknown")
        self.analyze_btn = QPushButton("分析")
        self.reanalyze_btn = QPushButton("重新分析")
        self.refresh_btn = QPushButton("刷新统计")
        for widget in [self.task_label, self.membership, self.analyze_btn, self.reanalyze_btn, self.refresh_btn]:
            top.addWidget(widget)
        layout.addLayout(top)

        self.overview_canvas = QWidget()
        self.transition_canvas = QWidget()
        self.extremes_table = QTableWidget(0, 4)
        self.extremes_table.setHorizontalHeaderLabels(["类型", "用户(mid)", "评论数", "平均置信度"])
        layout.addWidget(self.overview_canvas)
        layout.addWidget(self.transition_canvas)
        layout.addWidget(QLabel("极值 Top10"))
        layout.addWidget(self.extremes_table)

        self.analyze_btn.clicked.connect(lambda: self.analyze_requested.emit(self.task_id, False))
        self.reanalyze_btn.clicked.connect(lambda: self.analyze_requested.emit(self.task_id, True))
        self.refresh_btn.clicked.connect(self._emit_refresh)
        self.membership.currentIndexChanged.connect(self._emit_refresh)
        self.extremes_table.doubleClicked.connect(self._emit_detail)

        self.task_id: int | None = None
        self._overview = None
        self._transition = None
        self._extremes = None

    def set_task(self, task_id: int, name: str) -> None:
        self.task_id = task_id
        self.task_label.setText(f"任务：{name} (#{task_id})")

    def show_overview(self, overview: dict) -> None:
        self._overview = overview
        self._replace_canvas(self.overview_canvas, overview_figure(overview))

    def show_transition(self, transition: dict) -> None:
        self._transition = transition
        self._replace_canvas(self.transition_canvas, transition_figure(transition))

    def show_extremes(self, extremes: dict) -> None:
        self._extremes = extremes
        rows = []
        for item in extremes["always_positive"]:
            rows.append(("一直正面", item))
        for item in extremes["always_negative"]:
            rows.append(("一直负面", item))
        self.extremes_table.setRowCount(len(rows))
        for row, (kind, item) in enumerate(rows):
            values = [kind, item["masked_mid"], item["comment_count"], item["avg_confidence"]]
            for col, value in enumerate(values):
                item_widget = QTableWidgetItem(str(value))
                if col == 0:
                    item_widget.setData(Qt.UserRole, item["mid"])
                self.extremes_table.setItem(row, col, item_widget)

    def _emit_refresh(self) -> None:
        if self.task_id is not None:
            self.refresh_requested.emit(self.task_id, self.membership.currentData())

    def _emit_detail(self, row: int) -> None:
        if self.task_id is None:
            return
        item = self.extremes_table.item(row, 0)
        mid = item.data(Qt.UserRole) if item else 0
        self.detail_requested.emit(self.task_id, int(mid or 0))

    def _replace_canvas(self, placeholder: QWidget, figure) -> None:
        layout = placeholder.layout()
        if layout is None:
            layout = QVBoxLayout(placeholder)
            layout.setContentsMargins(0, 0, 0, 0)
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        layout.addWidget(FigureCanvas(figure))


class DetailPage(QWidget):
    back_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.title = QLabel("用户评论详情")
        layout.addWidget(self.title)
        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(
            ["时间", "BV", "视频标题", "评论原文", "点赞数", "情感", "置信度", "大会员状态"]
        )
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.table)
        self.back_btn = QPushButton("返回结果")
        self.back_btn.clicked.connect(self.back_requested.emit)
        layout.addWidget(self.back_btn)

    def set_comments(self, rows: list[list]) -> None:
        self.table.setRowCount(len(rows))
        for row, values in enumerate(rows):
            for col, value in enumerate(values):
                self.table.setItem(row, col, QTableWidgetItem(str(value)))


class SettingsPage(QWidget):
    save_requested = Signal(dict)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        form = QFormLayout(self)
        self.positive_threshold = QSpinBox()
        self.positive_threshold.setRange(0, 100)
        self.positive_threshold.setValue(60)
        self.negative_threshold = QSpinBox()
        self.negative_threshold.setRange(0, 100)
        self.negative_threshold.setValue(40)
        self.rate_limit = QSpinBox()
        self.rate_limit.setRange(1, 10000)
        self.rate_limit.setValue(500)
        self.export_path = QLineEdit()
        self.mask_mid = QCheckBox("展示/导出时脱敏用户 mid")
        self.mask_mid.setChecked(True)
        form.addRow("正面阈值(百分比)", self.positive_threshold)
        form.addRow("负面阈值(百分比)", self.negative_threshold)
        form.addRow("请求间隔(毫秒)", self.rate_limit)
        form.addRow("导出路径", self.export_path)
        form.addRow("", self.mask_mid)
        self.save_btn = QPushButton("保存设置")
        self.save_btn.clicked.connect(self._emit_save)
        form.addRow("", self.save_btn)

    def set_settings(self, settings: dict[str, Any]) -> None:
        self.positive_threshold.setValue(int(settings.get("positive_threshold", 0.6) * 100))
        self.negative_threshold.setValue(int(settings.get("negative_threshold", 0.4) * 100))
        self.rate_limit.setValue(int(settings.get("rate_limit_interval", 0.5) * 1000))
        self.export_path.setText(settings.get("export_dir", ""))
        self.mask_mid.setChecked(bool(settings.get("mask_mid", True)))

    def _emit_save(self) -> None:
        self.save_requested.emit(
            {
                "positive_threshold": self.positive_threshold.value() / 100,
                "negative_threshold": self.negative_threshold.value() / 100,
                "rate_limit_interval": self.rate_limit.value() / 1000,
                "export_dir": self.export_path.text().strip(),
                "mask_mid": self.mask_mid.isChecked(),
            }
        )
