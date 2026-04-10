# -*- coding: utf-8 -*-
"""Web アプリ風の入力（フィルタ付きコンボ・クリックで開く日付）。"""

from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import QDate, QEvent, QModelIndex, QObject, Qt, QTimer
from PySide6.QtGui import QColor, QKeyEvent, QMouseEvent, QPaintEvent, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QApplication,
    QComboBox,
    QDateEdit,
    QDialog,
)

from app.ui.date_picker_dialog import WebDatePickerDialog


class FilterableComboBox(QComboBox):
    """
    入力可能で、入力文字で候補を絞り込むコンボ。
    ドロップ矢印は QSS で非表示。
    単クリックで一覧を開く（一覧表示後も lineEdit にフォーカスを戻す）。
    Alt+↓・F4 でも開ける。
    """

    def __init__(
        self,
        parent=None,
        *,
        include_all_option: bool = False,
        all_option_label: str = "（すべて）",
        max_visible: int = 12,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("webCombo")
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        # 先頭候補への自動補完は lineEdit を上書きし、部分入力・削除を壊すため無効化
        self.setCompleter(None)
        self.setMaxVisibleItems(max_visible)
        self._include_all = include_all_option
        self._all_option_label = all_option_label
        self._all_items: list[str] = []
        self._filter_scheduled = False

        le = self.lineEdit()
        le.textEdited.connect(self._schedule_refill)
        le.installEventFilter(self)
        # 一覧表示時も lineEdit をアクティブに保つ（ビューが FocusIn で奪うのを抑止）
        v = self.view()
        if v is not None:
            v.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            v.installEventFilter(self)
            vp = v.viewport()
            if vp is not None:
                vp.setFocusPolicy(Qt.FocusPolicy.NoFocus)
                vp.installEventFilter(self)
        self.setToolTip(
            "クリックで一覧を開きます（入力欄のフォーカスは維持されます）。"
            "入力で候補を絞り込めます。Alt+↓・F4 でも一覧を開けます。"
        )

    def source_items(self) -> List[str]:
        """マスタ一覧（（すべて）を除く）。"""
        return list(self._all_items)

    def choices_for_dialog(self) -> List[str]:
        """子ダイアログに渡す全候補（（すべて）を含む場合あり）。"""
        if self._include_all:
            return [self._all_option_label, *self._all_items]
        return list(self._all_items)

    def set_source_items(self, items: List[str]) -> None:
        """候補のマスタをセットし、表示をリセットする（順序は引数の出現順で重複のみ除去）。"""
        seen = set()
        ordered: list[str] = []
        for x in items:
            s = str(x).strip()
            if not s or s in seen:
                continue
            seen.add(s)
            ordered.append(s)
        self._all_items = ordered
        if self._include_all:
            le = self.lineEdit()
            le.blockSignals(True)
            le.setText("")
            le.blockSignals(False)
            self._refill_from_filter("")
        else:
            self._refill_from_filter("")

    def setPlaceholderText(self, text: str) -> None:
        """プレースホルダ（Qt6 の QLineEdit と同様の見た目はスタイルで補う）。"""
        self.lineEdit().setPlaceholderText(text)

    def _schedule_refill(self, _text: str) -> None:
        if self._filter_scheduled:
            return
        self._filter_scheduled = True
        QTimer.singleShot(30, self._run_refill)

    def _run_refill(self) -> None:
        self._filter_scheduled = False
        # 開いたまま clear するとポップアップと入力が競合するため、一旦閉じて再オープンする
        popup_open = self.view() is not None and self.view().isVisible()
        if popup_open:
            self.hidePopup()
        self._refill_from_filter(None)
        if popup_open:
            QTimer.singleShot(0, self._reopen_popup_only)

    def _reopen_popup_only(self) -> None:
        """絞り込み後に一覧だけ再度表示（_refill は済んでいるので親の showPopup のみ）。"""
        if not self.isVisible():
            return
        v = self.view()
        if v is not None:
            v.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        super().showPopup()
        QTimer.singleShot(0, self._after_popup_open)
        QTimer.singleShot(10, self._after_popup_open)
        QTimer.singleShot(40, self._after_popup_open)

    def _refill_from_filter(self, raw_text: Optional[str] = None) -> None:
        cur = self.lineEdit().text()
        src = cur if raw_text is None else raw_text
        needle = (src or "").strip().lower()
        # 「（すべて）」表示中は候補一覧を全件出す（部分一致フィルタにかけない）
        if self._include_all and (src or "").strip() == self._all_option_label:
            needle = ""

        le = self.lineEdit()
        pos = le.cursorPosition()

        self.blockSignals(True)
        self.clear()

        def add_all_option() -> bool:
            if not self._include_all:
                return False
            if not needle:
                return True
            return needle in self._all_option_label.lower()

        if add_all_option():
            self.addItem(self._all_option_label)

        for name in self._all_items:
            if not needle or needle in name.lower():
                self.addItem(name)

        # addItem 後は currentIndex が 0 になり、編集可能コンボが先頭行のテキストで lineEdit を上書きする。
        # -1 にしてから入力文字列を戻す（削除・部分一致が効くようにする）。
        le.blockSignals(True)
        self.setCurrentIndex(-1)
        le.setText(cur)
        # 絞り込み後もキャレット位置を維持（従来は末尾に飛び入力しづらかった）
        new_pos = min(max(0, pos), len(cur))
        le.setCursorPosition(new_pos)
        le.blockSignals(False)
        self.blockSignals(False)

    def showPopup(self) -> None:
        self._refill_from_filter(None)
        v = self.view()
        if v is not None:
            v.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        super().showPopup()
        QTimer.singleShot(0, self._after_popup_open)
        QTimer.singleShot(10, self._after_popup_open)
        QTimer.singleShot(40, self._after_popup_open)

    def _after_popup_open(self) -> None:
        """一覧の先頭ハイライトを外し、フォーカスを lineEdit に戻す。"""
        self._clear_popup_row_highlight()
        self._keep_focus_in_line_edit()

    def _clear_popup_row_highlight(self) -> None:
        """ポップアップ内の現在行表示を消す（入力欄に留まる見た目にする）。"""
        v = self.view()
        if v is None:
            return
        v.setCurrentIndex(QModelIndex())
        sm = v.selectionModel()
        if sm is not None:
            sm.clearSelection()
            sm.clearCurrentIndex()

    def _keep_focus_in_line_edit(self) -> None:
        """ポップアップ直後にフォーカスを入力欄へ戻し、連続入力できるようにする。"""
        if not self.isVisible():
            return
        le = self.lineEdit()
        win = self.window()
        if win is not None:
            win.activateWindow()
            win.raise_()
            QApplication.setActiveWindow(win)
        self.activateWindow()
        le.setFocus(Qt.FocusReason.ActiveWindowFocusReason)
        le.activateWindow()

    def _reassert_line_edit_if_popup_visible(self) -> None:
        """ポップアップ表示中にフォーカスが一覧側へ逃げたとき、入力へ戻す。"""
        v = self.view()
        if v is None or not v.isVisible():
            return
        le = self.lineEdit()
        if le.hasFocus():
            return
        fw = QApplication.focusWidget()
        pop = v.window()
        if pop is None:
            self._after_popup_open()
            return
        w = fw
        while w is not None:
            if w == pop and fw is not le:
                self._after_popup_open()
                return
            w = w.parentWidget()

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        v = self.view()
        if v is not None and (obj is v or obj is v.viewport()):
            if event.type() == QEvent.Type.FocusIn:
                QTimer.singleShot(0, self._after_popup_open)
                return True
            return False

        if obj != self.lineEdit():
            return False
        if event.type() == QEvent.Type.FocusOut:
            QTimer.singleShot(0, self._reassert_line_edit_if_popup_visible)
        if isinstance(event, QMouseEvent):
            if (
                event.type() == QEvent.Type.MouseButtonPress
                and event.button() == Qt.MouseButton.LeftButton
            ):
                QTimer.singleShot(0, self.showPopup)
            return False
        if isinstance(event, QKeyEvent) and event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_F4 and event.modifiers() == Qt.KeyboardModifier.NoModifier:
                QTimer.singleShot(0, self.showPopup)
                return True
            if (
                event.key() == Qt.Key.Key_Down
                and event.modifiers() == Qt.KeyboardModifier.AltModifier
            ):
                QTimer.singleShot(0, self.showPopup)
                return True
        return False


class ClickToOpenComboBox(QComboBox):
    """編集不可コンボ。矢印を消し、クリックで必ずポップアップ。"""

    def __init__(self, parent=None, *, max_visible: int = 10) -> None:
        super().__init__(parent)
        self.setObjectName("webComboReadOnly")
        self.setEditable(False)
        self.setMaxVisibleItems(max_visible)
        self.setToolTip("クリックで一覧を開きます。")

    def mousePressEvent(self, event) -> None:
        super().mousePressEvent(event)
        QTimer.singleShot(0, self.showPopup)


class ClickableDateEdit(QDateEdit):
    """
    矢印は QSS で非表示。クリックで Web 風の日付選択ダイアログを開く。
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("webDateEdit")
        self.setCalendarPopup(False)
        # 右端のセクション上下矢印（スピンボタン）を非表示（クリックでカレンダーのみ）
        self.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.setDisplayFormat("yyyy/MM/dd")
        self.setSpecialValueText("年 / 月 / 日")
        self.lineEdit().installEventFilter(self)
        # 同一クリックで singleShot が二重登録され、ダイアログ終了直後に再度開くのを防ぐ
        self._picker_open = False

    def paintEvent(self, event: QPaintEvent) -> None:
        """QSS の data:URL は Windows で壊れるため、右端にカレンダーアイコンを自前描画する。"""
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        col = QColor("#64748b")
        if not self.isEnabled():
            col = QColor("#cbd5e1")
        pen = QPen(col)
        pen.setWidthF(1.25)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        iw, ih = 18, 18
        margin = 14
        x0 = self.width() - margin - iw
        y0 = (self.height() - ih) // 2
        # 本体枠
        p.drawRoundedRect(x0 + 3, y0 + 4, 12, 10, 1.5, 1.5)
        # 横線（月見出し下）
        p.drawLine(x0 + 3, y0 + 8, x0 + 15, y0 + 8)
        # 吊り下げ（日付ピン）
        p.drawLine(x0 + 6, y0 + 3, x0 + 6, y0 + 6)
        p.drawLine(x0 + 12, y0 + 3, x0 + 12, y0 + 6)
        p.end()

    def _open_calendar_dialog(self) -> None:
        if not self.isEnabled() or self._picker_open:
            return
        self._picker_open = True
        cur = self.date()
        st = self.specialValueText()
        if st and cur == self.minimumDate():
            init = QDate.currentDate()
        else:
            init = cur
        if init < self.minimumDate():
            init = self.minimumDate()
        if init > self.maximumDate():
            init = self.maximumDate()

        try:
            dlg = WebDatePickerDialog(
                self,
                self.minimumDate(),
                self.maximumDate(),
                init,
            )
            if dlg.exec() == QDialog.DialogCode.Accepted:
                self.setDate(dlg.selected_date())
        finally:
            self._picker_open = False

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if (
            obj == self.lineEdit()
            and isinstance(event, QMouseEvent)
            and event.type() == QEvent.Type.MouseButtonPress
            and event.button() == Qt.MouseButton.LeftButton
            and self.isEnabled()
        ):
            QTimer.singleShot(0, self._open_calendar_dialog)
        return False

    def mousePressEvent(self, event) -> None:
        super().mousePressEvent(event)
        if self.isEnabled():
            QTimer.singleShot(0, self._open_calendar_dialog)
