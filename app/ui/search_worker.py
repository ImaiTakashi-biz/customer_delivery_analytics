# -*- coding: utf-8 -*-
"""検索処理をメインスレッドから切り離し、UI のフリーズを防ぐ。"""

from __future__ import annotations

from datetime import date
from typing import Optional

from PySide6.QtCore import QThread, Signal

import pandas as pd

from app.db import access_connector
from app.service import delivery_service
from app.service import forecast_service


class DeliverySearchWorker(QThread):
    """別スレッドで ODBC 接続・全件取得・集計を行う。"""

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
    """明細 DataFrame から年次集計→予測までをバックグラウンドで実行する。"""

    forecast_done = Signal(object, str)  # combined_df（数値）, 説明テキスト
    forecast_failed = Signal(str)

    def __init__(self, raw_df: pd.DataFrame, future_year_count: int, parent=None) -> None:
        super().__init__(parent)
        self._raw = raw_df
        self._n = future_year_count

    def run(self) -> None:
        try:
            yearly = delivery_service.yearly_totals_from_raw_deliveries(self._raw)
            act, pred, note = forecast_service.run_yearly_forecast(yearly, self._n)
            combined = pd.concat([act, pred], ignore_index=True)
            self.forecast_done.emit(combined, note)
        except Exception as e:  # noqa: BLE001
            self.forecast_failed.emit(str(e))
