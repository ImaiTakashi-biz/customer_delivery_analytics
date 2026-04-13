# -*- coding: utf-8 -*-
"""アプリ全体の外観（Fusion ライト・モダン寄り QSS）。"""

from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

# ライト基調・角丸・余白多め（Material / Fluent に近い雰囲気、追加ライブラリなし）
_GLOBAL_STYLESHEET = """
QWidget {
    font-family: "Segoe UI", "Yu Gothic UI", "Meiryo UI", Meiryo, sans-serif;
    font-size: 13px;
}
QMainWindow {
    background-color: #f1f5f9;
}
/* メインダッシュボード（サイドバー廃止・Web アプリ風） */
QWidget#dashboardCentral {
    background-color: transparent;
}
QLabel#pageTitle {
    font-size: 17px;
    font-weight: 700;
    color: #0f172a;
    letter-spacing: -0.02em;
    padding: 0 0 2px 0;
}
QFrame#dashboardSearchCard {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
}
QFrame#webSplitPanelLeft {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 14px;
}
QFrame#webSplitPanelRight {
    background-color: #fcfdfb;
    border: 1px solid #dbe4df;
    border-radius: 14px;
}
QLabel#panelSectionTitle {
    font-size: 15px;
    font-weight: 700;
    color: #1e293b;
    padding: 0;
}
QLabel#panelSectionSubtitle {
    font-size: 12px;
    font-weight: 400;
    color: #64748b;
    line-height: 1.45;
    padding: 0 0 2px 0;
}
QLabel#formSectionCaption {
    font-size: 11px;
    font-weight: 700;
    color: #64748b;
    letter-spacing: 0.02em;
    padding: 0 4px 0 0;
    margin-right: 4px;
}
QLabel#formFieldLabel {
    font-size: 12px;
    font-weight: 600;
    color: #475569;
    min-width: 4.5em;
}
QSplitter#mainSplit::handle {
    background-color: #e2e8f0;
    width: 6px;
    border-radius: 3px;
    margin: 6px 4px;
}
QSplitter#mainSplit::handle:hover {
    background-color: #cbd5e1;
}
QTextEdit#forecastNoteBox,
QLabel#forecastNoteBox {
    background-color: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    padding: 8px 10px;
    font-size: 12px;
    color: #334155;
    selection-background-color: #dbeafe;
    selection-color: #1e3a8a;
}
QGroupBox {
    background-color: #ffffff;
    border: 1px solid #e2e5eb;
    border-radius: 10px;
    margin-top: 14px;
    padding: 16px 14px 14px 14px;
    font-weight: 600;
    color: #1c1c1e;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 14px;
    padding: 0 6px;
    background-color: #ffffff;
}
QLabel#statusLabel {
    color: #3c3c43;
    font-size: 12px;
    padding: 6px 4px;
}
QDialog#forecastExplanationDialog {
    background-color: #f1f5f9;
}
QLabel#forecastExplanationTitle {
    font-size: 18px;
    font-weight: 700;
    color: #0f172a;
    padding: 0 0 2px 0;
}
QScrollArea#forecastExplanationScroll {
    background-color: transparent;
    border: none;
}
QScrollArea#forecastExplanationScroll > QWidget > QWidget {
    background-color: transparent;
}
QWidget#forecastExplanationContent {
    background-color: transparent;
}
QFrame#forecastExplanationCard {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 14px;
}
QLabel#forecastExplanationCardTitle {
    font-size: 14px;
    font-weight: 700;
    color: #0f172a;
    padding: 0 0 2px 0;
}
QLabel#forecastExplanationCardBody {
    font-size: 13px;
    color: #475569;
    line-height: 1.55;
}
QPushButton {
    background-color: #2563eb;
    color: #ffffff;
    border: none;
    border-radius: 8px;
    padding: 9px 18px;
    font-weight: 600;
    min-height: 20px;
}
QPushButton:hover {
    background-color: #1d4ed8;
}
QPushButton:pressed {
    background-color: #1e40af;
}
QPushButton:disabled {
    background-color: #c5cad3;
    color: #f0f0f0;
}
QPushButton#forecastRunButton:disabled,
QPushButton#searchPrimaryButton:disabled {
    background-color: #f1f5f9;
    color: #94a3b8;
    border: 1px solid #e2e8f0;
}
/* モックの白ボタン列（検索以外） */
QPushButton#secondaryButton {
    background-color: #ffffff;
    color: #334155;
    border: 1px solid #d1d5db;
    font-weight: 600;
}
QPushButton#secondaryButton:hover {
    background-color: #f8fafc;
    border-color: #94a3b8;
    color: #0f172a;
}
QPushButton#secondaryButton:pressed {
    background-color: #f1f5f9;
    border-color: #64748b;
}
QPushButton#secondaryButton:disabled {
    background-color: #f1f5f9;
    color: #94a3b8;
    border-color: #e2e8f0;
}
QComboBox, QDateEdit, QLineEdit, QSpinBox {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    padding: 8px 12px;
    min-height: 24px;
    selection-background-color: #2563eb;
    selection-color: #ffffff;
}
QComboBox:hover, QDateEdit:hover, QLineEdit:hover, QSpinBox:hover {
    border-color: #cbd5e1;
}
QComboBox:focus, QDateEdit:focus, QLineEdit:focus, QSpinBox:focus {
    border: 1px solid #2563eb;
    outline: none;
}
QSpinBox#forecastYearSpin {
    padding-right: 26px;
    padding-left: 10px;
    min-width: 88px;
}
QSpinBox#forecastYearSpin::up-button {
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 18px;
    border: none;
    border-left: 1px solid #e2e8f0;
    border-top-right-radius: 10px;
    background-color: #f8fafc;
}
QSpinBox#forecastYearSpin::down-button {
    subcontrol-origin: border;
    subcontrol-position: bottom right;
    width: 18px;
    border: none;
    border-left: 1px solid #e2e8f0;
    border-top: 1px solid #e2e8f0;
    border-bottom-right-radius: 10px;
    background-color: #f8fafc;
}
QSpinBox#forecastYearSpin::up-button:hover, QSpinBox#forecastYearSpin::down-button:hover {
    background-color: #f1f5f9;
}
QSpinBox#forecastYearSpin::up-button:pressed, QSpinBox#forecastYearSpin::down-button:pressed {
    background-color: #e2e8f0;
}
QSpinBox#forecastYearSpin::up-arrow, QSpinBox#forecastYearSpin::down-arrow {
    image: none;
}
/* プルダウン（コンボのポップアップ＝Web の select メニュー風） */
QComboBox QAbstractItemView {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 6px;
    outline: none;
    selection-background-color: #eff6ff;
    selection-color: #1e40af;
}
QComboBox QAbstractItemView::item {
    min-height: 34px;
    padding: 6px 12px;
    border-radius: 8px;
}
QComboBox QAbstractItemView::item:hover {
    background-color: #f1f5f9;
}
QComboBox QAbstractItemView::item:selected {
    background-color: #dbeafe;
    color: #1e3a8a;
}
QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 34px;
    border: none;
    border-top-right-radius: 10px;
    border-bottom-right-radius: 10px;
}
QComboBox::down-arrow {
    width: 0;
    height: 0;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid #64748b;
    margin-right: 10px;
}
/* Web 入力専用：顧客・品番・開始日・終了日を同一のピル型に統一 */
QComboBox#webCombo, QComboBox#webComboReadOnly, QDateEdit#webDateEdit {
    border-radius: 999px;
    padding: 8px 16px;
    min-height: 24px;
}
QComboBox#webCombo, QComboBox#webComboReadOnly {
    padding-right: 12px;
}
/* 右端アイコンは ClickableDateEdit.paintEvent で描画（Windows で data:URL の SVG が QSS から壊れるため） */
QDateEdit#webDateEdit {
    padding-right: 40px;
}
QComboBox#webCombo::drop-down,
QComboBox#webComboReadOnly::drop-down {
    width: 0px;
    height: 0px;
    border: none;
}
QComboBox#webCombo::down-arrow,
QComboBox#webComboReadOnly::down-arrow {
    image: none;
    width: 0;
    height: 0;
    border: none;
}
/* 内蔵 QLineEdit の角がはみ出して四角く見えるのを防ぐ */
QDateEdit#webDateEdit QLineEdit {
    background-color: transparent;
    border: none;
    padding: 0px;
    min-height: 0px;
}
QDateEdit#webDateEdit::drop-down {
    width: 0px;
    height: 0px;
    border: none;
}
QDateEdit#webDateEdit::down-arrow {
    image: none;
    width: 0;
    height: 0;
    border: none;
}
QDateEdit::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 34px;
    border: none;
    border-top-right-radius: 10px;
    border-bottom-right-radius: 10px;
}
QDateEdit::down-arrow {
    image: none;
    width: 0;
    height: 0;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid #64748b;
    margin-right: 10px;
}
QCheckBox {
    spacing: 8px;
    color: #1c1c1e;
}
QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border-radius: 4px;
    border: 1px solid #c5cad3;
    background-color: #ffffff;
}
QCheckBox::indicator:checked {
    background-color: #2563eb;
    border-color: #2563eb;
}
QTableView {
    background-color: #ffffff;
    alternate-background-color: #f6f7f9;
    border: 1px solid #e2e5eb;
    border-radius: 8px;
    gridline-color: #eceef2;
    selection-background-color: #dbeafe;
    selection-color: #1e3a8a;
}
/* 実績・予測一覧（メイン／ダイアログ共通）Web テーブル風 */
QTableView#webDataTable {
    outline: none;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    background-color: #ffffff;
    alternate-background-color: #f8fafc;
    gridline-color: transparent;
    selection-background-color: #eff6ff;
    selection-color: #1e40af;
    font-size: 14px;
}
QTableView#webDataTable::item {
    padding: 2px 8px;
    border: none;
    border-bottom: 1px solid #f1f5f9;
}
QTableView#webDataTable::item:hover {
    background-color: #f8fafc;
}
QTableView#webDataTable::item:selected {
    background-color: #eff6ff;
    color: #1e40af;
}
QTableView#webDataTable::item:selected:hover {
    background-color: #eff6ff;
    color: #1e40af;
}
QTableView#webDataTable QHeaderView {
    background-color: transparent;
}
QTableView#webDataTable QHeaderView::section {
    background-color: #f1f5f9;
    color: #475569;
    padding: 4px 8px;
    border: none;
    border-bottom: 1px solid #e2e8f0;
    border-right: 1px solid #e8eef5;
    font-weight: 600;
    font-size: 14px;
}
/* 一覧テーブル専用：細い丸いスクロールバー（Web アプリ風、矢印なし） */
QTableView#webDataTable QScrollBar:vertical {
    background: transparent;
    width: 8px;
    margin: 4px 2px 4px 0;
    border: none;
}
QTableView#webDataTable QScrollBar::handle:vertical {
    background-color: #cbd5e1;
    border-radius: 4px;
    min-height: 28px;
    margin: 2px 1px;
}
QTableView#webDataTable QScrollBar::handle:vertical:hover {
    background-color: #94a3b8;
}
QTableView#webDataTable QScrollBar::add-line:vertical,
QTableView#webDataTable QScrollBar::sub-line:vertical {
    height: 0px;
    width: 0px;
    border: none;
}
QTableView#webDataTable QScrollBar::add-page:vertical,
QTableView#webDataTable QScrollBar::sub-page:vertical {
    background: none;
}
QTableView#webDataTable QScrollBar:horizontal {
    background: transparent;
    height: 8px;
    margin: 0 2px 2px 2px;
    border: none;
}
QTableView#webDataTable QScrollBar::handle:horizontal {
    background-color: #cbd5e1;
    border-radius: 4px;
    min-width: 28px;
    margin: 1px 2px;
}
QTableView#webDataTable QScrollBar::handle:horizontal:hover {
    background-color: #94a3b8;
}
QTableView#webDataTable QScrollBar::add-line:horizontal,
QTableView#webDataTable QScrollBar::sub-line:horizontal {
    height: 0px;
    width: 0px;
    border: none;
}
QTableView#webDataTable QScrollBar::add-page:horizontal,
QTableView#webDataTable QScrollBar::sub-page:horizontal {
    background: none;
}
QHeaderView::section {
    background-color: #f3f4f6;
    color: #374151;
    padding: 8px 10px;
    border: none;
    border-bottom: 2px solid #e5e7eb;
    border-right: 1px solid #eceef2;
    font-weight: 600;
    font-size: 12px;
}
QScrollBar:vertical {
    background: #f0f2f5;
    width: 12px;
    border-radius: 6px;
    margin: 4px 2px 4px 0;
}
QScrollBar::handle:vertical {
    background: #c5cad3;
    border-radius: 6px;
    min-height: 32px;
}
QScrollBar::handle:vertical:hover {
    background: #9ca3af;
}
QScrollBar:horizontal {
    background: #f0f2f5;
    height: 12px;
    border-radius: 6px;
    margin: 0 4px 2px 4px;
}
QScrollBar::handle:horizontal {
    background: #c5cad3;
    border-radius: 6px;
    min-width: 32px;
}
QTextEdit {
    background-color: #fafafa;
    border: 1px solid #e2e5eb;
    border-radius: 8px;
    padding: 8px;
}
QDialogButtonBox QPushButton {
    min-width: 88px;
    border-radius: 10px;
    padding: 8px 20px;
}
/* --- Web アプリ風：確認・エラーダイアログ --- */
QDialog#messageDialog {
    background-color: transparent;
}
QFrame#messageCard {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 16px;
}
QLabel#messageBadge {
    font-size: 24px;
    font-weight: 700;
    color: #ffffff;
    border-radius: 21px;
    background-color: #2563eb;
}
QLabel#messageBadge[level="warning"] {
    background-color: #d97706;
}
QLabel#messageBadge[level="error"] {
    background-color: #dc2626;
}
QLabel#messageTitle {
    color: #0f172a;
    font-size: 18px;
    font-weight: 700;
}
QLabel#messageBody {
    color: #334155;
    font-size: 14px;
    line-height: 1.5;
    min-width: 180px;
    max-width: 360px;
}
QPushButton#messagePrimaryButton {
    background-color: #2563eb;
    color: #ffffff;
    border: none;
    border-radius: 10px;
    padding: 10px 24px;
    font-weight: 600;
    min-width: 96px;
    min-height: 20px;
}
QPushButton#messagePrimaryButton:hover {
    background-color: #1d4ed8;
}
QPushButton#messagePrimaryButton:pressed {
    background-color: #1e40af;
}
QDialog {
    background-color: #ffffff;
}
QDialog QLabel {
    color: #334155;
}
/* Web 風日付ピッカーダイアログ（参照 UI に近いカード・見出し・リンクボタン） */
QDialog#webDatePickerDialog {
    background-color: #ffffff;
    border-radius: 16px;
}
QLabel#webDatePickerTitle {
    font-size: 18px;
    font-weight: 700;
    color: #0f172a;
    padding: 2px 4px 10px 4px;
}
QPushButton#webDatePickerLinkButton {
    background-color: transparent;
    border: none;
    color: #2563eb;
    font-size: 13px;
    font-weight: 600;
    padding: 6px 6px;
}
QPushButton#webDatePickerLinkButton:hover {
    color: #1d4ed8;
}
QPushButton#webDatePickerLinkButton:pressed {
    color: #1e40af;
}
/* 日付ダイアログ：参照 UI の 1 行ヘッダー（西暦・和暦・月▼・↑↓） */
QFrame#webDatePickerHeaderBar {
    background-color: transparent;
    border: none;
}
QLabel#webDatePickerEraLabel {
    font-size: 15px;
    font-weight: 700;
    color: #0f172a;
    padding: 0 1px;
}
QSpinBox#webDatePickerHeaderYearSpin {
    font-size: 15px;
    font-weight: 700;
    color: #0f172a;
    padding: 3px 5px;
    min-height: 26px;
    border-radius: 8px;
    border: 1px solid #e2e8f0;
    background-color: #ffffff;
}
QSpinBox#webDatePickerHeaderYearSpin:focus {
    border: 1px solid #2563eb;
}
QToolButton#webDatePickerMonthButton {
    font-size: 15px;
    font-weight: 700;
    color: #0f172a;
    padding: 3px 6px;
    border: none;
    background-color: transparent;
}
QToolButton#webDatePickerMonthButton:hover {
    background-color: #f1f5f9;
    border-radius: 8px;
}
QToolButton#webDatePickerMonthStepButton {
    font-size: 12px;
    font-weight: 700;
    color: #334155;
    min-width: 22px;
    min-height: 18px;
    padding: 0px;
    border: none;
    background-color: transparent;
}
QToolButton#webDatePickerMonthStepButton:hover {
    background-color: #e8eef5;
    border-radius: 6px;
}
/* カレンダーを包む白カード（影は QGraphicsDropShadowEffect を使わず二重枠で軽く浮かせる） */
QFrame#webDatePickerCalCard {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    margin: 0px 2px 4px 2px;
}
QCalendarWidget#webDatePickerCalendar {
    background-color: transparent;
    border: none;
}
QCalendarWidget#webDatePickerCalendar QAbstractItemView:enabled {
    font-size: 13px;
    color: #334155;
    selection-background-color: #2563eb;
    selection-color: #ffffff;
    outline: none;
    min-height: 196px;
    alternate-background-color: #f8fafc;
}
QCalendarWidget#webDatePickerCalendar QAbstractItemView:enabled:!active {
    selection-background-color: #2563eb;
    selection-color: #ffffff;
}
QCalendarWidget#webDatePickerCalendar QAbstractItemView::item:hover {
    background-color: #eff6ff;
    color: #1e40af;
}
QCalendarWidget#webDatePickerCalendar QAbstractItemView::item:selected {
    background-color: #2563eb;
    color: #ffffff;
    border: 2px solid #0f172a;
    border-radius: 6px;
}
QCalendarWidget#webDatePickerCalendar QAbstractItemView::item:selected:hover {
    background-color: #1d4ed8;
    color: #ffffff;
}
/* --- メニュー・ツールチップ（ポップオーバー風） --- */
QMenu {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 4px;
}
QMenu::item {
    padding: 8px 24px 8px 14px;
    border-radius: 8px;
    color: #334155;
}
QMenu::item:selected {
    background-color: #eff6ff;
    color: #1e40af;
}
QToolTip {
    background-color: #1e293b;
    color: #f8fafc;
    border: none;
    border-radius: 8px;
    padding: 8px 12px;
    font-size: 12px;
}
/* ファイルダイアログ（非ネイティブ時に角丸・余白を揃える） */
QFileDialog {
    background-color: #ffffff;
}
QFileDialog QTreeView, QFileDialog QListView, QFileDialog QTableView {
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    background-color: #ffffff;
    outline: none;
}
QFileDialog QLineEdit, QFileDialog QComboBox {
    border-radius: 10px;
}
/* フォーム左ラベル（Web のフォーム見出し風） */
QFormLayout QLabel {
    color: #64748b;
    font-weight: 500;
    font-size: 12px;
}
/* 処理中オーバーレイ */
QFrame#busyOverlay {
    background-color: rgba(15, 23, 42, 0.4);
    border: none;
}
QFrame#busyCard {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 16px;
}
QLabel#busyLabel {
    color: #334155;
    font-size: 14px;
    font-weight: 600;
    padding: 0 8px;
    max-width: 400px;
}
QProgressBar#busyProgress {
    background-color: #e2e8f0;
    border: none;
    border-radius: 999px;
    min-height: 8px;
    max-height: 8px;
}
QProgressBar#busyProgress::chunk {
    background-color: #2563eb;
    border-radius: 999px;
}
"""


def apply_app_theme(app: QApplication) -> None:
    """Fusion スタイル＋ライトパレット＋全体 QSS を適用する。"""
    app.setStyle("Fusion")
    # Windows では「名前を付けて保存」を OS 標準（エクスプローラー）にする。
    # True 固定だと Qt 製ファイルダイアログになり、業務利用で紛らわしい。
    # 他 OS では従来どおり QSS の効く Qt 製ダイアログを維持する。
    if sys.platform == "win32":
        app.setAttribute(Qt.ApplicationAttribute.AA_DontUseNativeDialogs, False)
    else:
        app.setAttribute(Qt.ApplicationAttribute.AA_DontUseNativeDialogs, True)

    pal = QPalette()
    c_window = QColor("#eef1f6")
    c_base = QColor("#ffffff")
    c_alt = QColor("#f6f7f9")
    c_text = QColor("#1c1c1e")
    c_disabled = QColor("#8e8e93")
    c_highlight = QColor("#2563eb")
    c_highlight_text = QColor("#ffffff")
    c_button = QColor("#ffffff")
    c_mid = QColor("#e2e5eb")

    pal.setColor(QPalette.Window, c_window)
    pal.setColor(QPalette.WindowText, c_text)
    pal.setColor(QPalette.Base, c_base)
    pal.setColor(QPalette.AlternateBase, c_alt)
    pal.setColor(QPalette.Text, c_text)
    pal.setColor(QPalette.Button, c_button)
    pal.setColor(QPalette.ButtonText, c_text)
    pal.setColor(QPalette.Highlight, c_highlight)
    pal.setColor(QPalette.HighlightedText, c_highlight_text)
    pal.setColor(QPalette.PlaceholderText, c_disabled)
    pal.setColor(QPalette.Mid, c_mid)
    pal.setColor(QPalette.Disabled, QPalette.WindowText, c_disabled)
    pal.setColor(QPalette.Disabled, QPalette.Text, c_disabled)
    pal.setColor(QPalette.Disabled, QPalette.ButtonText, c_disabled)
    app.setPalette(pal)

    app.setStyleSheet(_GLOBAL_STYLESHEET)

    f = app.font()
    f.setPointSize(10)
    app.setFont(f)


def configure_matplotlib_light() -> None:
    """グラフをライト背景に合わせる（ダイアログ生成前に1回でよい）。"""
    try:
        import sys

        import matplotlib.pyplot as plt

        plt.style.use("default")
        extra: dict = {
            "figure.facecolor": "#ffffff",
            "axes.facecolor": "#fafafa",
            "axes.edgecolor": "#d1d5db",
            "axes.labelcolor": "#374151",
            "text.color": "#1f2937",
            "xtick.color": "#4b5563",
            "ytick.color": "#4b5563",
            "grid.color": "#e5e7eb",
            "grid.alpha": 0.8,
            # マイナス記号が豆腐になるのを防ぐ
            "axes.unicode_minus": False,
        }
        # Windows では日本語ラベル用に UI フォントを先に試す（DejaVu だと警告・欠けが出る）
        if sys.platform == "win32":
            jp_first = [
                "Yu Gothic UI",
                "Meiryo UI",
                "Meiryo",
                "MS Gothic",
                "MS PGothic",
                "Segoe UI",
            ]
            existing = list(plt.rcParams.get("font.sans-serif", []))
            extra["font.family"] = "sans-serif"
            extra["font.sans-serif"] = jp_first + [
                f for f in existing if f not in jp_first
            ]
        plt.rcParams.update(extra)
    except Exception:
        pass
