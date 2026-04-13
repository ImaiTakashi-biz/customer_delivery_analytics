# -*- coding: utf-8 -*-
"""pandas DataFrame を QTableView に表示するモデル。"""

from __future__ import annotations

from typing import Any, Optional

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QBrush, QColor, QFont

import pandas as pd


def _format_with_commas(val: Any) -> str:
    if pd.isna(val):
        return ""
    try:
        n = float(val)
    except (TypeError, ValueError):
        return str(val)
    if n != n:  # NaN
        return ""
    rounded = round(n, 2)
    if abs(rounded - int(rounded)) < 1e-9:
        return f"{int(rounded):,}"
    s = f"{rounded:,.2f}"
    return s.rstrip("0").rstrip(".")


ROW_STYLES = {
    "実績": {"background": QColor("#f8fbff"), "foreground": QColor("#1d4ed8")},
    "予測": {"background": QColor("#fff8f1"), "foreground": QColor("#c2410c")},
    "直線延長予測": {"background": QColor("#FFF5EC"), "foreground": QColor("#C2410C")},
    "重み付き回帰予測": {"background": QColor("#FFF1E6"), "foreground": QColor("#EA580C")},
    "外部要因予測": {"background": QColor("#ECFDF3"), "foreground": QColor("#15803D")},
}

COLUMN_STYLES = {
    "実績": {"background": QColor("#f8fbff"), "foreground": QColor("#1d4ed8")},
    "直線": {"background": QColor("#FFF5EC"), "foreground": QColor("#C2410C")},
    "重み": {"background": QColor("#FFF1E6"), "foreground": QColor("#EA580C")},
    "外部": {"background": QColor("#ECFDF3"), "foreground": QColor("#15803D")},
}


class DataFrameTableModel(QAbstractTableModel):
    """読み取り専用の DataFrame モデル。"""

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

        column_name = str(self._df.columns[index.column()])
        row_kind = self._row_kind(index.row())
        column_group = self._column_group(column_name)

        if role in (Qt.DisplayRole, Qt.EditRole):
            value = self._df.iat[index.row(), index.column()]
            if column_name in (
                "納品数",
                "金額",
                "実績\n納品数",
                "実績\n金額",
                "直線延長\n納品数",
                "直線延長\n金額",
                "重み付き回帰\n納品数",
                "重み付き回帰\n金額",
                "外部要因予測\n納品数",
                "外部要因予測\n金額",
            ):
                return _format_with_commas(value)
            if pd.isna(value):
                return ""
            if isinstance(value, float):
                return f"{value:.2f}".rstrip("0").rstrip(".")
            return str(value)

        if role == Qt.TextAlignmentRole:
            if column_name == "年":
                return Qt.AlignCenter | Qt.AlignVCenter
            if any(key in column_name for key in ("数", "金額", "金")) or column_name in ("納品数", "金額"):
                return Qt.AlignRight | Qt.AlignVCenter
            if column_name == "種別":
                return Qt.AlignCenter | Qt.AlignVCenter

        if role == Qt.BackgroundRole:
            if column_group in COLUMN_STYLES:
                return QBrush(COLUMN_STYLES[column_group]["background"])
            if row_kind in ROW_STYLES:
                return QBrush(ROW_STYLES[row_kind]["background"])

        if role == Qt.ForegroundRole:
            if column_group in COLUMN_STYLES:
                return QBrush(COLUMN_STYLES[column_group]["foreground"])
            if column_name == "種別" and row_kind in ROW_STYLES:
                return QBrush(ROW_STYLES[row_kind]["foreground"])

        if role == Qt.FontRole:
            font = QFont()
            if column_name == "種別":
                font.setBold(True)
                return font
            if column_group in COLUMN_STYLES:
                font.setBold(True)
                return font

        return None

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole):  # noqa: N802
        if orientation == Qt.Horizontal and 0 <= section < len(self._df.columns):
            name = str(self._df.columns[section])
            group = self._column_group(name)
            if role == Qt.DisplayRole:
                return name
            if role == Qt.BackgroundRole and group in COLUMN_STYLES:
                return QBrush(COLUMN_STYLES[group]["background"])
            if role == Qt.ForegroundRole and group in COLUMN_STYLES:
                return QBrush(COLUMN_STYLES[group]["foreground"])
            if role == Qt.FontRole and group in COLUMN_STYLES:
                font = QFont()
                font.setBold(True)
                return font

        if role == Qt.DisplayRole and orientation == Qt.Vertical:
            return str(section + 1)
        return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:  # noqa: N802
        if not index.isValid():
            return Qt.NoItemFlags
        return Qt.ItemIsEnabled | Qt.ItemIsSelectable

    def _row_kind(self, row: int) -> Optional[str]:
        if "種別" not in self._df.columns or row < 0 or row >= len(self._df.index):
            return None
        return str(self._df.iat[row, self._df.columns.get_loc("種別")])

    @staticmethod
    def _column_group(column_name: str) -> Optional[str]:
        if column_name.startswith("実績("):
            return "実績"
        if column_name.startswith("実績\n"):
            return "実績"
        if column_name.startswith("直線(") or column_name.startswith("直線延長\n"):
            return "直線"
        if column_name.startswith("重み(") or column_name.startswith("重み付き回帰\n"):
            return "重み"
        if column_name.startswith("外部(") or column_name.startswith("外部要因予測\n"):
            return "外部"
        return None
