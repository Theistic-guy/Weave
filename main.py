"""
main.py — MainWindow + entry point
"""
import sys, json
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QSplitter,
    QAction, QLabel, QFileDialog, QMessageBox, QInputDialog, QShortcut,
    QToolButton, QMenu,
)
from PyQt5.QtCore import Qt, QSize, QTimer, QEvent
from PyQt5.QtGui import QFont, QKeySequence, QBrush

import config
from config import gc, qc
from canvas import GraphScene, CanvasView, NodeItem, EdgeItem
from ui import Sidebar, SearchBar, SettingsDialog


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GraphCanvas")
        self.resize(1440, 880)
        self._file_path = None
        self._dirty     = False

        self._build_scene()
        self._build_ui()
        self._build_toolbar()
        self._build_statusbar()
        self._connect_signals()
        self._apply_global_style()
        self._bind_shortcuts()
        self._load_sample()

    # ── Style ─────────────────────────────────────────────────────────────────
    def _apply_global_style(self):
        sf = config.SETTINGS["ui_font_size"]
        self.setStyleSheet(f"""
            QMainWindow {{ background:{gc('BG_DARK')}; }}
            QToolBar {{
                background:{gc('BG_PANEL')}; border-bottom:1px solid {gc('BORDER')};
                spacing:4px; padding:4px 8px;
            }}
            QToolBar QToolButton {{
                background:transparent; color:{gc('TEXT_PRIMARY')}; border:none;
                border-radius:6px; padding:5px 10px; font-size:{sf+1}px;
            }}
            QToolBar QToolButton:hover   {{ background:{gc('BG_CARD')}; }}
            QToolBar QToolButton:pressed {{ background:{gc('ACCENT')}; color:white; }}
            QToolBar QToolButton:checked {{ background:{gc('ACCENT')}; color:white; }}
            QStatusBar {{
                background:{gc('BG_PANEL')}; color:{gc('TEXT_MUTED')};
                font-size:{sf}px;
            }}
            QSplitter::handle {{ background:{gc('BORDER')}; width:1px; }}
        """)
        self.scene.setBackgroundBrush(QBrush(qc("BG_DARK")))
        self.view.setBackgroundBrush(QBrush(qc("BG_DARK")))

    # ── Build ─────────────────────────────────────────────────────────────────
    def _build_scene(self):
        self.scene = GraphScene()
        self.view  = CanvasView(self.scene)
        self.view.zoom_changed.connect(self._on_zoom)

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        ml = QVBoxLayout(central)
        ml.setContentsMargins(0, 0, 0, 0)
        ml.setSpacing(0)

        self.search_bar = SearchBar(self.scene, self.view)
        self.search_bar.hide()  # Docked but hidden by default
        ml.addWidget(self.search_bar)

        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.addWidget(self.view)
        self.sidebar = Sidebar(self.scene)
        self.splitter.addWidget(self.sidebar)
        self.splitter.setSizes([1140, 290])
        self.splitter.setHandleWidth(1)
        self.splitter.setCollapsible(0, False)
        self.splitter.setCollapsible(1, False)
        ml.addWidget(self.splitter)

    def _build_toolbar(self):
        tb = self.addToolBar("Main")
        tb.setMovable(False)
        tb.setIconSize(QSize(16, 16))
        tb.installEventFilter(self)

        self._toolbar = tb
        self._toolbar_items = []
        self._toolbar_overflow_menu = QMenu(self)
        self._toolbar_overflow_button = QToolButton(self)
        self._toolbar_overflow_button.setText(">>")
        self._toolbar_overflow_button.setToolTip("More tools")
        self._toolbar_overflow_button.setPopupMode(QToolButton.InstantPopup)
        self._toolbar_overflow_button.setMenu(self._toolbar_overflow_menu)
        self._toolbar_overflow_button.setAutoRaise(True)

        def btn(text, tip, fn, sc=None):
            a = QAction(text, self)
            a.setToolTip(tip)
            a.triggered.connect(fn)
            if sc:
                a.setShortcut(sc)
            tb.addAction(a)
            self._toolbar_items.append((a, False))
            return a

        def sep():
            a = tb.addSeparator()
            self._toolbar_items.append((a, True))
            return a

        btn("➕ Node",    "Add node (N)",            self._add_node_prompt, "N")
        btn("🔗 Connect", "Connect selected (C)",     self._start_connect,   "C")
        sep()
        self._sim_btn = btn("▶ Simulate", "Force layout (L)", self._toggle_layout, "L")
        sep()
        
        # Proper checkable toggle action for Search
        self.search_act = QAction("🔍", self)
        self.search_act.setToolTip("Search (Ctrl+F)")
        self.search_act.setShortcut("Ctrl+F")
        self.search_act.setCheckable(True)
        self.search_act.toggled.connect(self._on_search_toggled)
        tb.addAction(self.search_act)
        self._toolbar_items.append((self.search_act, False))
        
        sep()
        btn("💾 Save",    "Save (Ctrl+S)",             self._save,            "Ctrl+S")
        btn("📂 Load",    "Load (Ctrl+O)",             self._load,            "Ctrl+O")
        btn("🆕 New",     "New graph (Ctrl+N)",        self._new_graph,       "Ctrl+N")
        sep()
        btn("⛶ Fit",     "Fit all to view (F)",       self._fit_view,        "F")
        btn("🔲 Grid",    "Toggle grid",               self._toggle_grid)
        sep()
        btn("🌗 Theme",   "Toggle theme (T)",          self._toggle_theme,    "T")
        btn("⚙ Settings", "Settings",                 self._open_settings)
        sep()
        btn("🗑 Clear",   "Clear graph",               self._clear_all)

        self._toolbar_overflow_action = tb.addWidget(self._toolbar_overflow_button)
        QTimer.singleShot(0, self._update_toolbar_overflow)

    def eventFilter(self, obj, event):
        if obj is getattr(self, "_toolbar", None) and event.type() == QEvent.Resize:
            QTimer.singleShot(0, self._update_toolbar_overflow)
        return super().eventFilter(obj, event)

    def _update_toolbar_overflow(self):
        if not hasattr(self, "_toolbar"):
            return

        tb = self._toolbar
        for action, _is_sep in self._toolbar_items:
            action.setVisible(True)
            widget = tb.widgetForAction(action)
            if widget:
                widget.setVisible(True)
        self._toolbar_overflow_action.setVisible(False)
        self._toolbar_overflow_button.setVisible(False)

        reserve = self._toolbar_overflow_button.sizeHint().width() + 18
        available = max(0, tb.width() - reserve)
        used = 0
        hidden = []

        for action, is_sep in self._toolbar_items:
            widget = tb.widgetForAction(action)
            width = widget.sizeHint().width() if widget else 8
            if not is_sep and used + width > available:
                hidden.append(action)
                if widget:
                    widget.setVisible(False)
            else:
                used += width

        for action, is_sep in self._toolbar_items:
            if is_sep:
                action.setVisible(not hidden)

        self._toolbar_overflow_menu.clear()
        for action in hidden:
            menu_action = QAction(action.text(), self)
            menu_action.setToolTip(action.toolTip())
            menu_action.setEnabled(action.isEnabled())
            menu_action.setCheckable(action.isCheckable())
            menu_action.setChecked(action.isChecked())
            menu_action.triggered.connect(lambda _checked=False, a=action: a.trigger())
            self._toolbar_overflow_menu.addAction(menu_action)
        self._toolbar_overflow_action.setVisible(bool(hidden))
        self._toolbar_overflow_button.setVisible(bool(hidden))

    def _bind_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+C"), self.view,
                  activated=self.view._copy_selected)
        QShortcut(QKeySequence("Ctrl+V"), self.view,
                  activated=lambda: self.view._paste())   # pastes at viewport centre
        QShortcut(QKeySequence("Ctrl+B"), self,
                  activated=self._toggle_sidebar)

    def _build_statusbar(self):
        self.status    = self.statusBar()
        self._zoom_lbl = QLabel("100%")
        self._zoom_lbl.setStyleSheet(f"color:{gc('TEXT_MUTED')}; padding:0 8px;")
        self.status.addPermanentWidget(self._zoom_lbl)
        self._update_status()

    def _connect_signals(self):
        self.scene.node_selected.connect(self._on_node_sel)
        self.scene.edge_selected.connect(self._on_edge_sel)
        self.scene.graph_changed.connect(self._on_changed)
        
        # Link pressing escape inside the search bar to unchecking the toolbar button
        self.search_bar.hidden_by_escape.connect(lambda: self.search_act.setChecked(False))

    # ── Signal handlers ───────────────────────────────────────────────────────
    def _on_search_toggled(self, checked):
        self.search_bar.setVisible(checked)
        if checked:
            self.search_bar.edit.setFocus()
            self.search_bar.edit.selectAll()
        else:
            self.search_bar.edit.clear()
            self.view.setFocus()

    def _on_node_sel(self, node):
        if node:
            self.sidebar.show_node(node)
        elif self.sidebar._edge is None:
            self.sidebar.show_empty()

    def _on_edge_sel(self, edge):
        if edge:
            self.sidebar.show_edge(edge)
        elif self.sidebar._node is None:
            self.sidebar.show_empty()

    def _on_changed(self):
        self._dirty = True
        self._update_status()

    def _on_zoom(self, z):
        self._zoom_lbl.setText(f"{int(z * 100)}%")
        self._update_status()

    def _update_status(self):
        n   = len(self.scene.nodes)
        e   = len(self.scene.edges)
        dot = " ●" if self._dirty else ""
        fp  = self._file_path or "unsaved"
        self.status.showMessage(
            f"  {fp}{dot}   │   {n} node{'s' * (n != 1)}  {e} edge{'s' * (e != 1)}"
            f"   │   Scroll=zoom · Space/Middle=pan · Ctrl+C/V=copy/paste · Del=delete · F=fit")

    # ── Actions ───────────────────────────────────────────────────────────────
    def _add_node_prompt(self):
        lbl, ok = QInputDialog.getText(self, "Add Node", "Label:")
        if ok and lbl:
            c = self.view.mapToScene(self.view.viewport().rect().center())
            self.scene.add_node(label=lbl, x=c.x(), y=c.y())

    def _start_connect(self):
        sel = [i for i in self.scene.selectedItems() if isinstance(i, NodeItem)]
        if sel:
            self.scene.start_connect(sel[0])
        else:
            self.status.showMessage("Select a source node first, then press C", 3000)

    def _toggle_layout(self):
        active = self.scene.toggle_layout()
        self._sim_btn.setText("⏸ Pause" if active else "▶ Simulate")

    def _fit_view(self):
        """Fit all content to view — 'go home' button."""
        if self.scene.nodes:
            rect = self.scene.itemsBoundingRect().adjusted(-80, -80, 80, 80)
            self.view.fitInView(rect, Qt.KeepAspectRatio)
            # Clamp zoom
            t   = self.view.transform()
            scl = t.m11()
            if scl > self.view.MAX_ZOOM:
                self.view._set_zoom(self.view.MAX_ZOOM)
            elif scl < self.view.MIN_ZOOM:
                self.view._set_zoom(self.view.MIN_ZOOM)
            self.view._scale = self.view.transform().m11()
            self.view.zoom_changed.emit(self.view._scale)
        else:
            self.view.resetTransform()
            self.view._scale = 1.0

    def _toggle_grid(self):
        self.view._draw_grid = not self.view._draw_grid
        self.view.viewport().update()

    def _toggle_sidebar(self):
        self.sidebar.toggle_collapsed()

    def _toggle_theme(self):
        config.CURRENT_THEME = "dark" if config.CURRENT_THEME == "light" else "light"
        self._refresh_all_styles()

    def _refresh_all_styles(self):
        """Re-apply every style after theme or font-size change."""
        self._apply_global_style()
        self.search_bar.apply_style()
        self.sidebar.apply_style()
        for item in self.scene.items():
            if hasattr(item, "_refresh_text"):
                item._refresh_text()
            if hasattr(item, "_refresh_label_text"):
                item._refresh_label_text()
            item.update()
        self.view.viewport().update()
        # Rebuild whichever sidebar panel is open
        if self.sidebar._node:
            self.sidebar.show_node(self.sidebar._node)
        elif self.sidebar._edge:
            self.sidebar.show_edge(self.sidebar._edge)
        else:
            self.sidebar.show_empty()

    def _open_settings(self):
        dlg = SettingsDialog(self, self.scene)
        if dlg.exec_():
            QApplication.instance().setFont(
                QFont("Segoe UI", config.SETTINGS["ui_font_size"]))
            self._refresh_all_styles()
            self._dirty = True
            self._update_status()

    def _save(self):
        if not self._file_path:
            p, _ = QFileDialog.getSaveFileName(
                self, "Save", "graph.json", "JSON (*.json)")
            if not p:
                return
            self._file_path = p
        with open(self._file_path, "w") as f:
            json.dump(self.scene.to_dict(), f, indent=2)
        self._dirty = False
        self._update_status()

    def _load(self):
        if self._dirty:
            r = QMessageBox.question(self, "Unsaved changes",
                                     "Discard and load?",
                                     QMessageBox.Yes | QMessageBox.Cancel)
            if r != QMessageBox.Yes:
                return
        p, _ = QFileDialog.getOpenFileName(self, "Open", "", "JSON (*.json)")
        if p:
            with open(p) as f:
                data = json.load(f)
            self.scene.load_dict(data)
            self._file_path = p
            self._dirty     = False
            self._fit_view()
            self._update_status()
            self.sidebar.show_empty()
            # Schema may have changed — rebuild sidebar combos etc.
            self._refresh_all_styles()

    def _new_graph(self):
        if self._dirty:
            r = QMessageBox.question(self, "Unsaved changes",
                                     "Discard?",
                                     QMessageBox.Yes | QMessageBox.Cancel)
            if r != QMessageBox.Yes:
                return
        self.scene.clear()
        self.scene.nodes.clear()
        self.scene.edges.clear()
        self._file_path = None
        self._dirty     = False
        self.sidebar.show_empty()
        self._update_status()

    def _clear_all(self):
        r = QMessageBox.question(self, "Clear graph",
                                 "Remove all nodes and edges?",
                                 QMessageBox.Yes | QMessageBox.Cancel)
        if r == QMessageBox.Yes:
            self.scene.clear()
            self.scene.nodes.clear()
            self.scene.edges.clear()
            self._dirty = True
            self.sidebar.show_empty()
            self._update_status()

    def _load_sample(self):
        one_way = config.SETTINGS["default_direction"]
        data = {
            "nodes": [
                {"id": "n1", "label": "Problem", "x": -260, "y": -40,
                 "node_type": "concept", "color": None,
                 "properties": {"Question": "What needs to improve?"}},
                {"id": "n2", "label": "Research", "x": -80, "y": -140,
                 "node_type": "process", "color": None,
                 "properties": {"status": "in progress", "owner": "team"}},
                {"id": "n3", "label": "Dataset", "x": 120, "y": -120,
                 "node_type": "data", "color": None,
                 "properties": {"source": "observations"}},
                {"id": "n4", "label": "Prototype", "x": 120, "y": 80,
                 "node_type": "object", "color": None,
                 "properties": {"Version": "draft"}},
                {"id": "n5", "label": "User Feedback", "x": -90, "y": 140,
                 "node_type": "event", "color": None,
                 "properties": {"Signal": "needs and friction"}},
                {"id": "n6", "label": "Decision", "x": 330, "y": 10,
                 "node_type": "note", "color": None,
                 "properties": {"Outcome": "next step"}},
            ],
            "edges": [
                {"id": "e1", "source": "n1", "target": "n2",
                 "label": "frames", "direction": one_way, "edge_type": "relationship"},
                {"id": "e2", "source": "n2", "target": "n3",
                 "label": "collects", "direction": one_way, "edge_type": "flow"},
                {"id": "e3", "source": "n3", "target": "n4",
                 "label": "informs", "direction": one_way, "edge_type": "dependency"},
                {"id": "e4", "source": "n4", "target": "n5",
                 "label": "tested by", "direction": one_way, "edge_type": "relationship"},
                {"id": "e5", "source": "n5", "target": "n2",
                 "label": "refines", "direction": one_way, "edge_type": "note"},
                {"id": "e6", "source": "n4", "target": "n6",
                 "label": "supports", "direction": one_way, "edge_type": "flow"},
            ],
        }
        self.scene.load_dict(data)
        self._dirty = False
        QTimer.singleShot(120, self._fit_view)
        self._update_status()
    def closeEvent(self, event):
        if self._dirty:
            r = QMessageBox.question(
                self, "Unsaved changes", "Save before closing?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
            if r == QMessageBox.Save:
                self._save()
            elif r == QMessageBox.Cancel:
                event.ignore()
                return
        event.accept()


# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Load user's saved defaults before building any UI
    config.load_defaults()

    app = QApplication(sys.argv)
    app.setApplicationName("GraphCanvas")
    app.setFont(QFont("Segoe UI", config.SETTINGS["ui_font_size"]))

    w = MainWindow()
    w.show()
    sys.exit(app.exec_())
