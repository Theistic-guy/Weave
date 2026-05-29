"""
config.py — single source of truth for all mutable app state.
Nothing here has side-effects; it's imported everywhere.
"""
import uuid, json, os
from PyQt5.QtGui import QColor

# ── Theme ─────────────────────────────────────────────────────────────────────
THEMES = {
    "light": {
        "BG_DARK":      "#f0f2f5", "BG_PANEL":     "#f8f9fa",
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

# ── Node/edge type registries ─────────────────────────────────────────────────
# NODE_TYPE_COLORS  : {name: hex_color}
# EDGE_TYPE_COLORS  : {name: hex_color}
NODE_TYPE_COLORS = {
    "default":  "#d81b60",
    "process":  "#1e88e5",
    "data":     "#43a047",
    "event":    "#fb8c00",
    "note":     "#8d6e63",
    "object":   "#6d4c41",
    "concept":  "#7b1fa2",
    "resource": "#00838f",
}
EDGE_TYPE_COLORS = {
    "relationship": "#adb5bd",
    "dependency":   "#ff6b6b",
    "flow":         "#51cf66",
    "note":         "#8d6e63",
}

EDGE_DIRECTIONS = ["→", "←", "↔", "—"]

# ── Property schema ───────────────────────────────────────────────────────────
# PROPERTY_SCHEMA : {"__universal__": [key, ...],  <node_type>: [key, ...]}
# Values are always lists of key names; actual values live on the node.
PROPERTY_SCHEMA = {
    "__universal__": [],
    "process": ["status", "owner"],
    "data":    ["source"],
}

# ── Runtime settings ──────────────────────────────────────────────────────────
SETTINGS = {
    "ui_font_size":      10,
    "sidebar_font_size": 11,
    "default_node_type": "default",
    "default_edge_type": "relationship",
    "default_direction": "→",
}

# ── Helpers ───────────────────────────────────────────────────────────────────
def gc(key: str) -> str:
    """Get colour string from current theme."""
    return THEMES[CURRENT_THEME].get(key, key)

def qc(key: str) -> QColor:
    return QColor(gc(key) if not key.startswith("#") else key)

def new_id() -> str:
    return str(uuid.uuid4())[:8]

# ── Defaults file (persists user's baseline across sessions) ──────────────────
_DEFAULTS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "graphcanvas_defaults.json")

def save_as_default():
    """Write current registries + settings to defaults file."""
    data = {
        "node_types":    dict(NODE_TYPE_COLORS),
        "edge_types":    dict(EDGE_TYPE_COLORS),
        "property_schema": {k: list(v) for k, v in PROPERTY_SCHEMA.items()},
        "settings":      dict(SETTINGS),
        "theme":         CURRENT_THEME,
    }
    with open(_DEFAULTS_PATH, "w") as f:
        json.dump(data, f, indent=2)

def load_defaults():
    """Load defaults file into global state if it exists."""
    global CURRENT_THEME
    if not os.path.exists(_DEFAULTS_PATH):
        return
    try:
        with open(_DEFAULTS_PATH) as f:
            data = json.load(f)
        if "node_types" in data:
            NODE_TYPE_COLORS.clear()
            NODE_TYPE_COLORS.update(data["node_types"])
        if "edge_types" in data:
            EDGE_TYPE_COLORS.clear()
            EDGE_TYPE_COLORS.update(data["edge_types"])
        if "property_schema" in data:
            PROPERTY_SCHEMA.clear()
            PROPERTY_SCHEMA.update(data["property_schema"])
        if "settings" in data:
            SETTINGS.update(data["settings"])
        if "theme" in data:
            CURRENT_THEME = data["theme"]
    except Exception as e:
        print(f"[config] Could not load defaults: {e}")

def schema_block() -> dict:
    """Serialise all type/schema/settings state into a dict for saving."""
    return {
        "node_types":     dict(NODE_TYPE_COLORS),
        "edge_types":     dict(EDGE_TYPE_COLORS),
        "property_schema": {k: list(v) for k, v in PROPERTY_SCHEMA.items()},
        "settings":       dict(SETTINGS),
        "theme":          CURRENT_THEME,
    }

def restore_schema_block(data: dict):
    """Restore type/schema/settings from a saved dict."""
    global CURRENT_THEME
    if "node_types" in data:
        NODE_TYPE_COLORS.clear()
        NODE_TYPE_COLORS.update(data["node_types"])
    if "edge_types" in data:
        EDGE_TYPE_COLORS.clear()
        if isinstance(data["edge_types"], list):
            # handle old format that stored a list
            for et in data["edge_types"]:
                EDGE_TYPE_COLORS[et] = "#adb5bd"
        else:
            EDGE_TYPE_COLORS.update(data["edge_types"])
    if "property_schema" in data:
        PROPERTY_SCHEMA.clear()
        PROPERTY_SCHEMA.update(data["property_schema"])
    if "settings" in data:
        SETTINGS.update(data["settings"])
    if "theme" in data:
        CURRENT_THEME = data["theme"]