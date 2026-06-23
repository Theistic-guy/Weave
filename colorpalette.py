from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import List, Optional

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QToolButton,
    QVBoxLayout,
    QWidget,
    QSizePolicy,
)


@dataclass(frozen=True)
class PaletteColor:
    name: str
    base_hex: str


PALETTE: List[PaletteColor] = [
    PaletteColor("Neutral", "#000000"),
    PaletteColor("Red", "#e53935"),
    PaletteColor("Orange", "#fb8c00"),
    PaletteColor("Amber", "#ffb300"),
    PaletteColor("Yellow", "#fdd835"),
    PaletteColor("Lime", "#c0ca33"),
    PaletteColor("Green", "#43a047"),
    PaletteColor("Emerald", "#2e7d32"),
    PaletteColor("Teal", "#00897b"),
    PaletteColor("Cyan", "#00acc1"),
    PaletteColor("Sky", "#039be5"),
    PaletteColor("Blue", "#1e88e5"),
    PaletteColor("Indigo", "#3949ab"),
    PaletteColor("Violet", "#5e35b1"),
    PaletteColor("Purple", "#8e24aa"),
    PaletteColor("Magenta", "#d81b60"),
    PaletteColor("Pink", "#ec407a"),
    PaletteColor("Rose", "#f06292"),
    PaletteColor("Coral", "#ff7043"),
    PaletteColor("Gold", "#c9a227"),
    PaletteColor("Brown", "#8d6e63"),
    PaletteColor("Sand", "#bca58a"),
    PaletteColor("Olive", "#6b8e23"),
    PaletteColor("Mint", "#4db6ac"),
    PaletteColor("Slate", "#607d8b"),
    PaletteColor("Gray", "#78909c"),
    PaletteColor("Stone", "#757575"),
    PaletteColor("Navy", "#283593"),
    PaletteColor("Plum", "#7e57c2"),
    PaletteColor("Silver", "#b0bec5"),
    PaletteColor("Charcoal", "#455a64"),
]


def theme_color(base_hex: str, dark_theme: bool) -> str:
    """Return the theme-aware preview color for a palette entry."""
    base_hex = base_hex.lower()

    if base_hex == "#000000":
        return "#FFFFFF" if dark_theme else "#000000"
    if base_hex == "#ffffff":
        return "#000000" if not dark_theme else "#FFFFFF"

    c = QColor(base_hex)
    if not c.isValid():
        return base_hex

    h, s, v, a = c.getHsv()

    if dark_theme:
        v = min(255, int(v * 1.14) + 8)
        s = min(255, int(s * 1.03))
    else:
        v = max(0, int(v * 0.94))
        s = max(0, int(s * 0.98))

    c.setHsv(h, s, v, a)
    return c.name()


def text_contrast_color(bg: QColor) -> str:
    return "#111111" if bg.lightness() > 170 else "#f5f5f5"


class SwatchButton(QFrame):
    clicked = pyqtSignal(str, str)  # name, base hex

    def __init__(self, name: str, base_hex: str, dark_theme: bool, parent=None):
        super().__init__(parent)
        self.name = name
        self.base_hex = base_hex
        self._dark_theme = dark_theme
        self._selected = False

        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setMinimumHeight(72)
        self.setObjectName("SwatchButton")

        self._label = QLabel(name)
        self._label.setWordWrap(True)
        self._label.setAttribute(Qt.WA_TransparentForMouseEvents)

        self._sub = QLabel("")
        self._sub.setAttribute(Qt.WA_TransparentForMouseEvents)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 9, 10, 8)
        lay.setSpacing(6)
        lay.addWidget(self._label)
        lay.addWidget(self._sub)

        self._apply_style()

    def set_theme(self, dark_theme: bool):
        self._dark_theme = dark_theme
        self._apply_style()

    def set_selected(self, selected: bool):
        self._selected = selected
        self._apply_style()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.name, self.base_hex)
            event.accept()
            return
        super().mousePressEvent(event)

    def _apply_style(self):
        display_hex = theme_color(self.base_hex, self._dark_theme)
        base = QColor(display_hex)
        txt = text_contrast_color(base)
        border = "2px solid #6c63ff" if self._selected else "1px solid rgba(0,0,0,0.10)"

        self.setStyleSheet(
            f"QFrame#SwatchButton {{ background:{display_hex}; border-radius:12px; border:{border}; }}"
        )
        self._label.setStyleSheet(
            f"QLabel {{ color:{txt}; background:transparent; font-weight:600; font-size:12px; }}"
        )
        self._sub.setText(display_hex.upper())
        self._sub.setStyleSheet(
            f"QLabel {{ color:{txt}; background:transparent; font-size:10px; }}"
        )


class ColorPaletteDialog(QDialog):
    colorSelected = pyqtSignal(str, str)  # name, base hex

    def __init__(self, dark_theme: bool = False, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Choose Color")
        self.setModal(True)
        self.resize(920, 700)
        self.setMinimumSize(760, 540)

        self._dark_theme = dark_theme
        self._current_selected: Optional[SwatchButton] = None
        self._cards: List[SwatchButton] = []
        self.selected_color: Optional[str] = None
        self.selected_name: Optional[str] = None

        self._build_ui()
        self._apply_theme()
        self._populate_cards()
        self.search.setFocus()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(12)

        top = QHBoxLayout()
        top.setSpacing(8)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search color…")
        self.search.textChanged.connect(self._filter_cards)
        self.search.setClearButtonEnabled(True)
        self.search.setFixedHeight(30)
        self.search.setObjectName("PaletteSearch")

        self.theme_btn = QToolButton()
        self.theme_btn.setCheckable(True)
        self.theme_btn.setChecked(self._dark_theme)
        self.theme_btn.setToolTip("Toggle theme preview")
        self.theme_btn.setFixedSize(34, 34)
        self.theme_btn.clicked.connect(self._toggle_theme)

        top.addWidget(self.search, 1)
        top.addWidget(self.theme_btn)
        root.addLayout(top)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.content = QWidget()
        self.grid = QGridLayout(self.content)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(12)
        self.grid.setVerticalSpacing(12)
        self.scroll.setWidget(self.content)

        root.addWidget(self.scroll, 1)

    def _apply_theme(self):
        if self._dark_theme:
            bg = "#121418"
            panel = "#1a1f26"
            card = "#202733"
            text = "#eef2ff"
            border = "#2d3644"
            search_bg = "#0f1318"
        else:
            bg = "#f4f6fb"
            panel = "#ffffff"
            card = "#ffffff"
            text = "#1f2937"
            border = "#d8dee9"
            search_bg = "#ffffff"

        self.setStyleSheet(
            f"QDialog {{ background:{bg}; }}"
            f"QLineEdit#PaletteSearch {{ background:{search_bg}; color:{text}; border:1px solid {border}; border-radius:10px; padding:5px 10px; font-size:12px; }}"
            f"QLineEdit#PaletteSearch:focus {{ border:1px solid #6c63ff; }}"
            f"QToolButton {{ background:{panel}; color:{text}; border:1px solid {border}; border-radius:10px; }}"
            f"QToolButton:hover {{ background:{card}; }}"
            f"QScrollArea {{ background:transparent; border:none; }}"
        )

        self.scroll.viewport().setStyleSheet(f"background:{bg}; border:none;")
        self.content.setStyleSheet(f"background:{bg};")

        self.theme_btn.setText("☾" if self._dark_theme else "☀")
        self.theme_btn.setStyleSheet("QToolButton { font-size:16px; font-weight:700; }")
        for card in self._cards:
            card.set_theme(self._dark_theme)

    def _populate_cards(self):
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self._cards.clear()
        cols = 3
        for i, item in enumerate(PALETTE):
            card = SwatchButton(item.name, item.base_hex, self._dark_theme)
            card.clicked.connect(self._on_color_clicked)
            self._cards.append(card)
            self.grid.addWidget(card, i // cols, i % cols)

    def _filter_cards(self, query: str):
        q = query.strip().lower()
        for card in self._cards:
            card.setVisible(not q or q in card.name.lower())

    def _toggle_theme(self):
        self._dark_theme = self.theme_btn.isChecked()
        self._apply_theme()

    def _on_color_clicked(self, name: str, base_hex: str):
        self.selected_name = name
        self.selected_color = base_hex
        for c in self._cards:
            c.set_selected(False)
        sender = self.sender()
        if isinstance(sender, SwatchButton):
            sender.set_selected(True)
            self._current_selected = sender
        self.colorSelected.emit(name, base_hex)
        self.accept()

    def showEvent(self, event):
        super().showEvent(event)
        self.search.setFocus()
        self.search.selectAll()


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    dlg = ColorPaletteDialog(dark_theme=False)

    def on_pick(name: str, hex_color: str):
        print(f"Picked: {name} -> {hex_color}")

    dlg.colorSelected.connect(on_pick)
    dlg.exec_()


if __name__ == "__main__":
    main()
