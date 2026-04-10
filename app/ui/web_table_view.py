# -*- coding: utf-8 -*-
"""一覧 QTableView を Web アプリ風に整え、列幅（数値列の離れ）を調整する。"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QTableView

# theme.py 側で QTableView#webDataTable として装飾する
WEB_TABLE_OBJECT_NAME = "webDataTable"


def configure_web_table_view(view: QTableView) -> None:
    """行番号非表示・区切り線を弱め、行選択の Web 寄りの見た目用ベース設定。"""
    view.setObjectName(WEB_TABLE_OBJECT_NAME)
    view.setAlternatingRowColors(True)
    view.setShowGrid(False)
    view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    view.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    vh = view.verticalHeader()
    vh.setVisible(False)
    # QSS のフォント・セル padding と合わせて行高を固定
    vh.setDefaultSectionSize(26)
    hh = view.horizontalHeader()
    hh.setStretchLastSection(False)
    hh.setHighlightSections(False)
    hh.setDefaultAlignment(
        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
    )


def rebalance_table_columns(view: QTableView) -> None:
    """
    各列を内容幅に合わせる。顧客・品番を Stretch にすると短い文字列でも列が横幅いっぱいに伸び、
    列のあいだに無駄な空白ができるため、Stretch は使わない。
    """
    model = view.model()
    if model is None:
        return
    n = model.columnCount()
    if n <= 0:
        return

    hh = view.horizontalHeader()
    hh.setStretchLastSection(False)
    for i in range(n):
        hh.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
    view.resizeColumnsToContents()
