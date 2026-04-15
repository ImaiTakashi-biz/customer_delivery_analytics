# -*- coding: utf-8 -*-
"""メインウィンドウ：検索・実績一覧と年次予測の横並びダッシュボード。"""

from __future__ import annotations

from typing import Any, Callable, Optional

# Qt を先に読み込み、重い依存は必要時に遅延 import する
from PySide6.QtCore import QDate, QPoint, Qt, QTimer
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap, QPolygon
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStyle,
    QStyleOptionSpinBox,
    QSpinBox,
    QSplitter,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from app.config import settings
from app.db import access_connector
from app.ui.busy_overlay import BusyOverlay
from app.ui.message_dialog import show_critical, show_information, show_warning
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


def _make_year_chart_button_icon() -> QIcon:
    """年別推移グラフ用の棒グラフアイコン。"""
    pixmap = QPixmap(16, 16)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#2563eb"))
    painter.drawRoundedRect(1, 1, 14, 14, 4, 4)

    painter.setPen(QPen(QColor("#ffffff"), 1.2))
    painter.drawLine(4, 11, 12, 11)
    painter.drawLine(4, 11, 4, 4)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#ffffff"))
    painter.drawRoundedRect(5, 8, 2, 3, 1, 1)
    painter.drawRoundedRect(8, 6, 2, 5, 1, 1)
    painter.drawRoundedRect(11, 4, 2, 7, 1, 1)
    painter.end()
    return QIcon(pixmap)


def _make_month_chart_button_icon() -> QIcon:
    """月別推移グラフ用の折れ線グラフアイコン。"""
    pixmap = QPixmap(16, 16)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#0f766e"))
    painter.drawRoundedRect(1, 1, 14, 14, 4, 4)

    painter.setPen(QPen(QColor("#ffffff"), 1.4))
    painter.drawLine(4, 11, 12, 11)
    painter.drawLine(4, 11, 4, 4)
    points = [QPoint(5, 9), QPoint(7, 7), QPoint(9, 8), QPoint(12, 5)]
    for start, end in zip(points, points[1:]):
        painter.drawLine(start, end)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#ffffff"))
    for point in points:
        painter.drawEllipse(point, 1, 1)
    painter.end()
    return QIcon(pixmap)


def _make_forecast_chart_button_icon() -> QIcon:
    """予測グラフ用の上向きトレンドアイコン。"""
    pixmap = QPixmap(16, 16)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#d97706"))
    painter.drawRoundedRect(1, 1, 14, 14, 4, 4)

    painter.setPen(QPen(QColor("#ffffff"), 1.4))
    painter.drawLine(4, 11, 12, 11)
    painter.drawLine(4, 11, 4, 4)
    points = [QPoint(5, 9), QPoint(7, 8), QPoint(9, 7), QPoint(11, 5)]
    for start, end in zip(points, points[1:]):
        painter.drawLine(start, end)
    painter.drawLine(11, 5, 11, 8)
    painter.drawLine(11, 5, 8, 5)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#ffffff"))
    for point in points[:-1]:
        painter.drawEllipse(point, 1, 1)
    painter.end()
    return QIcon(pixmap)


def _make_search_button_icon() -> QIcon:
    """検索ボタン用（虫眼鏡）。プライマリ青はテーマの QPushButton と揃える。"""
    pixmap = QPixmap(16, 16)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#2563eb"))
    painter.drawRoundedRect(1, 1, 14, 14, 4, 4)

    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.setPen(QPen(QColor("#ffffff"), 1.35))
    painter.drawEllipse(4, 4, 6, 6)
    painter.drawLine(9, 9, 12, 12)
    painter.end()
    return QIcon(pixmap)


AGGREGATE_MODE_CHOICES: tuple[tuple[str, str], ...] = (
    ("顧客別", "BY_CUSTOMER"),
    ("品番別", "BY_PRODUCT"),
    ("顧客別 + 品番別", "BY_CUSTOMER_PRODUCT"),
)
AGGREGATE_MODE_LABELS = {name: label for label, name in AGGREGATE_MODE_CHOICES}


def _new_dataframe(*args, **kwargs):
    from pandas import DataFrame

    return DataFrame(*args, **kwargs)


def _make_forecast_run_button_icon() -> QIcon:
    """予測を実行ボタン用（再生マーク）。"""
    pixmap = QPixmap(16, 16)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#2563eb"))
    painter.drawRoundedRect(1, 1, 14, 14, 4, 4)

    painter.setBrush(QColor("#ffffff"))
    painter.drawPolygon(
        QPolygon([QPoint(6, 4), QPoint(6, 12), QPoint(12, 8)])
    )
    painter.end()
    return QIcon(pixmap)


def _make_forecast_detail_button_icon() -> QIcon:
    """予測算出詳細ボタン用（リスト／説明）。セカンダリ白ボタン列と同系の青バッジ。"""
    pixmap = QPixmap(16, 16)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#2563eb"))
    painter.drawRoundedRect(1, 1, 14, 14, 4, 4)

    painter.setBrush(QColor("#ffffff"))
    painter.drawRoundedRect(4, 3, 8, 10, 1.5, 1.5)
    painter.setPen(QPen(QColor("#2563eb"), 1.0))
    painter.drawLine(6, 6, 10, 6)
    painter.drawLine(6, 8, 10, 8)
    painter.drawLine(6, 10, 9, 10)
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
            all_years = sorted(
                {int(y) for y in work["年"].dropna().tolist()}
            )
            kind_styles = {
                "実績": ("o", "-", "tab:blue"),
                "予測": ("s", "--", "tab:orange"),
                "直線延長予測": ("s", ":", "#c2410c"),
                "重み付き回帰予測": ("D", "--", "#ea580c"),
                "外部要因予測": ("^", "-.", "tab:green"),
            }

            def _plot_pair(ax, col: str, ylabel: str) -> None:
                for kind in work["種別"].dropna().unique().tolist():
                    part = work[work["種別"] == kind]
                    if part.empty:
                        continue
                    marker, linestyle, color = kind_styles.get(
                        kind, ("o", "-", "#475569")
                    )
                    ax.plot(
                        part["年"],
                        part[col],
                        marker=marker,
                        linestyle=linestyle,
                        color=color,
                        label=str(kind),
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


class ChartMonthlyDialog(QDialog):
    """月別推移グラフ。"""

    def __init__(
        self,
        parent,
        df_monthly: pd.DataFrame,
        title: str = "月別推移",
        *,
        subtitle: str = "",
    ) -> None:
        super().__init__(parent)
        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
        from matplotlib.figure import Figure
        from matplotlib.ticker import StrMethodFormatter

        self.setWindowTitle(title)
        self.setMinimumSize(860, 540)
        self.resize(960, 620)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)

        fig = Figure(figsize=(8.6, 5.6), facecolor="#ffffff")
        canvas = FigureCanvasQTAgg(fig)

        ax1 = fig.add_subplot(2, 1, 1)
        ax2 = fig.add_subplot(2, 1, 2)
        ax1.set_facecolor("#fafafa")
        ax2.set_facecolor("#fafafa")

        work = df_monthly.copy()
        if work.empty:
            ax1.text(0.5, 0.5, "表示するデータがありません", ha="center", va="center")
            ax2.text(0.5, 0.5, "表示するデータがありません", ha="center", va="center")
        else:
            labels = work["年月"].astype(str).tolist()
            positions = list(range(len(labels)))
            tick_step = max(1, len(labels) // 12)
            tick_positions = positions[::tick_step] or positions
            if positions and tick_positions[-1] != positions[-1]:
                tick_positions.append(positions[-1])
            tick_labels = [labels[idx] for idx in tick_positions]

            def _plot_month(ax, col: str, ylabel: str) -> None:
                ax.plot(
                    positions,
                    work[col],
                    marker="o",
                    linestyle="-",
                    color="tab:blue",
                    label="実績",
                )
                ax.set_ylabel(ylabel)
                ax.grid(True, alpha=0.3)
                ax.legend(loc="upper left", frameon=False, fontsize=8)
                ax.ticklabel_format(style="plain", axis="y", useOffset=False)
                ax.yaxis.set_major_formatter(StrMethodFormatter("{x:,.0f}"))
                ax.set_xticks(tick_positions)
                ax.set_xticklabels(tick_labels, rotation=45, ha="right")

            _plot_month(ax1, "納品数", "納品数（月合計）")
            _plot_month(ax2, "金額", "金額（円・月合計）")
            ax2.set_xlabel("年月")

        if subtitle:
            fig.suptitle(f"{title}\n{subtitle}", fontsize=10, color="#1f2937")
        else:
            fig.suptitle(title, fontsize=11, color="#1f2937")
        fig.tight_layout(rect=(0, 0, 1.0, 0.92))

        layout = QVBoxLayout(self)
        layout.addWidget(canvas, stretch=1)
        bbox = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        bbox.rejected.connect(self.reject)
        layout.addWidget(bbox)


class ForecastExplanationDialog(QDialog):
    """予測算出の考え方をやさしく説明するダイアログ。"""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("forecastExplanationDialog")
        self.setWindowTitle("予測算出の詳細")
        self.setMinimumSize(660, 520)
        self.resize(720, 560)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        title = QLabel("予測の見方")
        title.setObjectName("forecastExplanationTitle")
        root.addWidget(title)

        scroll = QScrollArea()
        scroll.setObjectName("forecastExplanationScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        content.setObjectName("forecastExplanationContent")
        content_lay = QVBoxLayout(content)
        content_lay.setContentsMargins(0, 0, 0, 0)
        content_lay.setSpacing(10)

        sections = [
            (
                "1. この予測がしていること",
                "検索で取り出した納品実績を年ごとに合計し、"
                "これまでの増え方・減り方から先の年の目安を出しています。"
                "難しい式を意識しなくても、"
                "『過去の流れを使って先を見ている』と考えて大丈夫です。",
            ),
            (
                "2. 3つの予測のちがい",
                "直線延長は、これまでの全体の流れをそのまま先へ伸ばす見方です。"
                "重み付き回帰は、少し前よりも最近の動きを強めに見ます。"
                "外部要因予測は、社内の実績だけでなく、"
                "景気や生産の動きを表す公的な指標も参考にします。",
            ),
            (
                "3. 表とグラフの見方",
                "3つの予測が近い数字なら、方向感はそろっていると見やすくなります。"
                "逆に数字の差が大きいときは、"
                "『まだ読み切れない要素があるかもしれない』と考えるのが自然です。"
                "まずは増えそうか、横ばいか、減りそうかを見る使い方がおすすめです。",
            ),
            (
                "4. そのままでは読み切れないこと",
                "大きな単発案件、急な値上げや値下げ、"
                "取引先の増減、新製品の開始や終了のような出来事は、"
                "過去データだけでは十分に反映できない場合があります。"
                "この予測は確定値ではなく、判断のための目安です。",
            ),
            (
                "5. おすすめの使い方",
                "まずは 3 年くらいで予測を見て、"
                "3つの予測が同じ方向を向いているか確認してください。"
                "そのあとにグラフで流れを見て、"
                "必要なら Excel 出力で社内共有するのが使いやすい流れです。",
            ),
            (
                "6. 算出の仕組み（要点）",
                "直線延長も重み付きも、基本は『年』と実績の直線（最小二乗）です。"
                "重み付きだけ、直近の年を強く反映します。"
                "\n\n"
                "外部要因は、年に加えて IIP（鉱工業生産指数）と CI（景気動向指数・一致）を使う直線モデルです。"
                "将来の指標は履歴から外挿して入れます。"
                "指標が十分にそろわない年が少ないと、外部要因の列は重み付きと同じ値になります（要約文にその旨が出ます）。"
                "\n\n"
                "納品数と金額は別々に回帰するため、グラフで二本の予測の開き方が違って見えることがあります。"
                "外部要因は全国指数ベースの参考値であり、すべての顧客・品番に当てはまるとは限りません。",
            ),
        ]

        for heading, body in sections:
            card = QFrame()
            card.setObjectName("forecastExplanationCard")
            card_lay = QVBoxLayout(card)
            card_lay.setContentsMargins(14, 12, 14, 12)
            card_lay.setSpacing(6)

            head_lb = QLabel(heading)
            head_lb.setObjectName("forecastExplanationCardTitle")

            body_lb = QLabel(body)
            body_lb.setObjectName("forecastExplanationCardBody")
            body_lb.setWordWrap(True)

            card_lay.addWidget(head_lb)
            card_lay.addWidget(body_lb)
            content_lay.addWidget(card)

        content_lay.addStretch(1)
        scroll.setWidget(content)
        root.addWidget(scroll, stretch=1)

        bbox = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close_btn = bbox.button(QDialogButtonBox.StandardButton.Close)
        if close_btn is not None:
            close_btn.setText("閉じる")
        bbox.rejected.connect(self.reject)
        root.addWidget(bbox)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(settings.WINDOW_TITLE)

        self._last_list_df = None
        self._last_raw_df: Optional[Any] = None
        self._search_worker = None
        self._forecast_worker = None
        self._last_forecast_comparison: Optional[Any] = None
        self._last_forecast_chart: Optional[Any] = None
        self._last_forecast_summary_lines: list[str] = []
        self._last_forecast_graph_note: str = ""
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
        for label, name in AGGREGATE_MODE_CHOICES:
            self._agg_combo.addItem(label, name)
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
        btn_search.setIcon(_make_search_button_icon())
        btn_search.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_search.setEnabled(False)
        btn_search.clicked.connect(self._on_search)
        chart_icon = _make_chart_button_icon()
        year_chart_icon = _make_year_chart_button_icon()
        month_chart_icon = _make_month_chart_button_icon()
        forecast_chart_icon = _make_forecast_chart_button_icon()
        btn_year_chart = QPushButton("年別推移グラフ")
        btn_year_chart.setObjectName("secondaryButton")
        btn_year_chart.setIcon(year_chart_icon)
        btn_year_chart.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_year_chart.clicked.connect(self._on_chart_list)
        btn_month_chart = QPushButton("月別推移グラフ")
        btn_month_chart.setObjectName("secondaryButton")
        btn_month_chart.setIcon(month_chart_icon)
        btn_month_chart.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_month_chart.clicked.connect(self._on_chart_monthly)

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
        self._btn_forecast_run.setIcon(_make_forecast_run_button_icon())
        self._btn_forecast_run.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_forecast_run.setEnabled(False)
        self._btn_forecast_run.clicked.connect(self._on_forecast_run)
        self._btn_forecast_chart = QPushButton("予測グラフ")
        self._btn_forecast_chart.setObjectName("secondaryButton")
        self._btn_forecast_chart.setIcon(forecast_chart_icon)
        self._btn_forecast_chart.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_forecast_chart.setEnabled(False)
        self._btn_forecast_chart.clicked.connect(self._on_forecast_chart)
        self._btn_forecast_excel = QPushButton("予測を Excel 出力")
        self._btn_forecast_excel.setObjectName("secondaryButton")
        self._btn_forecast_excel.setIcon(_make_excel_button_icon())
        self._btn_forecast_excel.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_forecast_excel.setEnabled(False)
        self._btn_forecast_excel.clicked.connect(self._on_forecast_excel)
        fc_row.addWidget(self._btn_forecast_run)
        fc_row.addWidget(self._btn_forecast_chart)
        fc_row.addWidget(self._btn_forecast_excel)
        fc_row.addStretch()

        self._forecast_note = QLabel(
            "・直線延長: 合計実績を最小二乗で延長\n"
            "・重み付き回帰: 直近年を強めに反映\n"
            "・外部要因予測: IIP=鉱工業生産指数 / CI=景気動向指数"
        )
        self._forecast_note.setWordWrap(True)
        self._forecast_note.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        )
        self._forecast_note.setMaximumHeight(88)
        self._forecast_note.setMinimumHeight(76)
        self._forecast_note.setObjectName("forecastNoteBox")

        note_cap = QLabel("算出の説明")
        note_cap.setObjectName("formSectionCaption")
        self._btn_forecast_detail = QPushButton("予測算出詳細")
        self._btn_forecast_detail.setObjectName("secondaryButton")
        self._btn_forecast_detail.setIcon(_make_forecast_detail_button_icon())
        self._btn_forecast_detail.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_forecast_detail.setToolTip("予測の考え方を詳しく表示します。")
        self._btn_forecast_detail.clicked.connect(self._on_open_forecast_details)
        note_head = QHBoxLayout()
        note_head.setContentsMargins(0, 0, 0, 0)
        note_head.setSpacing(8)
        note_head.addWidget(note_cap)
        note_head.addStretch(1)
        note_head.addWidget(self._btn_forecast_detail)

        self._forecast_model = DataFrameTableModel()
        self._forecast_table = QTableView()
        self._forecast_table.setModel(self._forecast_model)
        configure_web_table_view(self._forecast_table)
        self._forecast_table.horizontalHeader().setDefaultAlignment(
            Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter
        )
        self._forecast_table.horizontalHeader().setFixedHeight(44)
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
            "検索で絞り込んだ集計結果です。下のボタンから年別推移グラフと月別推移グラフが利用できます。"
        )
        ls.setObjectName("panelSectionSubtitle")
        ls.setWordWrap(True)
        actual_bar = QHBoxLayout()
        actual_bar.setSpacing(8)
        actual_bar.setContentsMargins(0, 0, 0, 0)
        actual_bar.addWidget(btn_year_chart)
        actual_bar.addWidget(btn_month_chart)
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
            "実績・直線延長・重み付き回帰・外部要因予測を、1年1行で比較表示します。先に検索で明細を取得してから「予測を実行」してください。"
        )
        rs.setObjectName("panelSectionSubtitle")
        rs.setWordWrap(True)
        right_lay.addWidget(rt)
        right_lay.addWidget(rs)
        right_lay.addLayout(fc_row)
        right_lay.addLayout(note_head)
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

    def _current_aggregate_mode(self) -> str:
        """集計単位コンボから AggregateMode を取得（Qt の userData 変換差異を吸収）。"""
        key = self._agg_combo.currentData()
        if isinstance(key, str) and key in AGGREGATE_MODE_LABELS:
            return key
        return str(key or "BY_CUSTOMER")

    @staticmethod
    def _aggregate_mode_label(mode_name: str) -> str:
        return AGGREGATE_MODE_LABELS.get(mode_name, mode_name)

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
        if mode == "BY_CUSTOMER":
            self._set_customer_input_enabled(True, self._customer_placeholder)
            self._set_product_input_enabled(False, self._product_disabled_placeholder)
            self._clear_combo_text(self._product_combo)
            self._product_combo.set_source_items(self._all_hinbans)
            self._last_hinban_filter_customer = None
        elif mode == "BY_PRODUCT":
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

        if mode == "BY_CUSTOMER":
            ready = has_customer
        elif mode == "BY_PRODUCT":
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

        if mode == "BY_CUSTOMER":
            subject = cust or "全顧客"
        elif mode == "BY_PRODUCT":
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
        from app.service import delivery_service
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
        from app.service import delivery_service
        """顧客が確定したタイミングで品番候補をその顧客向けに絞り込む（DB と同じ結合条件）。"""
        if not self._hinban_lists_ready:
            self._refresh_search_button_state()
            return
        if self._current_aggregate_mode() != "BY_CUSTOMER_PRODUCT":
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
        from app.service import delivery_service
        from app.ui.search_worker import DeliverySearchWorker

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
        if mode == "BY_CUSTOMER":
            product = None
        elif mode == "BY_PRODUCT":
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
            mode,
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
        mode_label = self._aggregate_mode_label(mode_name)
        self._search_generation += 1
        self._last_forecast_comparison = None
        self._last_forecast_chart = None
        self._last_forecast_summary_lines = []
        self._last_forecast_graph_note = ""
        self._forecast_model.set_dataframe(_new_dataframe())
        self._forecast_note.setText(
            "・直線延長: 合計実績を最小二乗で延長\n"
            "・重み付き回帰: 直近年を強めに反映\n"
            "・外部要因予測: IIP=鉱工業生産指数 / CI=景気動向指数"
        )
        self._btn_forecast_run.setEnabled(raw is not None and not raw.empty)
        self._btn_forecast_chart.setEnabled(False)
        self._btn_forecast_excel.setEnabled(False)

        self._last_raw_df = raw
        self._last_list_df = agg
        self._model.set_dataframe(agg)
        self._status.setText(
            f"取得明細: {len(raw)} 行 / 表示行: {len(agg)} 行（集計単位: {mode_label}）\n"
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
        from app.service import delivery_service, export_service

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
        from app.service import delivery_service

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

    def _on_chart_monthly(self) -> None:
        from app.service import delivery_service

        raw = self._last_raw_df
        if raw is None or raw.empty:
            show_information(self, "グラフ", "先に検索を実行してください。")
            return
        self._busy_overlay.show_message("グラフを準備中…")
        QApplication.processEvents()
        try:
            monthly = delivery_service.monthly_totals_from_raw_deliveries(raw)
            cust_lbl = self._customer_display_label(self._customer_combo.currentText())
            prod_lbl = self._product_combo.currentText().strip() or "全品番"
            period_lbl = self._pending_search_period_note or "—"
            sub = f"顧客: {cust_lbl}  /  品番: {prod_lbl}  /  対象期間: {period_lbl}"
            dlg = ChartMonthlyDialog(
                self, monthly, title="月別推移（検索結果）", subtitle=sub
            )
            dlg.show()
        finally:
            self._busy_overlay.hide_overlay()

    def _on_forecast_run(self) -> None:
        from app.service import delivery_service
        from app.ui.search_worker import YearlyForecastFromRawWorker
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
            "検索明細を年次集計し、3つの予測モデルを算出しています。"
        )
        QApplication.processEvents()

        worker = YearlyForecastFromRawWorker(raw, n_years, parent=self)
        self._forecast_worker = worker
        worker.forecast_done.connect(lambda payload: self._on_forecast_worker_done(payload, run_gen))
        worker.forecast_failed.connect(
            lambda msg: self._on_forecast_worker_failed(msg, run_gen)
        )
        worker.finished.connect(self._on_forecast_worker_thread_finished)
        worker.start()

    def _on_forecast_worker_done(self, payload: dict, run_gen: int) -> None:
        if run_gen != self._search_generation:
            return
        comparison_df = payload.get("comparison_df", _new_dataframe()).copy()
        chart_df = payload.get("chart_df", _new_dataframe()).copy()
        summary_lines = list(payload.get("summary_lines", []))
        graph_note = str(payload.get("graph_note", "") or "")
        status_summary = str(payload.get("status_summary", "") or "")

        self._last_forecast_comparison = comparison_df
        self._last_forecast_chart = chart_df
        self._last_forecast_summary_lines = summary_lines
        self._last_forecast_graph_note = graph_note
        self._forecast_model.set_dataframe(comparison_df)
        rebalance_table_columns(self._forecast_table)
        note_lines = summary_lines[:4]
        if status_summary and len(note_lines) < 4:
            note_lines.append(f"外部指標: {status_summary}")
        self._forecast_note.setText("\n".join(f"・{line}" for line in note_lines[:4]))
        self._forecast_note.setToolTip("\n".join(f"・{line}" for line in summary_lines))
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

    def _forecast_chart_subtitle(self) -> str:
        cust_lbl = self._customer_display_label(self._customer_combo.currentText())
        prod_lbl = self._product_combo.currentText().strip() or "全品番"
        period_lbl = self._pending_search_period_note or "—"
        base = f"顧客: {cust_lbl}  /  品番: {prod_lbl}  /  対象期間: {period_lbl}"
        return f"{base}\n{self._last_forecast_graph_note}" if self._last_forecast_graph_note else base

    def _on_open_forecast_details(self) -> None:
        dlg = ForecastExplanationDialog(self)
        dlg.exec()

    def _on_forecast_chart(self) -> None:
        df = self._last_forecast_chart
        if df is None or df.empty:
            show_information(self, "グラフ", "先に「予測を実行」を行ってください。")
            return
        self._busy_overlay.show_message("グラフを準備中…")
        QApplication.processEvents()
        try:
            dlg = ChartYearlyDialog(
                self,
                df,
                title="年別推移（実績・直線延長・重み付き回帰・外部要因）",
                subtitle=self._forecast_chart_subtitle(),
            )
            dlg.show()
        finally:
            self._busy_overlay.hide_overlay()

    def _on_forecast_excel(self) -> None:
        from app.service import export_service

        df = self._last_forecast_comparison
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
            export_service.export_forecast_workbook(
                path,
                df,
                meta_lines=self._last_forecast_summary_lines,
                chart_subtitle=self._forecast_chart_subtitle(),
            )
            self._busy_overlay.hide_overlay()
            show_information(self, "Excel", "保存しました。")
        except export_service.ExportError as e:
            self._busy_overlay.hide_overlay()
            show_warning(self, "Excel", str(e))
        finally:
            self._busy_overlay.hide_overlay()
