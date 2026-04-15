# -*- coding: utf-8 -*-
"""アプリ全体の定数・既定値（仕様書・依頼仕様に準拠）"""

from pathlib import Path

# --- 表示・識別名（名称統一） ---
APP_DISPLAY_NAME = "顧客別納入分析システム"
WINDOW_TITLE = "顧客別納入分析システム - Customer Delivery Analytics"
EXE_BASENAME = "顧客別納入分析システム"
APP_ICON_PNG = ("docs", "icon.png")
APP_ICON_ICO = ("docs", "icon.ico")

# --- Access 繝・・繧ｿ繝吶・繧ｹ・亥盾辣ｧ蟆ら畑繝ｻUNC・・---
# 既定は .accdb の実ファイルを指す UNC。必要なら環境変数 CDA_ACCESS_DB で上書き。
DEFAULT_ACCESS_DB_PATH = r"\\192.168.1.200\共有\生産管理課\受注データApp.accdb"
ENV_ACCESS_DB = "CDA_ACCESS_DB"

# --- 実績対象期間（仕様） ---
DEFAULT_YEAR_START = 2018
DEFAULT_YEAR_END = 2025

# --- ODBC ドライバ候補（環境により名称が異なる場合がある） ---
ACCESS_ODBC_DRIVERS_PREFERRED = [
    "Microsoft Access Driver (*.mdb, *.accdb)",
    "Microsoft Access Driver (*.mdb)",
]


def resolve_access_db_path() -> str:
    """Access ファイルパスを解決する（環境変数優先）。"""
    import os

    override = os.environ.get(ENV_ACCESS_DB, "").strip()
    if override:
        return override
    return DEFAULT_ACCESS_DB_PATH


def project_root() -> Path:
    """開発時はリポジトリルート、exe 化時は実行ファイルの親を返す目安。"""
    import sys

    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent.parent


def resource_root() -> Path:
    """同梱リソースの基準ディレクトリ。PyInstaller onefile では展開先を返す。"""
    import sys

    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent.parent


def resource_path(*parts: str) -> Path:
    return resource_root().joinpath(*parts)


def app_icon_png_path() -> Path:
    return resource_path(*APP_ICON_PNG)


def app_icon_ico_path() -> Path:
    return resource_path(*APP_ICON_ICO)
