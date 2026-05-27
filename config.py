import uuid
from PyQt5.QtGui import QColor

THEMES = {
    "light": {
        "BG_DARK":      "#ffffff", "BG_PANEL":     "#f8f9fa",
        "BG_CARD":      "#ffffff", "ACCENT":       "#4c84ff",
        "ACCENT2":      "#ff6b6b", "ACCENT3":      "#51cf66",
        "TEXT_PRIMARY": "#212529", "TEXT_MUTED":   "#868e96",
        "BORDER":       "#dee2e6", "EDGE_COLOR":   "#adb5bd",
    },
    "dark": {
        "BG_DARK":      "#0f1117", "BG_PANEL":     "#1a1d27",
        "BG_CARD":      "#21253a", "ACCENT":       "#6c63ff",
        "ACCENT2":      "#ff6584", "ACCENT3":      "#43e97b",
        "TEXT_PRIMARY": "#e8eaf6", "TEXT_MUTED":   "#7986cb",
        "BORDER":       "#2d3154", "EDGE_COLOR":   "#4a5080",
    },
}

CURRENT_THEME = "light"

NODE_TYPE_COLORS = {
    "default":  "#d81b60", "process":  "#1e88e5",
    "data":     "#43a047", "event":    "#fb8c00",
    "note":     "#8d6e63", "object":   "#6d4c41",
    "concept":  "#7b1fa2", "resource": "#00838f",
}

EDGE_DIRECTIONS = ["→", "←", "↔", "—"]

EDGE_TYPE_COLORS = {
    "relationship": "#adb5bd",
    "dependency":   "#ff6b6b",
    "flow":         "#51cf66",
    "note":         "#8d6e63"
}

PROPERTY_SCHEMA = {
    "__universal__": [],
    "process": ["status", "owner"],
    "data": ["source"]
}

SETTINGS = {
    "ui_font_size":      10,
    "sidebar_font_size": 11,
    "default_node_type": "default",
    "default_edge_type": "relationship",
    "default_direction": "→",
}

def gc(key):
    v = THEMES[CURRENT_THEME].get(key)
    return v if v else key

def qc(key):
    return QColor(gc(key) if not key.startswith("#") else key)

def new_id():
    return str(uuid.uuid4())[:8]