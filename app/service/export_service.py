# -*- coding: utf-8 -*-
"""一覧・予測結果の Excel 出力（openpyxl）。"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd
from openpyxl import Workbook
from openpyxl.chart import Reference, ScatterChart, Series
from openpyxl.chart.layout import Layout, ManualLayout
from openpyxl.utils.dataframe import dataframe_to_rows


class ExportError(Exception):
    """出力失敗。"""


def _prepare_output_path(file_path: str) -> Path:
    path = Path(file_path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise ExportError(f"出力先フォルダを作成できません: {e}") from e
    return path


def _write_dataframe(
    ws,
    df: Optional[pd.DataFrame],
    *,
    title: str = "",
    empty_message: str = "データがありません。",
) -> None:
    row_cursor = 1
    if title:
        ws.cell(row=row_cursor, column=1, value=title)
        row_cursor += 1

    if df is None or df.empty:
        ws.cell(row=row_cursor, column=1, value=empty_message)
        return

    for r_idx, row in enumerate(dataframe_to_rows(df, index=False, header=True), start=0):
        for c_idx, value in enumerate(row, start=1):
            ws.cell(row=row_cursor + r_idx, column=c_idx, value=value)


def _build_chart_source(yearly_df: Optional[pd.DataFrame]) -> pd.DataFrame:
    columns = ["年", "実績_納品数", "予測_納品数", "実績_金額", "予測_金額"]
    if yearly_df is None or yearly_df.empty:
        return pd.DataFrame(columns=columns)

    work = yearly_df.copy()
    for col in ("年", "納品数", "金額"):
        if col not in work.columns:
            return pd.DataFrame(columns=columns)

    work["年"] = pd.to_numeric(work["年"], errors="coerce")
    work["納品数"] = pd.to_numeric(work["納品数"], errors="coerce")
    work["金額"] = pd.to_numeric(work["金額"], errors="coerce")
    work = work.dropna(subset=["年"]).copy()
    if work.empty:
        return pd.DataFrame(columns=columns)
    work["年"] = work["年"].astype(int)

    if "種別" not in work.columns:
        out = work[["年", "納品数", "金額"]].copy()
        out = out.rename(columns={"納品数": "実績_納品数", "金額": "実績_金額"})
        out["予測_納品数"] = None
        out["予測_金額"] = None
        return out[columns].sort_values("年").reset_index(drop=True)

    actual = work[work["種別"] == "実績"][["年", "納品数", "金額"]].copy()
    actual = actual.rename(columns={"納品数": "実績_納品数", "金額": "実績_金額"})
    forecast = work[work["種別"] == "予測"][["年", "納品数", "金額"]].copy()
    forecast = forecast.rename(columns={"納品数": "予測_納品数", "金額": "予測_金額"})

    out = pd.merge(actual, forecast, on="年", how="outer")
    return out[columns].sort_values("年").reset_index(drop=True)


def _configure_series(series: Series, color: str, *, dashed: bool = False, marker: str = "circle") -> None:
    series.graphicalProperties.line.solidFill = color
    series.graphicalProperties.line.width = 20000
    if dashed:
        series.graphicalProperties.line.dashStyle = "sysDot"
    series.marker.symbol = marker
    series.marker.size = 7
    series.graphicalProperties.solidFill = color


def _add_xy_series(chart: ScatterChart, ws_src, row_count: int, col_idx: int, *, color: str, dashed: bool = False, marker: str = "circle") -> None:
    values = Reference(ws_src, min_col=col_idx, min_row=1, max_row=row_count + 1)
    xvalues = Reference(ws_src, min_col=1, min_row=2, max_row=row_count + 1)
    series = Series(values, xvalues, title_from_data=True)
    _configure_series(series, color, dashed=dashed, marker=marker)
    chart.series.append(series)


def _configure_axes(chart: ScatterChart, *, y_title: str) -> None:
    chart.x_axis.title = "年（西暦）"
    chart.y_axis.title = y_title
    chart.x_axis.number_format = "0"
    chart.y_axis.number_format = "#,##0"
    chart.x_axis.majorTickMark = "out"
    chart.y_axis.majorTickMark = "out"
    chart.x_axis.minorTickMark = "none"
    chart.y_axis.minorTickMark = "none"
    chart.x_axis.tickLblPos = "low"
    chart.y_axis.tickLblPos = "nextTo"
    chart.x_axis.delete = False
    chart.y_axis.delete = False


def _configure_chart_layout(chart: ScatterChart) -> None:
    """軸タイトルや目盛りが重ならないよう、プロット領域に余白を確保する。"""
    chart.layout = Layout(
        manualLayout=ManualLayout(
            layoutTarget="inner",
            xMode="edge",
            yMode="edge",
            x=0.14,
            y=0.10,
            w=0.66,
            h=0.64,
        )
    )


def _add_chart_sheet(
    wb: Workbook,
    yearly_df: Optional[pd.DataFrame],
    *,
    chart_title: str,
    chart_subtitle: str = "",
) -> None:
    chart_source = _build_chart_source(yearly_df)
    if chart_source.empty:
        return

    ws_src = wb.create_sheet(title="グラフ元データ")
    _write_dataframe(ws_src, chart_source)
    ws_src.sheet_state = "hidden"

    ws_chart = wb.create_sheet(title="グラフ")
    ws_chart["A1"] = chart_title
    if chart_subtitle:
        ws_chart["A2"] = chart_subtitle

    row_count = len(chart_source.index)
    qty_chart = ScatterChart()
    qty_chart.scatterStyle = "lineMarker"
    qty_chart.title = "納品数"
    _configure_axes(qty_chart, y_title="納品数（年合計）")
    _configure_chart_layout(qty_chart)
    qty_chart.height = 9.4
    qty_chart.width = 18
    qty_chart.legend.position = "r"

    _add_xy_series(qty_chart, ws_src, row_count, 2, color="2F75B5", marker="circle")
    if chart_source["予測_納品数"].notna().any():
        _add_xy_series(qty_chart, ws_src, row_count, 3, color="ED7D31", dashed=True, marker="square")

    amount_chart = ScatterChart()
    amount_chart.scatterStyle = "lineMarker"
    amount_chart.title = "金額"
    _configure_axes(amount_chart, y_title="金額（円・年合計）")
    _configure_chart_layout(amount_chart)
    amount_chart.height = 9.4
    amount_chart.width = 18
    amount_chart.legend.position = "r"

    _add_xy_series(amount_chart, ws_src, row_count, 4, color="2F75B5", marker="circle")
    if chart_source["予測_金額"].notna().any():
        _add_xy_series(amount_chart, ws_src, row_count, 5, color="ED7D31", dashed=True, marker="square")

    top_row = 4 if chart_subtitle else 3
    ws_chart.add_chart(qty_chart, f"A{top_row}")
    ws_chart.add_chart(amount_chart, f"A{top_row + 20}")


def export_dataframe(
    file_path: str,
    df: pd.DataFrame,
    sheet_name: str = "一覧",
    table_name: Optional[str] = None,
    yearly_chart_df: Optional[pd.DataFrame] = None,
    chart_title: str = "年別推移",
    chart_subtitle: str = "",
) -> None:
    """
    DataFrame を xlsx に書き出す。
    yearly_chart_df があれば、年次グラフシートも追加する。
    """
    path = _prepare_output_path(file_path)

    wb = Workbook()
    ws = wb.active
    ws.title = sheet_name[:31] if sheet_name else "Sheet"
    _write_dataframe(ws, df, title=table_name)
    _add_chart_sheet(
        wb,
        yearly_chart_df,
        chart_title=chart_title,
        chart_subtitle=chart_subtitle,
    )

    try:
        wb.save(str(path))
    except OSError as e:
        raise ExportError(
            f"Excel ファイルの保存に失敗しました。別アプリで開いていないか確認してください: {e}"
        ) from e
    except Exception as e:
        raise ExportError(f"Excel 出力中にエラーが発生しました: {e}") from e


def export_two_sheets(
    file_path: str,
    df_actual: pd.DataFrame,
    df_forecast: pd.DataFrame,
    meta: str = "",
    yearly_chart_df: Optional[pd.DataFrame] = None,
    chart_title: str = "年別推移",
    chart_subtitle: str = "",
) -> None:
    """実績シートと予測シートの 2 枚で保存し、必要ならグラフも追加する。"""
    path = _prepare_output_path(file_path)

    wb = Workbook()

    ws1 = wb.active
    ws1.title = "実績年次"
    _write_dataframe(ws1, df_actual, title=meta, empty_message="実績がありません。")

    ws2 = wb.create_sheet(title="予測")
    _write_dataframe(ws2, df_forecast, empty_message="予測がありません。")

    chart_df = yearly_chart_df
    if chart_df is None:
        actual = df_actual.copy() if df_actual is not None else pd.DataFrame()
        forecast = df_forecast.copy() if df_forecast is not None else pd.DataFrame()
        if not actual.empty:
            actual["種別"] = "実績"
        if not forecast.empty:
            forecast["種別"] = "予測"
        chart_df = pd.concat([actual, forecast], ignore_index=True)

    _add_chart_sheet(
        wb,
        chart_df,
        chart_title=chart_title,
        chart_subtitle=chart_subtitle,
    )

    try:
        wb.save(str(path))
    except OSError as e:
        raise ExportError(
            f"Excel ファイルの保存に失敗しました。別アプリで開いていないか確認してください: {e}"
        ) from e
    except Exception as e:
        raise ExportError(f"Excel 出力中にエラーが発生しました: {e}") from e
