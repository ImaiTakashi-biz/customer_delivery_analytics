#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Web 風 Date Picker の単体デモ。

使い方（プロジェクトルートで）:
    .venv\\Scripts\\python.exe web_date_picker_demo.py

要件に沿って「中央に日付入力・クリックでポップアップ」を最小構成で確認する。
本体アプリは app 配下の ClickableDateEdit / WebDatePickerDialog を利用。
"""

from __future__ import annotations

import sys
from pathlib import Path

# パッケージ app を解決
_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import QApplication, QLabel, QMainWindow, QVBoxLayout, QWidget

from app.ui.theme import apply_app_theme
from app.ui.web_inputs import ClickableDateEdit


def main() -> int:
    app = QApplication(sys.argv)
    apply_app_theme(app)

    win = QMainWindow()
    win.setWindowTitle("Web 風 Date Picker デモ")
    central = QWidget()
    layout = QVBoxLayout(central)
    layout.addStretch(1)

    hint = QLabel("日付欄をクリックするとカレンダーが開きます（確定は OK）")
    hint.setStyleSheet("color: #64748b; font-size: 14px;")
    hint.setAlignment(Qt.AlignmentFlag.AlignCenter)

    date_edit = ClickableDateEdit()
    date_edit.setMinimumDate(QDate(2000, 1, 1))
    date_edit.setMaximumDate(QDate(2100, 12, 31))
    date_edit.setDate(QDate.currentDate())
    date_edit.setMinimumWidth(280)

    layout.addWidget(hint, alignment=Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(date_edit, alignment=Qt.AlignmentFlag.AlignCenter)
    layout.addStretch(1)

    win.setCentralWidget(central)
    win.resize(520, 320)
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
