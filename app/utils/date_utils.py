# -*- coding: utf-8 -*-
"""日付まわりのヘルパ（UI・SQL 境界用）"""

from __future__ import annotations

from datetime import date, datetime
from typing import Tuple

from PySide6.QtCore import QDate

from app.config import settings


def default_date_range() -> Tuple[date, date]:
    """既定の検索期間（年初〜年末）を返す。"""
    start = date(settings.DEFAULT_YEAR_START, 1, 1)
    end = date(settings.DEFAULT_YEAR_END, 12, 31)
    return start, end


def qdate_to_date(qd: QDate) -> date:
    """QDate を datetime.date に変換する。"""
    return date(qd.year(), qd.month(), qd.day())


def date_to_qdate(d: date) -> QDate:
    """datetime.date を QDate に変換する。"""
    return QDate(d.year, d.month, d.day)


def parse_db_date(value) -> date | None:
    """DB から取得した値を date に正規化する。"""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    # pyodbc 等で文字列の場合
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value[:10]).date()
        except ValueError:
            return None
    return None
