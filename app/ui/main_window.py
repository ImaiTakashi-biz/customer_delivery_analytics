# -*- coding: utf-8 -*-
"""メインウィンドウ：検索・実績一覧と年次予測の横並びダッシュボード。"""

from __future__ import annotations

from typing import Any, Callable, Optional

# pandas は dateutil 経由で import フックと干渉しうるため、Qt を先に読み込む
from PySide6.QtCore import QDate, Qt, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QTableView,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

import pandas as pd

from app.config import settings
from app.db import access_connector
from app.service import delivery_service, export_service
from app.ui.busy_overlay import BusyOverlay
from app.ui.search_worker import DeliverySearchWorker, YearlyForecastFromRawWorker
from app.ui.table_model import DataFrameTableModel
from app.ui.web_inputs import ClickableDateEdit, ClickToOpenComboBox, FilterableComboBox
from app.ui.web_table_view import configure_web_table_view, rebalance_table_columns
from app.utils import date_utils


def _form_side_label(text: str) -> QLabel:
    """検索行の補助ラベル（日付など）。"""
    lb = QLabel(text)
    lb.setStyleSheet("color: #64748b; font-weight: 500; font-size: 12px;")
    return lb


class ChartYearlyDialog(QDialog):
    """年別推移グラフ（matplotlib）。別ウィンドウで表示し、閉じる操作ができる。"""

    def __init__(
        self,
        parent,
        df_yearly: pd.DataFrame,
        title: str = "年別推移",
        *,
        subtitle: str = "",
    ) -> None:
        super().__init__(parent)
        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
        from matplotlib.figure import Figure
        from matplotlib.ticker import StrMethodFormatter

        self.setWindowTitle(title)
        self.setMinimumSize(800, 520)
        self.resize(900, 580)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)

        fig = Figure(figsize=(8, 5.2), facecolor="#ffffff")
        canvas = FigureCanvasQTAgg(fig)

        ax1 = fig.add_subplot(2, 1, 1)
        ax2 = fig.add_subplot(2, 1, 2)
        ax1.set_facecolor("#fafafa")
        ax2.set_facecolor("#fafafa")

        work = df_yearly.copy()
        if work.empty:
            ax1.text(0.5, 0.5, "表示するデータがありません", ha="center", va="center")
            ax2.text(0.5, 0.5, "表示するデータがありません", ha="center", va="center")
        else:
            if "種別" not in work.columns:
                work["種別"] = "実績"
            act = work[work["種別"] == "実績"]
            pred = work[work["種別"] == "予測"]
            all_years = sorted(
                {int(y) for y in work["年"].dropna().tolist()}
            )

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
                ax.legend(loc="upper left", fontsize=8)
                ax.ticklabel_format(style="plain", axis="y", useOffset=False)
                ax.yaxis.set_major_formatter(StrMethodFormatter("{x:,.0f}"))
                if all_years:
                    ax.set_xticks(all_years)

            _plot_pair(ax1, "納品数", "納品数（年合計）")
            _plot_pair(ax2, "金額", "金額（円・年合計）")
            ax2.set_xlabel("年（西暦）")

        if subtitle:
            fig.suptitle(f"{title}\n{subtitle}", fontsize=10, color="#1f2937")
        else:
            fig.suptitle(title, fontsize=11, color="#1f2937")
        fig.tight_layout(rect=(0, 0, 1, 0.92))

        layout = QVBoxLayout(self)
        layout.addWidget(canvas, stretch=1)
        bbox = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        bbox.rejected.connect(self.reject)
        layout.addWidget(bbox)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(settings.WINDOW_TITLE)

        self._last_list_df = pd.DataFrame()
        self._last_raw_df: Optional[pd.DataFrame] = None
        self._search_worker: Optional[DeliverySearchWorker] = None
        self._forecast_worker: Optional[YearlyForecastFromRawWorker] = None
        self._last_forecast_combined: Optional[pd.DataFrame] = None
        self._last_forecast_note: str = ""
        self._pending_search_period_note: str = ""
        # 検索のたびに増加。古い予測ワーカーの完了は無視する。
        self._search_generation: int = 0
        # 品番プルダウン：全件マスタと、顧客別に絞った直近の顧客キー
        self._all_hinbans: list[str] = []
        self._last_hinban_filter_customer: Optional[str] = None
        self._hinban_lists_ready: bool = False

        central = QWidget()
        central.setObjectName("dashboardCentral")
        self.setCentralWidget(central)
        main_lay = QVBoxLayout(central)
        main_lay.setContentsMargins(18, 10, 18, 12)
        main_lay.setSpacing(8)

        page_title = QLabel("納入実績の参照・集計")
        page_title.setObjectName("pageTitle")

        # 検索は横に広げて1〜2段に収め、縦の占有を抑える
        search_wrap = QWidget()
        search_wrap_lay = QHBoxLayout(search_wrap)
        search_wrap_lay.setContentsMargins(0, 0, 0, 0)

        search_card = QFrame()
        search_card.setObjectName("dashboardSearchCard")
        search_card.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum
        )
        root = QVBoxLayout(search_card)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(6)

        # --- 検索条件（既定は期間なし＝DB 上の全日付）---
        self._period_filter = QCheckBox("期間で絞る")
        self._period_filter.setChecked(False)
        self._period_filter.setToolTip(
            "オンにすると開始日・終了日で納入日を絞り込みます。"
            "オフのときは Access 内の納入日をすべて対象にします。"
        )
        # 期間オフ時は日付を「未指定」表示（QDateEdit の特別値＝最小日と同じときの文言）
        self._date_sentinel = QDate(1900, 1, 1)
        self._date_from = ClickableDateEdit()
        self._date_to = ClickableDateEdit()
        for de in (self._date_from, self._date_to):
            de.setMinimumDate(self._date_sentinel)
            de.setSpecialValueText("年 / 月 / 日")
            de.setDate(self._date_sentinel)
        self._date_from.setEnabled(False)
        self._date_to.setEnabled(False)
        self._period_filter.toggled.connect(self._on_period_filter_toggled)
        self._refresh_main_date_tooltips()

        self._customer_combo = FilterableComboBox(
            include_all_option=True, max_visible=12
        )
        self._customer_combo.setPlaceholderText("顧客（一覧／入力）")
        self._customer_combo.setMinimumWidth(160)
        self._customer_combo.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self._product_combo = FilterableComboBox(
            include_all_option=False, max_visible=12
        )
        self._product_combo.setPlaceholderText("品番（任意・顧客で候補絞込）")
        self._product_combo.setMinimumWidth(160)
        self._product_combo.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self._product_combo.setToolTip(
            "一覧から選ぶか、入力で部分一致検索できます。"
            "顧客を一覧で選ぶか、顧客入力からフォーカスを外すと、その顧客に紐づく品番候補に絞り込みます。"
            "顧客が空または「（すべて）」のときは全品番候補です。"
        )
        # 顧客のみ「（すべて）」の説明を追加（FilterableComboBox の既定ツールチップに連結）
        _cust_tip = self._customer_combo.toolTip()
        self._customer_combo.setToolTip(
            _cust_tip + " 空欄または「（すべて）」で全顧客を対象にします。"
        )
        cust_le = self._customer_combo.lineEdit()
        cust_le.editingFinished.connect(self._on_customer_changed_for_hinban_list)
        self._customer_combo.activated.connect(self._on_customer_changed_for_hinban_list)

        self._agg_combo = ClickToOpenComboBox(max_visible=8)
        # str 列挙体を userData に渡すと Qt が文字列化し currentData() が Enum にならないため、名前で保持する
        for m in delivery_service.AggregateMode:
            self._agg_combo.addItem(m.value, m.name)
        self._agg_combo.setMinimumWidth(120)
        self._agg_combo.setMaximumWidth(220)
        self._agg_combo.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed
        )

        self._date_from.setMaximumWidth(138)
        self._date_to.setMaximumWidth(138)

        cond_caption = QLabel("検索条件")
        cond_caption.setObjectName("formSectionCaption")

        # 1行目：見出し・期間チェック・開始／終了日
        row_period = QHBoxLayout()
        row_period.setSpacing(8)
        row_period.setContentsMargins(0, 0, 0, 0)
        row_period.addWidget(cond_caption, 0, Qt.AlignmentFlag.AlignVCenter)
        row_period.addWidget(self._period_filter, 0, Qt.AlignmentFlag.AlignVCenter)
        row_period.addSpacing(6)
        row_period.addWidget(_form_side_label("開始"), 0, Qt.AlignmentFlag.AlignVCenter)
        row_period.addWidget(self._date_from, 0, Qt.AlignmentFlag.AlignVCenter)
        row_period.addWidget(_form_side_label("終了"), 0, Qt.AlignmentFlag.AlignVCenter)
        row_period.addWidget(self._date_to, 0, Qt.AlignmentFlag.AlignVCenter)
        row_period.addStretch(1)

        # 2行目：顧客・品番・集計単位（横並び）
        lb_cust = QLabel("顧客")
        lb_cust.setObjectName("formFieldLabel")
        lb_cust.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        lb_prod = QLabel("品番")
        lb_prod.setObjectName("formFieldLabel")
        lb_prod.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        lb_agg = QLabel("集計")
        lb_agg.setObjectName("formFieldLabel")
        lb_agg.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        row_fields = QHBoxLayout()
        row_fields.setSpacing(6)
        row_fields.setContentsMargins(0, 0, 0, 0)
        row_fields.addWidget(lb_cust, 0, Qt.AlignmentFlag.AlignVCenter)
        row_fields.addWidget(self._customer_combo, 1)
        row_fields.addSpacing(10)
        row_fields.addWidget(lb_prod, 0, Qt.AlignmentFlag.AlignVCenter)
        row_fields.addWidget(self._product_combo, 1)
        row_fields.addSpacing(10)
        row_fields.addWidget(lb_agg, 0, Qt.AlignmentFlag.AlignVCenter)
        row_fields.addWidget(self._agg_combo, 0)

        fl = QVBoxLayout()
        fl.setSpacing(6)
        fl.setContentsMargins(0, 0, 0, 0)
        fl.addLayout(row_period)
        fl.addLayout(row_fields)

        # --- ボタン ---
        btn_search = QPushButton("検索")
        self._btn_search = btn_search
        btn_search.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_search.clicked.connect(self._on_search)
        btn_excel = QPushButton("一覧を Excel 出力")
        btn_excel.setObjectName("secondaryButton")
        btn_excel.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_excel.clicked.connect(self._on_export_list)
        btn_chart = QPushButton("年別推移グラフ")
        btn_chart.setObjectName("secondaryButton")
        btn_chart.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_chart.clicked.connect(self._on_chart_list)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)
        toolbar.setContentsMargins(0, 2, 0, 0)
        toolbar.addWidget(btn_search)
        toolbar.addStretch(1)

        root.addLayout(fl)
        root.addLayout(toolbar)

        search_wrap_lay.addWidget(search_card, 1)

        self._status = QLabel("Access パス: " + settings.resolve_access_db_path())
        self._status.setObjectName("statusLabel")
        self._status.setWordWrap(True)

        self._model = DataFrameTableModel()
        self._table = QTableView()
        self._table.setModel(self._model)
        configure_web_table_view(self._table)
        self._model.modelReset.connect(
            lambda: rebalance_table_columns(self._table)
        )

        # --- 年次予測コントロール（右パネルへ配置）---
        fc_row = QHBoxLayout()
        fc_row.setSpacing(8)
        fy_lbl = QLabel("予測年数")
        fy_lbl.setObjectName("formFieldLabel")
        fc_row.addWidget(fy_lbl)
        self._spin_forecast_years = QSpinBox()
        self._spin_forecast_years.setRange(1, 5)
        self._spin_forecast_years.setValue(3)
        self._spin_forecast_years.setMaximumWidth(72)
        self._spin_forecast_years.setToolTip("先の年を何年分、線形トレンドで外挿するか（1〜5年）。")
        fc_row.addWidget(self._spin_forecast_years)
        self._btn_forecast_run = QPushButton("予測を実行")
        self._btn_forecast_run.setObjectName("secondaryButton")
        self._btn_forecast_run.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_forecast_run.clicked.connect(self._on_forecast_run)
        self._btn_forecast_chart = QPushButton("予測グラフ")
        self._btn_forecast_chart.setObjectName("secondaryButton")
        self._btn_forecast_chart.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_forecast_chart.setEnabled(False)
        self._btn_forecast_chart.clicked.connect(self._on_forecast_chart)
        self._btn_forecast_excel = QPushButton("予測を Excel")
        self._btn_forecast_excel.setObjectName("secondaryButton")
        self._btn_forecast_excel.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_forecast_excel.setEnabled(False)
        self._btn_forecast_excel.clicked.connect(self._on_forecast_excel)
        fc_row.addWidget(self._btn_forecast_run)
        fc_row.addWidget(self._btn_forecast_chart)
        fc_row.addWidget(self._btn_forecast_excel)
        fc_row.addStretch()

        self._forecast_note = QTextEdit()
        self._forecast_note.setReadOnly(True)
        self._forecast_note.setMaximumHeight(96)
        self._forecast_note.setPlaceholderText(
            "検索実行後、「予測を実行」で直近の検索明細を年合計にまとめ、将来年を算出します。"
        )
        self._forecast_note.setObjectName("forecastNoteBox")

        note_cap = QLabel("算出の説明")
        note_cap.setObjectName("formSectionCaption")

        self._forecast_model = DataFrameTableModel(pd.DataFrame())
        self._forecast_table = QTableView()
        self._forecast_table.setModel(self._forecast_model)
        configure_web_table_view(self._forecast_table)
        self._forecast_model.modelReset.connect(
            lambda: rebalance_table_columns(self._forecast_table)
        )
        self._forecast_table.setMinimumHeight(160)

        # --- 左右 50/50：実績 / 年次予測 ---
        split = QSplitter(Qt.Orientation.Horizontal)
        split.setObjectName("mainSplit")
        split.setChildrenCollapsible(False)

        left_panel = QFrame()
        left_panel.setObjectName("webSplitPanelLeft")
        left_lay = QVBoxLayout(left_panel)
        left_lay.setContentsMargins(16, 14, 14, 16)
        left_lay.setSpacing(10)
        lt = QLabel("実績一覧")
        lt.setObjectName("panelSectionTitle")
        ls = QLabel(
            "検索で絞り込んだ集計結果です。下のボタンからこの一覧の Excel 出力と年別推移グラフが利用できます。"
        )
        ls.setObjectName("panelSectionSubtitle")
        ls.setWordWrap(True)
        actual_bar = QHBoxLayout()
        actual_bar.setSpacing(8)
        actual_bar.setContentsMargins(0, 0, 0, 0)
        actual_bar.addWidget(btn_excel)
        actual_bar.addWidget(btn_chart)
        actual_bar.addStretch(1)
        left_lay.addWidget(lt)
        left_lay.addWidget(ls)
        left_lay.addWidget(self._status)
        left_lay.addLayout(actual_bar)
        left_lay.addWidget(self._table, stretch=1)

        right_panel = QFrame()
        right_panel.setObjectName("webSplitPanelRight")
        right_lay = QVBoxLayout(right_panel)
        right_lay.setContentsMargins(14, 14, 16, 16)
        right_lay.setSpacing(10)
        rt = QLabel("年次予測")
        rt.setObjectName("panelSectionTitle")
        rs = QLabel(
            "将来の年次納品数・金額の見積もりです。先に検索で明細を取得してから「予測を実行」してください。"
        )
        rs.setObjectName("panelSectionSubtitle")
        rs.setWordWrap(True)
        right_lay.addWidget(rt)
        right_lay.addWidget(rs)
        right_lay.addLayout(fc_row)
        right_lay.addWidget(note_cap)
        right_lay.addWidget(self._forecast_note)
        right_lay.addWidget(self._forecast_table, stretch=1)

        split.addWidget(left_panel)
        split.addWidget(right_panel)
        split.setStretchFactor(0, 1)
        split.setStretchFactor(1, 1)
        split.setSizes([520, 520])

        main_lay.addWidget(page_title)
        main_lay.addWidget(search_wrap)
        main_lay.addWidget(split, stretch=1)

        self._busy_overlay = BusyOverlay(central)

        self.setMinimumSize(1100, 620)
        # コンストラクタ内で DB 接続すると、ウィンドウ表示前にハング／クラッシュし無言終了しうる。
        # イベントループ開始後に読み込み、画面は必ず先に出す。
        QTimer.singleShot(0, self._load_customers)

    def _current_aggregate_mode(self) -> delivery_service.AggregateMode:
        """集計単位コンボから AggregateMode を取得（Qt の userData 変換差異を吸収）。"""
        key = self._agg_combo.currentData()
        if isinstance(key, str) and key in delivery_service.AggregateMode.__members__:
            return delivery_service.AggregateMode[key]
        if isinstance(key, delivery_service.AggregateMode):
            return key
        return delivery_service.AggregateMode(self._agg_combo.currentText())

    def _refresh_main_date_tooltips(self) -> None:
        """期間オフ時は日付欄が無効のため、カレンダーが開かない理由をツールチップで示す。"""
        on = self._period_filter.isChecked()
        en = "クリックでカレンダーを開きます。キーボードでも日付を入力できます。"
        dis = (
            "全期間検索では日付は使いません。"
            "カレンダーを使うには「納入日の期間で絞り込む」にチェックしてください。"
        )
        self._date_from.setToolTip(en if on else dis)
        self._date_to.setToolTip(en if on else dis)

    def _on_period_filter_toggled(self, checked: bool) -> None:
        """期間指定のオンオフに合わせて日付入力の有効化と候補日をセットする。"""
        if checked:
            d0, d1 = date_utils.suggested_period_when_filter_enabled()
            self._date_from.setDate(date_utils.date_to_qdate(d0))
            self._date_to.setDate(date_utils.date_to_qdate(d1))
        else:
            self._date_from.setDate(self._date_sentinel)
            self._date_to.setDate(self._date_sentinel)
        self._date_from.setEnabled(checked)
        self._date_to.setEnabled(checked)
        self._refresh_main_date_tooltips()

    def run_with_connection(self, fn: Callable[[Any], Any]) -> Any:
        """DB 接続を開き fn(conn) を実行する。"""
        path = settings.resolve_access_db_path()
        with access_connector.open_connection(path) as conn:
            return fn(conn)

    def _load_customers(self) -> None:
        self._busy_overlay.show_message("顧客一覧を読み込み中…")
        QApplication.processEvents()
        try:

            def load(conn):
                names = delivery_service.fetch_customer_names(conn)
                hinbans = delivery_service.fetch_distinct_hinban(conn)
                return names, hinbans

            names, hinbans = self.run_with_connection(load)
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
        finally:
            self._busy_overlay.hide_overlay()

        self._all_hinbans = list(hinbans)
        self._hinban_lists_ready = True
        self._last_hinban_filter_customer = None
        self._customer_combo.set_source_items(names)
        self._product_combo.set_source_items(hinbans)
        self._status.setText(
            f"顧客件数: {len(names)} 件 / 品番候補: {len(hinbans)} 件を読み込みました。\n"
            f"Access: {settings.resolve_access_db_path()}"
        )

    def _on_customer_changed_for_hinban_list(self) -> None:
        """顧客が確定したタイミングで品番候補をその顧客向けに絞り込む（DB と同じ結合条件）。"""
        if not self._hinban_lists_ready:
            return
        cust = self._customer_combo.currentText().strip()
        if cust in ("", "（すべて）"):
            self._last_hinban_filter_customer = None
            self._product_combo.set_source_items(self._all_hinbans)
            return
        if cust == self._last_hinban_filter_customer:
            return
        self._busy_overlay.show_message(
            "品番候補を読み込み中…\n"
            "選択した顧客に紐づく品番を取得しています。"
        )
        QApplication.processEvents()
        try:

            def load(conn):
                return delivery_service.fetch_distinct_hinban_for_customer(conn, cust)

            items = self.run_with_connection(load)
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(
                self,
                "品番一覧",
                f"顧客に応じた品番の取得に失敗しました。\n{e}",
            )
            return
        finally:
            self._busy_overlay.hide_overlay()

        self._last_hinban_filter_customer = cust
        self._product_combo.set_source_items(items)

    def _on_search(self) -> None:
        if self._search_worker is not None and self._search_worker.isRunning():
            return

        if self._period_filter.isChecked():
            if (
                self._date_from.date() == self._date_sentinel
                or self._date_to.date() == self._date_sentinel
            ):
                QMessageBox.warning(self, "検索", "開始日と終了日を指定してください。")
                return
            df_from = date_utils.qdate_to_date(self._date_from.date())
            df_to = date_utils.qdate_to_date(self._date_to.date())
            if df_from > df_to:
                QMessageBox.warning(self, "検索", "開始日が終了日より後になっています。")
                return
        else:
            df_from, df_to = None, None

        customer = self._customer_combo.currentText().strip()
        if customer in ("", "（すべて）"):
            customer = None
        product = self._product_combo.currentText().strip() or None
        mode = self._current_aggregate_mode()

        self._pending_search_period_note = (
            f"{df_from} ～ {df_to}"
            if df_from is not None and df_to is not None
            else "全期間（DB 内の全日付）"
        )

        self._btn_search.setEnabled(False)
        self._busy_overlay.show_message(
            "検索中…\n"
            "ネットワーク上の Access からデータを取得しています。"
            "完了までしばらくお待ちください。"
        )
        self._status.setText(
            "検索中…\n"
            "ネットワーク上の Access から大量データを読み込んでいます。"
            "完了まで操作は可能ですが、しばらくお待ちください。"
        )

        worker = DeliverySearchWorker(
            settings.resolve_access_db_path(),
            df_from,
            df_to,
            customer,
            product,
            mode.name,
            parent=self,
        )
        self._search_worker = worker
        worker.search_done.connect(self._on_search_worker_done)
        worker.search_failed.connect(self._on_search_worker_failed)
        worker.finished.connect(self._on_search_worker_thread_finished)
        worker.start()

    def _on_search_worker_done(
        self, raw: pd.DataFrame, agg: pd.DataFrame, mode_name: str
    ) -> None:
        self._search_generation += 1
        self._last_forecast_combined = None
        self._last_forecast_note = ""
        self._forecast_model.set_dataframe(pd.DataFrame())
        self._forecast_note.clear()
        self._btn_forecast_chart.setEnabled(False)
        self._btn_forecast_excel.setEnabled(False)

        mode = delivery_service.AggregateMode[mode_name]
        self._last_raw_df = raw
        self._last_list_df = agg
        self._model.set_dataframe(agg)
        self._status.setText(
            f"取得明細: {len(raw)} 行 / 表示行: {len(agg)} 行（集計単位: {mode.value}）\n"
            f"対象期間: {self._pending_search_period_note}"
        )

    def _on_search_worker_failed(self, message: str) -> None:
        QMessageBox.critical(self, "検索エラー", f"検索中にエラーが発生しました。\n{message}")
        self._status.setText(
            f"検索に失敗しました。\nAccess: {settings.resolve_access_db_path()}"
        )

    def _on_search_worker_thread_finished(self) -> None:
        self._busy_overlay.hide_overlay()
        self._btn_search.setEnabled(True)
        self._search_worker = None

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
        self._busy_overlay.show_message("Excel ファイルを書き出し中…")
        QApplication.processEvents()
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
        finally:
            self._busy_overlay.hide_overlay()

    def _on_chart_list(self) -> None:
        raw = self._last_raw_df
        if raw is None or raw.empty:
            QMessageBox.information(self, "グラフ", "先に検索を実行してください。")
            return
        self._busy_overlay.show_message("グラフを準備中…")
        QApplication.processEvents()
        try:
            y = delivery_service.yearly_totals_from_raw_deliveries(raw)
            y = y.copy()
            y["種別"] = "実績"
            cust = self._customer_combo.currentText().strip()
            if cust in ("", "（すべて）"):
                cust_lbl = "全顧客"
            else:
                cust_lbl = cust
            prod_lbl = self._product_combo.currentText().strip() or "全品番"
            period_lbl = self._pending_search_period_note or "—"
            sub = f"顧客: {cust_lbl}  /  品番: {prod_lbl}  /  対象期間: {period_lbl}"
            dlg = ChartYearlyDialog(
                self, y, title="年別推移（検索結果）", subtitle=sub
            )
            dlg.show()
        finally:
            self._busy_overlay.hide_overlay()

    def _on_forecast_run(self) -> None:
        if self._forecast_worker is not None and self._forecast_worker.isRunning():
            QMessageBox.information(
                self, "予測", "予測計算の実行中です。完了を待ってから再度お試しください。"
            )
            return
        raw = self._last_raw_df
        if raw is None or raw.empty:
            QMessageBox.information(
                self, "予測", "先に検索を実行し、明細データを取得してください。"
            )
            return
        yearly = delivery_service.yearly_totals_from_raw_deliveries(raw)
        if yearly.empty:
            QMessageBox.warning(
                self,
                "予測",
                "年次集計できる明細がありません（納入日・納品数・金額が揃っているか確認してください）。",
            )
            return

        n_years = self._spin_forecast_years.value()
        run_gen = self._search_generation
        self._btn_forecast_run.setEnabled(False)
        self._busy_overlay.show_message(
            "予測を計算中…\n"
            "検索で取得した明細を年ごとに集計し、トレンドから将来年を算出しています。"
        )
        QApplication.processEvents()

        worker = YearlyForecastFromRawWorker(raw, n_years, parent=self)
        self._forecast_worker = worker
        worker.forecast_done.connect(
            lambda df, note: self._on_forecast_worker_done(df, note, run_gen)
        )
        worker.forecast_failed.connect(
            lambda msg: self._on_forecast_worker_failed(msg, run_gen)
        )
        worker.finished.connect(self._on_forecast_worker_thread_finished)
        worker.start()

    def _on_forecast_worker_done(
        self, combined: pd.DataFrame, note: str, run_gen: int
    ) -> None:
        if run_gen != self._search_generation:
            return
        self._last_forecast_combined = combined
        self._last_forecast_note = note
        view = combined.copy()
        for c in ("納品数", "金額"):
            if c in view.columns:
                view[c] = view[c].map(
                    lambda x: round(float(x), 2) if pd.notna(x) else x
                )
        self._forecast_model.set_dataframe(view)
        rebalance_table_columns(self._forecast_table)
        cust = self._customer_combo.currentText().strip()
        cust_lbl = "全顧客" if cust in ("", "（すべて）") else cust
        prod_lbl = self._product_combo.currentText().strip() or "全品番"
        period_lbl = self._pending_search_period_note or "—"
        self._forecast_note.setPlainText(
            f"{note}\n\n"
            f"入力データ: 直近の検索で取得した明細を西暦年ごとに合計した系列です。\n"
            f"検索条件の目安: 顧客={cust_lbl} / 品番={prod_lbl} / 期間={period_lbl}"
        )
        self._btn_forecast_chart.setEnabled(True)
        self._btn_forecast_excel.setEnabled(True)

    def _on_forecast_worker_failed(self, message: str, run_gen: int) -> None:
        if run_gen != self._search_generation:
            return
        QMessageBox.warning(self, "予測", f"予測の計算に失敗しました。\n{message}")

    def _on_forecast_worker_thread_finished(self) -> None:
        self._busy_overlay.hide_overlay()
        self._btn_forecast_run.setEnabled(True)
        self._forecast_worker = None

    def _on_forecast_chart(self) -> None:
        df = self._last_forecast_combined
        if df is None or df.empty:
            QMessageBox.information(self, "グラフ", "先に「予測を実行」を行ってください。")
            return
        self._busy_overlay.show_message("グラフを準備中…")
        QApplication.processEvents()
        try:
            cust = self._customer_combo.currentText().strip()
            cust_lbl = "全顧客" if cust in ("", "（すべて）") else cust
            prod_lbl = self._product_combo.currentText().strip() or "全品番"
            period_lbl = self._pending_search_period_note or "—"
            sub = (
                f"顧客: {cust_lbl}  /  品番: {prod_lbl}  /  対象期間: {period_lbl}\n"
                f"{self._last_forecast_note}"
            )
            dlg = ChartYearlyDialog(
                self,
                df,
                title="年別推移（実績と予測）",
                subtitle=sub,
            )
            dlg.show()
        finally:
            self._busy_overlay.hide_overlay()

    def _on_forecast_excel(self) -> None:
        df = self._last_forecast_combined
        if df is None or df.empty:
            QMessageBox.information(self, "Excel", "先に「予測を実行」を行ってください。")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Excel 保存（予測）", "", "Excel (*.xlsx)"
        )
        if not path:
            return
        if not path.lower().endswith(".xlsx"):
            path += ".xlsx"
        self._busy_overlay.show_message("Excel ファイルを書き出し中…")
        QApplication.processEvents()
        try:
            act = df[df["種別"] == "実績"].drop(columns=["種別"], errors="ignore")
            pred = df[df["種別"] == "予測"].drop(columns=["種別"], errors="ignore")
            export_service.export_two_sheets(
                path,
                act,
                pred,
                meta=self._last_forecast_note,
            )
            QMessageBox.information(self, "Excel", "保存しました。")
        except export_service.ExportError as e:
            QMessageBox.warning(self, "Excel", str(e))
        finally:
            self._busy_overlay.hide_overlay()
