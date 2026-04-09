# -*- coding: utf-8 -*-
"""年次予測ダイアログ（顧客必須・品番任意・予測年数選択）。"""

from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableView,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

import pandas as pd

from app.service import delivery_service, export_service, forecast_service
from app.ui.table_model import DataFrameTableModel
from app.utils import date_utils


class ForecastDialog(QDialog):
    """
    予測実行 UI。
    conn_runner: (callable taking conn -> result) を受け取り接続を確保するコールバック。
    chart_opener: 年次実績+予測のグラフ表示用コールバック(df_combined)
    """

    def __init__(
        self,
        parent: QWidget,
        customers: list[str],
        conn_runner: Callable,
        chart_opener: Optional[Callable[[pd.DataFrame], None]] = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("年次予測")
        self._conn_runner = conn_runner
        self._chart_opener = chart_opener
        self._customers = [c for c in customers if c and c != "（すべて）"]
        self._last_combined: Optional[pd.DataFrame] = None
        self._last_note: str = ""

        self._customer_combo = QComboBox()
        self._customer_combo.addItems(self._customers)
        self._product_edit = QLineEdit()
        self._product_edit.setPlaceholderText("任意（空欄で全品番）")

        d0, d1 = date_utils.default_date_range()
        self._date_from = QDateEdit(date_utils.date_to_qdate(d0))
        self._date_to = QDateEdit(date_utils.date_to_qdate(d1))
        self._date_from.setCalendarPopup(True)
        self._date_to.setCalendarPopup(True)

        self._years_spin = QSpinBox()
        self._years_spin.setRange(1, 15)
        self._years_spin.setValue(3)

        self._note = QTextEdit()
        self._note.setReadOnly(True)
        self._note.setMaximumHeight(80)

        self._model = DataFrameTableModel(pd.DataFrame())
        self._table = QTableView()
        self._table.setModel(self._model)
        self._table.horizontalHeader().setStretchLastSection(True)

        btn_run = QPushButton("予測を実行")
        btn_run.clicked.connect(self._on_run)
        btn_excel = QPushButton("Excel 出力")
        btn_excel.clicked.connect(self._on_excel)
        btn_chart = QPushButton("グラフ表示")
        btn_chart.clicked.connect(self._on_chart)

        form = QFormLayout()
        form.addRow("顧客", self._customer_combo)
        form.addRow("品番（任意）", self._product_edit)
        form.addRow("開始日", self._date_from)
        form.addRow("終了日", self._date_to)
        form.addRow("予測年数", self._years_spin)

        g = QGroupBox("条件")
        g.setLayout(form)

        buttons = QHBoxLayout()
        buttons.addWidget(btn_run)
        buttons.addWidget(btn_excel)
        buttons.addWidget(btn_chart)

        bbox = QDialogButtonBox(QDialogButtonBox.Close)
        bbox.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(g)
        layout.addWidget(QLabel("説明"))
        layout.addWidget(self._note)
        layout.addLayout(buttons)
        layout.addWidget(self._table, stretch=1)
        layout.addWidget(bbox)

        self.resize(720, 520)

    def _on_run(self) -> None:
        if self._customer_combo.count() == 0:
            QMessageBox.warning(self, "予測", "顧客一覧が空です。先にメイン画面で接続・顧客読込を確認してください。")
            return
        customer = self._customer_combo.currentText().strip()
        if not customer:
            QMessageBox.warning(self, "予測", "顧客を選択してください。")
            return

        df_from = date_utils.qdate_to_date(self._date_from.date())
        df_to = date_utils.qdate_to_date(self._date_to.date())
        if df_from > df_to:
            QMessageBox.warning(self, "予測", "開始日が終了日より後になっています。")
            return

        prod = self._product_edit.text().strip() or None
        n_years = self._years_spin.value()

        def work(conn):
            act = delivery_service.yearly_totals_for_customer(
                conn, customer, df_from, df_to, prod
            )
            act_part, pred_part, note = forecast_service.run_yearly_forecast(
                act[["年", "納品数", "金額"]], n_years
            )
            combined = pd.concat([act_part, pred_part], ignore_index=True)
            return combined, note, act_part, pred_part

        try:
            combined, note, _, _ = self._conn_runner(work)
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "予測", f"処理中にエラーが発生しました。\n{e}")
            return

        self._last_combined = combined
        self._last_note = note
        self._note.setPlainText(note)
        # 表示用に丸め
        view = combined.copy()
        for c in ("納品数", "金額"):
            if c in view.columns:
                view[c] = view[c].map(lambda x: round(float(x), 2) if pd.notna(x) else x)
        self._model.set_dataframe(view)

    def _on_excel(self) -> None:
        if self._last_combined is None or self._last_combined.empty:
            QMessageBox.information(self, "Excel 出力", "先に「予測を実行」を行ってください。")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Excel 保存", "", "Excel (*.xlsx)"
        )
        if not path:
            return
        if not path.lower().endswith(".xlsx"):
            path += ".xlsx"
        try:
            act = self._last_combined[self._last_combined["種別"] == "実績"].copy()
            pred = self._last_combined[self._last_combined["種別"] == "予測"].copy()
            export_service.export_two_sheets(
                path,
                act.drop(columns=["種別"], errors="ignore"),
                pred.drop(columns=["種別"], errors="ignore"),
                meta=self._last_note,
            )
            QMessageBox.information(self, "Excel 出力", "保存しました。")
        except export_service.ExportError as e:
            QMessageBox.warning(self, "Excel 出力", str(e))

    def _on_chart(self) -> None:
        if self._last_combined is None or self._last_combined.empty:
            QMessageBox.information(self, "グラフ", "先に「予測を実行」を行ってください。")
            return
        if self._chart_opener:
            self._chart_opener(self._last_combined.copy())
        else:
            QMessageBox.information(self, "グラフ", "グラフ表示が利用できません。")
