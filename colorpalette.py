from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import List, Tuple

from PyQt5.QtCore import Qt, pyqtSignal, QSize
from PyQt5.QtGui import QColor, QFont, QPainter, QIcon, QPixmap
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


# -----------------------------------------------------------------------------
# Palette data
# -----------------------------------------------------------------------------

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


# -----------------------------------------------------------------------------
# Color helpers
# -----------------------------------------------------------------------------

def _mix(a: QColor, b: QColor, t: float) -> QColor:
    t = max(0.0, min(1.0, t))
    return QColor(
        round(a.red() * (1 - t) + b.red() * t),
        round(a.green() * (1 - t) + b.green() * t),
        round(a.blue() * (1 - t) + b.blue() * t),
    )


def _shade_hex(hex_color: str, amount: float, dark_theme: bool) -> str:
    """Return a theme-aware shade of the base color.

    amount is in [0..1].
    For light theme, we bias a little toward white for the lighter swatches and
    darken for the deeper swatches.
    For dark theme, we keep the swatches more saturated and visible on a dark
    background by biasing less toward black and slightly toward white.
    """
    c = QColor(hex_color)
    if not c.isValid():
        return hex_color

    white = QColor("#ffffff")
    black = QColor("#000000")

    if dark_theme:
        # Swatches should remain visible on dark backgrounds.
        # 0.0 -> slightly lighter than base, 1.0 -> brighter/livelier.
        lighter = _mix(c, white, 0.18 + amount * 0.32)
        darker = _mix(c, black, 0.10 + amount * 0.12)
        # blend mostly toward the lighter direction for dark mode
        result = _mix(darker, lighter, 0.72)
    else:
        # Swatches should remain visible on light backgrounds.
        # 0.0 -> slightly darker than base, 1.0 -> even darker.
        lighter = _mix(c, white, 0.10 + amount * 0.20)
        darker = _mix(c, black, 0.12 + amount * 0.36)
        result = _mix(lighter, darker, 0.62)

    return result.name()


def make_theme_shades(base_hex: str, dark_theme: bool) -> List[str]:
    if base_hex == "#000000":
        if dark_theme:
            return ["#ffffff","#ffffff","#ffffff","#ffffff","#ffffff"]
    elif base_hex == "#ffffff":
        if not dark_theme:
            return ["#000000","#000000","#000000","#000000","#000000"]
             
    # Five shades from subtle to stronger.
    levels = [0.0, 0.25, 0.5, 0.75, 1.0]
    return [_shade_hex(base_hex, amt, dark_theme) for amt in levels]


def text_contrast_color(bg: QColor) -> str:
    # Simple readable text choice for labels on swatches.
    return "#111111" if bg.lightness() > 170 else "#f5f5f5"


# -----------------------------------------------------------------------------
# Swatch widget
# -----------------------------------------------------------------------------

class SwatchButton(QFrame):
    clicked = pyqtSignal(str, str)  # name, hex

    def __init__(self, name: str, shades: List[str], parent=None):
        super().__init__(parent)
        self.name = name
        self.shades = shades
        self._selected = False
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setMinimumHeight(72)
        self.setObjectName("SwatchButton")

        self._label = QLabel(name)
        self._label.setWordWrap(True)
        self._label.setAttribute(Qt.WA_TransparentForMouseEvents)

        self._sub = QLabel(shades[2].upper())
        self._sub.setAttribute(Qt.WA_TransparentForMouseEvents)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 9, 10, 8)
        lay.setSpacing(6)
        lay.addWidget(self._label)
        lay.addWidget(self._sub)

        self._apply_style()

    def set_shades(self, shades: List[str]):
        self.shades = shades
        self._sub.setText(shades[2].upper())
        self._apply_style()

    def set_selected(self, selected: bool):
        self._selected = selected
        self._apply_style()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            print("SWATCH CLICKED:", self.name, self.shades[2])
            self.clicked.emit(self.name, self.shades[2])
            event.accept()
            return
        super().mousePressEvent(event)

    def _apply_style(self):
        base = QColor(self.shades[2])
        txt = text_contrast_color(base)
        border = "2px solid #6c63ff" if self._selected else "1px solid rgba(0,0,0,0.12)"
        shadow = "box-shadow: 0 0 0 1px rgba(0,0,0,0.04);"
        self.setStyleSheet(
            f"QFrame#SwatchButton {{"
            f" background:{base.name()};"
            f" border-radius:12px;"
            f" border:{border};"
            f"}}"
        )
        self._label.setStyleSheet(
            f"QLabel {{ color:{txt}; background:transparent; font-weight:600; font-size:12px; }}"
        )
        self._sub.setStyleSheet(
            f"QLabel {{ color:{txt}; background:transparent; font-size:10px; opacity:0.92; }}"
        )


# -----------------------------------------------------------------------------
# Dialog
# -----------------------------------------------------------------------------

class ColorPaletteDialog(QDialog):
    colorSelected = pyqtSignal(str, str)  # name, hex

    def __init__(self, dark_theme: bool = False, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Choose Color")
        self.setModal(True)
        self.resize(920, 700)
        self.setMinimumSize(760, 540)
        self._dark_theme = dark_theme
        self._current_selected: SwatchButton | None = None
        self._cards: List[SwatchButton] = []
        self.selected_color = None

        self._build_ui()
        self._apply_theme()
        self._populate_cards()
        self.search.setFocus()

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(12)

        # Top bar
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

        # Scrollable grid
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
        
        # App chrome only.
        if self._dark_theme:
            bg = "#121418"
            panel = "#1a1f26"
            card = "#202733"
            text = "#eef2ff"
            muted = "#9ca3af"
            border = "#2d3644"
            search_bg = "#0f1318"
        else:
            bg = "#f4f6fb"
            panel = "#ffffff"
            card = "#ffffff"
            text = "#1f2937"
            muted = "#6b7280"
            border = "#d8dee9"
            search_bg = "#ffffff"

        self.content.setStyleSheet(
            f"background:transparent;"
        )
        self.setStyleSheet(
            f"QDialog {{ background:{bg}; }}"
            f"QLineEdit#PaletteSearch {{"
            f" background:{search_bg}; color:{text}; border:1px solid {border};"
            f" border-radius:10px; padding:5px 10px; font-size:12px; }}"
            f"QLineEdit#PaletteSearch:focus {{ border:1px solid #6c63ff; }}"
            f"QToolButton {{ background:{panel}; color:{text}; border:1px solid {border};"
            f" border-radius:10px; }}"
            f"QToolButton:hover {{ background:{card}; }}"
            f"QScrollArea {{ background:transparent; border:none; }}"
        )
        self.theme_btn.setText("☾" if self._dark_theme else "☀")
        self.theme_btn.setStyleSheet(
            f"QToolButton {{ font-size:16px; font-weight:700; }}"
        )

        # update cards if they already exist
        for card in self._cards:
            card.set_shades(make_theme_shades(card.name_hex_base, self._dark_theme))

    def _populate_cards(self):
        # clear any existing
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self._cards.clear()

        # 3 columns on average; cards will flow into rows.
        cols = 3
        for i, item in enumerate(PALETTE):
            shades = make_theme_shades(item.base_hex, self._dark_theme)
            card = SwatchButton(item.name, shades)
            card.name_hex_base = item.base_hex  # keep for theme switching
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
        self._refresh_shades()

    def _refresh_shades(self):
        for card, base in zip(self._cards, PALETTE):
            shades = make_theme_shades(base.base_hex, self._dark_theme)
            card.set_shades(shades)
        # preserve selection visuals
        if self._current_selected:
            self._current_selected.set_selected(True)

    def _on_color_clicked(self, name: str, hex_color: str):
        self.selected_color = hex_color
        for c in self._cards:
            c.set_selected(False)
        sender = self.sender()
        if isinstance(sender, SwatchButton):
            sender.set_selected(True)
            self._current_selected = sender
        self.colorSelected.emit(name, hex_color)
        self.accept()

    def showEvent(self, event):
        super().showEvent(event)
        self.search.setFocus()
        self.search.selectAll()


# -----------------------------------------------------------------------------
# Demo launcher
# -----------------------------------------------------------------------------

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
