# -*- coding: utf-8 -*-
"""pandas DataFrame を QTableView に載せるモデル。"""

from __future__ import annotations

from typing import Any, List, Optional

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QBrush, QColor, QFont

import pandas as pd


def _format_with_commas(val: Any) -> str:
    """納品数・金額の表示用（例: 1000 → 1,000）。"""
    if pd.isna(val):
        return ""
    try:
        n = float(val)
    except (TypeError, ValueError):
        return str(val)
    if n != n:  # NaN
        return ""
    rounded = round(n, 2)
    # 実質整数なら小数なし
    if abs(rounded - int(rounded)) < 1e-9:
        return f"{int(rounded):,}"
    s = f"{rounded:,.2f}"
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s


class DataFrameTableModel(QAbstractTableModel):
    """読み取り専用の簡易テーブルモデル。"""

    def __init__(self, df: Optional[pd.DataFrame] = None, parent=None):
        super().__init__(parent)
        self._df = df if df is not None else pd.DataFrame()

    def set_dataframe(self, df: pd.DataFrame) -> None:
        self.beginResetModel()
        self._df = df if df is not None else pd.DataFrame()
        self.endResetModel()

    def dataframe(self) -> pd.DataFrame:
        return self._df

    def rowCount(self, parent=QModelIndex()) -> int:  # noqa: N802
        if parent.isValid():
            return 0
        return len(self._df.index)

    def columnCount(self, parent=QModelIndex()) -> int:  # noqa: N802
        if parent.isValid():
            return 0
        return len(self._df.columns)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        if not index.isValid():
            return None
        row_kind = None
        if "種別" in self._df.columns:
            kind_col = self._df.columns.get_loc("種別")
            row_kind = self._df.iat[index.row(), kind_col]
        if role in (Qt.DisplayRole, Qt.EditRole):
            val = self._df.iat[index.row(), index.column()]
            col = self._df.columns[index.column()]
            if col == "種別":
                if val == "実績":
                    return "実績"
                if val == "予測":
                    return "予測"
            if col in ("納品数", "金額"):
                return _format_with_commas(val)
            if pd.isna(val):
                return ""
            if isinstance(val, float):
                return f"{val:.2f}".rstrip("0").rstrip(".")
            return str(val)
        if role == Qt.TextAlignmentRole:
            col = self._df.columns[index.column()]
            if col in ("納品数", "金額", "年", "月"):
                return Qt.AlignRight | Qt.AlignVCenter
            if col == "種別":
                return Qt.AlignCenter | Qt.AlignVCenter
        if role == Qt.BackgroundRole and row_kind in ("実績", "予測"):
            if row_kind == "実績":
                return QBrush(QColor("#f8fbff"))
            return QBrush(QColor("#fff8f1"))
        if role == Qt.ForegroundRole:
            col = self._df.columns[index.column()]
            if col == "種別" and row_kind == "実績":
                return QBrush(QColor("#1d4ed8"))
            if col == "種別" and row_kind == "予測":
                return QBrush(QColor("#c2410c"))
        if role == Qt.FontRole:
            col = self._df.columns[index.column()]
            if col == "種別":
                font = QFont()
                font.setBold(True)
                return font
        return None

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole):  # noqa: N802
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal:
            if 0 <= section < len(self._df.columns):
                return str(self._df.columns[section])
        else:
            return str(section + 1)
        return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:  # noqa: N802
        if not index.isValid():
            return Qt.NoItemFlags
        return Qt.ItemIsEnabled | Qt.ItemIsSelectable
