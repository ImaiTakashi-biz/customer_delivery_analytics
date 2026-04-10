# -*- coding: utf-8 -*-
"""処理中に親ウィジェット上へ半透明オーバーレイ＋不定プログレス（スピナー風）を重ねる。"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)


class BusyOverlay(QFrame):
    """親の矩形いっぱいに表示し、背面をブロックする待機 UI（Web 風の浮きカード）。"""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("busyOverlay")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addStretch()

        self._card = QFrame()
        self._card.setObjectName("busyCard")
        card_lay = QVBoxLayout(self._card)
        card_lay.setContentsMargins(28, 28, 28, 28)
        card_lay.setSpacing(18)
        card_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._label = QLabel()
        self._label.setObjectName("busyLabel")
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setWordWrap(True)

        self._bar = QProgressBar()
        self._bar.setObjectName("busyProgress")
        self._bar.setRange(0, 0)
        self._bar.setFixedWidth(280)
        self._bar.setTextVisible(False)

        card_lay.addWidget(self._label)
        card_lay.addWidget(self._bar, alignment=Qt.AlignmentFlag.AlignCenter)

        shadow = QGraphicsDropShadowEffect(self._card)
        shadow.setBlurRadius(28)
        shadow.setYOffset(10)
        shadow.setXOffset(0)
        shadow.setColor(QColor(15, 23, 42, 55))
        self._card.setGraphicsEffect(shadow)

        lay.addWidget(self._card, alignment=Qt.AlignmentFlag.AlignCenter)
        lay.addStretch()

        self.hide()
        parent.installEventFilter(self)
        self._sync_geometry()

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # noqa: N802
        if obj is self.parent() and event.type() == QEvent.Type.Resize:
            self._sync_geometry()
        return super().eventFilter(obj, event)

    def _sync_geometry(self) -> None:
        p = self.parent()
        if p is not None:
            self.setGeometry(p.rect())

    def show_message(self, message: str) -> None:
        """オーバーレイを最前面に出し、メッセージを表示する。"""
        self._label.setText(message)
        self._sync_geometry()
        self.raise_()
        self.show()

    def hide_overlay(self) -> None:
        """オーバーレイを隠す。"""
        self.hide()
