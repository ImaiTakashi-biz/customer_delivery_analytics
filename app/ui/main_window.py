# -*- coding: utf-8 -*-
"""メインウィンドウ：実績一覧・検索・Excel・グラフ・予測ダイアログ起動。"""

from __future__ import annotations

from typing import Any, Callable, Optional

# pandas は dateutil 経由で import フックと干渉しうるため、Qt を先に読み込む
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

import pandas as pd

from app.config import settings
from app.db import access_connector
from app.service import delivery_service, export_service
from app.ui.forecast_dialog import ForecastDialog
from app.ui.table_model import DataFrameTableModel
from app.utils import date_utils


class ChartYearlyDialog(QWidget):
    """年別推移グラフ（matplotlib）。実績と予測を線種で区別。"""

    def __init__(self, parent, df_yearly: pd.DataFrame, title: str = "年別推移"):
        super().__init__(parent)
        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
        from matplotlib.figure import Figure

        self.setWindowTitle(title)
        self.setMinimumSize(800, 520)

        fig = Figure(figsize=(8, 5), tight_layout=True)
        canvas = FigureCanvasQTAgg(fig)

        ax1 = fig.add_subplot(2, 1, 1)
        ax2 = fig.add_subplot(2, 1, 2)

        work = df_yearly.copy()
        if work.empty:
            ax1.text(0.5, 0.5, "表示するデータがありません", ha="center")
            ax2.text(0.5, 0.5, "表示するデータがありません", ha="center")
        else:
            if "種別" not in work.columns:
                work["種別"] = "実績"
            act = work[work["種別"] == "実績"]
            pred = work[work["種別"] == "予測"]

            def _plot_pair(ax, col: str, ylabel: str) -> None:
                if not act.empty:
                    ax.plot(
                        act["年"],
                        act[col],
                        marker="o",
                        linestyle="-",
                        color="tab:blue",
                        label="実績",
                    )
                if not pred.empty:
                    # 実績の続きとして見せるため同系色で破線
                    ax.plot(
                        pred["年"],
                        pred[col],
                        marker="s",
                        linestyle="--",
                        color="tab:orange",
                        label="予測",
                    )
                ax.set_ylabel(ylabel)
                ax.grid(True, alpha=0.3)
                ax.legend()

            _plot_pair(ax1, "納品数", "納品数")
            _plot_pair(ax2, "金額", "金額")
            ax2.set_xlabel("年")

        layout = QVBoxLayout(self)
        layout.addWidget(canvas)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(settings.WINDOW_TITLE)

        self._last_list_df = pd.DataFrame()
        self._last_raw_df: Optional[pd.DataFrame] = None

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        # --- 検索条件 ---
        self._date_from = QDateEdit()
        self._date_to = QDateEdit()
        d0, d1 = date_utils.default_date_range()
        self._date_from.setDate(date_utils.date_to_qdate(d0))
        self._date_to.setDate(date_utils.date_to_qdate(d1))
        self._date_from.setCalendarPopup(True)
        self._date_to.setCalendarPopup(True)

        self._customer_combo = QComboBox()
        self._customer_combo.setEditable(False)
        self._product_edit = QLineEdit()
        self._product_edit.setPlaceholderText("任意（部分一致）")

        self._agg_combo = QComboBox()
        for m in delivery_service.AggregateMode:
            self._agg_combo.addItem(m.value, m)

        form = QFormLayout()
        form.addRow("開始日", self._date_from)
        form.addRow("終了日", self._date_to)
        form.addRow("顧客", self._customer_combo)
        form.addRow("品番", self._product_edit)

        agg_row = QHBoxLayout()
        agg_row.addWidget(QLabel("集計単位"))
        agg_row.addWidget(self._agg_combo)
        agg_row.addStretch()

        cond = QGroupBox("検索条件")
        fl = QVBoxLayout()
        fl.addLayout(form)
        fl.addLayout(agg_row)
        cond.setLayout(fl)

        # --- ボタン ---
        btn_search = QPushButton("検索")
        btn_search.clicked.connect(self._on_search)
        btn_reload_customers = QPushButton("顧客一覧を再読込")
        btn_reload_customers.clicked.connect(self._load_customers)
        btn_excel = QPushButton("一覧を Excel 出力")
        btn_excel.clicked.connect(self._on_export_list)
        btn_chart = QPushButton("年別推移グラフ")
        btn_chart.clicked.connect(self._on_chart_list)
        btn_forecast = QPushButton("予測…")
        btn_forecast.clicked.connect(self._on_forecast)

        row = QHBoxLayout()
        for b in (
            btn_search,
            btn_reload_customers,
            btn_excel,
            btn_chart,
            btn_forecast,
        ):
            row.addWidget(b)
        row.addStretch()

        self._status = QLabel("Access パス: " + settings.resolve_access_db_path())
        self._status.setWordWrap(True)

        self._model = DataFrameTableModel()
        self._table = QTableView()
        self._table.setModel(self._model)
        self._table.horizontalHeader().setStretchLastSection(True)

        root.addWidget(cond)
        root.addLayout(row)
        root.addWidget(self._status)
        root.addWidget(self._table, stretch=1)

        self.resize(1000, 640)
        self._load_customers()

    def run_with_connection(self, fn: Callable[[Any], Any]) -> Any:
        """DB 接続を開き fn(conn) を実行する。"""
        path = settings.resolve_access_db_path()
        with access_connector.open_connection(path) as conn:
            return fn(conn)

    def _load_customers(self) -> None:
        try:

            def load(conn):
                names = delivery_service.fetch_customer_names(conn)
                return names

            names = self.run_with_connection(load)
        except access_connector.OdbcDriverNotFoundError as e:
            QMessageBox.critical(self, "接続エラー", str(e))
            return
        except access_connector.AccessFileUnavailableError as e:
            QMessageBox.critical(self, "接続エラー", str(e))
            return
        except access_connector.AccessConnectionError as e:
            QMessageBox.critical(self, "接続エラー", str(e))
            return
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "接続エラー", f"顧客一覧の取得に失敗しました。\n{e}")
            return

        self._customer_combo.clear()
        self._customer_combo.addItem("（すべて）")
        for n in names:
            self._customer_combo.addItem(n)
        self._status.setText(
            f"顧客件数: {len(names)} 件を読み込みました。\nAccess: {settings.resolve_access_db_path()}"
        )

    def _on_search(self) -> None:
        df_from = date_utils.qdate_to_date(self._date_from.date())
        df_to = date_utils.qdate_to_date(self._date_to.date())
        if df_from > df_to:
            QMessageBox.warning(self, "検索", "開始日が終了日より後になっています。")
            return

        customer = self._customer_combo.currentText().strip()
        if customer == "（すべて）":
            customer = None
        product = self._product_edit.text().strip() or None
        mode = self._agg_combo.currentData()

        try:

            def work(conn):
                raw = delivery_service.fetch_deliveries(
                    conn, df_from, df_to, customer, product
                )
                agg = delivery_service.aggregate_for_list(raw, mode)
                return raw, agg

            raw, agg = self.run_with_connection(work)
        except access_connector.OdbcDriverNotFoundError as e:
            QMessageBox.critical(self, "検索エラー", str(e))
            return
        except access_connector.AccessFileUnavailableError as e:
            QMessageBox.critical(self, "検索エラー", str(e))
            return
        except access_connector.AccessConnectionError as e:
            QMessageBox.critical(self, "検索エラー", str(e))
            return
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "検索エラー", f"検索中にエラーが発生しました。\n{e}")
            return

        self._last_raw_df = raw
        self._last_list_df = agg
        self._model.set_dataframe(agg)
        self._status.setText(
            f"取得明細: {len(raw)} 行 / 表示行: {len(agg)} 行（集計単位: {mode.value}）"
        )

    def _on_export_list(self) -> None:
        df = self._model.dataframe()
        if df.empty:
            QMessageBox.information(self, "Excel", "出力する一覧がありません。先に検索してください。")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Excel 保存", "", "Excel (*.xlsx)"
        )
        if not path:
            return
        if not path.lower().endswith(".xlsx"):
            path += ".xlsx"
        try:
            export_service.export_dataframe(
                path,
                df,
                sheet_name="一覧",
                table_name="顧客別納入分析システム / 実績一覧",
            )
            QMessageBox.information(self, "Excel", "保存しました。")
        except export_service.ExportError as e:
            QMessageBox.warning(self, "Excel", str(e))

    def _on_chart_list(self) -> None:
        raw = self._last_raw_df
        if raw is None or raw.empty:
            QMessageBox.information(self, "グラフ", "先に検索を実行してください。")
            return
        work = raw.copy()
        work["年"] = work["納入日"].dt.year
        y = work.groupby("年", as_index=False).agg(
            納品数=("納品数", "sum"),
            金額=("金額", "sum"),
        )
        y["種別"] = "実績"
        y["年"] = y["年"].astype(int)
        dlg = ChartYearlyDialog(self, y, title="年別推移（検索結果ベース）")
        dlg.show()

    def _on_forecast(self) -> None:
        customers = [self._customer_combo.itemText(i) for i in range(self._customer_combo.count())]

        def conn_runner(work_fn):
            return self.run_with_connection(work_fn)

        def open_chart(df: pd.DataFrame) -> None:
            dlg = ChartYearlyDialog(self, df, title="年別推移（実績と予測）")
            dlg.show()

        dlg = ForecastDialog(self, customers, conn_runner, chart_opener=open_chart)
        dlg.exec()
