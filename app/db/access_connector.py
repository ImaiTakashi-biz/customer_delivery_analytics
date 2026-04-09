# -*- coding: utf-8 -*-
"""Access（accdb）への ODBC 接続。NAS 未到達・ドライバ未導入時は分かりやすい例外を出す。"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Generator, Iterable, List

import pyodbc

from app.config import settings


class AccessConnectionError(Exception):
    """接続に失敗した場合の基底。"""


class OdbcDriverNotFoundError(AccessConnectionError):
    """Microsoft Access 用 ODBC ドライバが見つからない。"""


class AccessFileUnavailableError(AccessConnectionError):
    """DB ファイルに到達できない（NAS 切断・パス誤り・権限など）。"""


def _list_odbc_drivers() -> List[str]:
    try:
        return [d for d in pyodbc.drivers()]
    except Exception:
        return []


def _pick_access_driver() -> str:
    available = {d.lower(): d for d in _list_odbc_drivers()}
    for name in settings.ACCESS_ODBC_DRIVERS_PREFERRED:
        key = name.lower()
        if key in available:
            return available[key]
    raise OdbcDriverNotFoundError(
        "Microsoft Access 用 ODBC ドライバが見つかりません。\n"
        "Microsoft Access Database Engine（ACE）のインストールを確認してください。\n"
        f"検出されたドライバ一覧: {_list_odbc_drivers()}"
    )


def build_connection_string(db_path: str) -> str:
    """接続文字列を組み立てる（UNC パス対応）。"""
    driver = _pick_access_driver()
    # accdb パスにセミコロン等が含まれない前提でそのまま埋め込み
    return f"DRIVER={{{driver}}};DBQ={db_path};"


def check_db_path_reachable(db_path: str) -> None:
    """ファイルの存在確認。UNC はブロック回避のため ODBC 接続側に委ねる。"""
    if not db_path or not db_path.strip():
        raise AccessFileUnavailableError("Access ファイルのパスが空です。")
    # UNC は os.path.exists が長時間止まることがあるためチェックしない
    if db_path.startswith(r"\\"):
        return
    p = os.path.abspath(db_path)
    if not os.path.isfile(p):
        raise AccessFileUnavailableError(
            "Access ファイルが見つかりません。\n" f"パス: {p}"
        )


@contextmanager
def open_connection(db_path: str | None = None) -> Generator[pyodbc.Connection, None, None]:
    """
    Access へ接続するコンテキストマネージャ。
    db_path が None のときは settings の既定パスを使用。
    """
    path = db_path or settings.resolve_access_db_path()
    check_db_path_reachable(path)
    conn_str = build_connection_string(path)
    try:
        conn = pyodbc.connect(conn_str, timeout=30)
    except pyodbc.Error as e:
        msg = str(e).lower()
        hint = (
            "\n\n考えられる原因:\n"
            "- NAS / ネットワーク共有に接続できない\n"
            "- Access ファイルがロックされている、または権限がない\n"
            "- ODBC ドライバと accdb の組み合わせ不整合"
        )
        if "file in use" in msg or "locked" in msg:
            hint = "\n\nAccess ファイルが他プロセスで使用中の可能性があります。"
        raise AccessConnectionError(
            f"Access への接続に失敗しました。\n詳細: {e}{hint}"
        ) from e
    try:
        yield conn
    finally:
        try:
            conn.close()
        except Exception:
            pass


def fetch_all_dicts(
    conn: pyodbc.Connection, sql: str, params: Iterable | None = None
) -> list[dict]:
    """SELECT 結果を辞書のリストで返す。"""
    cur = conn.cursor()
    try:
        if params is None:
            cur.execute(sql)
        else:
            cur.execute(sql, tuple(params))
        columns = [c[0] for c in cur.description] if cur.description else []
        rows = []
        for row in cur.fetchall():
            rows.append(dict(zip(columns, row)))
        return rows
    finally:
        cur.close()
