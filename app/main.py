# -*- coding: utf-8 -*-
"""
顧客別納入分析システム エントリポイント。
実行:
  - 推奨: プロジェクトルートで  python -m app.main
  - 直接実行: python app/main.py（下記でプロジェクトルートを path に追加）
"""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

# app/main.py を直接実行したとき import app.* が通るよう、プロジェクトルートを先頭に追加
_project_root = Path(__file__).resolve().parent.parent
_root_str = str(_project_root)
if _root_str not in sys.path:
    sys.path.insert(0, _root_str)

# Shiboken が six.moves をフックした後に pandas→dateutil→six を通すと環境によって例外になるため、
# 先に pandas を完了 import してから Qt を読み込む。
import pandas as pd  # noqa: F401

# 年別グラフで遅延 import される matplotlib→dateutil.rrule→six.moves が、
# Qt 読込後だと Shiboken の inspect 連携と衝突する（Python 3.12 で AttributeError 等）。
# Qt より前に dateutil.rrule 経路を解決しておく。
import matplotlib.dates  # noqa: F401

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from app.config import settings
from app.ui.message_dialog import show_critical
from app.ui.main_window import MainWindow
from app.ui.theme import apply_app_theme, configure_matplotlib_light


def _report_fatal_startup_error(exc: BaseException, q_app: QApplication | None) -> None:
    """コンソール非表示起動でも内容が分かるよう stderr 出力と、可能ならダイアログを出す。"""
    tb = traceback.format_exc()
    try:
        sys.stderr.write(tb)
        sys.stderr.flush()
    except Exception:
        pass
    text = f"{type(exc).__name__}: {exc}\n\n{tb}"
    text = text[:3500]
    try:
        if q_app is not None:
            show_critical(None, "起動エラー", text)
        elif sys.platform == "win32":
            import ctypes

            ctypes.windll.user32.MessageBoxW(
                0,
                text,
                f"{settings.APP_DISPLAY_NAME} - 起動エラー",
                0x00000010,  # MB_ICONERROR
            )
    except Exception:
        pass


def main() -> int:
    q_app: QApplication | None = None
    try:
        if sys.platform == "win32":
            try:
                import ctypes

                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                    "customer_delivery_analytics.desktop"
                )
            except Exception:
                pass
        q_app = QApplication(sys.argv)
        q_app.setApplicationName(settings.APP_DISPLAY_NAME)
        icon_path = settings.app_icon_png_path()
        if icon_path.exists():
            q_app.setWindowIcon(QIcon(str(icon_path)))
        # Windows 11 等では setApplicationDisplayName がタイトルバーに連結され、
        # WINDOW_TITLE 内の日本語名と二重表示になるため設定しない。
        apply_app_theme(q_app)
        configure_matplotlib_light()

        window = MainWindow()
        window.setWindowTitle(settings.WINDOW_TITLE)
        if icon_path.exists():
            window.setWindowIcon(QIcon(str(icon_path)))
        # トップレベルでも、起動直後のみ参照が弱いとウィンドウが消える事例があるため保持する
        q_app._cda_main_window_ref = window  # type: ignore[attr-defined]
        window.showMaximized()
        return q_app.exec()
    except Exception as e:
        _report_fatal_startup_error(e, q_app)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
