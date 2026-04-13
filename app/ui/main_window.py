# -*- coding: utf-8 -*-
"""メインウィンドウ：検索・実績一覧と年次予測の横並びダッシュボード。"""

from __future__ import annotations

from typing import Any, Callable, Optional

# pandas は dateutil 経由で import フックと干渉しうるため、Qt を先に読み込む
from PySide6.QtCore import QDate, QPoint, Qt, QTimer
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap, QPolygon
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
    QPushButton,
    QSizePolicy,
    QStyle,
    QStyleOptionSpinBox,
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
from app.ui.message_dialog import show_critical, show_information, show_warning
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


def _make_excel_button_icon() -> QIcon:
    """Excel 出力ボタン用の簡易アイコン。"""
    pixmap = QPixmap(16, 16)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#16a34a"))
    painter.drawRoundedRect(1, 1, 14, 14, 4, 4)

    painter.setBrush(QColor("#ffffff"))
    painter.drawRoundedRect(4, 3, 8, 10, 1.5, 1.5)

    painter.setPen(QPen(QColor("#16a34a"), 1.0))
    painter.drawLine(6, 7, 10, 7)
    painter.drawLine(6, 9, 10, 9)

    painter.end()
    return QIcon(pixmap)


def _make_chart_button_icon() -> QIcon:
    """グラフ表示ボタン用の簡易アイコン。"""
    pixmap = QPixmap(16, 16)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#2563eb"))
    painter.drawRoundedRect(1, 1, 14, 14, 4, 4)

    painter.setBrush(QColor("#ffffff"))
    painter.drawRect(4, 8, 2, 3)
    painter.drawRect(7, 6, 2, 5)
    painter.drawRect(10, 4, 2, 7)
    painter.end()
    return QIcon(pixmap)


class ForecastYearSpinBox(QSpinBox):
    """予測年数専用。上下矢印を自前で描画して環境差を抑える。"""

    def paintEvent(self, event) -> None:  # noqa: N802
        super().paintEvent(event)

        opt = QStyleOptionSpinBox()
        self.initStyleOption(opt)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(
            QColor("#64748b") if self.isEnabled() else QColor("#cbd5e1")
        )

        for subcontrol, is_up in (
            (QStyle.SubControl.SC_SpinBoxUp, True),
            (QStyle.SubControl.SC_SpinBoxDown, False),
        ):
            rect = self.style().subControlRect(
                QStyle.ComplexControl.CC_SpinBox, opt, subcontrol, self
            )
            if not rect.isValid() or rect.width() <= 0 or rect.height() <= 0:
                continue

            cx = rect.center().x()
            cy = rect.center().y()
            if is_up:
                points = [
                    QPoint(cx - 4, cy + 2),
                    QPoint(cx + 4, cy + 2),
                    QPoint(cx, cy - 3),
                ]
            else:
                points = [
                    QPoint(cx - 4, cy - 2),
                    QPoint(cx + 4, cy - 2),
                    QPoint(cx, cy + 3),
                ]
            painter.drawPolygon(QPolygon(points))

        painter.end()


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
                ax.legend(
                    loc="upper left",
                    bbox_to_anchor=(1.01, 1.0),
                    borderaxespad=0.0,
                    frameon=False,
                    fontsize=8,
                )
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
        fig.tight_layout(rect=(0, 0, 0.89, 0.92))

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
        self._customer_display_to_name: dict[str, str] = {}
        self._customer_code_to_name: dict[str, str] = {}
        self._customer_name_to_display: dict[str, str] = {}
        self._customer_placeholder = "顧客コード・客先名（一覧／入力）"
        self._product_placeholder = "品番（任意・顧客で候補絞込）"
        self._product_disabled_placeholder = "顧客別では品番を使いません"
        self._customer_disabled_placeholder = "品番別では顧客を使いません"

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

        # --- 検索条件：開始日・終了日は常に使用 ---
        self._date_sentinel = QDate(1900, 1, 1)
        self._date_from = ClickableDateEdit()
        self._date_to = ClickableDateEdit()
        d0, d1 = date_utils.default_date_range()
        for de in (self._date_from, self._date_to):
            de.setMinimumDate(self._date_sentinel)
            de.setSpecialValueText("年 / 月 / 日")
            de.setDate(self._date_sentinel)
            de.setEnabled(True)
            de.setToolTip("クリックでカレンダーを開きます。キーボードでも日付を入力できます。")
        self._date_from.setDate(date_utils.date_to_qdate(d0))
        self._date_to.setDate(date_utils.date_to_qdate(d1))

        self._customer_combo = FilterableComboBox(
            include_all_option=True, max_visible=12
        )
        self._customer_combo.setPlaceholderText(self._customer_placeholder)
        self._customer_combo.setMinimumWidth(140)
        self._customer_combo.setMaximumWidth(600)
        self._customer_combo.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed
        )
        self._product_combo = FilterableComboBox(
            include_all_option=False, max_visible=12
        )
        self._product_combo.setPlaceholderText(self._product_placeholder)
        self._product_combo.setMinimumWidth(140)
        self._product_combo.setMaximumWidth(600)
        self._product_combo.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed
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
        cust_le.textChanged.connect(self._refresh_search_button_state)
        self._product_combo.lineEdit().textChanged.connect(
            self._refresh_search_button_state
        )

        self._agg_combo = ClickToOpenComboBox(max_visible=8)
        # str 列挙体を userData に渡すと Qt が文字列化し currentData() が Enum にならないため、名前で保持する
        for m in delivery_service.AggregateMode:
            self._agg_combo.addItem(m.value, m.name)
        self._agg_combo.setMinimumWidth(120)
        self._agg_combo.setMaximumWidth(220)
        self._agg_combo.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed
        )
        self._agg_combo.currentIndexChanged.connect(
            self._on_aggregate_mode_changed
        )

        self._date_from.setMaximumWidth(138)
        self._date_to.setMaximumWidth(138)
        self._date_from.dateChanged.connect(self._refresh_search_button_state)
        self._date_to.dateChanged.connect(self._refresh_search_button_state)

        cond_caption = QLabel("検索条件")
        cond_caption.setObjectName("formSectionCaption")

        # 1行目：見出し・開始／終了日
        row_period = QHBoxLayout()
        row_period.setSpacing(8)
        row_period.setContentsMargins(0, 0, 0, 0)
        row_period.addWidget(cond_caption, 0, Qt.AlignmentFlag.AlignVCenter)
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
        row_fields.addWidget(lb_agg, 0, Qt.AlignmentFlag.AlignVCenter)
        row_fields.addWidget(self._agg_combo, 0)
        row_fields.addSpacing(12)
        row_fields.addWidget(lb_cust, 0, Qt.AlignmentFlag.AlignVCenter)
        row_fields.addWidget(self._customer_combo, 1)
        row_fields.addSpacing(10)
        row_fields.addWidget(lb_prod, 0, Qt.AlignmentFlag.AlignVCenter)
        row_fields.addWidget(self._product_combo, 1)

        fl = QVBoxLayout()
        fl.setSpacing(6)
        fl.setContentsMargins(0, 0, 0, 0)
        fl.addLayout(row_period)
        fl.addLayout(row_fields)

        # --- ボタン ---
        btn_search = QPushButton("検索")
        self._btn_search = btn_search
        self._btn_search.setObjectName("searchPrimaryButton")
        btn_search.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_search.setEnabled(False)
        btn_search.clicked.connect(self._on_search)
        excel_icon = _make_excel_button_icon()
        chart_icon = _make_chart_button_icon()
        btn_excel = QPushButton("一覧を Excel 出力")
        btn_excel.setObjectName("secondaryButton")
        btn_excel.setIcon(excel_icon)
        btn_excel.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_excel.clicked.connect(self._on_export_list)
        btn_chart = QPushButton("年別推移グラフ")
        btn_chart.setObjectName("secondaryButton")
        btn_chart.setIcon(chart_icon)
        btn_chart.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_chart.clicked.connect(self._on_chart_list)

        row_fields.addSpacing(6)
        row_fields.addWidget(btn_search, 0, Qt.AlignmentFlag.AlignVCenter)
        row_fields.addStretch(1)

        root.addLayout(fl)

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
        self._spin_forecast_years = ForecastYearSpinBox()
        self._spin_forecast_years.setObjectName("forecastYearSpin")
        self._spin_forecast_years.setRange(1, 5)
        self._spin_forecast_years.setValue(3)
        self._spin_forecast_years.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._spin_forecast_years.setFixedWidth(88)
        self._spin_forecast_years.setToolTip("先の年を何年分、線形トレンドで外挿するか（1〜5年）。")
        fc_row.addWidget(self._spin_forecast_years)
        self._btn_forecast_run = QPushButton("予測を実行")
        self._btn_forecast_run.setObjectName("forecastRunButton")
        self._btn_forecast_run.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_forecast_run.setEnabled(False)
        self._btn_forecast_run.clicked.connect(self._on_forecast_run)
        self._btn_forecast_chart = QPushButton("予測グラフ")
        self._btn_forecast_chart.setObjectName("secondaryButton")
        self._btn_forecast_chart.setIcon(chart_icon)
        self._btn_forecast_chart.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_forecast_chart.setEnabled(False)
        self._btn_forecast_chart.clicked.connect(self._on_forecast_chart)
        self._btn_forecast_excel = QPushButton("予測を Excel 出力")
        self._btn_forecast_excel.setObjectName("secondaryButton")
        self._btn_forecast_excel.setIcon(excel_icon)
        self._btn_forecast_excel.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_forecast_excel.setEnabled(False)
        self._btn_forecast_excel.clicked.connect(self._on_forecast_excel)
        fc_row.addWidget(self._btn_forecast_run)
        fc_row.addWidget(self._btn_forecast_chart)
        fc_row.addWidget(self._btn_forecast_excel)
        fc_row.addStretch()

        self._forecast_note = QTextEdit()
        self._forecast_note.setReadOnly(True)
        self._forecast_note.setMaximumHeight(110)
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
        actual_bar.addWidget(btn_chart)
        actual_bar.addWidget(btn_excel)
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
        self._on_aggregate_mode_changed()
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

    @staticmethod
    def _has_customer_value(text: str) -> bool:
        s = (text or "").strip()
        return s not in ("", "（すべて）")

    @staticmethod
    def _has_product_value(text: str) -> bool:
        return bool((text or "").strip())

    def _clear_combo_text(self, combo) -> None:
        le = combo.lineEdit()
        le.blockSignals(True)
        le.clear()
        le.blockSignals(False)
        combo.setCurrentIndex(-1)

    @staticmethod
    def _format_customer_choice(code: str, name: str) -> str:
        return f"{code}  {name}"

    def _resolve_customer_name(self, raw_text: str) -> Optional[str]:
        text = (raw_text or "").strip()
        if text in ("", "（すべて）"):
            return None
        if text in self._customer_display_to_name:
            return self._customer_display_to_name[text]
        if text in self._customer_code_to_name:
            return self._customer_code_to_name[text]
        mapped = self._customer_name_to_display.get(text)
        if mapped is not None:
            return self._customer_display_to_name.get(mapped, text)
        return text

    def _customer_display_label(self, raw_text: str) -> str:
        text = (raw_text or "").strip()
        if text in ("", "（すべて）"):
            return "全顧客"
        if text in self._customer_display_to_name:
            return text
        if text in self._customer_code_to_name:
            name = self._customer_code_to_name[text]
            return self._customer_name_to_display.get(
                name, self._format_customer_choice(text, name)
            )
        return self._customer_name_to_display.get(text, text)

    def _set_product_input_enabled(self, enabled: bool, placeholder: str) -> None:
        self._product_combo.setEnabled(enabled)
        self._product_combo.setPlaceholderText(placeholder)

    def _set_customer_input_enabled(self, enabled: bool, placeholder: str) -> None:
        self._customer_combo.setEnabled(enabled)
        self._customer_combo.setPlaceholderText(placeholder)

    def _on_aggregate_mode_changed(self) -> None:
        mode = self._current_aggregate_mode()
        if mode == delivery_service.AggregateMode.BY_CUSTOMER:
            self._set_customer_input_enabled(True, self._customer_placeholder)
            self._set_product_input_enabled(False, self._product_disabled_placeholder)
            self._clear_combo_text(self._product_combo)
            self._product_combo.set_source_items(self._all_hinbans)
            self._last_hinban_filter_customer = None
        elif mode == delivery_service.AggregateMode.BY_PRODUCT:
            self._set_customer_input_enabled(False, self._customer_disabled_placeholder)
            self._set_product_input_enabled(True, self._product_placeholder)
            self._clear_combo_text(self._customer_combo)
            self._product_combo.set_source_items(self._all_hinbans)
            self._last_hinban_filter_customer = None
        else:
            self._set_customer_input_enabled(True, self._customer_placeholder)
            self._set_product_input_enabled(True, self._product_placeholder)
            if self._has_customer_value(self._customer_combo.currentText()):
                self._on_customer_changed_for_hinban_list()
            else:
                self._product_combo.set_source_items(self._all_hinbans)
                self._last_hinban_filter_customer = None
        self._refresh_search_button_state()

    def _refresh_search_button_state(self) -> None:
        if self._search_worker is not None and self._search_worker.isRunning():
            self._btn_search.setEnabled(False)
            return

        mode = self._current_aggregate_mode()
        has_customer = self._has_customer_value(self._customer_combo.currentText())
        has_product = self._has_product_value(self._product_combo.currentText())
        has_valid_period = self._date_from.date() <= self._date_to.date()

        if mode == delivery_service.AggregateMode.BY_CUSTOMER:
            ready = has_customer
        elif mode == delivery_service.AggregateMode.BY_PRODUCT:
            ready = has_product
        else:
            ready = has_customer and has_product

        self._btn_search.setEnabled(ready and has_valid_period)

    @staticmethod
    def _sanitize_filename_part(text: str) -> str:
        trans = str.maketrans({
            "\\": "￥",
            "/": "／",
            ":": "：",
            "*": "＊",
            "?": "？",
            '"': "”",
            "<": "＜",
            ">": "＞",
            "|": "｜",
        })
        return (text or "").strip().translate(trans)

    def _default_excel_export_name(self, *, include_forecast: bool) -> str:
        mode = self._current_aggregate_mode()
        cust = self._sanitize_filename_part(
            self._resolve_customer_name(self._customer_combo.currentText()) or "全顧客"
        )
        prod = self._sanitize_filename_part(self._product_combo.currentText())

        if mode == delivery_service.AggregateMode.BY_CUSTOMER:
            subject = cust or "全顧客"
        elif mode == delivery_service.AggregateMode.BY_PRODUCT:
            subject = prod or "全品番"
        else:
            subject = "_".join(part for part in (cust, prod) if part) or "検索結果"

        suffix = "納品実績・予測データ" if include_forecast else "納品実績データ"
        return f"{subject}{suffix}.xlsx"

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
                customer_pairs = delivery_service.fetch_customer_code_name_pairs(conn)
                hinbans = delivery_service.fetch_distinct_hinban(conn)
                return customer_pairs, hinbans

            customer_pairs, hinbans = self.run_with_connection(load)
        except access_connector.OdbcDriverNotFoundError as e:
            show_critical(self, "接続エラー", str(e))
            return
        except access_connector.AccessFileUnavailableError as e:
            show_critical(self, "接続エラー", str(e))
            return
        except access_connector.AccessConnectionError as e:
            show_critical(self, "接続エラー", str(e))
            return
        except Exception as e:  # noqa: BLE001
            show_critical(self, "接続エラー", f"顧客一覧の取得に失敗しました。\n{e}")
            return
        finally:
            self._busy_overlay.hide_overlay()

        customer_items: list[str] = []
        self._customer_display_to_name = {}
        self._customer_code_to_name = {}
        self._customer_name_to_display = {}
        for code, name in customer_pairs:
            item = self._format_customer_choice(code, name)
            customer_items.append(item)
            self._customer_display_to_name[item] = name
            self._customer_code_to_name[code] = name
            self._customer_name_to_display[name] = item
        self._all_hinbans = list(hinbans)
        self._hinban_lists_ready = True
        self._last_hinban_filter_customer = None
        self._customer_combo.set_source_items(customer_items)
        self._product_combo.set_source_items(hinbans)
        self._on_aggregate_mode_changed()
        self._status.setText(
            f"顧客件数: {len(customer_items)} 件 / 品番候補: {len(hinbans)} 件を読み込みました。\n"
            f"Access: {settings.resolve_access_db_path()}"
        )

    def _on_customer_changed_for_hinban_list(self) -> None:
        """顧客が確定したタイミングで品番候補をその顧客向けに絞り込む（DB と同じ結合条件）。"""
        if not self._hinban_lists_ready:
            self._refresh_search_button_state()
            return
        if self._current_aggregate_mode() != delivery_service.AggregateMode.BY_CUSTOMER_PRODUCT:
            self._refresh_search_button_state()
            return
        cust = self._resolve_customer_name(self._customer_combo.currentText())
        if not cust:
            self._last_hinban_filter_customer = None
            self._product_combo.set_source_items(self._all_hinbans)
            self._refresh_search_button_state()
            return
        if cust == self._last_hinban_filter_customer:
            self._refresh_search_button_state()
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
            show_warning(
                self,
                "品番一覧",
                f"顧客に応じた品番の取得に失敗しました。\n{e}",
            )
            return
        finally:
            self._busy_overlay.hide_overlay()

        self._last_hinban_filter_customer = cust
        self._product_combo.set_source_items(items)
        self._refresh_search_button_state()

    def _on_search(self) -> None:
        if self._search_worker is not None and self._search_worker.isRunning():
            return

        df_from = date_utils.qdate_to_date(self._date_from.date())
        df_to = date_utils.qdate_to_date(self._date_to.date())
        if df_from > df_to:
            show_warning(self, "検索", "開始日が終了日より後になっています。")
            return

        customer = self._customer_combo.currentText().strip()
        customer = self._resolve_customer_name(customer)
        product = self._product_combo.currentText().strip() or None
        mode = self._current_aggregate_mode()
        if mode == delivery_service.AggregateMode.BY_CUSTOMER:
            product = None
        elif mode == delivery_service.AggregateMode.BY_PRODUCT:
            customer = None

        self._pending_search_period_note = (
            f"{df_from} ～ {df_to}"
        )

        self._btn_search.setEnabled(False)
        self._btn_forecast_run.setEnabled(False)
        self._btn_forecast_chart.setEnabled(False)
        self._btn_forecast_excel.setEnabled(False)
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
        self._btn_forecast_run.setEnabled(raw is not None and not raw.empty)
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
        self._btn_forecast_run.setEnabled(False)
        self._btn_forecast_chart.setEnabled(False)
        self._btn_forecast_excel.setEnabled(False)
        show_critical(self, "検索エラー", f"検索中にエラーが発生しました。\n{message}")
        self._status.setText(
            f"検索に失敗しました。\nAccess: {settings.resolve_access_db_path()}"
        )

    def _on_search_worker_thread_finished(self) -> None:
        self._busy_overlay.hide_overlay()
        self._search_worker = None
        self._refresh_search_button_state()

    def _on_export_list(self) -> None:
        df = self._model.dataframe()
        if df.empty:
            show_information(self, "Excel", "出力する一覧がありません。先に検索してください。")
            return
        default_name = self._default_excel_export_name(include_forecast=False)
        path, _ = QFileDialog.getSaveFileName(
            self, "Excel 保存", default_name, "Excel (*.xlsx)"
        )
        if not path:
            return
        if not path.lower().endswith(".xlsx"):
            path += ".xlsx"
        self._busy_overlay.show_message("Excel ファイルを書き出し中…")
        QApplication.processEvents()
        try:
            yearly = delivery_service.yearly_totals_from_raw_deliveries(self._last_raw_df)
            cust_lbl = self._customer_display_label(self._customer_combo.currentText())
            prod_lbl = self._product_combo.currentText().strip() or "全品番"
            period_lbl = self._pending_search_period_note or "—"
            export_service.export_dataframe(
                path,
                df,
                sheet_name="一覧",
                table_name="顧客別納入分析システム / 実績一覧",
                yearly_chart_df=yearly,
                chart_title="年別推移（検索結果）",
                chart_subtitle=f"顧客: {cust_lbl} / 品番: {prod_lbl} / 対象期間: {period_lbl}",
            )
            self._busy_overlay.hide_overlay()
            show_information(self, "Excel", "保存しました。")
        except export_service.ExportError as e:
            self._busy_overlay.hide_overlay()
            show_warning(self, "Excel", str(e))
        finally:
            self._busy_overlay.hide_overlay()

    def _on_chart_list(self) -> None:
        raw = self._last_raw_df
        if raw is None or raw.empty:
            show_information(self, "グラフ", "先に検索を実行してください。")
            return
        self._busy_overlay.show_message("グラフを準備中…")
        QApplication.processEvents()
        try:
            y = delivery_service.yearly_totals_from_raw_deliveries(raw)
            y = y.copy()
            y["種別"] = "実績"
            cust_lbl = self._customer_display_label(self._customer_combo.currentText())
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
            show_information(
                self, "予測", "予測計算の実行中です。完了を待ってから再度お試しください。"
            )
            return
        raw = self._last_raw_df
        if raw is None or raw.empty:
            show_information(
                self, "予測", "先に検索を実行し、明細データを取得してください。"
            )
            return
        yearly = delivery_service.yearly_totals_from_raw_deliveries(raw)
        if yearly.empty:
            show_warning(
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
        combined = combined.copy()
        for c in ("納品数", "金額"):
            if c in combined.columns:
                combined[c] = pd.to_numeric(
                    combined[c], errors="coerce"
                ).round(0)
        self._last_forecast_combined = combined
        self._last_forecast_note = note
        self._forecast_model.set_dataframe(combined.copy())
        rebalance_table_columns(self._forecast_table)
        cust_lbl = self._customer_display_label(self._customer_combo.currentText())
        prod_lbl = self._product_combo.currentText().strip() or "全品番"
        period_lbl = self._pending_search_period_note or "—"
        actual = combined[combined["種別"] == "実績"].copy()
        year_count = len(actual.index)
        if year_count > 0:
            start_year = int(actual["年"].min())
            end_year = int(actual["年"].max())
            year_range_text = f"{start_year}〜{end_year}年の実績 {year_count} 年分"
        else:
            year_range_text = "実績年データ"
        self._forecast_note.setPlainText(
            f"{note}\n"
            f"・元データ: 検索結果を年ごとに合計した {year_range_text}\n"
            f"・考え方: 直近1年ではなく、対象期間全体の増減傾向で見積もります。\n"
            f"・補足: 実績が1年分だけならその値を使い、0未満は0に補正します。\n"
            f"・検索条件: 顧客={cust_lbl} / 品番={prod_lbl} / 期間={period_lbl}"
        )
        self._btn_forecast_chart.setEnabled(True)
        self._btn_forecast_excel.setEnabled(True)

    def _on_forecast_worker_failed(self, message: str, run_gen: int) -> None:
        if run_gen != self._search_generation:
            return
        show_warning(self, "予測", f"予測の計算に失敗しました。\n{message}")

    def _on_forecast_worker_thread_finished(self) -> None:
        self._busy_overlay.hide_overlay()
        self._btn_forecast_run.setEnabled(True)
        self._forecast_worker = None

    def _on_forecast_chart(self) -> None:
        df = self._last_forecast_combined
        if df is None or df.empty:
            show_information(self, "グラフ", "先に「予測を実行」を行ってください。")
            return
        self._busy_overlay.show_message("グラフを準備中…")
        QApplication.processEvents()
        try:
            cust_lbl = self._customer_display_label(self._customer_combo.currentText())
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
            show_information(self, "Excel", "先に「予測を実行」を行ってください。")
            return
        default_name = self._default_excel_export_name(include_forecast=True)
        path, _ = QFileDialog.getSaveFileName(
            self, "Excel 保存（予測）", default_name, "Excel (*.xlsx)"
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
            cust_lbl = self._customer_display_label(self._customer_combo.currentText())
            prod_lbl = self._product_combo.currentText().strip() or "全品番"
            period_lbl = self._pending_search_period_note or "—"
            export_service.export_two_sheets(
                path,
                act,
                pred,
                meta=self._last_forecast_note,
                yearly_chart_df=df,
                chart_title="年別推移（実績と予測）",
                chart_subtitle=(
                    f"顧客: {cust_lbl} / 品番: {prod_lbl} / 対象期間: {period_lbl}\n"
                    f"{self._last_forecast_note}"
                ),
            )
            self._busy_overlay.hide_overlay()
            show_information(self, "Excel", "保存しました。")
        except export_service.ExportError as e:
            self._busy_overlay.hide_overlay()
            show_warning(self, "Excel", str(e))
        finally:
            self._busy_overlay.hide_overlay()
