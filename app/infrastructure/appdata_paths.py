# -*- coding: utf-8 -*-
"""AppData 配下の保存先管理。"""

from __future__ import annotations

import os
from pathlib import Path

from app.config import settings


class AppDataPaths:
    """外部指標キャッシュの保存先を返す。"""

    def __init__(self) -> None:
        base = os.environ.get("LOCALAPPDATA", "").strip()
        if base:
            self._base_dir = Path(base) / settings.APP_DISPLAY_NAME
        else:
            self._base_dir = Path.home() / ".customer_delivery_analytics"

    def base_dir(self) -> Path:
        self._base_dir.mkdir(parents=True, exist_ok=True)
        return self._base_dir

    def indicators_db_path(self) -> Path:
        return self.base_dir() / "external_indicators.db"

