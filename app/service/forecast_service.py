# -*- coding: utf-8 -*-
"""
年次ベースの予測。

現行アルゴリズム（LinearTrendYearlyStrategy）:
    - 入力は「各西暦年の納品数合計・金額合計」の時系列（実績のみ）。
    - 納品数・金額それぞれについて、年を説明変数とした一次多項式を numpy.polyfit（次数1）
      で当てはめ、直線を「最終実績年の翌年」から指定年数ぶん外挿する。
    - 実績が1年分だけのときは傾きを持てないため、その年の値を一定（横ばい）で延長する。
    - 外挿結果が負になる場合は 0 に切り詰める。

未実装（仕様検討用）:
    移動平均・前年同月比・CAGR による統計系、および scikit-learn 等の ML 系は別戦略として
    YearlyForecastStrategy を実装すれば差し替え可能。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Tuple

import numpy as np
import pandas as pd


class YearlyForecastStrategy(ABC):
    """年次系列から将来 N 年分の納品数・金額を予測する戦略の基底。"""

    @abstractmethod
    def predict(
        self,
        years: np.ndarray,
        quantities: np.ndarray,
        amounts: np.ndarray,
        future_year_count: int,
    ) -> Tuple[pd.DataFrame, str]:
        """
        years: 実績の年（昇順・整数）
        quantities, amounts: 各年の合計
        戻り値: (予測結果 DataFrame[年, 納品数, 金額, 種別], 説明テキスト)
        """
        raise NotImplementedError


class LinearTrendYearlyStrategy(YearlyForecastStrategy):
    """
    一次の最小二乗直線（numpy.polyfit 次数1）で外挿。
    説明しやすい初版向け。点数が1のときは直近値を横ばいで延長。
    """

    def predict(
        self,
        years: np.ndarray,
        quantities: np.ndarray,
        amounts: np.ndarray,
        future_year_count: int,
    ) -> Tuple[pd.DataFrame, str]:
        if future_year_count < 1:
            raise ValueError("予測年数は 1 以上にしてください。")
        if len(years) == 0:
            return (
                pd.DataFrame(columns=["年", "納品数", "金額", "種別"]),
                "実績データがないため予測できません。",
            )

        last_year = int(np.max(years))
        future_years = np.arange(last_year + 1, last_year + 1 + future_year_count, dtype=int)

        def _line_or_flat(y_arr: np.ndarray, v_arr: np.ndarray) -> np.ndarray:
            if len(y_arr) >= 2:
                coef = np.polyfit(y_arr.astype(float), v_arr.astype(float), 1)
                return np.polyval(coef, future_years.astype(float))
            # 1点のみ: 定数
            return np.full(shape=future_years.shape, fill_value=float(v_arr[0]))

        q_pred = _line_or_flat(years, quantities)
        a_pred = _line_or_flat(years, amounts)
        # 負値は業務上不自然なので 0 下限
        q_pred = np.maximum(q_pred, 0.0)
        a_pred = np.maximum(a_pred, 0.0)

        out = pd.DataFrame(
            {
                "年": future_years,
                "納品数": q_pred,
                "金額": a_pred,
                "種別": "予測",
            }
        )
        if len(years) >= 2:
            note = (
                "予測方法: 年ごとの合計実績の傾向を直線で表し、"
                "その傾向を将来年へ延長しています（最小二乗法）。"
                " 納品数と金額は別々に計算します。"
            )
        else:
            note = (
                f"予測方法: 実績が 1 年分のみのため、{last_year} 年の値を"
                "そのまま将来年へ延長しています。"
            )
        return out, note


def run_yearly_forecast(
    actual_yearly: pd.DataFrame,
    future_year_count: int,
    strategy: YearlyForecastStrategy | None = None,
) -> Tuple[pd.DataFrame, pd.DataFrame, str]:
    """
    actual_yearly: 列 [年, 納品数, 金額]（種別列があれば無視可）
    戻り値: (実績に種別付与, 予測, 説明)
    """
    strat = strategy or LinearTrendYearlyStrategy()
    if actual_yearly is None or actual_yearly.empty:
        empty = pd.DataFrame(columns=["年", "納品数", "金額", "種別"])
        pred, msg = strat.predict(np.array([]), np.array([]), np.array([]), future_year_count)
        return empty, pred, msg

    work = actual_yearly.copy()
    for col in ("年", "納品数", "金額"):
        if col not in work.columns:
            raise ValueError(f"実績に必須列がありません: {col}")
    work = work.sort_values("年")
    years = work["年"].to_numpy(dtype=int)
    q = work["納品数"].to_numpy(dtype=float)
    a = work["金額"].to_numpy(dtype=float)

    act_out = work[["年", "納品数", "金額"]].copy()
    act_out["種別"] = "実績"

    pred, note = strat.predict(years, q, a, future_year_count)
    return act_out, pred, note
