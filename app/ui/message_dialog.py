# -*- coding: utf-8 -*-
"""スピナー表示に寄せたカード型メッセージダイアログ。"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QGuiApplication
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class MessageDialog(QDialog):
    def __init__(
        self,
        parent: QWidget | None,
        *,
        title: str,
        text: str,
        level: str = "info",
    ) -> None:
        super().__init__(parent)
        self.setObjectName("messageDialog")
        self.setModal(True)
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.CustomizeWindowHint
        )
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._card = QFrame(self)
        self._card.setObjectName("messageCard")
        card_lay = QVBoxLayout(self._card)
        card_lay.setContentsMargins(28, 26, 28, 24)
        card_lay.setSpacing(16)

        badge = QLabel(self._badge_text(level), self._card)
        badge.setObjectName("messageBadge")
        badge.setProperty("level", level)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setFixedSize(42, 42)

        title_lbl = QLabel(title, self._card)
        title_lbl.setObjectName("messageTitle")
        title_lbl.setWordWrap(True)
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        body_lbl = QLabel(text, self._card)
        body_lbl.setObjectName("messageBody")
        body_lbl.setWordWrap(True)
        body_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        body_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        ok_btn = QPushButton("OK", self._card)
        ok_btn.setObjectName("messagePrimaryButton")
        ok_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        ok_btn.clicked.connect(self.accept)
        ok_btn.setDefault(True)
        ok_btn.setMinimumWidth(124)

        card_lay.addWidget(badge, alignment=Qt.AlignmentFlag.AlignCenter)
        card_lay.addWidget(title_lbl)
        card_lay.addWidget(body_lbl)
        card_lay.addWidget(ok_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self._card)

        shadow = QGraphicsDropShadowEffect(self._card)
        shadow.setBlurRadius(28)
        shadow.setYOffset(10)
        shadow.setXOffset(0)
        shadow.setColor(QColor(15, 23, 42, 55))
        self._card.setGraphicsEffect(shadow)

        self.setMinimumWidth(360)
        self.adjustSize()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self._move_to_center()

    @staticmethod
    def _badge_text(level: str) -> str:
        if level == "error":
            return "!"
        if level == "warning":
            return "!"
        return "i"

    def _move_to_center(self) -> None:
        parent = self.parentWidget()
        if parent is not None:
            center = parent.frameGeometry().center()
            self.move(center.x() - self.width() // 2, center.y() - self.height() // 2)
            return
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return
        rect = screen.availableGeometry()
        self.move(rect.center().x() - self.width() // 2, rect.center().y() - self.height() // 2)


def show_information(parent: QWidget | None, title: str, text: str) -> int:
    return MessageDialog(parent, title=title, text=text, level="info").exec()


def show_warning(parent: QWidget | None, title: str, text: str) -> int:
    return MessageDialog(parent, title=title, text=text, level="warning").exec()


def show_critical(parent: QWidget | None, title: str, text: str) -> int:
    return MessageDialog(parent, title=title, text=text, level="error").exec()
