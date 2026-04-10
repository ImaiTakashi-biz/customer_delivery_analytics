# -*- coding: utf-8 -*-
"""Web アプリ風の日付選択ダイアログ（参照 UI：和暦見出し・ghost 日付・削除／今日）。"""

from __future__ import annotations

from functools import partial

from PySide6.QtCore import QDate, Qt, QSignalBlocker
from PySide6.QtGui import QColor, QAction, QTextCharFormat
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QCalendarWidget,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
)

from app.utils import date_utils


def _day_of_week_int(dow) -> int:
    """QDate.dayOfWeek() は int、firstDayOfWeek() は DayOfWeek 列挙で、直接比較すると一致しない（無限ループの原因になる）。"""
    if isinstance(dow, int):
        return dow
    v = getattr(dow, "value", None)
    if v is not None:
        return int(v)
    return int(dow)


class WebCalendarWidget(QCalendarWidget):
    """
    他月に属する日付を薄色にする（QTextCharFormat）。
    選択日の青背景は QSS に任せる（背景を QTextCharFormat で塗ると Fusion でグリッドが真っ白になることがある）。
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("webDatePickerCalendar")
        self._fmt_dates: list[QDate] = []
        # ghost 表示は表示中の年月のみ依存（選択変更では再計算不要）
        self.currentPageChanged.connect(self._refresh_cell_formats)

    def _refresh_cell_formats(self) -> None:
        cal = self
        # 付与した ghost 用フォーマットだけ解除（今月の日に clear を当て続けると Fusion でクリックが効かなくなる事例あり）
        for qd in self._fmt_dates:
            cal.setDateTextFormat(qd, QTextCharFormat())
        self._fmt_dates.clear()

        y, m = cal.yearShown(), cal.monthShown()
        first = QDate(y, m, 1)
        d = first
        fd_i = _day_of_week_int(cal.firstDayOfWeek())
        # グリッド先頭＝週の開始曜日まで最大 6 日戻す（比較は int に揃える）
        for _ in range(7):
            if _day_of_week_int(d.dayOfWeek()) == fd_i:
                break
            d = d.addDays(-1)

        gray = QColor("#94a3b8")

        for i in range(42):
            qd = d.addDays(i)
            if qd.month() != m or qd.year() != y:
                fmt = QTextCharFormat()
                fmt.setForeground(gray)
                cal.setDateTextFormat(qd, fmt)
                self._fmt_dates.append(qd)


class WebDatePickerDialog(QDialog):
    """参照デザインに近い日付ピッカー（カスタムヘッダー + WebCalendarWidget）。"""

    def __init__(
        self,
        parent,
        min_d: QDate,
        max_d: QDate,
        initial: QDate,
        *,
        window_title: str = "日付を選択",
    ) -> None:
        super().__init__(parent)
        self.setObjectName("webDatePickerDialog")
        self.setWindowTitle(window_title)
        self.setMinimumSize(440, 520)
        self._min_d = min_d
        self._max_d = max_d

        self._cal = WebCalendarWidget(self)
        self._cal.setMinimumDate(min_d)
        self._cal.setMaximumDate(max_d)
        self._cal.setNavigationBarVisible(False)
        self._cal.setGridVisible(True)
        self._cal.setVerticalHeaderFormat(
            QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader
        )
        self._cal.setMinimumSize(400, 360)

        fmt_sun = QTextCharFormat()
        fmt_sun.setForeground(QColor("#dc2626"))
        self._cal.setWeekdayTextFormat(Qt.DayOfWeek.Sunday, fmt_sun)
        fmt_sat = QTextCharFormat()
        fmt_sat.setForeground(QColor("#2563eb"))
        self._cal.setWeekdayTextFormat(Qt.DayOfWeek.Saturday, fmt_sat)

        init = initial
        if init < min_d:
            init = min_d
        if init > max_d:
            init = max_d
        self._cal.setSelectedDate(init)
        self._cal.setCurrentPage(init.year(), init.month())
        self._cal.currentPageChanged.connect(self._on_page_changed)

        # --- 参照 UI：1 行ヘッダー［西暦スピン］［年（和暦）］［月▼］ … ［↑］［↓］ ---
        self._header = QFrame(self)
        self._header.setObjectName("webDatePickerHeaderBar")
        head_lay = QHBoxLayout(self._header)
        head_lay.setContentsMargins(2, 4, 2, 10)
        head_lay.setSpacing(6)

        self._year_spin = QSpinBox(self._header)
        self._year_spin.setObjectName("webDatePickerHeaderYearSpin")
        self._year_spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self._year_spin.setRange(min_d.year(), max_d.year())
        self._year_spin.setFixedWidth(56)
        self._year_spin.valueChanged.connect(self._on_header_year_month_changed)

        self._era_lbl = QLabel(self._header)
        self._era_lbl.setObjectName("webDatePickerEraLabel")

        self._month_btn = QToolButton(self._header)
        self._month_btn.setObjectName("webDatePickerMonthButton")
        self._month_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self._month_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._month_btn.setAutoRaise(True)
        self._month_menu = QMenu(self._month_btn)
        self._month_btn.setMenu(self._month_menu)
        for mi in range(1, 13):
            act = QAction(f"{mi}月", self._month_menu)
            act.triggered.connect(partial(self._on_pick_month, mi))
            self._month_menu.addAction(act)

        head_lay.addWidget(self._year_spin, stretch=0)
        head_lay.addWidget(self._era_lbl, stretch=0)
        head_lay.addWidget(self._month_btn, stretch=0)
        head_lay.addStretch(1)

        step_col = QVBoxLayout()
        step_col.setSpacing(0)
        self._btn_month_up = QToolButton(self._header)
        self._btn_month_up.setObjectName("webDatePickerMonthStepButton")
        self._btn_month_up.setText("↑")
        self._btn_month_up.setAutoRaise(True)
        self._btn_month_up.setToolTip("前の月")
        self._btn_month_up.clicked.connect(self._go_prev_month)
        self._btn_month_down = QToolButton(self._header)
        self._btn_month_down.setObjectName("webDatePickerMonthStepButton")
        self._btn_month_down.setText("↓")
        self._btn_month_down.setAutoRaise(True)
        self._btn_month_down.setToolTip("次の月")
        self._btn_month_down.clicked.connect(self._go_next_month)
        step_col.addWidget(self._btn_month_up)
        step_col.addWidget(self._btn_month_down)
        head_lay.addLayout(step_col)

        # 白カード（シャドウは QGraphicsDropShadowEffect だと環境によって子が描画されないことがあるため QSS の枠のみ）
        self._cal_card = QFrame(self)
        self._cal_card.setObjectName("webDatePickerCalCard")
        card_lay = QVBoxLayout(self._cal_card)
        card_lay.setContentsMargins(0, 0, 0, 0)
        card_lay.addWidget(self._cal)

        btn_clear = QPushButton("削除")
        btn_clear.setObjectName("webDatePickerLinkButton")
        btn_clear.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_clear.clicked.connect(self._on_clear)
        btn_today = QPushButton("今日")
        btn_today.setObjectName("webDatePickerLinkButton")
        btn_today.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_today.clicked.connect(self._on_today)

        row_links = QHBoxLayout()
        row_links.setContentsMargins(4, 4, 4, 0)
        row_links.addWidget(btn_clear)
        row_links.addStretch()
        row_links.addWidget(btn_today)

        bbox = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        bbox.accepted.connect(self.accept)
        bbox.rejected.connect(self.reject)
        for btn in bbox.buttons():
            role = bbox.buttonRole(btn)
            if role == QDialogButtonBox.ButtonRole.AcceptRole:
                btn.setDefault(True)
            elif role == QDialogButtonBox.ButtonRole.RejectRole:
                btn.setObjectName("secondaryButton")

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 18)
        root.setSpacing(8)
        root.addWidget(self._header)
        root.addWidget(self._cal_card, stretch=1)
        root.addLayout(row_links)
        root.addWidget(bbox)

        self._on_page_changed(self._cal.yearShown(), self._cal.monthShown())

    def _min_page(self) -> QDate:
        return QDate(self._min_d.year(), self._min_d.month(), 1)

    def _max_page(self) -> QDate:
        return QDate(self._max_d.year(), self._max_d.month(), 1)

    def _clamp_page(self, page: QDate) -> QDate:
        lo, hi = self._min_page(), self._max_page()
        if page < lo:
            return lo
        if page > hi:
            return hi
        return page

    def _sync_header_from_calendar(self) -> None:
        y, m = self._cal.yearShown(), self._cal.monthShown()
        with QSignalBlocker(self._year_spin):
            self._year_spin.setValue(y)
        self._era_lbl.setText(date_utils.format_header_era_middle(y, m))
        self._month_btn.setText(f"{m}月 ▼")
        cur = QDate(y, m, 1)
        lo, hi = self._min_page(), self._max_page()
        self._btn_month_up.setEnabled(cur > lo)
        self._btn_month_down.setEnabled(cur < hi)

    def _on_page_changed(self, year: int, month: int) -> None:
        self._sync_header_from_calendar()

    def _apply_page(self, page: QDate) -> None:
        p = self._clamp_page(page)
        self._cal.setCurrentPage(p.year(), p.month())

    def _on_header_year_month_changed(self) -> None:
        m = self._cal.monthShown()
        y = self._year_spin.value()
        self._apply_page(QDate(y, m, 1))

    def _on_pick_month(self, month: int) -> None:
        y = self._year_spin.value()
        self._apply_page(QDate(y, month, 1))

    def _go_prev_month(self) -> None:
        cur = QDate(self._cal.yearShown(), self._cal.monthShown(), 1)
        self._apply_page(cur.addMonths(-1))

    def _go_next_month(self) -> None:
        cur = QDate(self._cal.yearShown(), self._cal.monthShown(), 1)
        self._apply_page(cur.addMonths(1))

    def _on_clear(self) -> None:
        self._cal.setSelectedDate(self._min_d)
        self._cal.setCurrentPage(self._min_d.year(), self._min_d.month())

    def _on_today(self) -> None:
        t = QDate.currentDate()
        if t < self._min_d:
            t = self._min_d
        elif t > self._max_d:
            t = self._max_d
        self._cal.setSelectedDate(t)
        self._cal.setCurrentPage(t.year(), t.month())

    def selected_date(self) -> QDate:
        return self._cal.selectedDate()
