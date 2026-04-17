# -*- coding: utf-8 -*-
"""Tkinter implementation for the customer delivery analytics app."""

from __future__ import annotations

import sys
from pathlib import Path
import threading
from datetime import date, datetime
from typing import Any, Callable, Optional

if __package__ in {None, ""}:
    _project_root = Path(__file__).resolve().parent.parent
    _root_str = str(_project_root)
    if _root_str not in sys.path:
        sys.path.insert(0, _root_str)

import matplotlib

matplotlib.use("TkAgg")

import pandas as pd
import tkinter as tk
import tkinter.font as tkfont
from tkinter import filedialog, messagebox, ttk
from tkcalendar import Calendar

import matplotlib as mpl
import matplotlib.dates as mdates
import matplotlib.font_manager as mpl_font_manager
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from matplotlib.ticker import StrMethodFormatter

from app.config import settings
from app.db import access_connector
from app.service import delivery_service, export_service, forecast_service


APP_BG = "#eef3f9"
CARD_BG = "#ffffff"
CARD_ALT_BG = "#f7fafc"
BORDER = "#d9e2ec"
TEXT = "#0f172a"
MUTED = "#64748b"
PRIMARY = "#2563eb"
PRIMARY_DARK = "#1d4ed8"
PRIMARY_LIGHT = "#dbeafe"
ACCENT_GREEN = "#0f766e"
ACCENT_SKY = "#0284c7"
ALL_LABEL = "（すべて）"

AGGREGATE_OPTIONS: list[tuple[str, str]] = [
    ("顧客別", delivery_service.AggregateMode.BY_CUSTOMER.name),
    ("顧客×品番別", delivery_service.AggregateMode.BY_CUSTOMER_PRODUCT.name),
]
AGGREGATE_LABEL_TO_MODE = {label: mode for label, mode in AGGREGATE_OPTIONS}
AGGREGATE_MODE_TO_LABEL = {mode: label for label, mode in AGGREGATE_OPTIONS}

MATPLOTLIB_FONT_CANDIDATES = [
    "Meiryo",
    "Yu Gothic",
    "MS Gothic",
    "Noto Sans JP",
    "DejaVu Sans",
]

UI_FONT_CANDIDATES = [
    "Yu Gothic UI",
    "Yu Gothic",
    "Meiryo",
    "MS Gothic",
    "DejaVu Sans",
]


def _pick_ui_font_family(widget: tk.Misc) -> str:
    try:
        families = set(widget.winfo_toplevel().tk.call("font", "families"))
    except Exception:
        families = set()
    for family in UI_FONT_CANDIDATES:
        if family in families:
            return family
    return "TkDefaultFont"


def _ui_font(widget: tk.Misc, size: int, *, weight: str = "normal") -> tkfont.Font:
    return tkfont.Font(root=widget, family=_pick_ui_font_family(widget), size=size, weight=weight)


def _pick_matplotlib_font_family() -> str:
    available = {font.name for font in mpl_font_manager.fontManager.ttflist}
    for family in MATPLOTLIB_FONT_CANDIDATES:
        if family in available:
            return family
    return "DejaVu Sans"


def _default_date_range() -> tuple[date, date]:
    start = date(settings.DEFAULT_YEAR_START, 1, 1)
    today = date.today()
    end = date(today.year - 1, 12, 31)
    return start, end


def _format_date(d: Optional[date]) -> str:
    return "" if d is None else d.strftime("%Y/%m/%d")


def _parse_date(text: str) -> Optional[date]:
    raw = (text or "").strip()
    if not raw:
        return None
    for fmt in ("%Y/%m/%d", "%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            pass
    return None


def _center_toplevel(win: tk.Toplevel, parent: tk.Misc | None = None) -> None:
    win.update_idletasks()
    if parent is not None:
        x = parent.winfo_rootx() + max(0, (parent.winfo_width() - win.winfo_width()) // 2)
        y = parent.winfo_rooty() + max(0, (parent.winfo_height() - win.winfo_height()) // 2)
    else:
        x = max(0, (win.winfo_screenwidth() - win.winfo_width()) // 2)
        y = max(0, (win.winfo_screenheight() - win.winfo_height()) // 2)
    win.geometry(f"+{x}+{y}")


def _mousewheel_units(event: tk.Event) -> int:
    num = getattr(event, "num", None)
    if num == 4:
        return 1
    if num == 5:
        return -1
    delta = int(getattr(event, "delta", 0) or 0)
    if delta == 0:
        return 0
    if sys.platform == "darwin":
        return delta
    return int(delta / 120)


def _bind_vertical_mousewheel(widget: tk.Misc, on_scroll: Callable[[int], None]) -> None:
    def _handler(event: tk.Event) -> str:
        units = _mousewheel_units(event)
        if units:
            on_scroll(units)
        return "break"

    widget.bind("<MouseWheel>", _handler, add="+")
    widget.bind("<Button-4>", _handler, add="+")
    widget.bind("<Button-5>", _handler, add="+")


def _bind_vertical_mousewheel_tree(widget: tk.Misc) -> None:
    _bind_vertical_mousewheel(widget, lambda units: widget.yview_scroll(-units, "units"))


def _bind_vertical_mousewheel_canvas(widget: tk.Misc) -> None:
    _bind_vertical_mousewheel(widget, lambda units: widget.yview_scroll(-units, "units"))


def _bind_vertical_mousewheel_recursive(widget: tk.Misc, on_scroll: Callable[[int], None]) -> None:
    _bind_vertical_mousewheel(widget, on_scroll)
    for child in widget.winfo_children():
        _bind_vertical_mousewheel_recursive(child, on_scroll)


class DateField(ttk.Frame):
    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent)
        self._var = tk.StringVar(value="")
        self._entry = ttk.Entry(self, textvariable=self._var, width=12)
        self._entry.grid(row=0, column=0, sticky="ew")
        self._button = ttk.Button(self, text="📅", width=3, command=self._open_picker)
        self._button.grid(row=0, column=1, padx=(6, 0))
        self.grid_columnconfigure(0, weight=1)
        self._entry.bind("<FocusOut>", lambda _e: self._normalize())
        self._entry.bind("<Return>", lambda _e: self._normalize())

    def get(self) -> Optional[date]:
        return _parse_date(self._var.get())

    def set(self, value: Optional[date]) -> None:
        self._var.set(_format_date(value))

    def get_text(self) -> str:
        return self._var.get().strip()

    def clear(self) -> None:
        self._var.set("")

    def set_enabled(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        self._entry.configure(state=state)
        self._button.configure(state=state)

    def _normalize(self) -> None:
        parsed = _parse_date(self._var.get())
        if parsed is not None:
            self._var.set(_format_date(parsed))

    def _open_picker(self) -> None:
        cur = self.get() or date.today()
        dlg = DatePickerDialog(self, cur)
        self.wait_window(dlg)
        if dlg.cleared():
            self.clear()
        elif dlg.result() is not None:
            self.set(dlg.result())


class DatePickerDialog(tk.Toplevel):
    def __init__(self, parent: tk.Misc, initial: date) -> None:
        super().__init__(parent)
        self.title("日付を選択")
        self.configure(bg=APP_BG)
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self._result: Optional[date] = None
        self._cleared = False

        card = tk.Frame(self, bg="#f8fbff", highlightbackground="#cbd5e1", highlightthickness=1)
        card.pack(fill="both", expand=True, padx=14, pady=14)
        tk.Frame(card, bg=PRIMARY, height=6).pack(fill="x")
        tk.Label(card, text="日付を選択", bg="#f8fbff", fg=TEXT, font=_ui_font(parent, 13, weight="bold")).pack(
            anchor="w", padx=18, pady=(14, 8)
        )

        self._calendar = Calendar(
            card,
            selectmode="day",
            year=initial.year,
            month=initial.month,
            day=initial.day,
            date_pattern="y-mm-dd",
            showweeknumbers=False,
        )
        self._calendar.pack(padx=18, pady=(0, 10))
        self._calendar.selection_set(initial)

        self._hint = tk.StringVar(value="クリックして日付を選択できます。")
        tk.Label(card, textvariable=self._hint, bg="#f8fbff", fg="#475569", anchor="w", justify="left").pack(
            fill="x", padx=18, pady=(0, 10)
        )

        btns = tk.Frame(card, bg="#f8fbff")
        btns.pack(fill="x", padx=18, pady=(0, 14))
        ttk.Button(btns, text="今日", command=self._today).pack(side="left")
        ttk.Button(btns, text="クリア", command=self._clear).pack(side="left", padx=(8, 0))
        ttk.Button(btns, text="キャンセル", command=self._cancel).pack(side="right")
        ttk.Button(btns, text="OK", command=self._accept).pack(side="right", padx=(0, 8))

        self.protocol("WM_DELETE_WINDOW", self._cancel)
        _center_toplevel(self, parent)

    def _today(self) -> None:
        today = date.today()
        self._calendar.selection_set(today)

    def _clear(self) -> None:
        self._result = None
        self._cleared = True
        self.destroy()

    def _accept(self) -> None:
        try:
            selected = self._calendar.selection_get()
            if hasattr(selected, "date"):
                selected = selected.date()
            self._result = selected
        except ValueError:
            messagebox.showwarning("日付", "有効な日付を入力してください。", parent=self)
            return
        self.destroy()

    def _cancel(self) -> None:
        self._result = None
        self.destroy()

    def result(self) -> Optional[date]:
        return self._result

    def cleared(self) -> bool:
        return self._cleared


class SearchableCombo(ttk.Frame):
    def __init__(self, parent: tk.Misc, *, include_all: bool = False, width: int = 34) -> None:
        super().__init__(parent)
        self._include_all = include_all
        self._source_items: list[str] = []
        self._var = tk.StringVar(value="")
        self._combo = ttk.Combobox(self, textvariable=self._var, state="normal", width=width)
        self._combo.grid(row=0, column=0, sticky="ew")
        self.grid_columnconfigure(0, weight=1)
        self._combo.bind("<KeyRelease>", lambda _e: self._refresh())
        self._combo.configure(postcommand=self._refresh)

    def widget(self) -> ttk.Combobox:
        return self._combo

    def get(self) -> str:
        return self._var.get().strip()

    def set(self, value: str) -> None:
        self._var.set(value)
        self._refresh()

    def clear(self) -> None:
        self._var.set("")
        self._refresh()

    def set_enabled(self, enabled: bool) -> None:
        self._combo.configure(state="normal" if enabled else "disabled")

    def set_items(self, items: list[str]) -> None:
        seen: set[str] = set()
        ordered: list[str] = []
        for item in items:
            value = str(item).strip()
            if not value or value in seen:
                continue
            seen.add(value)
            ordered.append(value)
        self._source_items = ordered
        self._refresh()

    def _refresh(self) -> None:
        text = self._var.get().strip().lower()
        values: list[str] = []
        if self._include_all and (not text or ALL_LABEL.lower().find(text) >= 0):
            values.append(ALL_LABEL)
        for item in self._source_items:
            if not text or text in item.lower():
                values.append(item)
        self._combo["values"] = values


class DataFrameTable(ttk.Frame):
    def __init__(self, parent: tk.Misc, *, height: int = 18) -> None:
        super().__init__(parent)
        self._style = ttk.Style()
        self._tree_style = f"Cda.Treeview.{id(self)}"
        self._heading_style = f"{self._tree_style}.Heading"
        self._heading_family = tkfont.nametofont("TkHeadingFont").cget("family")
        self._heading_font = tkfont.Font(root=self, family=self._heading_family, size=11, weight="bold")
        self._tree = ttk.Treeview(self, show="headings", height=height)
        self._yscroll = ttk.Scrollbar(self, orient="vertical", command=self._tree.yview)
        self._xscroll = ttk.Scrollbar(self, orient="horizontal", command=self._tree.xview)
        self._tree.configure(yscrollcommand=self._yscroll.set, xscrollcommand=self._xscroll.set)
        self._tree.grid(row=0, column=0, sticky="nsew")
        self._yscroll.grid(row=0, column=1, sticky="ns")
        self._xscroll.grid(row=1, column=0, sticky="ew")
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self._df = pd.DataFrame()
        base_tree_layout = self._style.layout("Treeview")
        base_heading_layout = self._style.layout("Treeview.Heading")
        if base_tree_layout:
            self._style.layout(self._tree_style, base_tree_layout)
        if base_heading_layout:
            self._style.layout(self._heading_style, base_heading_layout)
        self._style.configure(self._tree_style, background="white", fieldbackground="white", rowheight=30, borderwidth=0)
        self._style.configure(
            self._heading_style,
            background="#eff6ff",
            foreground=TEXT,
            font=self._heading_font,
            padding=(8, 8),
        )
        self._style.map(self._tree_style, background=[("selected", PRIMARY_LIGHT)])
        self._tree.configure(style=self._tree_style)

    def _configure_heading_style(self, labels: list[str], compact_headers: bool) -> None:
        if not labels:
            return
        longest = 0
        lines = 1
        for label in labels:
            parts = str(label).split("\n")
            lines = max(lines, len(parts))
            longest = max(longest, max((len(part) for part in parts), default=0))

        if compact_headers:
            if longest >= 14:
                size = 7
            elif longest >= 11:
                size = 8
            elif longest >= 8:
                size = 9
            else:
                size = 10
            padding = (8, 18 if lines >= 2 else 12)
        else:
            if longest >= 16:
                size = 9
            elif longest >= 12:
                size = 10
            else:
                size = 11
            padding = (8, 10 if lines <= 1 else 14)

        self._heading_font.configure(family=self._heading_family, size=size, weight="bold")
        self._style.configure(self._heading_style, font=self._heading_font, padding=padding)
        self._tree.configure(style=self._tree_style)

    def set_dataframe(
        self,
        df: Optional[pd.DataFrame],
        *,
        display_columns: Optional[dict[str, str]] = None,
        compact_headers: bool = False,
    ) -> None:
        work = df.copy() if df is not None else pd.DataFrame()
        self._df = work
        self._tree.delete(*self._tree.get_children())
        cols = [str(c) for c in work.columns]
        self._tree["columns"] = cols
        labels = [(display_columns or {}).get(col, col) for col in cols]
        self._configure_heading_style(labels, compact_headers)
        for col, label in zip(cols, labels):
            anchor = "center" if col in {"年", "月", "種別"} else "e" if ("数" in col or "額" in col) else "w"
            lines = str(label).split("\n")
            max_line = max(len(part) for part in lines) if lines else len(str(label))
            if compact_headers:
                width = max(72, min(180, max_line * 11 + 28))
                if len(lines) >= 2:
                    width += 10
            else:
                width = max(90, min(220, max_line * 12 + 24))
            if col in {"顧客", "品番", "種別"}:
                width = max(width, 120)
            if col in {"年", "月"}:
                width = max(width, 56 if compact_headers else 72)
            if "納品数" in col or "金額" in col:
                width = max(width, 82 if compact_headers else 130)
            self._tree.heading(col, text=label, anchor="center")
            minwidth = 44 if compact_headers else 60
            self._tree.column(col, width=width, minwidth=minwidth, stretch=False, anchor=anchor)
        if work.empty:
            if cols:
                values = ["該当データがありません"] + [""] * (len(cols) - 1)
                self._tree.insert("", "end", values=values)
            return
        for idx, (_, row) in enumerate(work.iterrows()):
            self._tree.insert("", "end", values=[self._fmt_value(row[col]) for col in work.columns], tags=("odd",) if idx % 2 else ("even",))
        self._tree.tag_configure("even", background="white")
        self._tree.tag_configure("odd", background="#f8fafc")
        _bind_vertical_mousewheel_tree(self._tree)

    def dataframe(self) -> pd.DataFrame:
        return self._df

    @staticmethod
    def _fmt_value(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, (pd.Timestamp, datetime)):
            return value.strftime("%Y/%m/%d")
        if isinstance(value, float) and pd.isna(value):
            return ""
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            n = float(value)
            if abs(n - round(n)) < 1e-9:
                return f"{int(round(n)):,}"
            return f"{n:,.2f}".rstrip("0").rstrip(".")
        return str(value)


class ChartDialog(tk.Toplevel):
    def __init__(self, parent: tk.Misc, title: str, figure: Figure) -> None:
        super().__init__(parent)
        self.title(title)
        self.configure(bg=APP_BG)
        self.geometry("1020x700")
        self.transient(parent)
        self.grab_set()
        card = tk.Frame(self, bg=CARD_BG, highlightbackground=BORDER, highlightthickness=1)
        card.pack(fill="both", expand=True, padx=14, pady=14)
        tk.Frame(card, bg=PRIMARY, height=4).pack(fill="x")
        header = tk.Frame(card, bg=CARD_BG)
        header.pack(fill="x", padx=18, pady=(14, 0))
        tk.Label(header, text=title, bg=CARD_BG, fg=TEXT, font=tkfont.nametofont("TkHeadingFont")).pack(side="left")
        ttk.Button(header, text="閉じる", command=self.destroy, style="Secondary.TButton").pack(side="right")
        canvas = FigureCanvasTkAgg(figure, master=card)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True, padx=12, pady=12)
        _center_toplevel(self, parent)


class BusyDialog(tk.Toplevel):
    def __init__(self, parent: tk.Misc, message: str) -> None:
        super().__init__(parent)
        self.title("処理中")
        self.configure(bg="#eaf2ff")
        self.resizable(False, False)
        self.transient(parent)
        self.attributes("-topmost", True)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", lambda: None)

        self.geometry("380x190")

        card = tk.Frame(self, bg=CARD_BG, highlightbackground="#cbd5e1", highlightthickness=1)
        card.pack(fill="both", expand=True, padx=14, pady=14)

        accent = tk.Frame(card, bg=PRIMARY, height=6)
        accent.pack(fill="x")

        tk.Label(
            card,
            text="読み込み中",
            bg=CARD_BG,
            fg=TEXT,
            font=_ui_font(parent, 14, weight="bold"),
        ).pack(anchor="w", padx=20, pady=(18, 4))

        self._message_var = tk.StringVar(value=message)
        tk.Label(
            card,
            textvariable=self._message_var,
            bg=CARD_BG,
            fg="#475569",
            justify="left",
            anchor="w",
            wraplength=300,
            font=_ui_font(parent, 10),
        ).pack(fill="x", padx=20, pady=(0, 16))

        style = ttk.Style(self)
        try:
            style.configure("Busy.Horizontal.TProgressbar", troughcolor="#dbeafe", background=PRIMARY, thickness=12)
        except tk.TclError:
            pass
        self._bar = ttk.Progressbar(card, mode="indeterminate", length=300, style="Busy.Horizontal.TProgressbar")
        self._bar.pack(fill="x", padx=20, pady=(0, 20))
        self._bar.start(10)

        self.update_idletasks()
        _center_toplevel(self, parent)
        self.lift()

    def update_message(self, message: str) -> None:
        self._message_var.set(message)

    def close(self) -> None:
        try:
            self._bar.stop()
        except tk.TclError:
            pass
        try:
            self.grab_release()
        except tk.TclError:
            pass
        self.destroy()


class ForecastExplanationDialog(tk.Toplevel):
    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent)
        self.title("予測算出の詳細")
        self.configure(bg=APP_BG)
        self.geometry("760x560")
        self.minsize(680, 480)
        self.transient(parent)
        self.grab_set()
        card = tk.Frame(self, bg=CARD_BG, highlightbackground=BORDER, highlightthickness=1)
        card.pack(fill="both", expand=True, padx=14, pady=14)
        tk.Frame(card, bg=ACCENT_SKY, height=4).pack(fill="x")

        header = tk.Frame(card, bg=CARD_BG)
        header.pack(fill="x", padx=18, pady=(14, 6))
        tk.Label(header, text="予測の見方", bg=CARD_BG, fg=TEXT, font=tkfont.nametofont("TkHeadingFont")).pack(side="left")
        ttk.Button(header, text="閉じる", command=self.destroy, style="Secondary.TButton").pack(side="right")

        subtitle = tk.Label(
            card,
            text="検索で取得した明細から年次集計を作り、3種類の予測を比較します。",
            bg=CARD_BG,
            fg="#475569",
            justify="left",
            anchor="w",
            wraplength=680,
        )
        subtitle.pack(fill="x", padx=18, pady=(0, 10))

        body_frame = tk.Frame(card, bg=CARD_BG)
        body_frame.pack(fill="both", expand=True, padx=18, pady=(0, 14))
        body_frame.grid_rowconfigure(0, weight=1)
        body_frame.grid_columnconfigure(0, weight=1)

        canvas = tk.Canvas(body_frame, bg=CARD_BG, highlightthickness=0, bd=0)
        scroll = ttk.Scrollbar(body_frame, orient="vertical", command=canvas.yview)
        content = tk.Frame(canvas, bg=CARD_BG)
        content.bind(
            "<Configure>",
            lambda _e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        window = canvas.create_window((0, 0), window=content, anchor="nw")

        def _resize_canvas(_e: tk.Event) -> None:
            canvas.itemconfigure(window, width=_e.width)

        canvas.bind("<Configure>", _resize_canvas)
        canvas.configure(yscrollcommand=scroll.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")

        sections = [
            (
                "1. この予測がしていること",
                "検索で取り出した納品実績を年ごとに合計し、これまでの増え方・減り方から先の年の目安を出しています。"
                "難しい式を意識しなくても、『過去の流れを使って先を見ている』と考えて大丈夫です。",
            ),
            (
                "2. 3つの予測のちがい",
                "直線延長は、これまでの全体の流れをそのまま先へ伸ばす見方です。"
                "重み付き回帰は、少し前よりも最近の動きを強めに見ます。"
                "外部要因予測は、社内の実績だけでなく、景気や生産の動きを表す公的な指標も参考にします。",
            ),
            (
                "3. 表とグラフの見方",
                "3つの予測が近い数字なら、方向感はそろっていると見やすくなります。"
                "逆に数字の差が大きいときは、『まだ読み切れない要素があるかもしれない』と考えるのが自然です。"
                "まずは増えそうか、横ばいか、減りそうかを見る使い方がおすすめです。",
            ),
            (
                "4. そのままでは読み切れないこと",
                "大きな単発案件、急な値上げや値下げ、取引先の増減、新製品の開始や終了のような出来事は、"
                "過去データだけでは十分に反映できない場合があります。"
                "この予測は確定値ではなく、判断のための目安です。",
            ),
            (
                "5. おすすめの使い方",
                "まずは 3 年くらいで予測を見て、3つの予測が同じ方向を向いているか確認してください。"
                "そのあとにグラフで流れを見て、必要なら Excel 出力で社内共有するのが使いやすい流れです。",
            ),
            (
                "6. 算出の仕組み（要点）",
                "直線延長も重み付きも、基本は『年』と実績の直線（最小二乗）です。"
                "重み付きだけ、直近の年を強く反映します。\n\n"
                "外部要因は、年に加えて IIP（鉱工業生産指数）と CI（景気動向指数・一致）を使う直線モデルです。"
                "将来の指標は履歴から外挿して入れます。"
                "指標が十分にそろわない年が少ないと、外部要因の列は重み付きと同じ値になります。\n\n"
                "納品数と金額は別々に回帰するため、グラフで二本の予測の開き方が違って見えることがあります。"
                "外部要因は全国指数ベースの参考値であり、すべての顧客・品番に当てはまるとは限りません。",
            ),
        ]

        for heading, body in sections:
            section = tk.Frame(content, bg="#f8fbff", highlightbackground="#dbe7f2", highlightthickness=1)
            section.pack(fill="x", pady=(0, 10))
            tk.Label(
                section,
                text=heading,
                bg="#f8fbff",
                fg=TEXT,
                font=_ui_font(self, 11, weight="bold"),
                anchor="w",
                justify="left",
            ).pack(fill="x", padx=14, pady=(12, 4))
            tk.Label(
                section,
                text=body,
                bg="#f8fbff",
                fg="#334155",
                wraplength=650,
                justify="left",
                anchor="w",
            ).pack(fill="x", padx=14, pady=(0, 12))
        _bind_vertical_mousewheel_canvas(canvas)
        _bind_vertical_mousewheel_recursive(content, lambda units: canvas.yview_scroll(-units, "units"))
        _center_toplevel(self, parent)


class DeliveryAnalyticsApp:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title(settings.WINDOW_TITLE)
        self.root.configure(bg=APP_BG)
        self._apply_theme()
        self._set_icon()
        self._try_maximize()

        self._open_windows: list[tk.Toplevel] = []
        self._busy_dialog: BusyDialog | None = None
        self._search_running = False
        self._forecast_running = False
        self._search_generation = 0

        self._all_hinbans: list[str] = []
        self._last_hinban_filter_customer: Optional[str] = None
        self._hinban_lists_ready = False
        self._customer_display_to_name: dict[str, str] = {}
        self._customer_code_to_name: dict[str, str] = {}
        self._customer_name_to_display: dict[str, str] = {}

        self._customer_placeholder = "顧客コード・客先名（一覧／入力）"
        self._product_placeholder = "品番（任意・顧客で候補絞込）"
        self._product_disabled_placeholder = "顧客別では品番を使いません"
        self._customer_disabled_placeholder = "品番別では顧客を使いません"

        self._last_raw_df: Optional[pd.DataFrame] = None
        self._last_list_df: Optional[pd.DataFrame] = None
        self._last_forecast_comparison: Optional[pd.DataFrame] = None
        self._last_forecast_chart: Optional[pd.DataFrame] = None
        self._last_forecast_summary_lines: list[str] = []
        self._last_forecast_graph_note = ""
        self._pending_search_period_note = ""

        self._build_ui()
        self._on_aggregate_mode_changed()
        self.root.after(100, self._load_customers)

    def run(self) -> int:
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            pass
        return 0

    def _apply_theme(self) -> None:
        mpl_font_family = _pick_matplotlib_font_family()
        mpl.rcParams.update(
            {
                "font.family": mpl_font_family,
                "axes.unicode_minus": False,
            }
        )
        self._ui_font_family = _pick_ui_font_family(self.root)
        default_font = tkfont.nametofont("TkDefaultFont")
        default_font.configure(family=self._ui_font_family, size=10)
        heading_font = tkfont.nametofont("TkHeadingFont")
        heading_font.configure(family=self._ui_font_family, size=11, weight="bold")
        try:
            text_font = tkfont.nametofont("TkTextFont")
            text_font.configure(family=self._ui_font_family, size=10)
        except tk.TclError:
            pass
        try:
            fixed_font = tkfont.nametofont("TkFixedFont")
            fixed_font.configure(family=self._ui_font_family, size=10)
        except tk.TclError:
            pass
        try:
            menu_font = tkfont.nametofont("TkMenuFont")
            menu_font.configure(family=self._ui_font_family, size=10)
        except tk.TclError:
            pass
        self._font_title = tkfont.Font(root=self.root, family=self._ui_font_family, size=16, weight="bold")
        self._font_section = tkfont.Font(root=self.root, family=self._ui_font_family, size=13, weight="bold")
        self._font_small_bold = tkfont.Font(root=self.root, family=self._ui_font_family, size=9, weight="bold")
        self._font_header = tkfont.Font(root=self.root, family=self._ui_font_family, size=14, weight="bold")
        self._font_body = tkfont.Font(root=self.root, family=self._ui_font_family, size=10)
        self._font_spin = tkfont.Font(root=self.root, family=self._ui_font_family, size=11)
        self.root.option_add("*Font", self._font_body)
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TFrame", background=APP_BG)
        style.configure("Card.TFrame", background=CARD_BG)
        style.configure("AltCard.TFrame", background=CARD_ALT_BG)
        style.configure("TLabel", background=APP_BG, foreground=TEXT)
        style.configure("Card.TLabel", background=CARD_BG, foreground=TEXT)
        style.configure("Muted.TLabel", background=APP_BG, foreground=MUTED)
        style.configure("CardMuted.TLabel", background=CARD_BG, foreground=MUTED)
        style.configure("TButton", padding=(12, 8), relief="raised", borderwidth=1)
        style.configure("Primary.TButton", foreground="white", background=PRIMARY, borderwidth=0, padding=(14, 9))
        style.map("Primary.TButton", background=[("active", PRIMARY_DARK), ("pressed", PRIMARY_DARK)])
        style.configure(
            "Secondary.TButton",
            foreground=TEXT,
            background="#ffffff",
            borderwidth=1,
            padding=(14, 9),
            relief="raised",
        )
        style.map("Secondary.TButton", background=[("active", "#f8fafc"), ("pressed", "#eef2f7")])
        style.configure("TCombobox", padding=7)
        style.configure("TEntry", padding=7)
        style.configure("Treeview", bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER, rowheight=30)
        style.configure(
            "Treeview.Heading",
            font=self._font_small_bold,
            background="#eff6ff",
            foreground=TEXT,
            relief="flat",
            padding=(10, 8),
        )

    def _set_icon(self) -> None:
        ico = settings.app_icon_ico_path()
        png = settings.app_icon_png_path()
        try:
            if ico.exists():
                self.root.iconbitmap(default=str(ico))
            elif png.exists():
                self._app_icon = tk.PhotoImage(file=str(png))
                self.root.iconphoto(True, self._app_icon)
        except Exception:
            pass

    def _try_maximize(self) -> None:
        self.root.update_idletasks()
        try:
            self.root.state("zoomed")
        except tk.TclError:
            self.root.geometry("1600x900")
        self.root.minsize(1180, 700)

    def _build_ui(self) -> None:
        outer = tk.Frame(self.root, bg=APP_BG)
        outer.pack(fill="both", expand=True)
        outer.grid_rowconfigure(3, weight=1)
        outer.grid_columnconfigure(0, weight=1)

        hero = tk.Frame(outer, bg=CARD_BG, highlightbackground=BORDER, highlightthickness=1)
        hero.grid(row=0, column=0, sticky="ew", padx=16, pady=(12, 10))
        hero.grid_columnconfigure(0, weight=1)
        tk.Frame(hero, bg=PRIMARY, height=4).grid(row=0, column=0, sticky="ew")
        hero_body = tk.Frame(hero, bg=CARD_BG)
        hero_body.grid(row=1, column=0, sticky="ew", padx=18, pady=(14, 12))
        hero_body.grid_columnconfigure(0, weight=0)
        hero_body.grid_columnconfigure(1, weight=1)
        title_row = tk.Frame(hero_body, bg=CARD_BG)
        title_row.grid(row=0, column=0, columnspan=2, sticky="ew")
        title_row.grid_columnconfigure(0, weight=0)
        title_row.grid_columnconfigure(1, weight=1)
        tk.Label(title_row, text="納入実績の参照・集計", bg=CARD_BG, fg=TEXT, font=self._font_title).grid(
            row=0, column=0, sticky="w"
        )
        tk.Label(
            title_row,
            text="検索、集計、予測、Excel 出力を一画面で操作する業務ダッシュボードです。",
            bg=CARD_BG,
            fg=MUTED,
            font=self._font_body,
            anchor="w",
            justify="left",
        ).grid(row=0, column=1, sticky="w", padx=(18, 0))

        search_card = tk.Frame(outer, bg=CARD_BG, highlightbackground=BORDER, highlightthickness=1)
        search_card.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 8))
        search_card.grid_columnconfigure(0, weight=1)
        tk.Frame(search_card, bg=PRIMARY, height=4).pack(fill="x")
        search_inner = tk.Frame(search_card, bg=CARD_BG)
        search_inner.pack(fill="both", expand=True, padx=14, pady=12)
        search_inner.grid_columnconfigure(1, weight=1)
        search_inner.grid_columnconfigure(3, weight=1)

        tk.Label(search_inner, text="検索条件", bg=CARD_BG, fg=MUTED, font=self._font_small_bold).grid(
            row=0, column=0, sticky="w", pady=(0, 8)
        )

        search_row = tk.Frame(search_inner, bg=CARD_BG)
        search_row.grid(row=1, column=0, sticky="ew")
        search_row.grid_columnconfigure(1, weight=0)
        search_row.grid_columnconfigure(3, weight=0)
        search_row.grid_columnconfigure(5, weight=0)
        search_row.grid_columnconfigure(7, weight=0)
        search_row.grid_columnconfigure(9, weight=0)
        search_row.grid_columnconfigure(11, weight=1)
        tk.Label(search_row, text="開始", bg=CARD_BG, fg=MUTED).grid(row=0, column=0, padx=(0, 8), pady=4, sticky="e")
        self._date_from = DateField(search_row)
        self._date_from.grid(row=0, column=1, padx=(0, 10), pady=4, sticky="w")
        tk.Label(search_row, text="終了", bg=CARD_BG, fg=MUTED).grid(row=0, column=2, padx=(0, 8), pady=4, sticky="e")
        self._date_to = DateField(search_row)
        self._date_to.grid(row=0, column=3, padx=(0, 10), pady=4, sticky="w")
        d0, d1 = _default_date_range()
        self._date_from.set(d0)
        self._date_to.set(d1)

        tk.Label(search_row, text="集計", bg=CARD_BG, fg=MUTED, width=6, anchor="e").grid(row=0, column=4, padx=(0, 8), sticky="e")
        self._agg_var = tk.StringVar(value=AGGREGATE_OPTIONS[0][0])
        self._agg_combo = ttk.Combobox(search_row, textvariable=self._agg_var, state="readonly", values=[label for label, _mode in AGGREGATE_OPTIONS], width=12)
        self._agg_combo.grid(row=0, column=5, padx=(0, 10), sticky="w")
        self._agg_combo.bind("<<ComboboxSelected>>", lambda _e: self._on_aggregate_mode_changed())

        tk.Label(search_row, text="顧客", bg=CARD_BG, fg=MUTED, width=6, anchor="e").grid(row=0, column=6, padx=(0, 8), sticky="e")
        self._customer_combo = SearchableCombo(search_row, include_all=True, width=30)
        self._customer_combo.grid(row=0, column=7, padx=(0, 10), sticky="w")
        self._customer_combo.widget().bind("<<ComboboxSelected>>", lambda _e: self._on_customer_changed_for_hinban_list())
        self._customer_combo.widget().bind("<FocusOut>", lambda _e: self._on_customer_changed_for_hinban_list())
        self._customer_combo.widget().bind("<KeyRelease>", lambda _e: self._refresh_search_button_state())

        tk.Label(search_row, text="品番", bg=CARD_BG, fg=MUTED, width=6, anchor="e").grid(row=0, column=8, padx=(0, 8), sticky="e")
        self._product_combo = SearchableCombo(search_row, width=30)
        self._product_combo.grid(row=0, column=9, padx=(0, 10), sticky="w")
        self._product_combo.widget().bind("<KeyRelease>", lambda _e: self._refresh_search_button_state())
        self._btn_search = ttk.Button(search_row, text="検索", style="Primary.TButton", command=self._on_search, width=8)
        self._btn_search.grid(row=0, column=11, sticky="e", padx=(10, 0))
        self._btn_search.configure(state="disabled")

        self._status_var = tk.StringVar(value=f"Access パス: {settings.resolve_access_db_path()}")
        self._status = tk.Label(outer, textvariable=self._status_var, bg=APP_BG, fg=MUTED, justify="left", anchor="w")
        self._status.grid(row=2, column=0, sticky="ew", padx=18, pady=(0, 8))

        body = tk.Frame(outer, bg=APP_BG)
        body.grid(row=3, column=0, sticky="nsew", padx=16, pady=(0, 12))
        body.grid_rowconfigure(0, weight=1)
        body.grid_columnconfigure(0, weight=1, uniform="body_cols")
        body.grid_columnconfigure(1, weight=1, uniform="body_cols")

        left_panel = tk.Frame(body, bg=CARD_BG, highlightbackground=BORDER, highlightthickness=1)
        left_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        left_panel.grid_rowconfigure(5, weight=1)
        left_panel.grid_columnconfigure(0, weight=1)
        tk.Frame(left_panel, bg=PRIMARY, height=4).grid(row=0, column=0, sticky="ew")
        right_panel = tk.Frame(body, bg=CARD_ALT_BG, highlightbackground=BORDER, highlightthickness=1)
        right_panel.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        right_panel.grid_rowconfigure(4, weight=1)
        right_panel.grid_columnconfigure(0, weight=1)
        tk.Frame(right_panel, bg=ACCENT_GREEN, height=4).grid(row=0, column=0, sticky="ew")

        tk.Label(left_panel, text="実績一覧", bg=CARD_BG, fg=TEXT, font=self._font_section).grid(row=1, column=0, sticky="w", padx=16, pady=(14, 2))
        tk.Label(left_panel, text="検索結果を一覧表示し、年別・月別の推移グラフへ進めます。", bg=CARD_BG, fg=MUTED, justify="left", wraplength=560).grid(row=2, column=0, sticky="w", padx=16, pady=(0, 6))
        self._left_info_var = tk.StringVar(value="")
        tk.Label(left_panel, textvariable=self._left_info_var, bg=CARD_BG, fg=TEXT, justify="left", anchor="w").grid(row=3, column=0, sticky="w", padx=16, pady=(0, 8))
        actual_button_row = tk.Frame(left_panel, bg=CARD_BG)
        actual_button_row.grid(row=4, column=0, sticky="ew", padx=16, pady=(0, 10))
        self._btn_year_chart = ttk.Button(actual_button_row, text="年別推移グラフ", style="Secondary.TButton", command=self._on_chart_list)
        self._btn_year_chart.pack(side="left")
        self._btn_month_chart = ttk.Button(actual_button_row, text="月別推移グラフ", style="Secondary.TButton", command=self._on_chart_monthly)
        self._btn_month_chart.pack(side="left", padx=(10, 0))
        self._table = DataFrameTable(left_panel, height=16)
        self._table.grid(row=5, column=0, sticky="nsew", padx=12, pady=(0, 12))

        tk.Label(right_panel, text="年次予測", bg=CARD_ALT_BG, fg=TEXT, font=self._font_section).grid(row=1, column=0, sticky="w", padx=16, pady=(14, 2))
        tk.Label(right_panel, text="実績・直線延長・重み付き回帰・外部要因予測を比較します。先に検索で明細を取得してください。", bg=CARD_ALT_BG, fg=MUTED, justify="left", wraplength=560).grid(row=2, column=0, sticky="w", padx=16, pady=(0, 10))
        control_row = tk.Frame(right_panel, bg=CARD_ALT_BG)
        control_row.grid(row=3, column=0, sticky="ew", padx=16, pady=(0, 8))
        tk.Label(control_row, text="予測年数", bg=CARD_ALT_BG, fg=MUTED).pack(side="left", padx=(0, 8))
        self._forecast_years_var = tk.IntVar(value=3)
        self._forecast_spin = tk.Spinbox(control_row, from_=1, to=5, textvariable=self._forecast_years_var, width=6, font=self._font_spin, justify="center", relief="solid", bd=1)
        self._forecast_spin.pack(side="left")
        self._btn_forecast_run = ttk.Button(control_row, text="予測を実行", style="Primary.TButton", command=self._on_forecast_run)
        self._btn_forecast_run.pack(side="left", padx=(10, 0))
        self._btn_forecast_chart = ttk.Button(control_row, text="予測グラフ", style="Secondary.TButton", command=self._on_forecast_chart)
        self._btn_forecast_chart.pack(side="left", padx=(10, 0))
        self._btn_forecast_excel = ttk.Button(control_row, text="予測を Excel 出力", style="Secondary.TButton", command=self._on_forecast_excel)
        self._btn_forecast_excel.pack(side="left", padx=(10, 0))
        control_row.grid_columnconfigure(4, weight=1)
        self._btn_forecast_detail = ttk.Button(control_row, text="予測算出詳細", style="Secondary.TButton", command=self._on_open_forecast_details)
        self._btn_forecast_detail.pack(side="right", padx=(10, 0))
        self._btn_forecast_run.configure(state="disabled")
        self._btn_forecast_chart.configure(state="disabled")
        self._btn_forecast_excel.configure(state="disabled")
        self._forecast_table = DataFrameTable(right_panel, height=12)
        self._forecast_table.grid(row=4, column=0, sticky="nsew", padx=12, pady=(0, 12))

    def _is_busy(self) -> bool:
        return self._search_running or self._forecast_running

    def _set_busy(self, message: str | None, *, running: bool) -> None:
        if message:
            self._status_var.set(message)
        if running:
            if self._busy_dialog is None or not self._busy_dialog.winfo_exists():
                self._busy_dialog = BusyDialog(self.root, message or "処理中…")
            elif message:
                self._busy_dialog.update_message(message)
            self.root.update_idletasks()
        else:
            if self._busy_dialog is not None:
                try:
                    self._busy_dialog.close()
                except tk.TclError:
                    pass
                self._busy_dialog = None

    def _show_info(self, title: str, text: str) -> None:
        messagebox.showinfo(title, text, parent=self.root)

    def _show_warning(self, title: str, text: str) -> None:
        messagebox.showwarning(title, text, parent=self.root)

    def _show_error(self, title: str, text: str) -> None:
        messagebox.showerror(title, text, parent=self.root)

    def _open_window(self, win: tk.Toplevel) -> None:
        self._open_windows.append(win)
        win.protocol("WM_DELETE_WINDOW", lambda w=win: self._close_window(w))

    def _close_window(self, win: tk.Toplevel) -> None:
        try:
            self._open_windows.remove(win)
        except ValueError:
            pass
        win.destroy()

    @staticmethod
    def _aggregate_mode_label(mode_name: str) -> str:
        return AGGREGATE_MODE_TO_LABEL.get(mode_name, mode_name)

    @staticmethod
    def _has_customer_value(text: str) -> bool:
        return bool((text or "").strip() and (text or "").strip() != ALL_LABEL)

    @staticmethod
    def _has_product_value(text: str) -> bool:
        return bool((text or "").strip())

    def _clear_combo_text(self, combo: SearchableCombo) -> None:
        combo.clear()

    @staticmethod
    def _format_customer_choice(code: str, name: str) -> str:
        return f"{code}  {name}"

    def _resolve_customer_name(self, raw_text: str) -> Optional[str]:
        text = (raw_text or "").strip()
        if text in ("", ALL_LABEL):
            return None
        if text in self._customer_display_to_name:
            return self._customer_display_to_name[text]
        if text in self._customer_code_to_name:
            return self._customer_code_to_name[text]
        return text

    def _customer_display_label(self, raw_text: str) -> str:
        text = (raw_text or "").strip()
        if text in ("", ALL_LABEL):
            return "全顧客"
        if text in self._customer_display_to_name:
            return text
        if text in self._customer_code_to_name:
            name = self._customer_code_to_name[text]
            return self._customer_name_to_display.get(name, self._format_customer_choice(text, name))
        return self._customer_name_to_display.get(text, text)

    def _set_product_input_enabled(self, enabled: bool, placeholder: str) -> None:
        self._product_combo.set_enabled(enabled)

    def _set_customer_input_enabled(self, enabled: bool, placeholder: str) -> None:
        self._customer_combo.set_enabled(enabled)

    def _current_aggregate_mode(self) -> str:
        return AGGREGATE_LABEL_TO_MODE.get(
            self._agg_var.get().strip(),
            delivery_service.AggregateMode.BY_CUSTOMER.name,
        )

    def _on_aggregate_mode_changed(self) -> None:
        mode = self._current_aggregate_mode()
        if mode == delivery_service.AggregateMode.BY_CUSTOMER.name:
            self._set_customer_input_enabled(True, self._customer_placeholder)
            self._set_product_input_enabled(False, self._product_disabled_placeholder)
            self._clear_combo_text(self._product_combo)
            self._product_combo.set_items(self._all_hinbans)
            self._last_hinban_filter_customer = None
        elif mode == delivery_service.AggregateMode.BY_PRODUCT.name:
            self._set_customer_input_enabled(False, self._customer_disabled_placeholder)
            self._set_product_input_enabled(True, self._product_placeholder)
            self._clear_combo_text(self._customer_combo)
            self._product_combo.set_items(self._all_hinbans)
            self._last_hinban_filter_customer = None
        else:
            self._set_customer_input_enabled(True, self._customer_placeholder)
            self._set_product_input_enabled(True, self._product_placeholder)
            if self._has_customer_value(self._customer_combo.get()):
                self._on_customer_changed_for_hinban_list()
            else:
                self._product_combo.set_items(self._all_hinbans)
                self._last_hinban_filter_customer = None
        self._refresh_search_button_state()

    def _refresh_search_button_state(self) -> None:
        if self._is_busy():
            self._btn_search.configure(state="disabled")
            return
        mode = self._current_aggregate_mode()
        has_customer = self._has_customer_value(self._customer_combo.get())
        has_product = self._has_product_value(self._product_combo.get())
        d_from = self._date_from.get()
        d_to = self._date_to.get()
        has_valid_period = bool(d_from and d_to and d_from <= d_to)
        if mode == delivery_service.AggregateMode.BY_CUSTOMER.name:
            ready = has_customer
        elif mode == delivery_service.AggregateMode.BY_PRODUCT.name:
            ready = has_product
        else:
            ready = has_customer and has_product
        self._btn_search.configure(state="normal" if ready and has_valid_period else "disabled")

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
        cust = self._sanitize_filename_part(self._resolve_customer_name(self._customer_combo.get()) or "全顧客")
        prod = self._sanitize_filename_part(self._product_combo.get())
        if mode == delivery_service.AggregateMode.BY_CUSTOMER.name:
            subject = cust or "全顧客"
        elif mode == delivery_service.AggregateMode.BY_PRODUCT.name:
            subject = prod or "全品番"
        else:
            subject = "_".join(part for part in (cust, prod) if part) or "検索結果"
        suffix = "納品実績・予測データ" if include_forecast else "納品実績データ"
        return f"{subject}{suffix}.xlsx"

    def _run_threaded(self, description: str, fn: Callable[[], Any], on_done: Callable[[Any], None], on_fail: Callable[[BaseException], None], *, running_flag: str) -> None:
        if self._is_busy():
            return

        setattr(self, running_flag, True)
        self._set_busy(description, running=True)

        def runner() -> None:
            result: Any = None
            error: BaseException | None = None
            try:
                result = fn()
            except BaseException as exc:  # noqa: BLE001
                error = exc

            def finish() -> None:
                try:
                    setattr(self, running_flag, False)
                    self._set_busy(None, running=False)
                    if error is not None:
                        on_fail(error)
                    else:
                        on_done(result)
                finally:
                    self._refresh_search_button_state()

            self.root.after(0, finish)

        threading.Thread(target=runner, daemon=True).start()

    def _load_customers(self) -> None:
        def task() -> tuple[list[tuple[str, str]], list[str]]:
            with access_connector.open_connection(settings.resolve_access_db_path()) as conn:
                customer_pairs = delivery_service.fetch_customer_code_name_pairs(conn)
                hinbans = delivery_service.fetch_distinct_hinban(conn)
                return customer_pairs, hinbans

        def done(payload: tuple[list[tuple[str, str]], list[str]]) -> None:
            customer_pairs, hinbans = payload
            customer_pairs = sorted(customer_pairs, key=lambda item: (item[1], item[0]))
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
            self._customer_combo.set_items(customer_items)
            self._product_combo.set_items(hinbans)
            self._on_aggregate_mode_changed()
            self._status_var.set(
                f"顧客件数: {len(customer_items)} 件 / 品番候補: {len(hinbans)} 件を読み込みました。\n"
                f"Access: {settings.resolve_access_db_path()}"
            )

        def fail(exc: BaseException) -> None:
            if isinstance(exc, access_connector.OdbcDriverNotFoundError):
                self._show_error("接続エラー", str(exc))
            elif isinstance(exc, access_connector.AccessFileUnavailableError):
                self._show_error("接続エラー", str(exc))
            elif isinstance(exc, access_connector.AccessConnectionError):
                self._show_error("接続エラー", str(exc))
            else:
                self._show_error("接続エラー", f"顧客一覧の取得に失敗しました。\n{exc}")

        self._run_threaded("顧客一覧を読み込み中…", task, done, fail, running_flag="_search_running")

    def _on_customer_changed_for_hinban_list(self) -> None:
        if not self._hinban_lists_ready:
            self._refresh_search_button_state()
            return
        if self._current_aggregate_mode() != delivery_service.AggregateMode.BY_CUSTOMER_PRODUCT.name:
            self._refresh_search_button_state()
            return
        cust = self._resolve_customer_name(self._customer_combo.get())
        if not cust:
            self._last_hinban_filter_customer = None
            self._product_combo.set_items(self._all_hinbans)
            self._refresh_search_button_state()
            return
        if cust == self._last_hinban_filter_customer:
            self._refresh_search_button_state()
            return

        def task() -> list[str]:
            with access_connector.open_connection(settings.resolve_access_db_path()) as conn:
                return delivery_service.fetch_distinct_hinban_for_customer(conn, cust)

        def done(items: list[str]) -> None:
            self._last_hinban_filter_customer = cust
            self._product_combo.set_items(items)
            self._refresh_search_button_state()

        def fail(exc: BaseException) -> None:
            self._show_warning("品番一覧", f"顧客に応じた品番の取得に失敗しました。\n{exc}")

        self._run_threaded("品番候補を読み込み中…", task, done, fail, running_flag="_forecast_running")

    def _on_search(self) -> None:
        if self._search_running:
            return
        d_from = self._date_from.get()
        d_to = self._date_to.get()
        if d_from is None or d_to is None:
            self._show_warning("検索", "開始日と終了日を正しく入力してください。")
            return
        if d_from > d_to:
            self._show_warning("検索", "開始日が終了日より後になっています。")
            return

        customer = self._resolve_customer_name(self._customer_combo.get().strip())
        product = self._product_combo.get().strip() or None
        mode = self._current_aggregate_mode()
        if mode == delivery_service.AggregateMode.BY_CUSTOMER.name:
            product = None
        elif mode == delivery_service.AggregateMode.BY_PRODUCT.name:
            customer = None

        self._pending_search_period_note = f"{d_from} ～ {d_to}"
        self._btn_search.configure(state="disabled")
        self._btn_forecast_run.configure(state="disabled")
        self._btn_forecast_chart.configure(state="disabled")
        self._btn_forecast_excel.configure(state="disabled")

        def task() -> tuple[pd.DataFrame, pd.DataFrame, str]:
            with access_connector.open_connection(settings.resolve_access_db_path()) as conn:
                raw = delivery_service.fetch_deliveries(conn, d_from, d_to, customer, product)
                agg = delivery_service.aggregate_for_list(raw, delivery_service.AggregateMode[mode])
                return raw, agg, mode

        def done(payload: tuple[pd.DataFrame, pd.DataFrame, str]) -> None:
            raw, agg, mode_name = payload
            self._search_generation += 1
            self._last_forecast_comparison = None
            self._last_forecast_chart = None
            self._last_forecast_summary_lines = []
            self._last_forecast_graph_note = ""
            self._last_raw_df = raw
            self._last_list_df = agg
            self._table.set_dataframe(agg)
            self._left_info_var.set(
                f"納入件数: {len(raw)} 行 / 表示行: {len(agg)} 行\n"
                f"対象期間: {self._pending_search_period_note}\n"
                f"集計単位: {self._aggregate_mode_label(mode_name)}"
            )
            self._status_var.set(
                f"取得明細: {len(raw)} 行 / 表示行: {len(agg)} 行（集計単位: {self._aggregate_mode_label(mode_name)}）\n"
                f"対象期間: {self._pending_search_period_note}"
            )
            self._btn_forecast_run.configure(state="normal" if not raw.empty else "disabled")

        def fail(exc: BaseException) -> None:
            self._btn_forecast_run.configure(state="disabled")
            self._btn_forecast_chart.configure(state="disabled")
            self._btn_forecast_excel.configure(state="disabled")
            self._show_error("検索エラー", f"検索中にエラーが発生しました。\n{exc}")
            self._status_var.set(f"検索に失敗しました。\nAccess: {settings.resolve_access_db_path()}")

        self._run_threaded("検索中…", task, done, fail, running_flag="_search_running")

    def _on_export_list(self) -> None:
        if self._last_list_df is None or self._last_list_df.empty:
            self._show_info("Excel", "出力する一覧がありません。先に検索してください。")
            return
        default_name = self._default_excel_export_name(include_forecast=False)
        path = filedialog.asksaveasfilename(
            parent=self.root,
            title="Excel 保存",
            initialfile=default_name,
            defaultextension=".xlsx",
            filetypes=[("Excel", "*.xlsx")],
        )
        if not path:
            return
        try:
            yearly = delivery_service.yearly_totals_from_raw_deliveries(self._last_raw_df)
            cust_lbl = self._customer_display_label(self._customer_combo.get())
            prod_lbl = self._product_combo.get().strip() or "全品番"
            period_lbl = self._pending_search_period_note or "—"
            export_service.export_dataframe(
                path,
                self._last_list_df,
                sheet_name="一覧",
                table_name="顧客別納入分析システム / 実績一覧",
                yearly_chart_df=yearly,
                chart_title="年別推移（検索結果）",
                chart_subtitle=f"顧客: {cust_lbl} / 品番: {prod_lbl} / 対象期間: {period_lbl}",
            )
            self._show_info("Excel", "保存しました。")
        except export_service.ExportError as exc:
            self._show_warning("Excel", str(exc))

    def _chart_yearly_figure(self, df: pd.DataFrame, title: str, subtitle: str = "") -> Figure:
        fig = Figure(figsize=(9.8, 6.4), facecolor="white")
        ax1 = fig.add_subplot(2, 1, 1)
        ax2 = fig.add_subplot(2, 1, 2)
        ax1.set_facecolor("#fafafa")
        ax2.set_facecolor("#fafafa")
        if df.empty:
            ax1.text(0.5, 0.5, "表示するデータがありません", ha="center", va="center")
            ax2.text(0.5, 0.5, "表示するデータがありません", ha="center", va="center")
        else:
            work = df.copy()
            if "種別" not in work.columns:
                work["種別"] = "実績"
            years = sorted({int(v) for v in pd.to_numeric(work["年"], errors="coerce").dropna().tolist()})
            styles = {
                "実績": ("o", "-", "#2563eb"),
                "直線延長予測": ("s", "--", "#c2410c"),
                "重み付き回帰予測": ("D", "--", "#ea580c"),
                "外部要因予測": ("^", "-", "#15803d"),
            }

            def plot_pair(ax, col: str, ylabel: str) -> None:
                for kind in work["種別"].dropna().astype(str).unique().tolist():
                    part = work[work["種別"] == kind]
                    if part.empty:
                        continue
                    marker, linestyle, color = styles.get(kind, ("o", "-", "#475569"))
                    ax.plot(
                        pd.to_numeric(part["年"], errors="coerce"),
                        pd.to_numeric(part[col], errors="coerce"),
                        marker=marker,
                        linestyle=linestyle,
                        color=color,
                        label=kind,
                    )
                ax.set_ylabel(ylabel)
                ax.grid(True, alpha=0.28)
                ax.yaxis.set_major_formatter(StrMethodFormatter("{x:,.0f}"))
                if years:
                    ax.set_xticks(years)
                ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1.0), frameon=False, fontsize=7)
                ax.tick_params(axis="both", labelsize=8)

            plot_pair(ax1, "納品数", "納品数")
            plot_pair(ax2, "金額", "金額")
            ax2.set_xlabel("年")
        fig.suptitle(f"{title}\n{subtitle}" if subtitle else title, fontsize=10.5, color=TEXT)
        fig.tight_layout(rect=(0, 0, 0.86, 0.92))
        return fig

    def _chart_monthly_figure(self, df: pd.DataFrame, title: str, subtitle: str = "") -> Figure:
        fig = Figure(figsize=(9.8, 6.4), facecolor="white")
        ax1 = fig.add_subplot(2, 1, 1)
        ax2 = fig.add_subplot(2, 1, 2)
        ax1.set_facecolor("#fafafa")
        ax2.set_facecolor("#fafafa")
        if df.empty:
            ax1.text(0.5, 0.5, "表示するデータがありません", ha="center", va="center")
            ax2.text(0.5, 0.5, "表示するデータがありません", ha="center", va="center")
        else:
            dates = pd.to_datetime(df["年月"].astype(str), errors="coerce")
            work = df.copy()
            work["_date"] = dates
            work = work.dropna(subset=["_date"]).sort_values("_date").reset_index(drop=True)
            if work.empty:
                ax1.text(0.5, 0.5, "表示するデータがありません", ha="center", va="center")
                ax2.text(0.5, 0.5, "表示するデータがありません", ha="center", va="center")
                fig.suptitle(f"{title}\n{subtitle}" if subtitle else title, fontsize=10.5, color=TEXT)
                fig.tight_layout(rect=(0, 0, 0.86, 0.92))
                return fig
            x_dates = work["_date"].dt.to_pydatetime().tolist()

            def plot_month(ax, col: str, ylabel: str) -> None:
                ax.plot(x_dates, pd.to_numeric(work[col], errors="coerce"), color=PRIMARY, marker="o", linewidth=1.8)
                ax.set_ylabel(ylabel)
                ax.grid(True, alpha=0.28)
                ax.yaxis.set_major_formatter(StrMethodFormatter("{x:,.0f}"))
                ax.xaxis.set_major_locator(mdates.MonthLocator(interval=6))
                ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
                ax.tick_params(axis="x", which="major", labelsize=8, pad=8, labelrotation=45)
                ax.tick_params(axis="y", labelsize=8)
                ax.margins(x=0.02)
                ax.set_xlim(min(x_dates), max(x_dates))

            plot_month(ax1, "納品数", "納品数")
            plot_month(ax2, "金額", "金額")
            ax2.set_xlabel("年月")
        fig.suptitle(f"{title}\n{subtitle}" if subtitle else title, fontsize=10.5, color=TEXT)
        fig.tight_layout(rect=(0, 0, 0.86, 0.92))
        return fig

    def _on_chart_list(self) -> None:
        raw = self._last_raw_df
        if raw is None or raw.empty:
            self._show_info("グラフ", "先に検索を実行してください。")
            return
        y = delivery_service.yearly_totals_from_raw_deliveries(raw)
        y = y.copy()
        y["種別"] = "実績"
        cust_lbl = self._customer_display_label(self._customer_combo.get())
        prod_lbl = self._product_combo.get().strip() or "全品番"
        period_lbl = self._pending_search_period_note or "—"
        sub = f"顧客: {cust_lbl} / 品番: {prod_lbl} / 対象期間: {period_lbl}"
        dlg = ChartDialog(self.root, "年別推移（検索結果）", self._chart_yearly_figure(y, "年別推移（検索結果）", sub))
        self._open_window(dlg)

    def _on_chart_monthly(self) -> None:
        raw = self._last_raw_df
        if raw is None or raw.empty:
            self._show_info("グラフ", "先に検索を実行してください。")
            return
        monthly = delivery_service.monthly_totals_from_raw_deliveries(raw)
        cust_lbl = self._customer_display_label(self._customer_combo.get())
        prod_lbl = self._product_combo.get().strip() or "全品番"
        period_lbl = self._pending_search_period_note or "—"
        sub = f"顧客: {cust_lbl} / 品番: {prod_lbl} / 対象期間: {period_lbl}"
        dlg = ChartDialog(self.root, "月別推移（検索結果）", self._chart_monthly_figure(monthly, "月別推移（検索結果）", sub))
        self._open_window(dlg)

    def _on_forecast_run(self) -> None:
        if self._forecast_running:
            self._show_info("予測", "予測計算の実行中です。完了を待ってから再度お試しください。")
            return
        raw = self._last_raw_df
        if raw is None or raw.empty:
            self._show_info("予測", "先に検索を実行し、明細データを取得してください。")
            return
        yearly = delivery_service.yearly_totals_from_raw_deliveries(raw)
        if yearly.empty:
            self._show_warning("予測", "年次集計できる明細がありません。")
            return
        n_years = int(self._forecast_years_var.get())
        run_gen = self._search_generation

        def task() -> dict[str, Any]:
            from app.service import external_indicator_service

            yearly_local = delivery_service.yearly_totals_from_raw_deliveries(raw)
            indicator_svc = external_indicator_service.ExternalIndicatorService()
            indicator_statuses = indicator_svc.refresh_if_needed()
            status_summary = indicator_svc.summarize_statuses(indicator_statuses)
            if yearly_local.empty:
                indicator_yearly = pd.DataFrame(columns=["年", "iip_avg", "ci_avg"])
            else:
                year_to = int(yearly_local["年"].max())
                future_last_year = year_to + n_years
                year_from = int(yearly_local["年"].min())
                indicator_yearly = indicator_svc.build_yearly_indicator_frame(year_from, future_last_year)
            bundle = forecast_service.run_yearly_forecast_bundle(yearly_local, indicator_yearly, n_years)
            return {
                "comparison_df": bundle.comparison_df,
                "chart_df": bundle.chart_df,
                "summary_lines": bundle.summary_lines,
                "graph_note": bundle.graph_note,
                "status_summary": status_summary,
            }

        def done(payload: dict[str, Any]) -> None:
            if run_gen != self._search_generation:
                return
            comparison_df = payload.get("comparison_df", pd.DataFrame()).copy()
            chart_df = payload.get("chart_df", pd.DataFrame()).copy()
            summary_lines = list(payload.get("summary_lines", []))
            graph_note = str(payload.get("graph_note", "") or "")
            status_summary = str(payload.get("status_summary", "") or "")

            self._last_forecast_comparison = comparison_df
            self._last_forecast_chart = chart_df
            self._last_forecast_summary_lines = summary_lines
            self._last_forecast_graph_note = graph_note
            display_columns = {
                "年": "年",
                "実績\n納品数": "実績\n納品数",
                "実績\n金額": "実績\n金額",
                "直線延長\n納品数": "直線延長\n納品数",
                "直線延長\n金額": "直線延長\n金額",
                "重み付き回帰\n納品数": "重み付き回帰\n納品数",
                "重み付き回帰\n金額": "重み付き回帰\n金額",
                "外部要因予測\n納品数": "外部要因予測\n納品数",
                "外部要因予測\n金額": "外部要因予測\n金額",
            }
            self._forecast_table.set_dataframe(comparison_df, display_columns=display_columns, compact_headers=True)
            self._btn_forecast_chart.configure(state="normal")
            self._btn_forecast_excel.configure(state="normal")

        def fail(exc: BaseException) -> None:
            if run_gen != self._search_generation:
                return
            self._show_warning("予測", f"予測の計算に失敗しました。\n{exc}")

        self._run_threaded("予測を計算中…", task, done, fail, running_flag="_forecast_running")

    def _forecast_chart_subtitle(self) -> str:
        cust_lbl = self._customer_display_label(self._customer_combo.get())
        prod_lbl = self._product_combo.get().strip() or "全品番"
        period_lbl = self._pending_search_period_note or "—"
        base = f"顧客: {cust_lbl} / 品番: {prod_lbl} / 対象期間: {period_lbl}"
        return f"{base}\n{self._last_forecast_graph_note}" if self._last_forecast_graph_note else base

    def _on_open_forecast_details(self) -> None:
        if self._busy_dialog is not None and self._busy_dialog.winfo_exists():
            self._busy_dialog.lift()
        dlg = ForecastExplanationDialog(self.root)
        self._open_window(dlg)

    def _on_forecast_chart(self) -> None:
        df = self._last_forecast_chart
        if df is None or df.empty:
            self._show_info("グラフ", "先に「予測を実行」を行ってください。")
            return
        dlg = ChartDialog(
            self.root,
            "年別推移（実績・直線延長・重み付き回帰・外部要因）",
            self._chart_yearly_figure(df, "年別推移（実績・直線延長・重み付き回帰・外部要因）", self._forecast_chart_subtitle()),
        )
        self._open_window(dlg)

    def _on_forecast_excel(self) -> None:
        df = self._last_forecast_comparison
        if df is None or df.empty:
            self._show_info("Excel", "先に「予測を実行」を行ってください。")
            return
        default_name = self._default_excel_export_name(include_forecast=True)
        path = filedialog.asksaveasfilename(
            parent=self.root,
            title="Excel 保存（予測）",
            initialfile=default_name,
            defaultextension=".xlsx",
            filetypes=[("Excel", "*.xlsx")],
        )
        if not path:
            return
        try:
            export_service.export_forecast_workbook(
                path,
                df,
                meta_lines=self._last_forecast_summary_lines,
                chart_subtitle=self._forecast_chart_subtitle(),
            )
            self._show_info("Excel", "保存しました。")
        except export_service.ExportError as exc:
            self._show_warning("Excel", str(exc))


def main() -> int:
    app = DeliveryAnalyticsApp()
    return app.run()
