# -*- coding: utf-8 -*-
"""外部指標のローカル保存。"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, Optional

import pandas as pd


@dataclass(frozen=True)
class IndicatorMaster:
    code: str
    name: str
    unit: str
    source_name: str
    source_url: str


class IndicatorStore:
    def __init__(self, db_path: Path) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self._db_path)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def initialize(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS indicator_master (
                    indicator_code TEXT PRIMARY KEY,
                    indicator_name TEXT NOT NULL,
                    unit TEXT NOT NULL,
                    source_name TEXT NOT NULL,
                    source_url TEXT NOT NULL,
                    is_active INTEGER NOT NULL DEFAULT 1
                );

                CREATE TABLE IF NOT EXISTS indicator_monthly (
                    indicator_code TEXT NOT NULL,
                    year_month TEXT NOT NULL,
                    value REAL NOT NULL,
                    published_date TEXT,
                    fetched_at TEXT NOT NULL,
                    PRIMARY KEY (indicator_code, year_month)
                );

                CREATE TABLE IF NOT EXISTS indicator_fetch_status (
                    indicator_code TEXT PRIMARY KEY,
                    last_success_at TEXT,
                    last_attempt_at TEXT,
                    last_error TEXT,
                    source_last_published_date TEXT
                );
                """
            )

    def upsert_masters(self, masters: Iterable[IndicatorMaster]) -> None:
        rows = [
            (
                master.code,
                master.name,
                master.unit,
                master.source_name,
                master.source_url,
            )
            for master in masters
        ]
        if not rows:
            return
        with self._connect() as conn:
            conn.executemany(
                """
                INSERT INTO indicator_master (
                    indicator_code, indicator_name, unit, source_name, source_url
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(indicator_code) DO UPDATE SET
                    indicator_name=excluded.indicator_name,
                    unit=excluded.unit,
                    source_name=excluded.source_name,
                    source_url=excluded.source_url,
                    is_active=1
                """,
                rows,
            )

    def replace_monthly_values(
        self,
        indicator_code: str,
        frame: pd.DataFrame,
    ) -> None:
        if frame is None or frame.empty:
            return
        work = frame.copy()
        rows = []
        for _, row in work.iterrows():
            rows.append(
                (
                    indicator_code,
                    str(row["year_month"]),
                    float(row["value"]),
                    str(row.get("published_date") or ""),
                    str(row["fetched_at"]),
                )
            )
        with self._connect() as conn:
            conn.executemany(
                """
                INSERT INTO indicator_monthly (
                    indicator_code, year_month, value, published_date, fetched_at
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(indicator_code, year_month) DO UPDATE SET
                    value=excluded.value,
                    published_date=excluded.published_date,
                    fetched_at=excluded.fetched_at
                """,
                rows,
            )

    def update_fetch_status(
        self,
        indicator_code: str,
        *,
        last_success_at: Optional[str] = None,
        last_attempt_at: Optional[str] = None,
        last_error: Optional[str] = None,
        source_last_published_date: Optional[str] = None,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO indicator_fetch_status (
                    indicator_code, last_success_at, last_attempt_at, last_error, source_last_published_date
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(indicator_code) DO UPDATE SET
                    last_success_at=COALESCE(excluded.last_success_at, indicator_fetch_status.last_success_at),
                    last_attempt_at=COALESCE(excluded.last_attempt_at, indicator_fetch_status.last_attempt_at),
                    last_error=excluded.last_error,
                    source_last_published_date=COALESCE(excluded.source_last_published_date, indicator_fetch_status.source_last_published_date)
                """,
                (
                    indicator_code,
                    last_success_at,
                    last_attempt_at,
                    last_error,
                    source_last_published_date,
                ),
            )

    def get_monthly_values(
        self,
        indicator_code: str,
        *,
        from_ym: Optional[str] = None,
        to_ym: Optional[str] = None,
    ) -> pd.DataFrame:
        sql = """
            SELECT year_month, value, published_date, fetched_at
            FROM indicator_monthly
            WHERE indicator_code = ?
        """
        params: list[object] = [indicator_code]
        if from_ym:
            sql += " AND year_month >= ?"
            params.append(from_ym)
        if to_ym:
            sql += " AND year_month <= ?"
            params.append(to_ym)
        sql += " ORDER BY year_month"
        with self._connect() as conn:
            return pd.read_sql_query(sql, conn, params=params)

    def get_fetch_status(self, indicator_code: str) -> Optional[dict[str, str]]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT indicator_code, last_success_at, last_attempt_at, last_error, source_last_published_date
                FROM indicator_fetch_status
                WHERE indicator_code = ?
                """,
                (indicator_code,),
            ).fetchone()
        if row is None:
            return None
        return {
            "indicator_code": str(row[0]),
            "last_success_at": str(row[1] or ""),
            "last_attempt_at": str(row[2] or ""),
            "last_error": str(row[3] or ""),
            "source_last_published_date": str(row[4] or ""),
        }

    def has_monthly_values(self, indicator_code: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM indicator_monthly WHERE indicator_code = ? LIMIT 1",
                (indicator_code,),
            ).fetchone()
        return row is not None
