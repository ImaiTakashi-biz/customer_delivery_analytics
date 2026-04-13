# -*- coding: utf-8 -*-
"""検索・年次予測用のワーカースレッド。"""

from __future__ import annotations

from datetime import date
from typing import Optional

from PySide6.QtCore import QThread, Signal

import pandas as pd

from app.db import access_connector
from app.service import delivery_service
from app.service import external_indicator_service
from app.service import forecast_service


class DeliverySearchWorker(QThread):
    """検索を別スレッドで実行する。"""

    search_done = Signal(object, object, str)  # raw_df, agg_df, mode_name
    search_failed = Signal(str)

    def __init__(
        self,
        db_path: str,
        date_from: Optional[date],
        date_to: Optional[date],
        customer: Optional[str],
        product_code_filter: Optional[str],
        mode_name: str,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._db_path = db_path
        self._date_from = date_from
        self._date_to = date_to
        self._customer = customer
        self._product = product_code_filter
        self._mode_name = mode_name

    def run(self) -> None:
        try:
            mode = delivery_service.AggregateMode[self._mode_name]
            with access_connector.open_connection(self._db_path) as conn:
                raw = delivery_service.fetch_deliveries(
                    conn,
                    self._date_from,
                    self._date_to,
                    self._customer,
                    self._product,
                )
                agg = delivery_service.aggregate_for_list(raw, mode)
            self.search_done.emit(raw, agg, self._mode_name)
        except Exception as e:  # noqa: BLE001
            self.search_failed.emit(str(e))


class YearlyForecastFromRawWorker(QThread):
    """検索済み明細から年次予測を作る。"""

    forecast_done = Signal(object)  # payload dict
    forecast_failed = Signal(str)

    def __init__(self, raw_df: pd.DataFrame, future_year_count: int, parent=None) -> None:
        super().__init__(parent)
        self._raw = raw_df
        self._n = future_year_count

    def run(self) -> None:
        try:
            yearly = delivery_service.yearly_totals_from_raw_deliveries(self._raw)
            indicator_service = external_indicator_service.ExternalIndicatorService()
            indicator_statuses = indicator_service.refresh_if_needed()
            status_summary = indicator_service.summarize_statuses(indicator_statuses)

            if yearly.empty:
                indicator_yearly = pd.DataFrame(columns=["年", "iip_avg", "ci_avg"])
            else:
                year_to = int(yearly["年"].max())
                future_last_year = year_to + self._n
                year_from = int(yearly["年"].min())
                indicator_yearly = indicator_service.build_yearly_indicator_frame(
                    year_from, future_last_year
                )

            bundle = forecast_service.run_yearly_forecast_bundle(
                yearly,
                indicator_yearly,
                self._n,
            )

            payload = {
                "comparison_df": bundle.comparison_df,
                "chart_df": bundle.chart_df,
                "summary_lines": bundle.summary_lines,
                "graph_note": bundle.graph_note,
                "status_summary": status_summary,
                "indicator_db_path": indicator_service.db_path,
                "future_indicator_df": bundle.future_indicator_df,
            }
            self.forecast_done.emit(payload)
        except Exception as e:  # noqa: BLE001
            self.forecast_failed.emit(str(e))
