"""Application entry point.

The GUI is intentionally not created in phase 1. This module currently
initialises the database so the skeleton can be run and tested from the
command line while later phases add the PySide6 UI.
"""

from __future__ import annotations

from bili_analyzer.config import load_config
from bili_analyzer.db import create_engine, init_db


def main() -> None:
    config = load_config()
    engine = create_engine(config.db_path)
    init_db(engine)
    print(f"Database initialised at: {config.db_path}")


if __name__ == "__main__":
    main()

