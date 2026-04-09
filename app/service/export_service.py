# -*- coding: utf-8 -*-
"""一覧・予測結果の Excel 出力（openpyxl）。"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd
from openpyxl import Workbook
from openpyxl.utils.dataframe import dataframe_to_rows


class ExportError(Exception):
    """出力失敗"""


def export_dataframe(
    file_path: str,
    df: pd.DataFrame,
    sheet_name: str = "結果",
    table_name: Optional[str] = None,
) -> None:
    """
    DataFrame を xlsx に書き出す。
    table_name があれば先頭行にメタ情報として記載する。
    """
    path = Path(file_path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise ExportError(f"出力先フォルダを作成できません: {e}") from e

    wb = Workbook()
    ws = wb.active
    ws.title = sheet_name[:31] if sheet_name else "Sheet"

    row_cursor = 1
    if table_name:
        ws.cell(row=row_cursor, column=1, value=table_name)
        row_cursor += 1

    if df is None or df.empty:
        ws.cell(row=row_cursor, column=1, value="（データなし）")
    else:
        for r_idx, row in enumerate(
            dataframe_to_rows(df, index=False, header=True), start=0
        ):
            for c_idx, value in enumerate(row, start=1):
                ws.cell(row=row_cursor + r_idx, column=c_idx, value=value)

    try:
        wb.save(str(path))
    except OSError as e:
        raise ExportError(
            f"Excel ファイルの保存に失敗しました（他アプリで開いていませんか）: {e}"
        ) from e
    except Exception as e:
        raise ExportError(f"Excel 出力中にエラーが発生しました: {e}") from e


def export_two_sheets(
    file_path: str,
    df_actual: pd.DataFrame,
    df_forecast: pd.DataFrame,
    meta: str = "",
) -> None:
    """実績シートと予測シートの 2 枚で保存。"""
    path = Path(file_path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise ExportError(f"出力先フォルダを作成できません: {e}") from e

    wb = Workbook()
    # 実績
    ws1 = wb.active
    ws1.title = "実績年次"
    r = 1
    if meta:
        ws1.cell(row=r, column=1, value=meta)
        r += 1
    if df_actual is not None and not df_actual.empty:
        for r_idx, row in enumerate(
            dataframe_to_rows(df_actual, index=False, header=True), start=0
        ):
            for c_idx, value in enumerate(row, start=1):
                ws1.cell(row=r + r_idx, column=c_idx, value=value)
    else:
        ws1.cell(row=r, column=1, value="（実績なし）")

    ws2 = wb.create_sheet(title="予測")
    r2 = 1
    if df_forecast is not None and not df_forecast.empty:
        for r_idx, row in enumerate(
            dataframe_to_rows(df_forecast, index=False, header=True), start=0
        ):
            for c_idx, value in enumerate(row, start=1):
                ws2.cell(row=r2 + r_idx, column=c_idx, value=value)
    else:
        ws2.cell(row=r2, column=1, value="（予測なし）")

    try:
        wb.save(str(path))
    except OSError as e:
        raise ExportError(
            f"Excel ファイルの保存に失敗しました（他アプリで開いていませんか）: {e}"
        ) from e
    except Exception as e:
        raise ExportError(f"Excel 出力中にエラーが発生しました: {e}") from e
