# -*- coding: utf-8 -*-
"""pandas DataFrame を QTableView に載せるモデル。"""

from __future__ import annotations

from typing import Any, List, Optional

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt

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
        if role in (Qt.DisplayRole, Qt.EditRole):
            val = self._df.iat[index.row(), index.column()]
            col = self._df.columns[index.column()]
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
