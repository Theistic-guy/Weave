"""
ui.py — Sidebar, SearchBar, SettingsDialog
"""
import copy
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QScrollArea, QFrame, QComboBox, QDialog, QDialogButtonBox, QFormLayout,
    QColorDialog, QSpinBox, QGroupBox, QListWidget, QListWidgetItem,
    QMessageBox, QTabWidget, QInputDialog, QSizePolicy,
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QPixmap, QIcon

import config
from config import gc, qc


# ─────────────────────────────────────────────────────────────────────────────
#  Shared style helpers
# ─────────────────────────────────────────────────────────────────────────────
def _inp_ss():
    sf = config.SETTINGS["sidebar_font_size"]
    return (f"QLineEdit {{ background:{gc('BG_CARD')}; color:{gc('TEXT_PRIMARY')};"
            f" border:1px solid {gc('BORDER')}; border-radius:6px;"
            f" padding:5px 9px; font-size:{sf}px; }}"
            f" QLineEdit:focus {{ border-color:{gc('ACCENT')}; }}")

def _combo_ss():
    sf = config.SETTINGS["sidebar_font_size"]
    return (f"QComboBox {{ background:{gc('BG_CARD')}; color:{gc('TEXT_PRIMARY')};"
            f" border:1px solid {gc('BORDER')}; border-radius:6px;"
            f" padding:4px 9px; font-size:{sf}px; }}"
            f" QComboBox::drop-down {{ border:none; }}"
            f" QComboBox QAbstractItemView {{ background:{gc('BG_PANEL')};"
            f" color:{gc('TEXT_PRIMARY')}; border:1px solid {gc('BORDER')};"
            f" selection-background-color:{gc('ACCENT')}; }}")

def _btn_ss(color):
    sf = config.SETTINGS["sidebar_font_size"]
    return (f"QPushButton {{ background:{color}; color:white; border:none;"
            f" border-radius:6px; padding:6px 12px;"
            f" font-size:{sf}px; font-weight:bold; }}"
            f" QPushButton:hover {{ background:{QColor(color).lighter(120).name()}; }}")

def _swatch_ss(color):
    return f"background:{color}; border-radius:11px; border:2px solid {gc('BORDER')};"


# ─────────────────────────────────────────────────────────────────────────────
#  PropRow
# ─────────────────────────────────────────────────────────────────────────────
class PropRow(QFrame):
    deleted = pyqtSignal(str)
    changed = pyqtSignal(str, str)

    def __init__(self, key, value, is_schema=False):
        super().__init__()
        self.key_name = key
        self.setStyleSheet(
            f"QFrame {{ background:{gc('BG_CARD')}; border-radius:6px;"
            f" border:1px solid {gc('BORDER')}; }}")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 4, 4, 4)
        lay.setSpacing(6)

        sf = config.SETTINGS["sidebar_font_size"]
        kl = QLabel(key)
        kl.setFixedWidth(86)
        kl.setWordWrap(True)
        kl.setStyleSheet(
            f"color:{gc('ACCENT') if is_schema else gc('TEXT_PRIMARY')};"
            f" font-weight:bold; font-size:{sf-1}px; border:none; background:transparent;")
        if is_schema:
            kl.setToolTip("Schema property — delete button clears value only")

        ve = QLineEdit(str(value))
        ve.setStyleSheet(_inp_ss())
        ve.editingFinished.connect(lambda: self.changed.emit(self.key_name, ve.text()))

        # Schema props: clear button; custom props: delete button
        db = QPushButton("⎚" if is_schema else "✕")
        db.setFixedSize(22, 22)
        db.setToolTip("Clear value" if is_schema else "Delete property")
        db.setStyleSheet(
            f"QPushButton {{ background:transparent;"
            f" color:{gc('TEXT_MUTED') if is_schema else gc('ACCENT2')};"
            f" border:none; font-weight:bold; }}"
            f" QPushButton:hover {{ background:{gc('BORDER') if is_schema else gc('ACCENT2')};"
            f" color:{'white' if not is_schema else gc('TEXT_PRIMARY')}; border-radius:4px; }}")
        if is_schema:
            db.clicked.connect(lambda: (ve.setText(""), self.changed.emit(self.key_name, "")))
        else:
            db.clicked.connect(lambda: self.deleted.emit(self.key_name))

        lay.addWidget(kl)
        lay.addWidget(ve)
        lay.addWidget(db)


# ─────────────────────────────────────────────────────────────────────────────
#  Sidebar
# ─────────────────────────────────────────────────────────────────────────────
class Sidebar(QWidget):
    def __init__(self, scene):
        super().__init__()
        self.scene = scene
        self._node = None
        self._edge = None
        self.setFixedWidth(290)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.header = QLabel("Properties")
        root.addWidget(self.header)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.content = QWidget()
        self.cl = QVBoxLayout(self.content)
        self.cl.setContentsMargins(12, 12, 12, 12)
        self.cl.setSpacing(8)
        self.cl.addStretch()
        self.scroll.setWidget(self.content)
        root.addWidget(self.scroll)

        self.apply_style()
        self.show_empty()

    def apply_style(self):
        sf = config.SETTINGS["sidebar_font_size"]
        self.setStyleSheet(f"background:{gc('BG_PANEL')};")
        self.header.setStyleSheet(
            f"QLabel {{ background:{gc('BG_DARK')}; color:{gc('TEXT_PRIMARY')};"
            f" font-size:{sf+3}px; font-weight:bold;"
            f" padding:14px 16px; border-bottom:1px solid {gc('BORDER')}; }}")
        self.scroll.setStyleSheet(
            f"QScrollArea {{ background:transparent; border:none; }}"
            f" QScrollBar:vertical {{ background:{gc('BG_DARK')}; width:6px; border-radius:3px; }}"
            f" QScrollBar::handle:vertical {{ background:{gc('BORDER')}; border-radius:3px; min-height:20px; }}")
        self.content.setStyleSheet(f"background:{gc('BG_PANEL')};")

    def _clear(self):
        while self.cl.count():
            it = self.cl.takeAt(0)
            if it.widget():
                it.widget().deleteLater()

    def _section(self, title):
        sf  = config.SETTINGS["sidebar_font_size"]
        lbl = QLabel(title.upper())
        lbl.setStyleSheet(
            f"color:{gc('TEXT_MUTED')}; font-size:{sf-3}px; font-weight:bold;"
            f" letter-spacing:1.5px; padding:6px 0 2px 0; background:transparent;")
        self.cl.addWidget(lbl)

    def show_empty(self):
        self._node = self._edge = None
        self._clear()
        self.header.setText("Properties")
        sf  = config.SETTINGS["sidebar_font_size"]
        lbl = QLabel("Click a node or edge\nto view its properties.")
        lbl.setStyleSheet(
            f"color:{gc('TEXT_MUTED')}; font-size:{sf}px;"
            f" padding:20px 0; background:transparent;")
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setWordWrap(True)
        self.cl.addWidget(lbl)
        self.cl.addStretch()

    def show_node(self, node):
        self._node = node
        self._edge = None
        self._clear()
        self.header.setText(f"Node  ·  {node.node_id}")
        self._build_node_ui(node)
        self.cl.addStretch()

    def show_edge(self, edge):
        self._edge = edge
        self._node = None
        self._clear()
        self.header.setText(f"Edge  ·  {edge.edge_id}")
        self._build_edge_ui(edge)
        self.cl.addStretch()

    # ── Node UI ───────────────────────────────────────────────────────────────
    def _build_node_ui(self, node):
        sf = config.SETTINGS["sidebar_font_size"]
        self._section("Identity")

        le = QLineEdit(node.label)
        le.setStyleSheet(_inp_ss())
        def _upd_label():
            node.label = le.text()
            node._refresh_text()
            self.scene.graph_changed.emit()
        le.editingFinished.connect(_upd_label)
        self.cl.addWidget(le)

        tc = QComboBox()
        tc.addItems(list(config.NODE_TYPE_COLORS.keys()))
        tc.setCurrentText(node.node_type)
        tc.setStyleSheet(_combo_ss())
        def _upd_type(t):
            node.node_type = t
            node.color = config.NODE_TYPE_COLORS.get(t, node.color)
            node._inject_schema()
            node._refresh_text()
            self.scene.update()
            self.scene.graph_changed.emit()
            self.show_node(node)
        tc.currentTextChanged.connect(_upd_type)
        self.cl.addWidget(tc)

        # Custom colour picker
        cr = QFrame(); cr.setStyleSheet("background:transparent;")
        cl = QHBoxLayout(cr); cl.setContentsMargins(0, 0, 0, 0); cl.setSpacing(6)
        sw = QPushButton(); sw.setFixedSize(22, 22)
        sw.setStyleSheet(_swatch_ss(node.color))
        col_lbl = QLabel("Custom colour")
        col_lbl.setStyleSheet(
            f"color:{gc('TEXT_MUTED')}; background:transparent; font-size:{sf-1}px;")
        def _pick_col():
            c = QColorDialog.getColor(QColor(node.color), self)
            if c.isValid():
                node.color = c.name()
                sw.setStyleSheet(_swatch_ss(node.color))
                node._refresh_text()
                self.scene.update()
                self.scene.graph_changed.emit()
        sw.clicked.connect(_pick_col)
        cl.addWidget(sw); cl.addWidget(col_lbl); cl.addStretch()
        self.cl.addWidget(cr)

        # Properties
        self._section("Properties")
        expected_keys = (config.PROPERTY_SCHEMA.get("__universal__", [])
                         + config.PROPERTY_SCHEMA.get(node.node_type, []))
        for k, v in node.properties.items():
            row = PropRow(k, v, is_schema=(k in expected_keys))
            def _del(key, n=node):
                n.properties.pop(key, None)
                self.scene.graph_changed.emit()
                self.show_node(n)
            def _chg(key, val, n=node):
                n.properties[key] = val
                self.scene.graph_changed.emit()
            row.deleted.connect(_del)
            row.changed.connect(_chg)
            self.cl.addWidget(row)

        # Add custom property
        add_row = QFrame(); add_row.setStyleSheet("background:transparent;")
        al = QHBoxLayout(add_row); al.setContentsMargins(0, 0, 0, 0); al.setSpacing(4)
        ki = QLineEdit(); ki.setPlaceholderText("key"); ki.setStyleSheet(_inp_ss())
        vi = QLineEdit(); vi.setPlaceholderText("value"); vi.setStyleSheet(_inp_ss())
        ab = QPushButton("+"); ab.setFixedSize(28, 28); ab.setStyleSheet(_btn_ss(gc("ACCENT3")))
        def _add():
            k = ki.text().strip(); v = vi.text().strip()
            if k:
                node.properties[k] = v
                self.scene.graph_changed.emit()
                self.show_node(node)
        ab.clicked.connect(_add); ki.returnPressed.connect(_add); vi.returnPressed.connect(_add)
        al.addWidget(ki); al.addWidget(vi); al.addWidget(ab)
        self.cl.addWidget(add_row)

        # Connections list
        if node.edges:
            self._section(f"Edges ({len(node.edges)})")
            for e in node.edges:
                other = e.target_node if e.source_node is node else e.source_node
                txt = f"{e.direction} {other.label}" + (f"  [{e.label}]" if e.label else "")
                el = QLabel(txt)
                el.setStyleSheet(
                    f"color:{gc('TEXT_PRIMARY')}; font-size:{sf-1}px; padding:4px 8px;"
                    f" background:{gc('BG_CARD')}; border-radius:4px;"
                    f" border:1px solid {gc('BORDER')};")
                self.cl.addWidget(el)

        db = QPushButton("🗑  Delete Node"); db.setStyleSheet(_btn_ss(gc("ACCENT2")))
        db.clicked.connect(lambda: (self.scene.delete_node(node), self.show_empty()))
        self.cl.addWidget(db)

    # ── Edge UI ───────────────────────────────────────────────────────────────
    def _build_edge_ui(self, edge):
        self._section("Direction")
        dc = QComboBox(); dc.addItems(config.EDGE_DIRECTIONS)
        dc.setCurrentText(edge.direction); dc.setStyleSheet(_combo_ss())
        dc.currentTextChanged.connect(
            lambda d: (edge.set_direction(d), self.scene.graph_changed.emit()))
        self.cl.addWidget(dc)

        self._section("Edge Type")
        etc = QComboBox(); etc.addItems(list(config.EDGE_TYPE_COLORS.keys()))
        etc.setCurrentText(edge.edge_type); etc.setStyleSheet(_combo_ss())
        etc.currentTextChanged.connect(
            lambda t: (edge.set_edge_type(t), self.scene.graph_changed.emit()))
        self.cl.addWidget(etc)

        # Custom colour
        cr = QFrame(); cr.setStyleSheet("background:transparent;")
        cl = QHBoxLayout(cr); cl.setContentsMargins(0, 0, 0, 0); cl.setSpacing(6)
        sw = QPushButton(); sw.setFixedSize(22, 22)
        sw.setStyleSheet(_swatch_ss(edge.color))
        sf = config.SETTINGS["sidebar_font_size"]
        col_lbl = QLabel("Custom colour")
        col_lbl.setStyleSheet(
            f"color:{gc('TEXT_MUTED')}; background:transparent; font-size:{sf-1}px;")
        def _pick_col():
            c = QColorDialog.getColor(QColor(edge.color), self)
            if c.isValid():
                edge.color = c.name()
                sw.setStyleSheet(_swatch_ss(edge.color))
                edge._refresh_label_text()
                self.scene.update()
                self.scene.graph_changed.emit()
        sw.clicked.connect(_pick_col)
        cl.addWidget(sw); cl.addWidget(col_lbl); cl.addStretch()
        self.cl.addWidget(cr)

        self._section("Label")
        le = QLineEdit(edge.label); le.setStyleSheet(_inp_ss())
        le.editingFinished.connect(
            lambda: (edge.set_label(le.text()), self.scene.graph_changed.emit()))
        self.cl.addWidget(le)

        self._section("Connection")
        info = QLabel(f"From:  {edge.source_node.label}\nTo:      {edge.target_node.label}")
        info.setStyleSheet(
            f"color:{gc('TEXT_PRIMARY')}; font-size:{sf}px; padding:6px; background:transparent;")
        self.cl.addWidget(info)

        db = QPushButton("🗑  Delete Edge"); db.setStyleSheet(_btn_ss(gc("ACCENT2")))
        db.clicked.connect(lambda: (self.scene.delete_edge(edge), self.show_empty()))
        self.cl.addWidget(db)


# ─────────────────────────────────────────────────────────────────────────────
#  SearchBar
# ─────────────────────────────────────────────────────────────────────────────
class SearchBar(QWidget):
    def __init__(self, scene, view):
        super().__init__()
        self.scene = scene; self.view = view
        self._matches = []; self._match_idx = 0

        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 7, 12, 7); lay.setSpacing(6)

        self.icon = QLabel("🔍"); lay.addWidget(self.icon)
        self.edit = QLineEdit()
        self.edit.setPlaceholderText("Search nodes… (Ctrl+F)")
        self.edit.textChanged.connect(self._search)
        self.edit.installEventFilter(self)
        lay.addWidget(self.edit)

        self.prev_btn = QPushButton("◀"); self.next_btn = QPushButton("▶")
        for b in (self.prev_btn, self.next_btn): b.setFixedWidth(28)
        self.prev_btn.clicked.connect(lambda: self._centre_on(self._match_idx - 1))
        self.next_btn.clicked.connect(lambda: self._centre_on(self._match_idx + 1))
        lay.addWidget(self.prev_btn); lay.addWidget(self.next_btn)

        self.result_lbl = QLabel(""); lay.addWidget(self.result_lbl)

        self.clear_btn = QPushButton("✕"); self.clear_btn.setFixedWidth(24)
        self.clear_btn.clicked.connect(self.edit.clear); lay.addWidget(self.clear_btn)
        self.apply_style()

    def eventFilter(self, obj, event):
        from PyQt5.QtCore import QEvent
        if (obj == self.edit and event.type() == QEvent.KeyPress
                and event.key() == Qt.Key_Escape):
            self.edit.clear(); self.view.setFocus(); return True
        return False

    def apply_style(self):
        sf = config.SETTINGS["sidebar_font_size"]
        self.setStyleSheet(
            f"background:{gc('BG_PANEL')}; border-bottom:1px solid {gc('BORDER')};")
        self.icon.setStyleSheet("font-size:14px; background:transparent; border:none;")
        self.edit.setStyleSheet(_inp_ss())
        bss = (f"QPushButton {{ background:{gc('BG_CARD')}; color:{gc('TEXT_PRIMARY')};"
               f" border:1px solid {gc('BORDER')}; border-radius:4px; }}"
               f" QPushButton:hover {{ background:{gc('ACCENT')}; color:white; }}")
        for b in (self.prev_btn, self.next_btn, self.clear_btn):
            b.setStyleSheet(bss)
        self.result_lbl.setStyleSheet(
            f"color:{gc('TEXT_MUTED')}; font-size:{sf-1}px; background:transparent; border:none;")

    def _search(self, text):
        text = text.strip().lower()
        self._matches = []; self._match_idx = 0
        for node in self.scene.nodes.values():
            node.setSelected(False)
        if text:
            for node in self.scene.nodes.values():
                if (text in node.label.lower()
                        or any(text in str(v).lower()
                               for v in node.properties.values())):
                    self._matches.append(node); node.setSelected(True)
            if self._matches:
                self._centre_on(0)
            else:
                self.result_lbl.setText("No matches")
        else:
            self.result_lbl.setText("")

    def _centre_on(self, idx):
        if not self._matches: return
        self._match_idx = idx % len(self._matches)
        self.view.centerOn(self._matches[self._match_idx])
        self.result_lbl.setText(f"{self._match_idx+1}/{len(self._matches)}")


# ─────────────────────────────────────────────────────────────────────────────
#  SettingsDialog
# ─────────────────────────────────────────────────────────────────────────────
class SettingsDialog(QDialog):
    """
    Tabs:
      General        — font sizes, default type/direction
      Node & Edge Types — add / rename / change-colour / delete types
      Property Schema — universal + per-type template keys
    Bottom row:
      Save Settings   — commits to running state
      Save as Default — also writes graphcanvas_defaults.json
      Cancel
    """
    def __init__(self, parent, scene):
        super().__init__(parent)
        self.scene = scene
        self.setWindowTitle("Settings")
        self.setMinimumSize(540, 520)
        self.resize(580, 580)

        # Deep copies — nothing touches global state until Save
        self.temp_colors   = copy.deepcopy(config.NODE_TYPE_COLORS)
        self.temp_edges    = copy.deepcopy(config.EDGE_TYPE_COLORS)
        self.temp_schema   = copy.deepcopy(config.PROPERTY_SCHEMA)
        self.temp_settings = copy.deepcopy(config.SETTINGS)

        self._apply_base_style()

        main_lay = QVBoxLayout(self)
        main_lay.setSpacing(10)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_general_tab(),  "⚙  General")
        self.tabs.addTab(self._build_types_tab(),    "⬡  Node & Edge Types")
        self.tabs.addTab(self._build_props_tab(),    "⊞  Property Schema")
        main_lay.addWidget(self.tabs)

        # Button row
        btn_row = QHBoxLayout()
        btn_save    = QPushButton("Save Settings")
        btn_default = QPushButton("💾 Save as App Default")
        btn_cancel  = QPushButton("Cancel")

        btn_save.setStyleSheet(_btn_ss(gc("ACCENT")))
        btn_default.setStyleSheet(_btn_ss(gc("ACCENT3")))
        btn_cancel.setStyleSheet(
            f"QPushButton {{ background:{gc('BG_CARD')}; color:{gc('TEXT_PRIMARY')};"
            f" border:1px solid {gc('BORDER')}; border-radius:6px; padding:6px 12px; }}"
            f" QPushButton:hover {{ background:{gc('BORDER')}; }}")

        btn_save.clicked.connect(self._apply)
        btn_default.clicked.connect(self._apply_and_set_default)
        btn_cancel.clicked.connect(self.reject)

        btn_row.addWidget(btn_save)
        btn_row.addWidget(btn_default)
        btn_row.addStretch()
        btn_row.addWidget(btn_cancel)
        main_lay.addLayout(btn_row)

    def _apply_base_style(self):
        self.setStyleSheet(f"""
            QDialog {{ background:{gc('BG_PANEL')}; color:{gc('TEXT_PRIMARY')}; }}
            QTabWidget::pane {{ background:{gc('BG_CARD')}; border:1px solid {gc('BORDER')}; border-radius:6px; }}
            QTabBar::tab {{ background:{gc('BG_CARD')}; color:{gc('TEXT_MUTED')}; padding:8px 16px;
                            border:1px solid {gc('BORDER')}; border-bottom:none; margin-right:2px;
                            border-top-left-radius:6px; border-top-right-radius:6px; }}
            QTabBar::tab:selected {{ background:{gc('BG_PANEL')}; color:{gc('ACCENT')}; font-weight:bold; }}
            QLabel  {{ color:{gc('TEXT_PRIMARY')}; background:transparent; }}
            QGroupBox {{ color:{gc('TEXT_MUTED')}; border:1px solid {gc('BORDER')}; border-radius:6px;
                         margin-top:8px; padding:12px 8px 8px; font-weight:bold; }}
            QGroupBox::title {{ subcontrol-origin:margin; left:8px; }}
            QSpinBox, QComboBox, QLineEdit {{ background:{gc('BG_CARD')}; color:{gc('TEXT_PRIMARY')};
                border:1px solid {gc('BORDER')}; border-radius:4px; padding:4px 8px; }}
            QPushButton {{ background:{gc('ACCENT')}; color:white; border:none;
                           border-radius:4px; padding:6px 12px; font-weight:bold; }}
            QPushButton:hover {{ background:{QColor(gc('ACCENT')).lighter(120).name()}; }}
            QListWidget {{ background:{gc('BG_CARD')}; color:{gc('TEXT_PRIMARY')};
                           border:1px solid {gc('BORDER')}; border-radius:4px; outline:none; }}
            QListWidget::item {{ padding:6px; border-bottom:1px solid {gc('BORDER')}; }}
            QListWidget::item:selected {{ background:{gc('ACCENT')}; color:white; }}
            QScrollArea {{ background:transparent; border:none; }}
            QScrollBar:vertical {{ background:{gc('BG_DARK')}; width:6px; border-radius:3px; }}
            QScrollBar::handle:vertical {{ background:{gc('BORDER')}; border-radius:3px; min-height:20px; }}
        """)

    # ── General tab ───────────────────────────────────────────────────────────
    def _build_general_tab(self):
        w = QWidget(); lay = QVBoxLayout(w); lay.setSpacing(12)

        grp_font = QGroupBox("Eye Comfort / Fonts")
        gfl = QFormLayout(grp_font)
        self.ui_font_spin = QSpinBox(); self.ui_font_spin.setRange(7, 24)
        self.ui_font_spin.setValue(self.temp_settings["ui_font_size"])
        self.sb_font_spin = QSpinBox(); self.sb_font_spin.setRange(8, 24)
        self.sb_font_spin.setValue(self.temp_settings["sidebar_font_size"])
        gfl.addRow("Canvas label size:", self.ui_font_spin)
        gfl.addRow("Sidebar font size:", self.sb_font_spin)
        lay.addWidget(grp_font)

        grp_def = QGroupBox("Defaults for New Nodes / Edges")
        gdl = QFormLayout(grp_def)
        self.def_node_type = QComboBox()
        self.def_node_type.addItems(list(self.temp_colors.keys()))
        self.def_node_type.setCurrentText(self.temp_settings["default_node_type"])
        self.def_edge_type = QComboBox()
        self.def_edge_type.addItems(list(self.temp_edges.keys()))
        self.def_edge_type.setCurrentText(self.temp_settings["default_edge_type"])
        self.def_direction = QComboBox()
        self.def_direction.addItems(config.EDGE_DIRECTIONS)
        self.def_direction.setCurrentText(self.temp_settings["default_direction"])
        gdl.addRow("Default node type:", self.def_node_type)
        gdl.addRow("Default edge type:", self.def_edge_type)
        gdl.addRow("Default direction:", self.def_direction)
        lay.addWidget(grp_def)
        lay.addStretch()
        return w

    # ── Types tab ─────────────────────────────────────────────────────────────
    def _build_types_tab(self):
        w = QWidget(); lay = QHBoxLayout(w); lay.setSpacing(12)

        # ── Node types ──
        nt_grp = QGroupBox("Node Types"); nt_lay = QVBoxLayout(nt_grp)
        self.nt_list = QListWidget()
        for nt, col in self.temp_colors.items():
            self._add_nt_item(nt, col)
        nt_lay.addWidget(self.nt_list)

        nt_btns = QHBoxLayout()
        b_add  = QPushButton("+ Add");     b_add.setFixedHeight(28)
        b_ren  = QPushButton("✏ Rename");  b_ren.setFixedHeight(28)
        b_col  = QPushButton("🎨 Colour"); b_col.setFixedHeight(28)
        b_del  = QPushButton("✕ Delete");  b_del.setFixedHeight(28)
        b_del.setStyleSheet(f"background:{gc('ACCENT2')}; color:white;"
                            f" border-radius:4px; padding:4px 8px; font-weight:bold;")
        b_add.clicked.connect(self._add_node_type)
        b_ren.clicked.connect(self._rename_node_type)
        b_col.clicked.connect(self._change_node_color)
        b_del.clicked.connect(self._delete_node_type)
        for b in (b_add, b_ren, b_col, b_del):
            nt_btns.addWidget(b)
        nt_lay.addLayout(nt_btns)
        lay.addWidget(nt_grp)

        # ── Edge types ──
        et_grp = QGroupBox("Edge Types"); et_lay = QVBoxLayout(et_grp)
        self.et_list = QListWidget()
        for et, col in self.temp_edges.items():
            self._add_et_item(et, col)
        et_lay.addWidget(self.et_list)

        et_btns = QHBoxLayout()
        eb_add = QPushButton("+ Add");     eb_add.setFixedHeight(28)
        eb_ren = QPushButton("✏ Rename");  eb_ren.setFixedHeight(28)
        eb_col = QPushButton("🎨 Colour"); eb_col.setFixedHeight(28)
        eb_del = QPushButton("✕ Delete");  eb_del.setFixedHeight(28)
        eb_del.setStyleSheet(b_del.styleSheet())
        eb_add.clicked.connect(self._add_edge_type)
        eb_ren.clicked.connect(self._rename_edge_type)
        eb_col.clicked.connect(self._change_edge_color)
        eb_del.clicked.connect(self._delete_edge_type)
        for b in (eb_add, eb_ren, eb_col, eb_del):
            et_btns.addWidget(b)
        et_lay.addLayout(et_btns)
        lay.addWidget(et_grp)
        return w

    def _add_nt_item(self, name, color):
        item = QListWidgetItem(name)
        pix  = QPixmap(14, 14); pix.fill(QColor(color))
        item.setIcon(QIcon(pix)); item.setData(Qt.UserRole, name)
        self.nt_list.addItem(item)

    def _add_et_item(self, name, color):
        item = QListWidgetItem(name)
        pix  = QPixmap(14, 14); pix.fill(QColor(color))
        item.setIcon(QIcon(pix)); item.setData(Qt.UserRole, name)
        self.et_list.addItem(item)

    # ── Node type actions ─────────────────────────────────────────────────────
    def _add_node_type(self):
        name, ok = QInputDialog.getText(self, "New Node Type", "Type name:")
        name = name.strip()
        if not ok or not name:
            return
        if name in self.temp_colors:
            QMessageBox.warning(self, "Duplicate", f"Node type '{name}' already exists."); return
        col = QColorDialog.getColor(QColor("#888888"), self, "Pick colour for this type")
        if col.isValid():
            self.temp_colors[name] = col.name()
            self._add_nt_item(name, col.name())
            self.def_node_type.addItem(name)

    def _rename_node_type(self):
        item = self.nt_list.currentItem()
        if not item:
            QMessageBox.information(self, "Nothing selected", "Select a node type first."); return
        old = item.data(Qt.UserRole)
        new, ok = QInputDialog.getText(self, "Rename Node Type", "New name:", text=old)
        new = new.strip()
        if not ok or not new or new == old:
            return
        if new in self.temp_colors:
            QMessageBox.warning(self, "Duplicate",
                f"A node type named '{new}' already exists.\nChoose a different name."); return
        # Migrate registry
        self.temp_colors[new] = self.temp_colors.pop(old)
        if old in self.temp_schema:
            self.temp_schema[new] = self.temp_schema.pop(old)
        # Update list item display
        item.setText(new); item.setData(Qt.UserRole, new)
        # Update defaults combo
        idx = self.def_node_type.findText(old)
        if idx >= 0:
            self.def_node_type.setItemText(idx, new)
        # Update schema combo if it exists
        if hasattr(self, "schema_combo"):
            sidx = self.schema_combo.findText(old)
            if sidx >= 0:
                self.schema_combo.setItemText(sidx, new)

    def _change_node_color(self):
        item = self.nt_list.currentItem()
        if not item: return
        nt = item.data(Qt.UserRole)
        c  = QColorDialog.getColor(QColor(self.temp_colors[nt]), self)
        if c.isValid():
            self.temp_colors[nt] = c.name()
            pix = QPixmap(14, 14); pix.fill(c); item.setIcon(QIcon(pix))

    def _delete_node_type(self):
        item = self.nt_list.currentItem()
        if not item: return
        nt = item.data(Qt.UserRole)
        if nt == "default":
            QMessageBox.warning(self, "Protected", "The 'default' type cannot be deleted."); return
        users = [n.label for n in self.scene.nodes.values() if n.node_type == nt]
        if users:
            QMessageBox.warning(self, "Type in use",
                f"Cannot delete '{nt}' — {len(users)} node(s) use it.\n"
                f"Re-assign them first."); return
        del self.temp_colors[nt]
        if nt in self.temp_schema:
            del self.temp_schema[nt]
        self.nt_list.takeItem(self.nt_list.row(item))
        idx = self.def_node_type.findText(nt)
        if idx >= 0: self.def_node_type.removeItem(idx)

    # ── Edge type actions ─────────────────────────────────────────────────────
    def _add_edge_type(self):
        name, ok = QInputDialog.getText(self, "New Edge Type", "Type name:")
        name = name.strip()
        if not ok or not name:
            return
        if name in self.temp_edges:
            QMessageBox.warning(self, "Duplicate", f"Edge type '{name}' already exists."); return
        col = QColorDialog.getColor(QColor("#adb5bd"), self, "Pick colour for this type")
        if col.isValid():
            self.temp_edges[name] = col.name()
            self._add_et_item(name, col.name())
            self.def_edge_type.addItem(name)

    def _rename_edge_type(self):
        item = self.et_list.currentItem()
        if not item:
            QMessageBox.information(self, "Nothing selected", "Select an edge type first."); return
        old = item.data(Qt.UserRole)
        new, ok = QInputDialog.getText(self, "Rename Edge Type", "New name:", text=old)
        new = new.strip()
        if not ok or not new or new == old:
            return
        if new in self.temp_edges:
            QMessageBox.warning(self, "Duplicate",
                f"An edge type named '{new}' already exists.\nChoose a different name."); return
        self.temp_edges[new] = self.temp_edges.pop(old)
        item.setText(new); item.setData(Qt.UserRole, new)
        idx = self.def_edge_type.findText(old)
        if idx >= 0:
            self.def_edge_type.setItemText(idx, new)

    def _change_edge_color(self):
        item = self.et_list.currentItem()
        if not item: return
        et = item.data(Qt.UserRole)
        c  = QColorDialog.getColor(QColor(self.temp_edges[et]), self)
        if c.isValid():
            self.temp_edges[et] = c.name()
            pix = QPixmap(14, 14); pix.fill(c); item.setIcon(QIcon(pix))

    def _delete_edge_type(self):
        item = self.et_list.currentItem()
        if not item: return
        et = item.data(Qt.UserRole)
        if et == "relationship":
            QMessageBox.warning(self, "Protected",
                "The 'relationship' type cannot be deleted."); return
        users = [e.edge_id for e in self.scene.edges.values() if e.edge_type == et]
        if users:
            QMessageBox.warning(self, "Type in use",
                f"Cannot delete '{et}' — {len(users)} edge(s) use it.\n"
                f"Re-assign them first."); return
        del self.temp_edges[et]
        self.et_list.takeItem(self.et_list.row(item))
        idx = self.def_edge_type.findText(et)
        if idx >= 0: self.def_edge_type.removeItem(idx)

    # ── Property schema tab ───────────────────────────────────────────────────
    def _build_props_tab(self):
        w = QWidget(); lay = QVBoxLayout(w); lay.setSpacing(8)

        hint = QLabel(
            "Template properties are auto-injected into nodes of the matching type.\n"
            "Removing a key only clears nodes where the value is still empty.")
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color:{gc('TEXT_MUTED')}; font-size:11px; padding:4px 0 8px 0;")
        lay.addWidget(hint)

        sel_row = QHBoxLayout()
        sel_row.addWidget(QLabel("Target type:"))
        self.schema_combo = QComboBox()
        self.schema_combo.addItems(["__universal__"] + list(self.temp_colors.keys()))
        self.schema_combo.currentTextChanged.connect(self._load_schema_list)
        sel_row.addWidget(self.schema_combo, 1); lay.addLayout(sel_row)

        self.schema_list = QListWidget(); lay.addWidget(self.schema_list)
        self._load_schema_list(self.schema_combo.currentText())

        btn_row = QHBoxLayout()
        add_p = QPushButton("+ Add Key")
        del_p = QPushButton("✕ Remove Key")
        del_p.setStyleSheet(f"background:{gc('ACCENT2')}; color:white;"
                            f" border-radius:4px; padding:6px 12px; font-weight:bold;")
        add_p.clicked.connect(self._add_schema_prop)
        del_p.clicked.connect(self._del_schema_prop)
        btn_row.addWidget(add_p); btn_row.addWidget(del_p); btn_row.addStretch()
        lay.addLayout(btn_row)
        return w

    def _load_schema_list(self, target):
        self.schema_list.clear()
        for key in self.temp_schema.get(target, []):
            self.schema_list.addItem(key)

    def _add_schema_prop(self):
        target = self.schema_combo.currentText()
        p, ok  = QInputDialog.getText(self, "New Property Key", "Key name:")
        p = p.strip()
        if not ok or not p:
            return
        if target not in self.temp_schema:
            self.temp_schema[target] = []
        if p in self.temp_schema[target]:
            QMessageBox.warning(self, "Duplicate",
                f"Key '{p}' already exists for '{target}'."); return
        self.temp_schema[target].append(p)
        self.schema_list.addItem(p)

    def _del_schema_prop(self):
        item = self.schema_list.currentItem()
        if not item: return
        target = self.schema_combo.currentText()
        key    = item.text()
        self.temp_schema[target].remove(key)
        self.schema_list.takeItem(self.schema_list.row(item))

    # ── Apply helpers ─────────────────────────────────────────────────────────
    def _collect_settings(self):
        self.temp_settings["ui_font_size"]      = self.ui_font_spin.value()
        self.temp_settings["sidebar_font_size"] = self.sb_font_spin.value()
        self.temp_settings["default_node_type"] = self.def_node_type.currentText()
        self.temp_settings["default_edge_type"] = self.def_edge_type.currentText()
        self.temp_settings["default_direction"] = self.def_direction.currentText()
        # Guard against stale defaults
        if self.temp_settings["default_node_type"] not in self.temp_colors:
            self.temp_settings["default_node_type"] = next(iter(self.temp_colors), "default")
        if self.temp_settings["default_edge_type"] not in self.temp_edges:
            self.temp_settings["default_edge_type"] = next(iter(self.temp_edges), "relationship")

    def _commit(self):
        """Push temp state into global config and update scene nodes/edges."""
        self._collect_settings()

        # --- Compute schema diffs before committing ---
        old_schema = copy.deepcopy(config.PROPERTY_SCHEMA)

        # Push to global
        config.NODE_TYPE_COLORS.clear(); config.NODE_TYPE_COLORS.update(self.temp_colors)
        config.EDGE_TYPE_COLORS.clear(); config.EDGE_TYPE_COLORS.update(self.temp_edges)
        config.PROPERTY_SCHEMA.clear();  config.PROPERTY_SCHEMA.update(self.temp_schema)
        config.SETTINGS.update(self.temp_settings)

        # Propagate schema changes + colour changes to existing nodes
        for node in self.scene.nodes.values():
            uni_old  = old_schema.get("__universal__", [])
            type_old = old_schema.get(node.node_type, [])
            old_exp  = set(uni_old + type_old)

            uni_new  = config.PROPERTY_SCHEMA.get("__universal__", [])
            type_new = config.PROPERTY_SCHEMA.get(node.node_type, [])
            new_exp  = set(uni_new + type_new)

            # Inject new keys
            for k in new_exp:
                if k not in node.properties:
                    node.properties[k] = ""
            # Remove dropped keys only where value is empty
            for k in (old_exp - new_exp):
                if k in node.properties and str(node.properties.get(k, "")).strip() == "":
                    del node.properties[k]

            # Sync node colour to (possibly renamed/recoloured) type
            node.color = config.NODE_TYPE_COLORS.get(node.node_type, node.color)
            node._refresh_text()
            node.update()

        # Sync edge colours
        for edge in self.scene.edges.values():
            edge.color = config.EDGE_TYPE_COLORS.get(edge.edge_type, edge.color)
            edge._refresh_label_text()

        self.scene.update()
        self.scene.graph_changed.emit()

    def _apply(self):
        self._commit()
        self.accept()

    def _apply_and_set_default(self):
        self._commit()
        config.save_as_default()
        QMessageBox.information(
            self, "Default Saved",
            "Current settings saved as app default.\n"
            "They will be loaded automatically on next launch.")
        self.accept()