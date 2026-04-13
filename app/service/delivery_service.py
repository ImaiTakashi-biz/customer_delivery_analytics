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


def _delivery_from_join_sql(inner_join: bool) -> str:
    """納入明細 SELECT … FROM … JOIN まで（WHERE は呼び出し側で付与）。"""
    # Access のテキスト型は末尾スペース付きで格納されがち。JOIN・比較は Trim で揃える。
    # 結合は t_納品.品番 ↔ t_製品マスタ.製品番号（製品名は説明列でコードと一致しない）。
    # 顧客で絞るときは m 必須のため INNER JOIN にし、全件走査・結合の負荷を抑える。
    join_kw = "INNER JOIN" if inner_join else "LEFT JOIN"
    return f"""
SELECT
    d.[納入日] AS 納入日,
    Trim(m.[客先名]) AS 顧客,
    Trim(d.[品番]) AS 品番,
    d.[納品数] AS 納品数,
    d.[単価] AS 単価,
    d.[金額] AS 金額
FROM
    [t_納品] AS d
{join_kw}
    [t_製品マスタ] AS m
    ON Trim(d.[品番]) = Trim(m.[製品番号])
WHERE 1=1
"""


def fetch_customer_names(conn) -> List[str]:
    """顧客（t_製品マスタ.客先名）の一覧を DISTINCT で取得（件数は納品明細より軽量）。"""
    # Nz は Access アプリ向けで ODBC 経由では未定義になることがあるため使わない。
    # NULL は IS NOT NULL、空・空白のみは Len(Trim(...)) で除く（文字列リテラル比較を避ける）。
    # DISTINCT 使用時、Access は ORDER BY に SELECT と同一の式が必要でエイリアス「顧客」は 22018 になる。
    sql = """
    SELECT DISTINCT Trim(m.[客先名]) AS 顧客
    FROM [t_製品マスタ] AS m
    WHERE m.[客先名] IS NOT NULL AND Len(Trim(m.[客先名])) > 0
    ORDER BY Trim(m.[客先名])
    """
    rows = access_connector.fetch_all_dicts(conn, sql)
    return [str(r["顧客"]).strip() for r in rows if r.get("顧客") is not None]


def fetch_customer_code_name_pairs(conn) -> list[tuple[str, str]]:
    """客先マスタから顧客コードと客先名の一覧を取得する。"""
    sql = """
    SELECT
        Trim(k.[コード]) AS 顧客コード,
        Trim(k.[客先]) AS 顧客名
    FROM [t_客先マスタ] AS k
    WHERE k.[コード] IS NOT NULL
      AND k.[客先] IS NOT NULL
      AND Len(Trim(k.[コード])) > 0
      AND Len(Trim(k.[客先])) > 0
    ORDER BY Trim(k.[コード]), Trim(k.[客先])
    """
    rows = access_connector.fetch_all_dicts(conn, sql)
    out: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for row in rows:
        code = str(row.get("顧客コード") or "").strip()
        name = str(row.get("顧客名") or "").strip()
        if not code or not name:
            continue
        key = (code, name)
        if key in seen:
            continue
        seen.add(key)
        out.append(key)
    return out


def fetch_distinct_hinban(conn) -> List[str]:
    """納品テーブルに現れる品番の一覧（候補プルダウン用・重複除去）。"""
    sql = """
    SELECT DISTINCT Trim(d.[品番]) AS 品番
    FROM [t_納品] AS d
    WHERE d.[品番] IS NOT NULL AND Len(Trim(d.[品番])) > 0
    """
    rows = access_connector.fetch_all_dicts(conn, sql)
    return sorted(
        {str(r["品番"]).strip() for r in rows if r.get("品番") is not None}
    )


def fetch_distinct_hinban_for_customer(conn, customer: str) -> List[str]:
    """
    指定顧客に紐づく品番のみ（納品×製品マスタの結合は fetch_deliveries と同じ考え方）。
    顧客名は製品マスタの客先名と完全一致（Trim 済み文字列）で比較する。
    """
    cust = (customer or "").strip()
    if not cust or cust == "（すべて）":
        return fetch_distinct_hinban(conn)
    sql = """
    SELECT DISTINCT Trim(d.[品番]) AS 品番
    FROM [t_納品] AS d
    INNER JOIN [t_製品マスタ] AS m
        ON Trim(d.[品番]) = Trim(m.[製品番号])
    WHERE d.[品番] IS NOT NULL AND Len(Trim(d.[品番])) > 0
      AND Trim(m.[客先名]) = ?
    """
    rows = access_connector.fetch_all_dicts(conn, sql, [cust])
    return sorted(
        {str(r["品番"]).strip() for r in rows if r.get("品番") is not None}
    )


def fetch_deliveries(
    conn,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    customer: Optional[str] = None,
    product_code_filter: Optional[str] = None,
) -> pd.DataFrame:
    """
    納入明細を取得。日付は省略時は DB 上の全納入日を対象。
    期間指定時は開始・終了の両方を渡すこと。品番は部分一致（LIKE）。
    """
    if (date_from is None) ^ (date_to is None):
        raise ValueError("納入日の期間指定は開始日と終了日の両方が必要です。")

    cust = (customer or "").strip()
    has_customer = bool(cust and cust != "（すべて）")
    sql = _delivery_from_join_sql(inner_join=has_customer)
    params: list = []

    if date_from is not None and date_to is not None:
        sql += " AND d.[納入日] BETWEEN ? AND ?"
        params.extend([date_from, date_to])

    if has_customer:
        sql += " AND Trim(m.[客先名]) = ?"
        params.append(cust)

    prod = (product_code_filter or "").strip()
    if prod:
        sql += " AND Trim(d.[品番]) LIKE ?"
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


def yearly_totals_from_raw_deliveries(df: pd.DataFrame) -> pd.DataFrame:
    """
    検索で取得した明細 DataFrame から年次合計を作る（予測・年別グラフの入力用）。
    列: 年, 納品数, 金額。必須列が無い・空なら空の枠を返す。
    """
    if df is None or df.empty:
        return pd.DataFrame(columns=["年", "納品数", "金額"])
    needed = {"納入日", "納品数", "金額"}
    if not needed.issubset(df.columns):
        return pd.DataFrame(columns=["年", "納品数", "金額"])
    work = df.copy()
    work["年"] = work["納入日"].dt.year
    y = work.groupby("年", as_index=False).agg(
        納品数=("納品数", "sum"),
        金額=("金額", "sum"),
    )
    y["年"] = y["年"].astype(int)
    return y.sort_values("年").reset_index(drop=True)


def yearly_totals_for_customer(
    conn,
    customer: str,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    product_code_filter: Optional[str] = None,
) -> pd.DataFrame:
    """指定顧客の年次集計（予測・グラフ用）。列: 年, 納品数, 金額。日付省略時は全期間。"""
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
