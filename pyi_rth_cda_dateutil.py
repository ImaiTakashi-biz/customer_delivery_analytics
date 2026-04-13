# -*- coding: utf-8 -*-
"""
PyInstaller 用ランタイムフック（--runtime-hook で指定）。

PyInstaller はカスタム rthook を公式の pyi_rth_inspect / pyi_rth_pyside6 より先に実行する。
PySide6 の rthook が QtCore を import すると Shiboken の import 連携が有効になり、
その後 dateutil が six.moves を通ると inspect（pyi_rth_inspect のパッチ）と衝突し
「_SixMetaPathImporter に _path がない」となる。

main.py は pandas のあと matplotlib.dates を import するが、
matplotlib.dates は dateutil.rrule 等を読み込み、rrule は six.moves を使う。
Shiboken 有効化より前に、当該 dateutil 経路をすべて sys.modules に載せておく。
"""

from __future__ import annotations

import sys

if getattr(sys, "frozen", False):
    _preloads = (
        "dateutil.tz",
        "dateutil.rrule",
        "dateutil.relativedelta",
        "dateutil.parser",
    )
    for _name in _preloads:
        try:
            __import__(_name)
        except Exception:
            pass
