import copy
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QScrollArea, QFrame, QComboBox, QDialog, QDialogButtonBox, QFormLayout,
    QColorDialog, QSpinBox, QGroupBox, QListWidget, QListWidgetItem, QMessageBox, QTabWidget
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QPixmap, QIcon

from config import (
    gc, qc, SETTINGS, NODE_TYPE_COLORS, EDGE_DIRECTIONS,
    EDGE_TYPE_COLORS, PROPERTY_SCHEMA
)
import config

class PropRow(QFrame):
    deleted = pyqtSignal(str); changed = pyqtSignal(str, str)
    def __init__(self, key, value, is_schema=False):
        super().__init__()
        self.key_name = key; self.setStyleSheet(f"QFrame {{ background:{gc('BG_CARD')}; border-radius:6px; border:1px solid {gc('BORDER')}; }}")
        lay = QHBoxLayout(self); lay.setContentsMargins(8, 4, 4, 4); lay.setSpacing(6)
        self.key_lbl = QLabel(key); self.key_lbl.setFixedWidth(86); self.key_lbl.setWordWrap(True)
        self.key_lbl.setStyleSheet(f"color:{gc('ACCENT') if is_schema else gc('TEXT_PRIMARY')}; font-weight:bold; font-size:{SETTINGS['sidebar_font_size']-1}px; border:none; background:transparent;")
        if is_schema: self.key_lbl.setToolTip("Schema Property")
        self.val_edit = QLineEdit(str(value))
        self.val_edit.setStyleSheet(f"QLineEdit {{ background:{gc('BG_PANEL')}; color:{gc('TEXT_PRIMARY')}; border:1px solid {gc('BORDER')}; border-radius:4px; padding:3px 6px; font-size:{SETTINGS['sidebar_font_size']-1}px; }} QLineEdit:focus {{ border-color:{gc('ACCENT')}; }}")
        self.val_edit.editingFinished.connect(lambda: self.changed.emit(self.key_name, self.val_edit.text()))
        db = QPushButton("⎚" if is_schema else "✕"); db.setFixedSize(22, 22); db.setToolTip("Clear Value" if is_schema else "Delete Property")
        db.setStyleSheet(f"QPushButton {{ background:transparent; color:{gc('TEXT_MUTED') if is_schema else gc('ACCENT2')}; border:none; font-weight:bold; }} QPushButton:hover {{ background:{gc('BORDER') if is_schema else gc('ACCENT2')}; color:{'white' if not is_schema else gc('TEXT_PRIMARY')}; border-radius:4px; }}")
        if is_schema: db.clicked.connect(lambda: (self.val_edit.setText(""), self.changed.emit(self.key_name, "")))
        else: db.clicked.connect(lambda: self.deleted.emit(self.key_name))
        lay.addWidget(self.key_lbl); lay.addWidget(self.val_edit); lay.addWidget(db)

class Sidebar(QWidget):
    def __init__(self, scene):
        super().__init__()
        self.scene = scene; self._node = None; self._edge = None; self.setFixedWidth(290)
        self._root = QVBoxLayout(self); self._root.setContentsMargins(0, 0, 0, 0); self._root.setSpacing(0)
        self.header = QLabel("Properties"); self._root.addWidget(self.header)
        self.scroll = QScrollArea(); self.scroll.setWidgetResizable(True); self.scroll.setFrameShape(QFrame.NoFrame)
        self.content = QWidget(); self.cl = QVBoxLayout(self.content); self.cl.setContentsMargins(12, 12, 12, 12); self.cl.setSpacing(8); self.cl.addStretch()
        self.scroll.setWidget(self.content); self._root.addWidget(self.scroll); self.apply_style(); self.show_empty()

    def apply_style(self):
        sf = SETTINGS["sidebar_font_size"]; self.setStyleSheet(f"background:{gc('BG_PANEL')};")
        self.header.setStyleSheet(f"QLabel {{ background:{gc('BG_DARK')}; color:{gc('TEXT_PRIMARY')}; font-size:{sf+3}px; font-weight:bold; padding:14px 16px; border-bottom:1px solid {gc('BORDER')}; }}")
        self.scroll.setStyleSheet(f"QScrollArea {{ background:transparent; border:none; }} QScrollBar:vertical {{ background:{gc('BG_DARK')}; width:6px; border-radius:3px; }} QScrollBar::handle:vertical {{ background:{gc('BORDER')}; border-radius:3px; min-height:20px; }}")
        self.content.setStyleSheet(f"background:{gc('BG_PANEL')};")

    def _clear(self):
        while self.cl.count():
            it = self.cl.takeAt(0)
            if it.widget(): it.widget().deleteLater()

    def show_empty(self):
        self._node = self._edge = None; self._clear(); self.header.setText("Properties")
        lbl = QLabel("Click a node or edge\nto view its properties."); lbl.setStyleSheet(f"color:{gc('TEXT_MUTED')}; font-size:{SETTINGS['sidebar_font_size']}px; padding:20px 0; background:transparent;")
        lbl.setAlignment(Qt.AlignCenter); self.cl.addWidget(lbl); self.cl.addStretch()

    def show_node(self, node):
        self._node = node; self._edge = None; self._clear(); self.header.setText(f"Node  ·  {node.node_id}"); self._build_node_ui(node); self.cl.addStretch()

    def show_edge(self, edge):
        self._edge = edge; self._node = None; self._clear(); self.header.setText(f"Edge  ·  {edge.edge_id}"); self._build_edge_ui(edge); self.cl.addStretch()

    def _section(self, title):
        lbl = QLabel(title.upper()); lbl.setStyleSheet(f"color:{gc('TEXT_MUTED')}; font-size:{SETTINGS['sidebar_font_size']-3}px; font-weight:bold; letter-spacing:1.5px; padding:6px 0 2px 0; background:transparent;"); self.cl.addWidget(lbl)

    def _inp(self): return f"QLineEdit {{ background:{gc('BG_CARD')}; color:{gc('TEXT_PRIMARY')}; border:1px solid {gc('BORDER')}; border-radius:6px; padding:6px 10px; font-size:{SETTINGS['sidebar_font_size']}px; }} QLineEdit:focus {{ border-color:{gc('ACCENT')}; }}"
    def _combo(self): return f"QComboBox {{ background:{gc('BG_CARD')}; color:{gc('TEXT_PRIMARY')}; border:1px solid {gc('BORDER')}; border-radius:6px; padding:5px 10px; font-size:{SETTINGS['sidebar_font_size']}px; }} QComboBox::drop-down {{ border:none; }} QComboBox QAbstractItemView {{ background:{gc('BG_PANEL')}; color:{gc('TEXT_PRIMARY')}; border:1px solid {gc('BORDER')}; selection-background-color:{gc('ACCENT')}; }}"
    def _btn(self, color): return f"QPushButton {{ background:{color}; color:white; border:none; border-radius:6px; padding:7px 12px; font-size:{SETTINGS['sidebar_font_size']}px; font-weight:bold; }} QPushButton:hover {{ background:{QColor(color).lighter(120).name()}; }}"

    def _build_node_ui(self, node):
        self._section("Identity")
        le = QLineEdit(node.label); le.setStyleSheet(self._inp())
        def _upd_label(): node.label = le.text(); node._refresh_text(); self.scene.graph_changed.emit()
        le.editingFinished.connect(_upd_label); self.cl.addWidget(le)

        tc = QComboBox(); tc.addItems(list(NODE_TYPE_COLORS.keys())); tc.setCurrentText(node.node_type); tc.setStyleSheet(self._combo())
        def _upd_type(t):
            node.node_type = t; node.color = NODE_TYPE_COLORS.get(t, node.color); node._inject_schema(); node._refresh_text(); self.scene.update(); self.scene.graph_changed.emit(); self.show_node(node)
        tc.currentTextChanged.connect(_upd_type); self.cl.addWidget(tc)

        col_row = QFrame(); col_row.setStyleSheet("background:transparent;"); col_lay = QHBoxLayout(col_row); col_lay.setContentsMargins(0,0,0,0)
        self._swatch = QPushButton(); self._swatch.setFixedSize(28, 28); self._swatch.setStyleSheet(f"background:{node.color}; border-radius:14px; border:none;")
        col_lbl = QLabel("Custom colour"); col_lbl.setStyleSheet(f"color:{gc('TEXT_MUTED')}; background:transparent; font-size:{SETTINGS['sidebar_font_size']-1}px;")
        def _pick_col():
            c = QColorDialog.getColor(QColor(node.color), self)
            if c.isValid(): node.color = c.name(); self._swatch.setStyleSheet(f"background:{node.color}; border-radius:14px; border:none;"); node._refresh_text(); self.scene.update(); self.scene.graph_changed.emit()
        self._swatch.clicked.connect(_pick_col); col_lay.addWidget(self._swatch); col_lay.addWidget(col_lbl); col_lay.addStretch(); self.cl.addWidget(col_row)

        self._section("Properties")
        expected_keys = PROPERTY_SCHEMA.get("__universal__", []) + PROPERTY_SCHEMA.get(node.node_type, [])
        for k, v in node.properties.items():
            row = PropRow(k, v, is_schema=(k in expected_keys))
            row.deleted.connect(lambda key, n=node: (n.properties.pop(key, None), self.scene.graph_changed.emit(), self.show_node(n)))
            row.changed.connect(lambda key, val, n=node: (n.properties.update({key: val}), self.scene.graph_changed.emit()))
            self.cl.addWidget(row)
        
        row = QFrame(); row.setStyleSheet("background:transparent;"); lay = QHBoxLayout(row); lay.setContentsMargins(0,0,0,0); lay.setSpacing(4)
        ki = QLineEdit(); ki.setPlaceholderText("key"); ki.setStyleSheet(self._inp()); vi = QLineEdit(); vi.setPlaceholderText("value"); vi.setStyleSheet(self._inp())
        ab = QPushButton("+"); ab.setFixedSize(28,28); ab.setStyleSheet(self._btn(gc("ACCENT3")))
        def _add():
            k = ki.text().strip(); v = vi.text().strip()
            if k: node.properties[k] = v; self.scene.graph_changed.emit(); self.show_node(node)
        ab.clicked.connect(_add); ki.returnPressed.connect(_add); vi.returnPressed.connect(_add)
        lay.addWidget(ki); lay.addWidget(vi); lay.addWidget(ab); self.cl.addWidget(row)

        db = QPushButton("🗑  Delete Node"); db.setStyleSheet(self._btn(gc("ACCENT2"))); db.clicked.connect(lambda: (self.scene.delete_node(node), self.show_empty())); self.cl.addWidget(db)

    def _build_edge_ui(self, edge):
        self._section("Direction"); dc = QComboBox(); dc.addItems(EDGE_DIRECTIONS); dc.setCurrentText(edge.direction); dc.setStyleSheet(self._combo())
        dc.currentTextChanged.connect(lambda d: (edge.set_direction(d), self.scene.graph_changed.emit())); self.cl.addWidget(dc)

        self._section("Edge Type"); etc = QComboBox(); etc.addItems(list(EDGE_TYPE_COLORS.keys())); etc.setCurrentText(edge.edge_type); etc.setStyleSheet(self._combo())
        etc.currentTextChanged.connect(lambda t: (edge.set_edge_type(t), self.scene.graph_changed.emit())); self.cl.addWidget(etc)

        col_row = QFrame(); col_row.setStyleSheet("background:transparent;"); col_lay = QHBoxLayout(col_row); col_lay.setContentsMargins(0,0,0,0)
        self._edge_swatch = QPushButton(); self._edge_swatch.setFixedSize(28, 28); self._edge_swatch.setStyleSheet(f"background:{edge.color}; border-radius:14px; border:none;")
        col_lbl = QLabel("Custom colour"); col_lbl.setStyleSheet(f"color:{gc('TEXT_MUTED')}; background:transparent; font-size:{SETTINGS['sidebar_font_size']-1}px;")
        def _pick_col():
            c = QColorDialog.getColor(QColor(edge.color), self)
            if c.isValid(): edge.color = c.name(); self._edge_swatch.setStyleSheet(f"background:{edge.color}; border-radius:14px; border:none;"); edge._refresh_label_text(); self.scene.update(); self.scene.graph_changed.emit()
        self._edge_swatch.clicked.connect(_pick_col); col_lay.addWidget(self._edge_swatch); col_lay.addWidget(col_lbl); col_lay.addStretch(); self.cl.addWidget(col_row)

        self._section("Label"); le = QLineEdit(edge.label); le.setStyleSheet(self._inp())
        le.editingFinished.connect(lambda: (edge.set_label(le.text()), self.scene.graph_changed.emit())); self.cl.addWidget(le)

        db = QPushButton("🗑  Delete Edge"); db.setStyleSheet(self._btn(gc("ACCENT2"))); db.clicked.connect(lambda: (self.scene.delete_edge(edge), self.show_empty())); self.cl.addWidget(db)

class SearchBar(QWidget):
    def __init__(self, scene, view):
        super().__init__()
        self.scene = scene; self.view = view; self._matches = []; self._match_idx = 0
        lay = QHBoxLayout(self); lay.setContentsMargins(12, 7, 12, 7); lay.setSpacing(6)
        self.icon = QLabel("🔍"); lay.addWidget(self.icon)
        self.edit = QLineEdit(); self.edit.setPlaceholderText("Search nodes… (Ctrl+F)"); self.edit.textChanged.connect(self._search); self.edit.installEventFilter(self); lay.addWidget(self.edit)
        self.prev_btn = QPushButton("◀"); self.next_btn = QPushButton("▶")
        for b in (self.prev_btn, self.next_btn): b.setFixedWidth(28)
        self.prev_btn.clicked.connect(lambda: self._centre_on(self._match_idx - 1)); self.next_btn.clicked.connect(lambda: self._centre_on(self._match_idx + 1))
        lay.addWidget(self.prev_btn); lay.addWidget(self.next_btn); self.result_lbl = QLabel(""); lay.addWidget(self.result_lbl)
        self.clear_btn = QPushButton("✕"); self.clear_btn.setFixedWidth(24); self.clear_btn.clicked.connect(self.edit.clear); lay.addWidget(self.clear_btn); self.apply_style()

    def eventFilter(self, obj, event):
        from PyQt5.QtCore import QEvent
        if obj == self.edit and event.type() == QEvent.KeyPress and event.key() == Qt.Key_Escape:
            self.edit.clear(); self.view.setFocus(); return True
        return False

    def apply_style(self):
        sf = SETTINGS["sidebar_font_size"]; self.setStyleSheet(f"background:{gc('BG_PANEL')}; border-bottom:1px solid {gc('BORDER')};")
        self.icon.setStyleSheet("font-size:14px; background:transparent; border:none;")
        self.edit.setStyleSheet(f"QLineEdit {{ background:{gc('BG_CARD')}; color:{gc('TEXT_PRIMARY')}; border:1px solid {gc('BORDER')}; border-radius:6px; padding:5px 10px; font-size:{sf}px; }} QLineEdit:focus {{ border-color:{gc('ACCENT')}; }}")
        btn_ss = f"QPushButton {{ background:{gc('BG_CARD')}; color:{gc('TEXT_PRIMARY')}; border:1px solid {gc('BORDER')}; border-radius:4px; }} QPushButton:hover {{ background:{gc('ACCENT')}; color:white; }}"
        for b in (self.prev_btn, self.next_btn, self.clear_btn): b.setStyleSheet(btn_ss)
        self.result_lbl.setStyleSheet(f"color:{gc('TEXT_MUTED')}; font-size:{sf-1}px; background:transparent; border:none;")

    def _search(self, text):
        text = text.strip().lower(); self._matches = []; self._match_idx = 0
        for node in self.scene.nodes.values(): node.setSelected(False)
        if text:
            for node in self.scene.nodes.values():
                if text in node.label.lower() or any(text in str(v).lower() for v in node.properties.values()):
                    self._matches.append(node); node.setSelected(True)
            if self._matches: self._centre_on(0)
            else: self.result_lbl.setText("No matches")
        else: self.result_lbl.setText("")

    def _centre_on(self, idx):
        if not self._matches: return
        self._match_idx = idx % len(self._matches); self.view.centerOn(self._matches[self._match_idx]); self.result_lbl.setText(f"{self._match_idx+1}/{len(self._matches)}")

class SettingsDialog(QDialog):
    def __init__(self, parent, scene):
        super().__init__(parent); self.scene = scene; self.setWindowTitle("Settings"); self.setMinimumSize(500, 450)
        self.temp_colors = copy.deepcopy(NODE_TYPE_COLORS); self.temp_edges = copy.deepcopy(EDGE_TYPE_COLORS)
        self.temp_schema = copy.deepcopy(PROPERTY_SCHEMA); self.temp_settings = copy.deepcopy(SETTINGS)
        self.setStyleSheet(f"""
            QDialog, QTabWidget::pane {{ background:{gc('BG_PANEL')}; color:{gc('TEXT_PRIMARY')}; border:none; }}
            QTabBar::tab {{ background:{gc('BG_CARD')}; color:{gc('TEXT_MUTED')}; padding:8px 16px; border:1px solid {gc('BORDER')}; border-bottom:none; margin-right:2px; border-top-left-radius:6px; border-top-right-radius:6px; }}
            QTabBar::tab:selected {{ background:{gc('BG_PANEL')}; color:{gc('ACCENT')}; font-weight:bold; }}
            QLabel {{ color:{gc('TEXT_PRIMARY')}; background:transparent; }}
            QGroupBox {{ color:{gc('TEXT_MUTED')}; border:1px solid {gc('BORDER')}; border-radius:6px; margin-top:8px; padding:12px 8px 8px; font-weight:bold; }}
            QGroupBox::title {{ subcontrol-origin:margin; left:8px; }}
            QSpinBox, QComboBox, QLineEdit {{ background:{gc('BG_CARD')}; color:{gc('TEXT_PRIMARY')}; border:1px solid {gc('BORDER')}; border-radius:4px; padding:4px 8px; }}
            QPushButton {{ background:{gc('ACCENT')}; color:white; border:none; border-radius:4px; padding:6px 12px; font-weight:bold; }}
            QPushButton:hover {{ background:{QColor(gc('ACCENT')).lighter(120).name()}; }}
            QListWidget {{ background:{gc('BG_CARD')}; color:{gc('TEXT_PRIMARY')}; border:1px solid {gc('BORDER')}; border-radius:4px; outline:none; }}
            QListWidget::item {{ padding:6px; border-bottom:1px solid {gc('BORDER')}; }}
            QListWidget::item:selected {{ background:{gc('ACCENT')}; color:white; }}
        """)
        main_lay = QVBoxLayout(self); self.tabs = QTabWidget()
        self.tabs.addTab(self._build_general_tab(), "General"); self.tabs.addTab(self._build_types_tab(), "Node & Edge Types"); self.tabs.addTab(self._build_props_tab(), "Property Schema")
        main_lay.addWidget(self.tabs)
        
        # --- THE FIX IS HERE ---
        # Changed .Apply to .Save so the button properly emits the accepted signal
        bb = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Save).setText("Save Settings")
        bb.accepted.connect(self._apply)
        bb.rejected.connect(self.reject)
        bb.setStyleSheet(f'QDialogButtonBox QPushButton[text="Cancel"] {{ background:{gc("BG_CARD")}; color:{gc("TEXT_PRIMARY")}; border:1px solid {gc("BORDER")}; }}')
        main_lay.addWidget(bb)

        
    def _build_general_tab(self):
        w = QWidget(); lay = QVBoxLayout(w); lay.setSpacing(12)
        grp_font = QGroupBox("Eye Comfort"); gfl = QFormLayout(grp_font)
        self.ui_font_spin = QSpinBox(); self.ui_font_spin.setRange(7, 24); self.ui_font_spin.setValue(self.temp_settings["ui_font_size"])
        self.sb_font_spin = QSpinBox(); self.sb_font_spin.setRange(8, 24); self.sb_font_spin.setValue(self.temp_settings["sidebar_font_size"])
        gfl.addRow("Canvas label size:", self.ui_font_spin); gfl.addRow("Sidebar font size:", self.sb_font_spin); lay.addWidget(grp_font)
        grp_def = QGroupBox("Defaults"); gdl = QFormLayout(grp_def)
        self.def_node_type = QComboBox(); self.def_node_type.addItems(list(self.temp_colors.keys())); self.def_node_type.setCurrentText(self.temp_settings["default_node_type"])
        self.def_edge_type = QComboBox(); self.def_edge_type.addItems(list(self.temp_edges.keys())); self.def_edge_type.setCurrentText(self.temp_settings["default_edge_type"])
        self.def_direction = QComboBox(); self.def_direction.addItems(EDGE_DIRECTIONS); self.def_direction.setCurrentText(self.temp_settings["default_direction"])
        gdl.addRow("Default node type:", self.def_node_type); gdl.addRow("Default edge type:", self.def_edge_type); gdl.addRow("Default direction:", self.def_direction)
        lay.addWidget(grp_def); lay.addStretch(); return w

    def _build_types_tab(self):
        w = QWidget(); lay = QHBoxLayout(w)
        nt_grp = QGroupBox("Node Types"); nt_lay = QVBoxLayout(nt_grp)
        self.nt_list = QListWidget()
        for nt, col in self.temp_colors.items(): self._add_nt_list_item(nt, col)
        nt_btns = QHBoxLayout()
        btn_add_nt = QPushButton("+ Add"); btn_col_nt = QPushButton("🎨 Colour"); btn_del_nt = QPushButton("- Delete")
        btn_del_nt.setStyleSheet(f"background:{gc('ACCENT2')}; color:white; border-radius:4px; padding:6px 12px; font-weight:bold;")
        btn_add_nt.clicked.connect(self._add_node_type); btn_col_nt.clicked.connect(self._change_node_color); btn_del_nt.clicked.connect(self._delete_node_type)
        nt_btns.addWidget(btn_add_nt); nt_btns.addWidget(btn_col_nt); nt_btns.addWidget(btn_del_nt); nt_lay.addWidget(self.nt_list); nt_lay.addLayout(nt_btns); lay.addWidget(nt_grp)
        
        et_grp = QGroupBox("Edge Types"); et_lay = QVBoxLayout(et_grp)
        self.et_list = QListWidget()
        for et, col in self.temp_edges.items(): self._add_et_list_item(et, col)
        et_btns = QHBoxLayout()
        btn_add_et = QPushButton("+ Add"); btn_col_et = QPushButton("🎨 Colour"); btn_del_et = QPushButton("- Delete")
        btn_del_et.setStyleSheet(btn_del_nt.styleSheet())
        btn_add_et.clicked.connect(self._add_edge_type); btn_col_et.clicked.connect(self._change_edge_color); btn_del_et.clicked.connect(self._delete_edge_type)
        et_btns.addWidget(btn_add_et); et_btns.addWidget(btn_col_et); et_btns.addWidget(btn_del_et); et_lay.addWidget(self.et_list); et_lay.addLayout(et_btns); lay.addWidget(et_grp)
        return w

    def _add_nt_list_item(self, nt, col):
        item = QListWidgetItem(nt); pix = QPixmap(14, 14); pix.fill(QColor(col)); item.setIcon(QIcon(pix)); item.setData(Qt.UserRole, nt); self.nt_list.addItem(item)

    def _add_et_list_item(self, et, col):
        item = QListWidgetItem(et); pix = QPixmap(14, 14); pix.fill(QColor(col)); item.setIcon(QIcon(pix)); item.setData(Qt.UserRole, et); self.et_list.addItem(item)

    def _add_node_type(self):
        nt, ok = QInputDialog.getText(self, "New Node Type", "Type Name:")
        if ok and nt and nt not in self.temp_colors:
            col = QColorDialog.getColor(Qt.gray, self)
            if col.isValid(): self.temp_colors[nt] = col.name(); self._add_nt_list_item(nt, col.name()); self.def_node_type.addItem(nt)

    def _add_edge_type(self):
        et, ok = QInputDialog.getText(self, "New Edge Type", "Type Name:")
        if ok and et and et not in self.temp_edges:
            col = QColorDialog.getColor(QColor("#adb5bd"), self)
            if col.isValid(): self.temp_edges[et] = col.name(); self._add_et_list_item(et, col.name()); self.def_edge_type.addItem(et)

    def _change_node_color(self):
        item = self.nt_list.currentItem()
        if not item: return
        nt = item.data(Qt.UserRole); c = QColorDialog.getColor(QColor(self.temp_colors[nt]), self)
        if c.isValid(): self.temp_colors[nt] = c.name(); pix = QPixmap(14, 14); pix.fill(c); item.setIcon(QIcon(pix))

    def _change_edge_color(self):
        item = self.et_list.currentItem()
        if not item: return
        et = item.data(Qt.UserRole); c = QColorDialog.getColor(QColor(self.temp_edges[et]), self)
        if c.isValid(): self.temp_edges[et] = c.name(); pix = QPixmap(14, 14); pix.fill(c); item.setIcon(QIcon(pix))

    def _delete_node_type(self):
        item = self.nt_list.currentItem()
        if not item: return
        nt = item.data(Qt.UserRole)
        if nt == "default": return QMessageBox.warning(self, "Denied", "Cannot delete the 'default' node type.")
        if any(n.node_type == nt for n in self.scene.nodes.values()): return QMessageBox.warning(self, "In Use", f"Cannot delete '{nt}': It is in use by nodes on the canvas.")
        del self.temp_colors[nt]
        if nt in self.temp_schema: del self.temp_schema[nt]
        self.nt_list.takeItem(self.nt_list.row(item))
        self.def_node_type.removeItem(self.def_node_type.findText(nt))

    def _delete_edge_type(self):
        item = self.et_list.currentItem()
        if not item: return
        et = item.data(Qt.UserRole)
        if et == "relationship": return QMessageBox.warning(self, "Denied", "Cannot delete the 'relationship' edge type.")
        if any(e.edge_type == et for e in self.scene.edges.values()): return QMessageBox.warning(self, "In Use", f"Cannot delete '{et}': It is in use by edges on the canvas.")
        del self.temp_edges[et]
        self.et_list.takeItem(self.et_list.row(item))
        self.def_edge_type.removeItem(self.def_edge_type.findText(et))

    def _build_props_tab(self):
        w = QWidget(); lay = QVBoxLayout(w); ctrl_lay = QHBoxLayout(); ctrl_lay.addWidget(QLabel("Target Type:"))
        self.schema_combo = QComboBox(); self.schema_combo.addItems(["__universal__"] + list(self.temp_colors.keys()))
        self.schema_combo.currentTextChanged.connect(self._load_schema_list)
        ctrl_lay.addWidget(self.schema_combo); lay.addLayout(ctrl_lay)
        self.schema_list = QListWidget(); lay.addWidget(self.schema_list)
        btn_lay = QHBoxLayout(); add_p = QPushButton("+ Add Property"); del_p = QPushButton("- Delete Property")
        del_p.setStyleSheet(f"background:{gc('ACCENT2')}; color:white; border-radius:4px; padding:6px 12px; font-weight:bold;")
        add_p.clicked.connect(self._add_schema_prop); del_p.clicked.connect(self._del_schema_prop)
        btn_lay.addWidget(add_p); btn_lay.addWidget(del_p); lay.addLayout(btn_lay)
        self._load_schema_list(self.schema_combo.currentText()); return w

    def _load_schema_list(self, target):
        self.schema_list.clear(); self.schema_list.addItems(self.temp_schema.get(target, []))

    def _add_schema_prop(self):
        target = self.schema_combo.currentText()
        p, ok = QInputDialog.getText(self, "New Property", "Property Key:")
        if ok and p:
            if target not in self.temp_schema: self.temp_schema[target] = []
            if p not in self.temp_schema[target]: self.temp_schema[target].append(p); self.schema_list.addItem(p)

    def _del_schema_prop(self):
        item = self.schema_list.currentItem()
        if not item: return
        target = self.schema_combo.currentText()
        self.temp_schema[target].remove(item.text()); self.schema_list.takeItem(self.schema_list.row(item))

    def _apply(self):
        self.temp_settings["ui_font_size"] = self.ui_font_spin.value()
        self.temp_settings["sidebar_font_size"] = self.sb_font_spin.value()
        self.temp_settings["default_node_type"] = self.def_node_type.currentText()
        self.temp_settings["default_edge_type"] = self.def_edge_type.currentText()
        self.temp_settings["default_direction"] = self.def_direction.currentText()

        if self.temp_settings["default_node_type"] not in self.temp_colors: self.temp_settings["default_node_type"] = list(self.temp_colors.keys())[0] if self.temp_colors else "default"
        if self.temp_settings["default_edge_type"] not in self.temp_edges: self.temp_settings["default_edge_type"] = list(self.temp_edges.keys())[0] if self.temp_edges else "relationship"

        for node in self.scene.nodes.values():
            old_expected = PROPERTY_SCHEMA.get("__universal__", []) + PROPERTY_SCHEMA.get(node.node_type, [])
            new_expected = self.temp_schema.get("__universal__", []) + self.temp_schema.get(node.node_type, [])
            for k in new_expected:
                if k not in node.properties: node.properties[k] = ""
            for k in set(old_expected) - set(new_expected):
                if k in node.properties and str(node.properties.get(k, "")).strip() == "": del node.properties[k]
            node.color = self.temp_colors.get(node.node_type, node.color)

        for edge in self.scene.edges.values():
            edge.color = self.temp_edges.get(edge.edge_type, edge.color)

        NODE_TYPE_COLORS.clear(); NODE_TYPE_COLORS.update(self.temp_colors)
        EDGE_TYPE_COLORS.clear(); EDGE_TYPE_COLORS.update(self.temp_edges)
        PROPERTY_SCHEMA.clear(); PROPERTY_SCHEMA.update(self.temp_schema)
        SETTINGS.update(self.temp_settings)
        self.accept()