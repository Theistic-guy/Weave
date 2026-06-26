"""
ui.py — Sidebar, SearchBar, SettingsDialog, FileExplorer
"""
import os, copy
from PyQt5.QtWidgets import (
    QApplication,QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QScrollArea, QFrame, QComboBox, QDialog, QDialogButtonBox, QFormLayout,
    QColorDialog, QSpinBox, QGroupBox, QListWidget, QListWidgetItem,
    QMessageBox, QTabWidget, QInputDialog, QSizePolicy, QTextEdit, QCheckBox,
    QTreeWidget, QTreeWidgetItem, QAbstractItemView,QStyle, QFileDialog,QGridLayout,QToolButton
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QPixmap, QIcon,QPalette
from PyQt5.QtCore import Qt, pyqtSignal, QEvent, QFileSystemWatcher, QTimer

import config
from config import gc, qc
import gitsync
from utils import pick_color,is_dark_theme
from colorpalette import ColorPaletteDialog

# ─────────────────────────────────────────────────────────────────────────────
#  Shared style helpers
# ─────────────────────────────────────────────────────────────────────────────
def _inp_ss():
    sf = config.SETTINGS["sidebar_font_size"]
    return (f"QLineEdit {{ background:{gc('BG_CARD')}; color:{gc('TEXT_PRIMARY')};"
            f" border:1px solid {gc('BORDER')}; border-radius:6px;"
            f" padding:5px 9px; font-size:{sf}px; }}"
            f" QLineEdit:focus {{ border-color:{gc('ACCENT')}; }}")

def _textedit_ss():
    sf = config.SETTINGS["sidebar_font_size"]
    return (f"QTextEdit {{ background:{gc('BG_CARD')}; color:{gc('TEXT_PRIMARY')};"
            f" border:1px solid {gc('BORDER')}; border-radius:6px;"
            f" padding:6px 8px; font-size:{sf}px; }}"
            f" QTextEdit:focus {{ border-color:{gc('ACCENT')}; }}")

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

class SidebarResizeHandle(QWidget):
    HANDLE_W = 10

    def __init__(self, sidebar):
        super().__init__(sidebar)
        self.sidebar = sidebar
        self._dragging = False
        self._start_global_x = 0
        self._start_width = 0
        self.setCursor(Qt.SizeHorCursor)
        self.setMouseTracking(True)
        self.setStyleSheet("background: transparent;")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self.sidebar._collapsed:
                self.sidebar.set_collapsed(False)
                event.accept()
                return

            self._dragging = True
            self._start_global_x = event.globalPos().x()
            self._start_width = self.sidebar.width()
            event.accept()
            return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not self._dragging:
            self.setCursor(Qt.SizeHorCursor)
            super().mouseMoveEvent(event)
            return

        dx = self._start_global_x - event.globalPos().x()
        new_width = max(240, self._start_width + dx)

        self.sidebar._expanded_width = new_width
        
        self.sidebar.setMinimumWidth(240)
        self.sidebar.setMaximumWidth(16777215)
        self.sidebar.resize(new_width, self.sidebar.height())

        host = self.sidebar.parentWidget()
        if host and hasattr(host, "reflow"):
            host.reflow()

        event.accept()

    def mouseReleaseEvent(self, event):
        if self._dragging and event.button() == Qt.LeftButton:
            self._dragging = False
            event.accept()
            return

        super().mouseReleaseEvent(event)


class Sidebar(QWidget):
    def __init__(self, scene,parent=None):
        super().__init__(parent)
        self.scene = scene
        self._node = None
        self._edge = None
        self._group = None
        self._expanded_width = 290
        self._collapsed_width = 32
        self._collapsed = False
        self.inspector_pinned = False
        self._last_kind = None
        self._last_item = None
        self.pin_btn = QToolButton()
        self.pin_btn.clicked.connect(self._toggle_pin)
        self.pin_btn.setCheckable(True)
        self.pin_btn.setText("📌")
        self._section_collapsed = {"sticky": False, "notes": False}
        self.setMinimumWidth(240)
        self.setMaximumWidth(16777215)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

        
        

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.header_wrap = QFrame()
        header_lay = QHBoxLayout(self.header_wrap)
        header_lay.setContentsMargins(0, 0, 0, 0)
        header_lay.setSpacing(0)
        self.header = QLabel("Properties")
        self.collapse_btn = QPushButton(">")
        self.collapse_btn.setFixedSize(self._collapsed_width, 42)
        self.collapse_btn.setToolTip("Collapse inspector")
        self.collapse_btn.clicked.connect(self.toggle_collapsed)
        self.pin_btn.setToolTip("Pin inspector")
        self.pin_btn.clicked.connect(self._toggle_pin)
        
        self.pin_btn.setAutoRaise(True)
        self.pin_btn.setCursor(Qt.PointingHandCursor)
        self.pin_btn.setFixedSize(24, 24)
        header_lay.addSpacing(6)
        header_lay.addWidget(self.header, 1)
        header_lay.addWidget(self.pin_btn)
        header_lay.addWidget(self.collapse_btn)
        root.addWidget(self.header_wrap)

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

        self._restoring_width = False
        self._resize_handle = SidebarResizeHandle(self)
        self._resize_handle.setGeometry(
            0, 0, SidebarResizeHandle.HANDLE_W, self.height()
        )
        self._resize_handle.hide()
        self._resize_handle.raise_()

        self.apply_style()
        self.show_empty()

    def apply_style(self):
        sf = config.SETTINGS["sidebar_font_size"]
        self.setStyleSheet(f"background:{gc('BG_PANEL')}")
        self.pin_btn.setStyleSheet(f"""
        QToolButton {{
            background: transparent;
            border: none;
            color: {gc('TEXT_MUTED')};
            font-size: {sf+1}px;
        }}

        QToolButton:hover {{
            color: {gc('TEXT_PRIMARY')};
            background: {gc('BG_CARD')};
            border-radius: 4px;
        }}
        """)
        self.header_wrap.setStyleSheet(
            f"QFrame {{ background:{gc('BG_DARK')};"
            f" border-bottom:1px solid {gc('BORDER')}; }}")
        self.header.setStyleSheet(
            f"QLabel {{ background:{gc('BG_DARK')}; color:{gc('TEXT_PRIMARY')};"
            f" font-size:{sf+3}px; font-weight:bold;"
            f" padding:14px 16px; border:none; }}")
        self.collapse_btn.setStyleSheet(
            f"QPushButton {{ background:transparent; color:{gc('TEXT_MUTED')};"
            f" border:none; font-size:{sf+4}px; font-weight:bold; }}"
            f" QPushButton:hover {{ background:{gc('BG_CARD')};"
            f" color:{gc('TEXT_PRIMARY')}; }}")
        self.scroll.setStyleSheet(
            f"QScrollArea {{ background:transparent; border:none; }}"
            f" QScrollBar:vertical {{ background:{gc('BG_DARK')}; width:6px; border-radius:3px; }}"
            f" QScrollBar::handle:vertical {{ background:{gc('BORDER')}; border-radius:3px; min-height:20px; }}")
        self.content.setStyleSheet(f"background:{gc('BG_PANEL')};")

    def toggle_collapsed(self):
        self.set_collapsed(not self._collapsed)

    def set_collapsed(self, collapsed):

        if collapsed and not self._collapsed:
            self._expanded_width = self.width()

        self._collapsed = collapsed
        if collapsed:
            self.setStyleSheet(f"background:{gc('BG_PANEL')};border-left: 1px solid {gc('BORDER')}")
        else:
            self.setStyleSheet(f"background:{gc('BG_PANEL')}")
        self.header.setVisible(not collapsed)
        self.pin_btn.setVisible(not collapsed)
        self.scroll.setVisible(not collapsed)
        self.collapse_btn.setText("<" if collapsed else ">")
        self.collapse_btn.setToolTip(
            "Expand inspector" if collapsed else "Collapse inspector")
        
        if hasattr(self, "_resize_handle"):
            self._resize_handle.setVisible(not collapsed)


        if collapsed:
            self.setFixedWidth(self._collapsed_width)
        else:
            target = self._expanded_width
            self._restoring_width = True

            self.setMinimumWidth(240)
            self.setMaximumWidth(16777215)
            self.resize(target, self.height())

            self._restoring_width = False


        host = self.parentWidget()
        if host and hasattr(host, "reflow"):
            host.reflow()

    def _install_zoom_filters(self):
        widgets = [self, self.header_wrap, self.scroll, self.scroll.viewport(), self.content]
        widgets.extend(self.findChildren(QWidget))

        for w in widgets:
            if w is not None:
                w.installEventFilter(self)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Wheel and (event.modifiers() & Qt.ControlModifier):
            self._apply_sidebar_zoom(event.angleDelta().y())
            event.accept()
            return True
        return super().eventFilter(obj, event)

    def _apply_sidebar_zoom(self, delta):
        step = 1 if delta > 0 else -1
        config.SETTINGS["sidebar_font_size"] = max(
            8,
            min(24, config.SETTINGS["sidebar_font_size"] + step)
        )

        current_node = self._node
        current_edge = self._edge
        current_group = self._group

        self.apply_style()

        if current_node is not None:
            self.show_node(current_node)
        elif current_edge is not None:
            self.show_edge(current_edge)
        elif current_group is not None:
            self.show_group(current_group)
        else:
            self.show_empty()

        self._install_zoom_filters()

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

    def _collapsible_section(self, key, title):
        collapsed = self._section_collapsed.get(key, False)
        head = QFrame()
        head.setStyleSheet("background:transparent;")
        lay = QHBoxLayout(head)
        lay.setContentsMargins(0, 8, 0, 2)
        lay.setSpacing(6)

        sf = config.SETTINGS["sidebar_font_size"]
        lbl = QLabel(title.upper())
        lbl.setStyleSheet(
            f"color:{gc('TEXT_MUTED')}; font-size:{sf-3}px; font-weight:bold;"
            f" letter-spacing:1.5px; background:transparent;")
        btn = QPushButton("+" if collapsed else "-")
        btn.setFixedSize(22, 22)
        btn.setStyleSheet(
            f"QPushButton {{ background:{gc('BG_CARD')}; color:{gc('TEXT_PRIMARY')};"
            f" border:1px solid {gc('BORDER')}; border-radius:4px;"
            f" font-weight:bold; }}"
            f" QPushButton:hover {{ background:{gc('ACCENT')}; color:white; }}")
        def _toggle():
            self._section_collapsed[key] = not self._section_collapsed.get(key, False)
            if self._node:
                self.show_node(self._node)
        btn.clicked.connect(_toggle)
        lay.addWidget(lbl)
        lay.addStretch()
        lay.addWidget(btn)
        self.cl.addWidget(head)
        return not collapsed
    
    def _toggle_pin(self):
        self.inspector_pinned = self.pin_btn.isChecked()

        self.pin_btn.setText(
            "📍" if self.inspector_pinned else "📌"
        )

        self.pin_btn.setToolTip(
            "Unpin inspector"
            if self.inspector_pinned
            else "Pin inspector"
        )

    def show_empty(self):
        self._node = self._edge = self._group = None
        self._label_edit = None
        self._edge_label_edit = None
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
        self._install_zoom_filters()

    def show_node(self, node):
        self._last_kind = "node"
        self._last_item = node
        self._node = node; self._edge = None; self._group = None
        self._clear()
        self.header.setText(f"Node  ·  {node.node_id}")
        self._label_edit = None
        self._build_node_ui(node)
        self.cl.addStretch()
        self._install_zoom_filters()
        

    def show_edge(self, edge):
        self._last_kind = "edge"
        self._last_item = edge
        self._edge = edge; self._node = None; self._group = None
        self._clear()
        self.header.setText(f"Edge  ·  {edge.edge_id}")
        self._build_edge_ui(edge)
        self.cl.addStretch()
        self._install_zoom_filters()

    def show_group(self, group):
        self._last_kind = "group"
        self._last_item = group
        self._group = group; self._node = None; self._edge = None
        self._clear()
        sf = config.SETTINGS["sidebar_font_size"]
        self.header.setText(f"Group  ·  {group.group_id}")

        self._section("Name")
        name_edit = QLineEdit(group.name)
        name_edit.setStyleSheet(_inp_ss())
        def _save_name():
            group.name = name_edit.text()
            group.update()
            self.scene.graph_changed.emit()
        name_edit.editingFinished.connect(_save_name)
        self.cl.addWidget(name_edit)

        self._section("Colour")
        cr = QFrame(); cr.setStyleSheet("background:transparent;")
        cl = QHBoxLayout(cr); cl.setContentsMargins(0, 0, 0, 0); cl.setSpacing(6)
        sw = QPushButton(); sw.setFixedSize(22, 22)
        sw.setStyleSheet(_swatch_ss(group.color))
        col_lbl = QLabel("Group colour")
        col_lbl.setStyleSheet(
            f"color:{gc('TEXT_MUTED')}; background:transparent; font-size:{sf-1}px;")
        def _pick_col():
            col = pick_color(
                self,
                group.color
            )

            if col:
                group.color = col
                sw.setStyleSheet(_swatch_ss(group.color))
                group.update()
                self.scene.graph_changed.emit()
        sw.clicked.connect(_pick_col)
        cl.addWidget(sw); cl.addWidget(col_lbl); cl.addStretch()
        self.cl.addWidget(cr)

        self._section(f"Members ({len(group.member_ids)})")
        for nid in group.member_ids:
            node = self.scene.nodes.get(nid)
            if not node:
                continue
            mb = QPushButton(f"↗  {node.label}")
            mb.setToolTip(f"Jump to: {node.label}")
            mb.setStyleSheet(
                f"QPushButton {{ text-align:left; padding:5px 10px;"
                f" background:{gc('BG_CARD')}; color:{gc('TEXT_PRIMARY')};"
                f" border:1px solid {gc('BORDER')}; border-radius:4px;"
                f" font-size:{sf-1}px; }}"
                f" QPushButton:hover {{ background:{gc('ACCENT')}; color:white; }}")
            def _jump(checked=False, n=node):
                self.scene.clearSelection()
                n.setSelected(True)
                self.scene.node_selected.emit(n)
                for view in self.scene.views():
                    view.centerOn(n)
            mb.clicked.connect(_jump)
            self.cl.addWidget(mb)

        ub = QPushButton("⬡  Ungroup")
        ub.setStyleSheet(_btn_ss(gc("ACCENT2")))
        ub.clicked.connect(lambda: (self.scene.ungroup(group), self.show_empty()))
        self.cl.addWidget(ub)
        self.cl.addStretch()
        self._install_zoom_filters()

    # ── Node UI ───────────────────────────────────────────────────────────────
    def _build_node_ui(self, node):
        sf = config.SETTINGS["sidebar_font_size"]
        self._section("Identity")

        le = QLineEdit(node.label)
        le.setStyleSheet(_inp_ss())
        self._label_edit = le   # stored so show_node can focus it
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
            col = pick_color(
                self,
                node.color
            )

            if col:
                node.color = col
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

        # Connections list — clickable jump buttons
        if node.edges:
            self._section(f"Edges ({len(node.edges)})")
            for e in node.edges:
                other = e.target_node if e.source_node is node else e.source_node
                direction_lbl = e.direction
                edge_lbl = f"  [{e.label}]" if e.label else ""
                btn_text = f"{direction_lbl} {other.label}{edge_lbl}"
                jump_btn = QPushButton(btn_text)
                jump_btn.setToolTip(f"Jump to: {other.label}")
                jump_btn.setStyleSheet(
                    f"QPushButton {{ text-align:left; padding:5px 10px;"
                    f" background:{gc('BG_CARD')}; color:{gc('TEXT_PRIMARY')};"
                    f" border:1px solid {gc('BORDER')}; border-radius:4px;"
                    f" font-size:{sf-1}px; }}"
                    f" QPushButton:hover {{ background:{gc('ACCENT')}; color:white;"
                    f" border-color:{gc('ACCENT')}; }}")
                # Capture other node for the closure
                def _jump(checked=False, target=other):
                    self.scene.clearSelection()
                    target.setSelected(True)
                    self.scene.node_selected.emit(target)
                    # Centre the view on the target node
                    for view in self.scene.views():
                        view.centerOn(target)
                jump_btn.clicked.connect(_jump)
                self.cl.addWidget(jump_btn)

        if self._collapsible_section("sticky", "Sticky Text"):
            show = QCheckBox("Show on canvas")
            show.setChecked(node.sticky_visible)
            show.setStyleSheet(
                f"QCheckBox {{ color:{gc('TEXT_PRIMARY')}; background:transparent;"
                f" font-size:{sf}px; }}"
                f" QCheckBox::indicator {{ width:14px; height:14px; }}")
            def _toggle_sticky(v, n=node):
                n.set_sticky_visible(bool(v))
                self.scene.graph_changed.emit()
            show.stateChanged.connect(_toggle_sticky)
            self.cl.addWidget(show)

            dock = QComboBox()
            dock_map = {
                "Dock Left": "left",
                "Dock Right": "right",
                "Dock Above": "above",
                "Dock Below": "below",
            }
            dock.addItems(list(dock_map.keys()))
            current = next((label for label, value in dock_map.items()
                            if value == node.sticky_dock), "Dock Right")
            dock.setCurrentText(current)
            dock.setStyleSheet(_combo_ss())
            def _dock_changed(label, n=node):
                n.set_sticky_dock(dock_map.get(label, "right"))
                self.scene.graph_changed.emit()
            dock.currentTextChanged.connect(_dock_changed)
            self.cl.addWidget(dock)

            sticky_edit = QTextEdit()
            sticky_edit.setPlaceholderText("Text to float near this node")
            sticky_edit.setPlainText(node.sticky_text)
            sticky_edit.setFixedHeight(84)
            sticky_edit.setStyleSheet(_textedit_ss())
            def _sticky_changed(n=node, edit=sticky_edit):
                n.set_sticky_text(edit.toPlainText())
                self.scene.graph_changed.emit()
            sticky_edit.textChanged.connect(_sticky_changed)
            self.cl.addWidget(sticky_edit)

        if self._collapsible_section("notes", "Notes"):
            notes = QTextEdit()
            notes.setPlaceholderText("Private notes for this node")
            notes.setPlainText(node.notes)
            notes.setFixedHeight(110)
            notes.setStyleSheet(_textedit_ss())
            def _notes_changed(n=node, edit=notes):
                n.set_notes(edit.toPlainText())
                self.scene.graph_changed.emit()
            notes.textChanged.connect(_notes_changed)
            self.cl.addWidget(notes)
        db = QPushButton("🗑  Delete Node"); db.setStyleSheet(_btn_ss(gc("ACCENT2")))
        db.clicked.connect(lambda: (self.scene.delete_node(node), self.show_empty()))
        self.cl.addWidget(db)

    # ── Edge UI ───────────────────────────────────────────────────────────────
    def _build_edge_ui(self, edge):
        self._section("Line Style")
        lsc = QComboBox()
        lsc.addItems(["Solid", "Dashed", "Dotted"])
        lsc.setCurrentText(edge.line_style.capitalize())
        lsc.setStyleSheet(_combo_ss())
        lsc.currentTextChanged.connect(
            lambda s: (edge.set_line_style(s.lower()), self.scene.graph_changed.emit()))
        self.cl.addWidget(lsc)

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
            col = pick_color(
                self,
                edge.color
            )

            if col:
                edge.color = col
                sw.setStyleSheet(_swatch_ss(edge.color))
                edge._refresh_label_text()
                self.scene.update()
                self.scene.graph_changed.emit()
        sw.clicked.connect(_pick_col)
        cl.addWidget(sw); cl.addWidget(col_lbl); cl.addStretch()
        self.cl.addWidget(cr)

        self._section("Label")
        le = QLineEdit(edge.label)
        self._edge_label_edit = le
        le.setStyleSheet(_inp_ss())
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

    def focus_node_label(self):
        if getattr(self, "_label_edit", None):
            self._label_edit.setFocus()
            self._label_edit.selectAll()

    def focus_edge_label(self):
        if getattr(self, "_edge_label_edit", None):
            self._edge_label_edit.setFocus()
            self._edge_label_edit.selectAll()

    def mousePressEvent(self, event):
        
        if (
            self._collapsed and
            event.button() == Qt.LeftButton
        ):
            self.set_collapsed(False)
            # event.accept()
            # return 

        super().mousePressEvent(event)

    

    def resizeEvent(self, event):
        if hasattr(self, "_resize_handle"):
            self._resize_handle.setGeometry(
                0, 0, SidebarResizeHandle.HANDLE_W, self.height()
            )
            self._resize_handle.raise_()
        if not self._collapsed and  not self._restoring_width:
            self._expanded_width = max(self.width(), 240)
        super().resizeEvent(event)

    def clear_pin_memory(self):
        """Drop any remembered last-inspected item.

        Must be called whenever the scene's items are wholesale replaced or
        cleared (new file load, Clear Graph) — otherwise a pinned inspector
        keeps a reference to a now-deleted QGraphicsItem, and the next
        deselect crashes with 'wrapped C/C++ object has been deleted'.
        """
        self._last_item = None
        self._last_kind = None

    def restore_last_inspected(self):
        if self._last_item is None:
            self.show_empty()
            return

        try:
            if self._last_kind == "node":
                if self._last_item.node_id in self.scene.nodes:
                    self.show_node(self._last_item)
                else:
                    self.show_empty()

            elif self._last_kind == "edge":
                if self._last_item.edge_id in self.scene.edges:
                    self.show_edge(self._last_item)
                else:
                    self.show_empty()

            elif self._last_kind == "group":
                if self._last_item.group_id in self.scene.groups:
                    self.show_group(self._last_item)
                else:
                    self.show_empty()
        except RuntimeError:
            # The underlying C++ item was deleted out from under us (e.g. a
            # file load/Clear Graph happened without clear_pin_memory() being
            # called from somewhere it should have been). Fail safe instead
            # of crashing.
            self.clear_pin_memory()
            self.show_empty()




# ─────────────────────────────────────────────────────────────────────────────
#  SearchBar
# ─────────────────────────────────────────────────────────────────────────────
class SearchBar(QWidget):
    hidden_by_escape = pyqtSignal()

    def __init__(self, scene, view):
        super().__init__()
        self.scene = scene; self.view = view
        self._matches = []; self._match_idx = 0
        
        # Prevent the massive empty vertical gap
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 7, 12, 7); lay.setSpacing(6)

        self.icon = QLabel("🔍"); lay.addWidget(self.icon)
        self.edit = QLineEdit()
        self.edit.setPlaceholderText("Search… (Ctrl+F)")
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
            # Emit signal to tell the main window to untoggle the button and hide
            self.hidden_by_escape.emit() 
            return True
        return False

    def apply_style(self):
        sf = config.SETTINGS["app_ui_font_size"]
        self.setStyleSheet(
            f"background:{gc('BG_PANEL')}; border-bottom:1px solid {gc('BORDER')};")
        self.icon.setStyleSheet("font-size:14px; background:transparent; border:none;")
        self.edit.setStyleSheet(f"QLineEdit {{ background:{gc('BG_CARD')}; color:{gc('TEXT_PRIMARY')};"
            f" border:1px solid {gc('BORDER')}; border-radius:6px;"
            f" padding:5px 9px; font-size:{sf}px; }}"
            f" QLineEdit:focus {{ border-color:{gc('ACCENT')}; }}")
        bss = (f"QPushButton {{ background:{gc('BG_CARD')}; color:{gc('TEXT_PRIMARY')};"
               f" border:1px solid {gc('BORDER')}; border-radius:4px; }}"
               f" QPushButton:hover {{ background:{gc('ACCENT')}; color:white; }}")
        for b in (self.prev_btn, self.next_btn, self.clear_btn):
            b.setStyleSheet(bss)
        self.result_lbl.setStyleSheet(
            f"color:{gc('TEXT_MUTED')}; font-size:{sf-1}px; background:transparent; border:none;")

    def _search(self, text):
        text = text.strip().lower()
        self._matches = []
        self._match_idx = 0

        self.scene.clearSelection()

        if not text:
            self.result_lbl.setText("")
            return

        # ----------------------------
        # Nodes
        # ----------------------------
        for node in self.scene.nodes.values():
            match = text in node.label.lower()

            if (
                not match
                and config.SETTINGS["search_properties"]
            ):
                match = any(
                    text in str(k).lower()
                    or text in str(v).lower()
                    for k, v in node.properties.items()
                )

            if (
                not match
                and config.SETTINGS["search_notes"]
            ):
                match = text in (node.notes or "").lower()

            if (
                not match
                and config.SETTINGS["search_sticky_text"]
            ):
                match = text in (node.sticky_text or "").lower()

            if match:
                self._matches.append(node)
                node.setSelected(True)

        # ----------------------------
        # Edge Labels
        # ----------------------------
        if config.SETTINGS["search_edge_labels"]:
            for edge in self.scene.edges.values():
                if text in (edge.label or "").lower():
                    self._matches.append(edge)
                    edge.setSelected(True)

        # ----------------------------
        # Group Names
        # ----------------------------
        if config.SETTINGS["search_group_names"]:
            for group in self.scene.groups.values():
                if text in (group.name or "").lower():
                    self._matches.append(group)
                    group.setSelected(True)

        # ----------------------------
        # Canvas Text Items
        # ----------------------------
        if config.SETTINGS["search_canvas_text"]:
            for txt in self.scene.texts.values():
                if text in (txt.text or "").lower():
                    self._matches.append(txt)
                    txt.setSelected(True)

        # ----------------------------
        # Results
        # ----------------------------
        if self._matches:
            self._centre_on(0)
        else:
            self.result_lbl.setText("No matches")

    def _centre_on(self, idx):
        if not self._matches: return
        self._match_idx = idx % len(self._matches)
        self.view.centerOn(self._matches[self._match_idx])
        self.result_lbl.setText(f"{self._match_idx+1}/{len(self._matches)}")


# ─────────────────────────────────────────────────────────────────────────────
#  SettingsDialog
# ─────────────────────────────────────────────────────────────────────────────
class SettingsDialog(QDialog):
    def __init__(self, parent, scene):
        super().__init__(parent)
        self.scene = scene
        self.setWindowTitle("Settings")
        # Boosted minimum sizes to fix clipped text on buttons
        self.setMinimumSize(650, 620)
        self.resize(780, 620)

        # Deep copies — nothing touches global state until Save
        self.temp_colors   = copy.deepcopy(config.NODE_TYPE_COLORS)
        self.temp_edges    = copy.deepcopy(config.EDGE_TYPE_COLORS)
        self.temp_schema   = copy.deepcopy(config.PROPERTY_SCHEMA)
        self.temp_settings = copy.deepcopy(config.SETTINGS)

        self._node_type_renames = {}
        self._edge_type_renames = {}

        self._apply_base_style()

        main_lay = QVBoxLayout(self)
        main_lay.setSpacing(10)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_general_tab(),  "⚙  General")
        self.tabs.addTab(self._build_types_tab(),    "⬡  Node & Edge Types")
        self.tabs.addTab(self._build_props_tab(),    "⊞  Property Schema")
        self.tabs.addTab(self._build_sync_tab(),     "🔄  Sync")
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
            QCheckBox {{ color:{gc('TEXT_PRIMARY')}; background:transparent; }}
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
            }}
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
        gfl = QGridLayout(grp_font)
        self.ui_font_spin = QSpinBox(); self.ui_font_spin.setRange(7, 24)
        self.ui_font_spin.setValue(self.temp_settings["ui_font_size"])
        self.app_ui_spin = QSpinBox()
        self.app_ui_spin.setRange(8, 24)
        self.app_ui_spin.setValue(
            config.SETTINGS["app_ui_font_size"]
        )
        self.edge_label_size_spin = QSpinBox()
        self.edge_label_size_spin.setRange(8, 24)
        self.edge_label_size_spin.setValue(
            config.SETTINGS["edge_label_size"]
        )
        

        gfl.setHorizontalSpacing(20)
        gfl.setVerticalSpacing(8)

        gfl.addWidget(QLabel("Canvas Base Size"), 0, 0)
        gfl.addWidget(self.ui_font_spin,          0, 1)

        gfl.addWidget(QLabel("App UI Size"),      0, 2)
        gfl.addWidget(self.app_ui_spin,           0, 3)

        gfl.addWidget(QLabel("Edge Label Size"),  1, 0)
        gfl.addWidget(self.edge_label_size_spin,  1, 1)
       
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

        grp_pref = QGroupBox("Preferences")
        vbox_pref = QVBoxLayout(grp_pref)
        pref_form = QFormLayout()
        self.ask_edge_label_chk = QCheckBox()
        

        self.ask_edge_label_chk.setChecked(
            config.SETTINGS.get(
                "ask_edge_label_before_add",
                False
            )
        )
        self.hide_node_labels_chk = QCheckBox()
        self.hide_edge_labels_chk = QCheckBox()
        self.hide_node_bodies_chk = QCheckBox()
        
        self.hide_node_labels_chk.setChecked(config.SETTINGS["hide_node_labels"])
        self.hide_edge_labels_chk.setChecked(config.SETTINGS["hide_edge_labels"])
        self.hide_node_bodies_chk.setChecked(config.SETTINGS["hide_node_bodies"])
        pref_form.addRow("Ask edge label before adding new edge:", self.ask_edge_label_chk)
        pref_form.addRow("Hide Node Labels", self.hide_node_labels_chk)
        pref_form.addRow("Hide Edge Labels:", self.hide_edge_labels_chk)
        pref_form.addRow("Hide Node Bodies:", self.hide_node_bodies_chk)

        grp_search_in = QGroupBox("Search In")
        gdl_search_in = QGridLayout(grp_search_in)
        self.search_properties_chk = QCheckBox("Search properties")
        self.search_notes_chk      = QCheckBox("Search notes")
        self.search_sticky_chk     = QCheckBox("Search sticky text")
        self.search_edge_labels_chk = QCheckBox("Search edge labels")
        self.search_group_names_chk = QCheckBox("Search group names")
        self.search_canvas_text_chk = QCheckBox("Search canvas text items")
        

        self.search_properties_chk.setChecked(
            config.SETTINGS["search_properties"]
        )

        self.search_notes_chk.setChecked(
            config.SETTINGS["search_notes"]
        )

        self.search_sticky_chk.setChecked(
            config.SETTINGS["search_sticky_text"]
        )
        self.search_edge_labels_chk.setChecked(
            config.SETTINGS["search_edge_labels"]
        )
        self.search_group_names_chk.setChecked(
            config.SETTINGS["search_group_names"]
        )
        self.search_canvas_text_chk.setChecked(
            config.SETTINGS["search_canvas_text"]
        )
        gdl_search_in.addWidget(self.search_properties_chk, 0, 0)
        gdl_search_in.addWidget(self.search_edge_labels_chk, 0, 1)

        gdl_search_in.addWidget(self.search_notes_chk, 1, 0)
        gdl_search_in.addWidget(self.search_group_names_chk, 1, 1)

        gdl_search_in.addWidget(self.search_sticky_chk, 2, 0)
        gdl_search_in.addWidget(self.search_canvas_text_chk, 2, 1)
        gdl_search_in.setHorizontalSpacing(20)
        gdl_search_in.setVerticalSpacing(6)
        vbox_pref.addLayout(pref_form)
        vbox_pref.addWidget(grp_search_in)

        # ----------------------------------------------------------
        # Preferences are the only section that keeps growing.
        # Put just this section inside a scroll area so the dialog
        # itself can remain a fixed height.
        # ----------------------------------------------------------

        pref_container = QWidget()
        pref_layout = QVBoxLayout(pref_container)
        pref_layout.setContentsMargins(0, 0, 0, 0)
        pref_layout.addWidget(grp_pref)
        pref_layout.addStretch()

        pref_scroll = QScrollArea()
        pref_scroll.setWidgetResizable(True)
        pref_scroll.setFrameShape(QFrame.NoFrame)
        pref_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        pref_scroll.setWidget(pref_container)

        # Match the application's theme.
        pref_scroll.viewport().setStyleSheet(
            f"background:{gc('BG_PANEL')};"
        )
        pref_container.setStyleSheet(
            f"background:{gc('BG_PANEL')};"
        )

        # Give the scroll area a reasonable minimum height.
        pref_scroll.setMinimumHeight(220)

        lay.addWidget(pref_scroll)

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
        col = pick_color(
            self,
            "#888888"
        )

        if col:
            self.temp_colors[name] = col
            self._add_nt_item(name, col)
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

        for k, v in list(self._node_type_renames.items()):
            if v == old:
                self._node_type_renames[k] = new

        self._node_type_renames[old] = new
    

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
        col = pick_color(
            self,
            self.temp_colors[nt]
        )

        if col:
            self.temp_colors[nt] = col
            pix = QPixmap(14, 14)
            pix.fill(QColor(col))
            item.setIcon(QIcon(pix))

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
        col = pick_color(
            self,
            "#adb5bd"
        )

        if col:
            self.temp_edges[name] = col
            self._add_et_item(name, col)
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

        for k, v in list(self._edge_type_renames.items()):
            if v == old:
                self._edge_type_renames[k] = new

        self._edge_type_renames[old] = new
        
        
        item.setText(new)
        item.setData(Qt.UserRole, new)
        idx = self.def_edge_type.findText(old)
        if idx >= 0:
            self.def_edge_type.setItemText(idx, new)

    def _change_edge_color(self):
        item = self.et_list.currentItem()
        if not item: return
        et = item.data(Qt.UserRole)
        col = pick_color(
            self,
            self.temp_edges[et]
        )

        if col:
            self.temp_edges[et] = col
            pix = QPixmap(14, 14)
            pix.fill(QColor(col))
            item.setIcon(QIcon(pix))

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

    # ── Sync tab ──────────────────────────────────────────────────────────────
    def _build_sync_tab(self):
        w = QWidget(); lay = QVBoxLayout(w); lay.setSpacing(12)

        grp = QGroupBox("Git Repo (single-user, two-machine sync)")
        gl = QFormLayout(grp)

        path_row = QHBoxLayout()
        default_path = self.temp_settings.get("sync_repo_path", "") or self._default_sync_path()
        self.sync_path_edit = QLineEdit(default_path)
        self.sync_path_edit.setStyleSheet(_inp_ss())
        browse_btn = QPushButton("Browse…")
        browse_btn.setFixedHeight(28)
        browse_btn.clicked.connect(self._browse_sync_path)
        path_row.addWidget(self.sync_path_edit)
        path_row.addWidget(browse_btn)
        gl.addRow("Repo path:", path_row)

        self.sync_url_edit = QLineEdit(self.temp_settings.get("sync_remote_url", ""))
        self.sync_url_edit.setStyleSheet(_inp_ss())
        self.sync_url_edit.setPlaceholderText("git@github.com:user/weave-data.git")
        gl.addRow("Remote URL:", self.sync_url_edit)

        lay.addWidget(grp)

        link_row = QHBoxLayout()
        self.link_btn = QPushButton("🔗 Initialize / Link")
        self.link_btn.clicked.connect(self._do_link)
        link_row.addWidget(self.link_btn)
        link_row.addStretch()
        lay.addLayout(link_row)

        info = QLabel(
            "Links the folder above to the given remote for two-machine sync of the\n"
            ".weave file only (.bweave exports stay untouched, separate from this).\n\n"
            "Git must already be installed & configured (SSH keys etc.) on this machine —\n"
            "this feature just shells out to the git CLI and trusts your existing setup;\n"
            "it doesn't manage credentials or tokens itself.\n\n"
            "Once linked, use the 🔄 Sync button (Ctrl+Alt+S) in the main toolbar for\n"
            "day-to-day syncing — no need to come back to this tab."
        )
        info.setStyleSheet(f"color:{gc('TEXT_MUTED')}; font-size:11px;")
        info.setWordWrap(True)
        lay.addWidget(info)

        lay.addStretch()
        return w

    def _default_sync_path(self):
        """Default repo path = folder containing the currently-open .weave file."""
        fp = getattr(self.parent(), "_file_path", None)
        if fp:
            return os.path.dirname(os.path.abspath(fp))
        return ""

    def _browse_sync_path(self):
        start = self.sync_path_edit.text().strip() or os.path.expanduser("~")
        d = QFileDialog.getExistingDirectory(self, "Select Sync Folder", start)
        if d:
            self.sync_path_edit.setText(d)

    def _save_sync_settings(self):
        self.temp_settings["sync_repo_path"]  = self.sync_path_edit.text().strip()
        self.temp_settings["sync_remote_url"] = self.sync_url_edit.text().strip()

    def _do_link(self):
        repo_path  = self.sync_path_edit.text().strip()
        remote_url = self.sync_url_edit.text().strip()
        if not repo_path or not remote_url:
            QMessageBox.warning(self, "Missing info",
                "Both a repo path and a remote URL are needed to link.")
            return

        self.link_btn.setEnabled(False)
        self.link_btn.setText("Linking…")
        QApplication.processEvents()
        try:
            case, info = gitsync.detect_link_case(repo_path, remote_url)

            if case == "error":
                QMessageBox.critical(self, "Link failed", info)
                return

            if case == "already_linked":
                QMessageBox.information(self, "Already linked",
                    "This folder is already linked to that remote. Nothing to do.")
                self._save_sync_settings()
                return

            if case == "conflict_ambiguous":
                QMessageBox.critical(self, "Cannot link",
                    "This folder already contains files but isn't a git repo, and the\n"
                    "remote already has commits — linking these would create conflicting\n"
                    "histories.\n\n"
                    "Pick an empty folder instead (it'll be cloned from the remote), or\n"
                    "resolve this manually (e.g. move the existing files aside) and try again.")
                return

            if case == "repoint":
                resp = QMessageBox.question(
                    self, "Change remote?",
                    f"This folder is already a git repo pointing to:\n{info}\n\n"
                    f"Re-point it to:\n{remote_url}\n\n"
                    "This won't delete any commits — it just changes where future\n"
                    "pulls/pushes go.",
                    QMessageBox.Yes | QMessageBox.No)
                if resp != QMessageBox.Yes:
                    return
                res = gitsync.do_repoint(repo_path, remote_url)
                if not res.ok:
                    QMessageBox.critical(self, "Link failed", res.stderr or "git remote set-url failed.")
                    return
                QMessageBox.information(self, "Linked", "Remote updated.")
                self._save_sync_settings()
                return

            if case == "clone":
                res = gitsync.do_clone(remote_url, repo_path)
                if not res.ok:
                    QMessageBox.critical(self, "Link failed", res.stderr or "git clone failed.")
                    return
                QMessageBox.information(self, "Linked", "Repo cloned successfully.")
                self._save_sync_settings()
                return

            if case == "init_new":
                res = gitsync.do_init_new(repo_path, remote_url)
                if not res.ok:
                    QMessageBox.critical(self, "Link failed", res.stderr or "git init failed.")
                    return

                weave_files = gitsync.find_weave_files(repo_path)
                if weave_files:
                    resp = QMessageBox.question(
                        self, "Push initial files?",
                        f"Found {len(weave_files)} .weave file(s) already in this folder.\n"
                        "Commit and push them to the new remote now?",
                        QMessageBox.Yes | QMessageBox.No)
                    if resp == QMessageBox.Yes:
                        push_res = gitsync.do_first_commit_push(repo_path, weave_files)
                        if not push_res.ok:
                            QMessageBox.critical(self, "Push failed",
                                push_res.stderr or "Initial commit/push failed.")
                            return
                QMessageBox.information(self, "Linked", "Repo initialized and linked to remote.")
                self._save_sync_settings()
                return
        finally:
            self.link_btn.setEnabled(True)
            self.link_btn.setText("🔗 Initialize / Link")

    # ── Apply helpers ─────────────────────────────────────────────────────────
    def _collect_settings(self):
        self._save_sync_settings()
        self.temp_settings["ui_font_size"]      = self.ui_font_spin.value()
        self.temp_settings["app_ui_font_size"] = (
            self.app_ui_spin.value()
        )
        self.temp_settings["edge_label_size"] = (
            self.edge_label_size_spin.value()
        )
        self.temp_settings["default_node_type"] = self.def_node_type.currentText()
        self.temp_settings["default_edge_type"] = self.def_edge_type.currentText()
        self.temp_settings["default_direction"] = self.def_direction.currentText()
        self.temp_settings["ask_edge_label_before_add"] = (
            self.ask_edge_label_chk.isChecked()
        )
        self.temp_settings["hide_node_labels"] = self.hide_node_labels_chk.isChecked()
        self.temp_settings["hide_edge_labels"] = self.hide_edge_labels_chk.isChecked()
        self.temp_settings["hide_node_bodies"] = self.hide_node_bodies_chk.isChecked()
        self.temp_settings["search_properties"] = (
            self.search_properties_chk.isChecked()
        )

        self.temp_settings["search_notes"] = (
            self.search_notes_chk.isChecked()
        )

        self.temp_settings["search_sticky_text"] = (
            self.search_sticky_chk.isChecked()
        )
        self.temp_settings["search_edge_labels"] = self.search_edge_labels_chk.isChecked()
        self.temp_settings["search_group_names"] = self.search_group_names_chk.isChecked()
        self.temp_settings["search_canvas_text"] = self.search_canvas_text_chk.isChecked()
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
        


        for node in self.scene.nodes.values():
            if node.node_type in self._node_type_renames:
                node.node_type = self._node_type_renames[node.node_type]

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

        for edge in self.scene.edges.values():
            if edge.edge_type in self._edge_type_renames:
                edge.edge_type = self._edge_type_renames[edge.edge_type]

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


# ─────────────────────────────────────────────────────────────────────────────
#  FileExplorer — collapsible left sidebar (VS Code / Remnote style)
# ─────────────────────────────────────────────────────────────────────────────
SUPPORTED_EXT = {".json", ".weave", ".bweave"}

def _is_valid_graph_file(path: str) -> bool:
    """Return True only if the file looks like a Weave graph."""
    ext = os.path.splitext(path)[1].lower()
    if ext not in SUPPORTED_EXT:
        return False
    try:
        if ext == ".bweave":
            import zlib
            with open(path, "rb") as f:
                magic = f.read(4)
            return magic == b"BWVE"
        else:
            import json
            with open(path, encoding="utf-8") as f:
                d = json.load(f)
            return isinstance(d, dict) and ("nodes" in d or "edges" in d)
    except Exception:
        return False


class FileExplorer(QWidget):
    """
    Left-side file explorer.

    Signals
    -------
    open_file(str)   — emitted when the user double-clicks / activates a file
    """
    open_file = pyqtSignal(str)

    _EXPANDED_W  = 240
    _COLLAPSED_W = 32

    def __init__(self, parent=None):
        super().__init__(parent)
        self._collapsed  = False
        self._root_path  = None   # folder path (or None when single-file mode)
        self._file_path  = None   # single file path

        # ── Live filesystem watch state ─────────────────────────────────────
        # _path_to_item: normalized path -> QTreeWidgetItem currently showing it.
        # Rebuilt from scratch on every load_folder()/load_single_file() call —
        # never carried over from a previous folder/file.
        self._path_to_item = {}
        self._watcher = QFileSystemWatcher(self)
        self._watcher.directoryChanged.connect(self._on_dir_changed)
        self._watcher.fileChanged.connect(self._on_file_changed)
        self._pending_refresh_dirs = set()
        self._pending_single_file_check = False
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.timeout.connect(self._process_pending_refreshes)

        self.setFixedWidth(self._EXPANDED_W)
        self.setMinimumWidth(self._COLLAPSED_W)

        root_lay = QVBoxLayout(self)
        root_lay.setContentsMargins(0, 0, 0, 0)
        root_lay.setSpacing(0)

        # ── Header bar ────────────────────────────────────────────────────────
        self._header = QFrame()
        self._header.setFixedHeight(42)
        h_lay = QHBoxLayout(self._header)
        h_lay.setContentsMargins(10, 0, 4, 0)
        h_lay.setSpacing(4)

        self._title = QLabel("Explorer")
        self._title.setStyleSheet(
            f"color:{gc('TEXT_PRIMARY')}; font-weight:bold; font-size:13px;"
            f" background:transparent; border:none;")
        h_lay.addWidget(self._title, 1)

        self._toggle_btn = QPushButton("‹")
        self._toggle_btn.setFixedSize(28, 28)
        self._toggle_btn.setToolTip("Collapse explorer  (Ctrl+E)")
        self._toggle_btn.clicked.connect(self.toggle_collapsed)
        self._toggle_btn.setStyleSheet(self._btn_style())
        h_lay.addWidget(self._toggle_btn)

        root_lay.addWidget(self._header)

        # ── Thin separator line ───────────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background:{gc('BORDER')}; border:none;")
        root_lay.addWidget(sep)

        # ── Tree widget ───────────────────────────────────────────────────────
        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.setIndentation(16)
        self._tree.setAnimated(True)
        self._tree.setSelectionMode(QAbstractItemView.SingleSelection)
        self._tree.itemActivated.connect(self._on_item_activated)
        self._tree.setStyleSheet(self._tree_style())


        self._init_icons()
        self._tree.setRootIsDecorated(True)
        self._tree.setItemsExpandable(True)
        self._tree.setExpandsOnDoubleClick(True)
        self._tree.setUniformRowHeights(True)
        self._tree.itemExpanded.connect(self._update_folder_icon)
        self._tree.itemCollapsed.connect(self._update_folder_icon)

        root_lay.addWidget(self._tree, 1)

        # ── Empty-state hint (shown when nothing is loaded) ───────────────────
        self._hint = QLabel(
            "Use  File ▾  to open\na file or folder.")
        self._hint.setAlignment(Qt.AlignCenter)
        self._hint.setWordWrap(True)
        self._hint.setStyleSheet(
            f"color:{gc('TEXT_MUTED')}; font-size:11px;"
            f" padding:20px 12px; background:transparent;")
        root_lay.addWidget(self._hint)
        root_lay.addStretch()

        self._apply_header_style()
        self._sync_visibility()

    # ── Public API ────────────────────────────────────────────────────────────
    def load_single_file(self, path: str):
        """Show exactly one file entry (Open File mode)."""
        self._teardown_watch_state()
        self._root_path = None
        self._file_path = path
        self._tree.clear()
        item = QTreeWidgetItem([os.path.basename(path)])
        item.setData(0, Qt.UserRole, path)
        item.setToolTip(0, path)
        self._apply_item_visuals(item, False)
        self._tree.addTopLevelItem(item)
        self._tree.expandAll()
        self._hint.hide()
        self._tree.show()

        self._path_to_item[self._norm(path)] = item
        # Watch the *parent* folder so a delete/rename/replace of this one
        # file (e.g. from outside the app, or a git pull) is still noticed —
        # QFileSystemWatcher can't watch a path that doesn't exist, and a
        # single file offers no useful directoryChanged signal of its own.
        parent_dir = os.path.dirname(os.path.abspath(path))
        if parent_dir and os.path.isdir(parent_dir):
            self._watcher.addPath(parent_dir)

    def load_folder(self, folder: str):
        """Show the folder tree (Open Folder mode), only supported files/dirs."""
        self._teardown_watch_state()
        self._root_path = folder
        self._file_path = None
        self._tree.clear()
        self._title.setText(os.path.basename(folder) or folder)
        root_item = QTreeWidgetItem([os.path.basename(folder) or folder])
        root_item.setData(0, Qt.UserRole, folder)
        root_item.setToolTip(0, folder)
        self._store_item_name(root_item, os.path.basename(folder) or folder)
        self._apply_item_visuals(root_item, True)
        self._set_folder_label(root_item, True)
        self._path_to_item[self._norm(folder)] = root_item
        self._watch_dir(folder)
        self._populate(root_item, folder)
        self._tree.addTopLevelItem(root_item)
        root_item.setExpanded(True)
        self._update_folder_icon(root_item)
        self._hint.hide()
        self._tree.show()

    def apply_style(self):
        self._apply_header_style()
        self._tree.setStyleSheet(self._tree_style())
        self._hint.setStyleSheet(
            f"color:{gc('TEXT_MUTED')}; font-size:11px;"
            f" padding:20px 12px; background:transparent;")
        self.setStyleSheet(f"background:{gc('BG_PANEL')};")

    def toggle_collapsed(self):
        self.set_collapsed(not self._collapsed)

    def set_collapsed(self, val: bool):
        self._collapsed = val
        self._sync_visibility()

    def wheelEvent(self, event):

        if event.modifiers() & Qt.ControlModifier:

            step = 1 if event.angleDelta().y() > 0 else -1

            config.SETTINGS["explorer_font_size"] = max(
                8,
                min(
                    24,
                    config.SETTINGS["explorer_font_size"] + step
                )
            )

            self.apply_style()

            event.accept()
            return

        super().wheelEvent(event)

    def mousePressEvent(self, event):
        if self._collapsed and event.button() == Qt.LeftButton:
            self.set_collapsed(False)
            event.accept()
            return

        super().mousePressEvent(event)

    # ── Internal ──────────────────────────────────────────────────────────────
    def _populate(self, parent_item: QTreeWidgetItem, folder: str):
        """Recursively add sub-folders and supported files under parent_item."""
        try:
            entries = sorted(os.scandir(folder), key=lambda e: (not e.is_dir(), e.name.lower()))
        except PermissionError:
            return

        for entry in entries:
            if entry.name.startswith("."):
                continue
            if entry.is_dir():
                child = QTreeWidgetItem([entry.name])
                child.setData(0, Qt.UserRole, entry.path)
                child.setToolTip(0, entry.path)
                self._store_item_name(child, entry.name)
                self._apply_item_visuals(child, True)
                self._set_folder_label(child, False)

                if self._dir_has_content(entry.path):
                    self._path_to_item[self._norm(entry.path)] = child
                    self._watch_dir(entry.path)
                    self._populate(child, entry.path)
                    parent_item.addChild(child)

            elif entry.is_file():
                ext = os.path.splitext(entry.name)[1].lower()
                if ext in SUPPORTED_EXT:
                    child = QTreeWidgetItem([entry.name])
                    child.setData(0, Qt.UserRole, entry.path)
                    child.setToolTip(0, entry.path)
                    self._apply_item_visuals(child, False)
                    self._path_to_item[self._norm(entry.path)] = child
                    parent_item.addChild(child)

    def _dir_has_content(self, folder: str) -> bool:
        """Recursively check if folder contains any supported files."""
        try:
            for entry in os.scandir(folder):
                if entry.name.startswith("."):
                    continue
                if entry.is_file():
                    ext = os.path.splitext(entry.name)[1].lower()
                    if ext in SUPPORTED_EXT:
                        return True
                elif entry.is_dir() and self._dir_has_content(entry.path):
                    return True
        except PermissionError:
            pass
        return False

    # ── Filesystem watch / live refresh ─────────────────────────────────────────
    # Design: QFileSystemWatcher only ever drives *what the tree displays*. It
    # never touches canvas/editor state — content the user is editing is never
    # reloaded out from under them just because a file changed on disk.
    @staticmethod
    def _norm(path: str) -> str:
        return os.path.normpath(os.path.abspath(path))

    def _watch_dir(self, path: str):
        """Add a directory to the watcher, ignoring duplicates/missing paths."""
        if path and os.path.isdir(path) and path not in self._watcher.directories():
            self._watcher.addPath(path)

    def _teardown_watch_state(self):
        """Fully reset watch state. Called at the start of every
        load_folder()/load_single_file() — never carry watched paths,
        pending refreshes, or the path->item map over from a previous
        folder/file."""
        dirs = self._watcher.directories()
        if dirs:
            self._watcher.removePaths(dirs)
        files = self._watcher.files()
        if files:
            self._watcher.removePaths(files)
        self._path_to_item.clear()
        self._pending_refresh_dirs.clear()
        self._pending_single_file_check = False
        self._refresh_timer.stop()

    def _on_dir_changed(self, path: str):
        if self._root_path is None:
            # Single-file mode: the only thing we watch is the open file's
            # parent folder, purely to notice if *that one file* disappears
            # or gets replaced. Nothing else in that folder is shown.
            self._pending_single_file_check = True
        else:
            self._pending_refresh_dirs.add(self._norm(path))
        self._refresh_timer.start(250)  # debounce rapid bursts (e.g. a git pull)

    def _on_file_changed(self, path: str):
        # Currently informational only (content edits aren't reflected in the
        # tree); deletion is handled via the parent directory's
        # directoryChanged, which always fires alongside this.
        pass

    def _process_pending_refreshes(self):
        if self._pending_single_file_check:
            self._pending_single_file_check = False
            self._refresh_single_file_presence()
            return

        dirs, self._pending_refresh_dirs = self._pending_refresh_dirs, set()
        for d in dirs:
            self._refresh_branch(d)

    def _refresh_single_file_presence(self):
        """Single-file mode: if the one tracked file vanished (deleted,
        renamed, or replaced from outside the app), fall back to the empty
        hint state rather than show a stale, dead tree entry."""
        if not self._file_path or os.path.exists(self._file_path):
            return
        self._teardown_watch_state()
        self._root_path = None
        self._file_path = None
        self._tree.clear()
        self._hint.show()
        self._tree.hide()

    def _forget_subtree(self, item: QTreeWidgetItem):
        """Remove `item` and all its descendants from _path_to_item before
        the item itself is discarded, so the map never holds stale entries
        pointing at deleted QTreeWidgetItems."""
        path = item.data(0, Qt.UserRole)
        if path:
            self._path_to_item.pop(self._norm(path), None)
        for i in range(item.childCount()):
            self._forget_subtree(item.child(i))

    def _capture_expanded(self, item: QTreeWidgetItem) -> set:
        """Snapshot which descendant folder paths are currently expanded."""
        expanded = set()
        def walk(it):
            p = it.data(0, Qt.UserRole)
            if p and it.isExpanded():
                expanded.add(self._norm(p))
            for i in range(it.childCount()):
                walk(it.child(i))
        walk(item)
        return expanded

    def _restore_expanded(self, item: QTreeWidgetItem, expanded: set):
        def walk(it):
            p = it.data(0, Qt.UserRole)
            if p and self._norm(p) in expanded:
                it.setExpanded(True)
                self._update_folder_icon(it)
            for i in range(it.childCount()):
                walk(it.child(i))
        walk(item)

    def _refresh_branch(self, dir_path: str):
        """Rebuild the children of whichever tree item corresponds to
        dir_path, preserving expand-state and keeping the watcher's set of
        watched directories in sync with what's actually on disk."""
        norm = self._norm(dir_path)
        item = self._path_to_item.get(norm)
        if item is None:
            return  # stale/unknown path — folder no longer part of this tree

        if not os.path.isdir(dir_path):
            # The directory itself was removed/renamed; let the *parent's*
            # own refresh (triggered by its own directoryChanged) drop this
            # row. Just stop watching it ourselves to avoid a dangling watch.
            if dir_path in self._watcher.directories():
                self._watcher.removePath(dir_path)
            return

        expanded = self._capture_expanded(item)
        was_root_expanded = item.isExpanded()

        for i in reversed(range(item.childCount())):
            child = item.takeChild(i)
            self._forget_subtree(child)

        self._populate(item, dir_path)
        item.setExpanded(was_root_expanded)
        self._restore_expanded(item, expanded)
        self._update_folder_icon(item)
        self._prune_orphaned_watches()

    def _prune_orphaned_watches(self):
        """Drop any watched directory that's no longer represented in the
        tree — e.g. a folder that still exists on disk but lost its last
        qualifying file and is therefore no longer shown. Without this,
        such a directory would stay watched indefinitely for no purpose."""
        tracked = set(self._path_to_item.keys())
        for d in self._watcher.directories():
            if self._norm(d) not in tracked:
                self._watcher.removePath(d)

    def _on_item_activated(self, item: QTreeWidgetItem, _col: int):
        path = item.data(0, Qt.UserRole)
        if path and os.path.isfile(path):
            if not _is_valid_graph_file(path):
                name = os.path.basename(path)
                QMessageBox.warning(
                    self, "Incompatible file",
                    f"'{name}' doesn't look like a Weave graph file.\n"
                    "Only .json files exported by Weave are supported.")
                return
            self.open_file.emit(path)

    def _sync_visibility(self):
        collapsed = self._collapsed
        self.setFixedWidth(self._COLLAPSED_W if collapsed else self._EXPANDED_W)
        self._title.setVisible(not collapsed)
        self._tree.setVisible(not collapsed and not self._hint.isVisible()
                              or (not collapsed and self._tree.topLevelItemCount() > 0))
        self._hint.setVisible(not collapsed and self._tree.topLevelItemCount() == 0)
        self._toggle_btn.setText("›" if collapsed else "‹")
        self._toggle_btn.setToolTip(
            "Expand explorer  (Ctrl+E)" if collapsed else "Collapse explorer  (Ctrl+E)")

    def _apply_header_style(self):
        self.setStyleSheet(f"background:{gc('BG_PANEL')};")
        self._header.setStyleSheet(
            f"QFrame {{ background:{gc('BG_DARK')};"
            f" border-bottom:1px solid {gc('BORDER')}; }}")
        self._title.setStyleSheet(
            f"color:{gc('TEXT_PRIMARY')}; font-weight:bold; font-size:13px;"
            f" background:transparent; border:none;")
        self._toggle_btn.setStyleSheet(self._btn_style())

    def _btn_style(self):
        return (f"QPushButton {{ background:transparent; color:{gc('TEXT_MUTED')};"
                f" border:none; font-size:16px; font-weight:bold; border-radius:4px; }}"
                f" QPushButton:hover {{ background:{gc('BG_CARD')};"
                f" color:{gc('TEXT_PRIMARY')}; }}")

    def _tree_style(self):
        return (
        f"""
        QTreeWidget {{
            background:{gc('BG_PANEL')};
            color:{gc('TEXT_PRIMARY')};
            border:none;
            font-size:{config.SETTINGS.get('explorer_font_size', 12)}px;
            outline:0;
        }}
        QTreeWidget::item {{
            padding:6px 8px;
            border-radius:6px;
            min-height:24px;
        }}
        QTreeWidget::item:hover {{
            background:{gc('BG_CARD')};
        }}
        QTreeWidget::item:selected {{
            background:{gc('ACCENT')};
            color:white;
        }}
        QTreeWidget::branch {{
            background:transparent;
        }}
        """
    )

    def _init_icons(self):
        self._ico_folder_closed = self.style().standardIcon(QStyle.SP_DirClosedIcon)
        self._ico_folder_open = self.style().standardIcon(QStyle.SP_DirOpenIcon)
        self._ico_file = self.style().standardIcon(QStyle.SP_FileIcon)

    def _is_dir_item(self, item: QTreeWidgetItem) -> bool:
        path = item.data(0, Qt.UserRole)
        return bool(path and os.path.isdir(path))

    def _apply_item_visuals(self, item: QTreeWidgetItem, is_dir: bool):
        font = item.font(0)
        font.setBold(is_dir)
        item.setFont(0, font)
        item.setIcon(0, self._ico_folder_closed if is_dir else self._ico_file)

    def _update_folder_icon(self, item: QTreeWidgetItem):
        if self._is_dir_item(item):
             self._set_folder_label(item, item.isExpanded())
    
    def _set_folder_label(self, item: QTreeWidgetItem, expanded: bool):
        path = item.data(0, Qt.UserRole)
        if not path or not os.path.isdir(path):
            return

        name = item.data(0, Qt.UserRole + 1) or item.text(0).lstrip("▸▾▶▼ ").strip()
        chevron = "▾" if expanded else "▸"
        item.setText(0, f"{chevron} {name}")
    
    def _store_item_name(self, item: QTreeWidgetItem, name: str):
        item.setData(0, Qt.UserRole + 1, name)