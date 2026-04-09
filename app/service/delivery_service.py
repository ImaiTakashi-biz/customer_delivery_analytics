# -*- coding: utf-8 -*-
"""納入実績の取得・集計（SQL で期間・顧客・品番を絞り込み、起動時全件ロードはしない）。"""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import List, Optional

import pandas as pd

from app.db import access_connector


class AggregateMode(str, Enum):
    """一覧の集計単位。"""

    BY_CUSTOMER = "顧客別"
    BY_PRODUCT = "品番別"
    BY_CUSTOMER_PRODUCT = "顧客×品番別"


# 一覧表示カラム（仕様）
LIST_COLUMNS = ["顧客", "品番", "年", "月", "納品数", "金額"]


def _base_sql_where_date() -> str:
    """納入日 BETWEEN の骨子（テーブル・結合は固定）。"""
    return """
SELECT
    d.[納入日] AS 納入日,
    m.[客先] AS 顧客,
    d.[品番] AS 品番,
    d.[納品数] AS 納品数,
    d.[単価] AS 単価,
    d.[金額] AS 金額
FROM
    [t_納品] AS d
LEFT JOIN
    [t_製品マスタ] AS m
    ON d.[品番] = m.[製品名]
WHERE
    d.[納入日] BETWEEN ? AND ?
"""


def fetch_customer_names(conn) -> List[str]:
    """顧客（客先）の一覧を DISTINCT で取得（件数は納品明細より軽量）。"""
    sql = """
    SELECT DISTINCT m.[客先] AS 顧客
    FROM [t_製品マスタ] AS m
    WHERE m.[客先] IS NOT NULL AND Trim(m.[客先]) <> ''
    ORDER BY m.[客先]
    """
    rows = access_connector.fetch_all_dicts(conn, sql)
    return [str(r["顧客"]).strip() for r in rows if r.get("顧客") is not None]


def fetch_deliveries(
    conn,
    date_from: date,
    date_to: date,
    customer: Optional[str] = None,
    product_code_filter: Optional[str] = None,
) -> pd.DataFrame:
    """
    指定期間の納入明細を取得。顧客・品番は任意条件。
    品番は部分一致（LIKE、パラメータはユーザー入力をそのまま使わずエスケープ）。
    """
    sql = _base_sql_where_date()
    params: list = [date_from, date_to]

    cust = (customer or "").strip()
    if cust and cust != "（すべて）":
        sql += " AND m.[客先] = ?"
        params.append(cust)

    prod = (product_code_filter or "").strip()
    if prod:
        sql += " AND d.[品番] LIKE ?"
        params.append(f"%{prod}%")

    rows = access_connector.fetch_all_dicts(conn, sql, params)
    if not rows:
        return pd.DataFrame(columns=["納入日", "顧客", "品番", "納品数", "単価", "金額"])

    df = pd.DataFrame(rows)
    # 型整備
    if "納入日" in df.columns:
        df["納入日"] = pd.to_datetime(df["納入日"], errors="coerce")
    for col in ("納品数", "単価", "金額"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    df["顧客"] = df["顧客"].fillna("（未設定）").astype(str)
    df["品番"] = df["品番"].fillna("").astype(str)
    return df


def aggregate_for_list(df: pd.DataFrame, mode: AggregateMode) -> pd.DataFrame:
    """
    明細 DataFrame を一覧用に集計する。
    出力列: 顧客, 品番, 年, 月, 納品数, 金額
    """
    if df.empty:
        return pd.DataFrame(columns=LIST_COLUMNS)

    work = df.copy()
    work["年"] = work["納入日"].dt.year
    work["月"] = work["納入日"].dt.month

    if mode == AggregateMode.BY_CUSTOMER:
        g = work.groupby(["顧客", "年", "月"], as_index=False).agg(
            納品数=("納品数", "sum"),
            金額=("金額", "sum"),
        )
        g.insert(1, "品番", "*")
    elif mode == AggregateMode.BY_PRODUCT:
        g = work.groupby(["品番", "年", "月"], as_index=False).agg(
            納品数=("納品数", "sum"),
            金額=("金額", "sum"),
        )
        # 品番を先頭列付近にそろえるため顧客列を後付け
        g.insert(0, "顧客", "*")
        # 列順: 顧客, 品番, 年, 月...
        cols = ["顧客", "品番", "年", "月", "納品数", "金額"]
        g = g[cols]
    else:  # BY_CUSTOMER_PRODUCT
        g = work.groupby(["顧客", "品番", "年", "月"], as_index=False).agg(
            納品数=("納品数", "sum"),
            金額=("金額", "sum"),
        )

    g = g.sort_values(by=["顧客", "品番", "年", "月"]).reset_index(drop=True)
    # 整数表示用
    g["年"] = g["年"].astype(int)
    g["月"] = g["月"].astype(int)
    return g[LIST_COLUMNS]


def yearly_totals_for_customer(
    conn,
    customer: str,
    date_from: date,
    date_to: date,
    product_code_filter: Optional[str] = None,
) -> pd.DataFrame:
    """指定顧客の年次集計（予測・グラフ用）。列: 年, 納品数, 金額"""
    df = fetch_deliveries(conn, date_from, date_to, customer, product_code_filter)
    if df.empty:
        return pd.DataFrame(columns=["年", "納品数", "金額", "種別"])
    work = df.copy()
    work["年"] = work["納入日"].dt.year
    y = work.groupby("年", as_index=False).agg(
        納品数=("納品数", "sum"),
        金額=("金額", "sum"),
    )
    y["種別"] = "実績"
    y["年"] = y["年"].astype(int)
    return y.sort_values("年").reset_index(drop=True)
