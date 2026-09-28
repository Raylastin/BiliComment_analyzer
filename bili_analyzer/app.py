"""PySide6 application bootstrap."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from bili_analyzer.config import load_config
from bili_analyzer.db import create_engine, init_db, session_factory
from bili_analyzer.ui.main_window import MainWindow


def run() -> int:
    config = load_config()
    config.ensure_dirs()
    engine = create_engine(config.db_path)
    init_db(engine)

    app = QApplication(sys.argv)
    window = MainWindow(session_factory(engine), config)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(run())

