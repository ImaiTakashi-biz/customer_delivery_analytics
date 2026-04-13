# -*- coding: utf-8 -*-
"""日付まわりのヘルパ（UI・SQL 境界用）"""

from __future__ import annotations

from datetime import date, datetime
from typing import Tuple

from PySide6.QtCore import QDate

from app.config import settings


def default_date_range() -> Tuple[date, date]:
    """開始日は固定、終了日は前年末を返す。"""
    start = date(settings.DEFAULT_YEAR_START, 1, 1)
    today = date.today()
    end = date(today.year - 1, 12, 31)
    return start, end


def suggested_period_when_filter_enabled() -> Tuple[date, date]:
    """「期間で絞り込む」をオンにしたときの候補（当年 1/1～12/31）。"""
    today = date.today()
    return date(today.year, 1, 1), date(today.year, 12, 31)


def qdate_to_date(qd: QDate) -> date:
    """QDate を datetime.date に変換する。"""
    return date(qd.year(), qd.month(), qd.day())


def date_to_qdate(d: date) -> QDate:
    """datetime.date を QDate に変換する。"""
    return QDate(d.year, d.month, d.day)


def format_header_era_middle(y: int, m: int) -> str:
    """
    見出し用の「年（元号）」部分のみ。西暦の数字は含めない。
    例: 令和 → 「年（令和7年）」、和暦外 → 「年」
    """
    from datetime import date

    d = date(y, m, min(15, _days_in_month(y, m)))
    if d >= date(2019, 5, 1):
        sy = y if m >= 5 else y - 1
        rn = sy - 2018
        return f"年（令和{rn}年）"
    if date(1989, 1, 8) <= d <= date(2019, 4, 30):
        hn = 31 if y == 2019 else y - 1988
        return f"年（平成{hn}年）"
    if date(1926, 12, 25) <= d < date(1989, 1, 8):
        if y == 1989 and m == 1:
            return "年（昭和64年）"
        sn = y - 1925
        if y == 1926 and m == 12:
            sn = 1
        return f"年（昭和{sn}年）"
    return "年"


def format_wareki_month_header(y: int, m: int) -> str:
    """
    カレンダー見出し用（月の中日基準で和暦年を付与）。
    例: 2026年4月 → 「2026年（令和7年）4月」（5月以降の月は同年の令和年が進む）。
    """
    return f"{y}{format_header_era_middle(y, m)}{m}月"


def _days_in_month(y: int, m: int) -> int:
    from calendar import monthrange

    return monthrange(y, m)[1]


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
