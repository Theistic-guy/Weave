from colorpalette import ColorPaletteDialog,theme_color
import config
from PyQt5.QtGui import  QColor

def pick_color(parent=None, current_color=None):
    dlg = ColorPaletteDialog(
        dark_theme=is_dark_theme(),
        parent=parent,
    )

    selected = {"color": None}

    def on_pick(name, hex_color):
        selected["color"] = hex_color

    dlg.colorSelected.connect(on_pick)

    if dlg.exec_():
        return selected["color"]

    return None

def is_dark_theme()->bool:
    return (True if config.CURRENT_THEME == "dark" else False)


def graph_color(hex_color: str) -> QColor:
    return QColor(
        theme_color(
            hex_color,
            is_dark_theme()
        )
    )