from colorpalette import ColorPaletteDialog
import config

def pick_color(parent=None, current_color=None):
    dlg = ColorPaletteDialog(
        dark_theme=is_dark_theme(),
        parent=parent,
    )

    selected = {"color": None}

    def on_pick(name, hex_color):
        print("PICK_COLOR RECEIVED:", name, hex_color)
        selected["color"] = hex_color

    dlg.colorSelected.connect(on_pick)

    if dlg.exec_():
        return selected["color"]

    return None

def is_dark_theme()->bool:
    return (True if config.CURRENT_THEME == "dark" else False)