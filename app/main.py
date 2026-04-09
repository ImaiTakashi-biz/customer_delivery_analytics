# -*- coding: utf-8 -*-
"""
顧客別納入分析システム エントリポイント。
実行: プロジェクトルートで  python -m app.main
"""

from __future__ import annotations

import sys

# Shiboken が six.moves をフックした後に pandas→dateutil→six を通すと環境によって例外になるため、
# 先に pandas を完了 import してから Qt を読み込む。
import pandas as pd  # noqa: F401

from PySide6.QtWidgets import QApplication

from app.config import settings
from app.ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(settings.APP_DISPLAY_NAME)
    app.setApplicationDisplayName(settings.APP_DISPLAY_NAME)

    window = MainWindow()
    window.setWindowTitle(settings.WINDOW_TITLE)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
