import sys, json
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QSplitter,
    QAction, QLabel, QFileDialog, QMessageBox, QInputDialog
)
from PyQt5.QtCore import Qt, QSize, QTimer
from PyQt5.QtGui import QFont, QKeySequence, QBrush
from PyQt5.QtWidgets import QShortcut

from config import gc, qc, SETTINGS
import config
from canvas import GraphScene, CanvasView, NodeItem
from ui import Sidebar, SearchBar, SettingsDialog

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GraphCanvas")
        self.resize(1440, 880)
        self._file_path = None; self._dirty = False
        self._build_scene(); self._build_ui(); self._build_toolbar()
        self._build_statusbar(); self._connect_signals()
        self._apply_global_style(); self._bind_shortcuts()
        self._load_sample()

    def _apply_global_style(self):
        self.setStyleSheet(f"""
            QMainWindow {{ background:{gc('BG_DARK')}; }}
            QToolBar {{ background:{gc('BG_PANEL')}; border-bottom:1px solid {gc('BORDER')}; spacing:4px; padding:4px 8px; }}
            QToolBar QToolButton {{ background:transparent; color:{gc('TEXT_PRIMARY')}; border:none; border-radius:6px; padding:5px 10px; font-size:{SETTINGS['ui_font_size']+1}px; }}
            QToolBar QToolButton:hover  {{ background:{gc('BG_CARD')}; }}
            QToolBar QToolButton:pressed {{ background:{gc('ACCENT')}; color:white; }}
            QStatusBar {{ background:{gc('BG_PANEL')}; color:{gc('TEXT_MUTED')}; font-size:{SETTINGS['ui_font_size']}px; }}
            QSplitter::handle {{ background:{gc('BORDER')}; width:1px; }}
        """)
        self.scene.setBackgroundBrush(QBrush(qc("BG_DARK"))); self.view.setBackgroundBrush(QBrush(qc("BG_DARK")))

    def _build_scene(self):
        self.scene = GraphScene(); self.view = CanvasView(self.scene); self.view.zoom_changed.connect(self._on_zoom); self.view._clipboard = []

    def _build_ui(self):
        central = QWidget(); self.setCentralWidget(central)
        ml = QVBoxLayout(central); ml.setContentsMargins(0, 0, 0, 0); ml.setSpacing(0)
        self.search_bar = SearchBar(self.scene, self.view); ml.addWidget(self.search_bar)
        self.splitter = QSplitter(Qt.Horizontal); self.splitter.addWidget(self.view)
        self.sidebar = Sidebar(self.scene); self.splitter.addWidget(self.sidebar)
        self.splitter.setSizes([1140, 290]); self.splitter.setHandleWidth(1); ml.addWidget(self.splitter)

    def _build_toolbar(self):
        tb = self.addToolBar("Main"); tb.setMovable(False); tb.setIconSize(QSize(16, 16))
        def btn(text, tip, fn, sc=None):
            a = QAction(text, self); a.setToolTip(tip); a.triggered.connect(fn)
            if sc: a.setShortcut(sc)
            tb.addAction(a); return a
        btn("➕ Node", "Add node (N)", self._add_node_prompt, "N")
        btn("🔗 Connect", "Connect selected→ (C)", self._start_connect, "C"); tb.addSeparator()
        self._sim_btn = btn("▶ Simulate", "Force layout (L)", self._toggle_layout, "L"); tb.addSeparator()
        btn("🔍", "Search (Ctrl+F)", lambda: self.search_bar.edit.setFocus(), "Ctrl+F"); tb.addSeparator()
        btn("💾 Save", "Save (Ctrl+S)", self._save, "Ctrl+S")
        btn("📂 Load", "Load (Ctrl+O)", self._load, "Ctrl+O")
        btn("🆕 New", "New (Ctrl+N)", self._new_graph, "Ctrl+N"); tb.addSeparator()
        btn("⛶ Fit", "Fit all to view (F)", self._fit_view, "F")
        btn("🔲 Grid", "Toggle grid", self._toggle_grid); tb.addSeparator()
        btn("🌗 Theme", "Toggle theme (T)", self._toggle_theme, "T")
        btn("⚙ Settings", "Settings", self._open_settings); tb.addSeparator()
        btn("🗑 Clear", "Clear graph", self._clear_all)

    def _bind_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+C"), self.view, activated=self.view._copy_selected)
        QShortcut(QKeySequence("Ctrl+V"), self.view, activated=lambda: self.view._paste())
        QShortcut(QKeySequence("Ctrl+B"), self, activated=self._toggle_sidebar)

    def _build_statusbar(self):
        self.status = self.statusBar()
        self._zoom_lbl = QLabel("100%"); self._zoom_lbl.setStyleSheet(f"color:{gc('TEXT_MUTED')}; padding:0 8px;")
        self.status.addPermanentWidget(self._zoom_lbl); self._update_status()

    def _connect_signals(self):
        self.scene.node_selected.connect(self._on_node_sel); self.scene.edge_selected.connect(self._on_edge_sel)
        self.scene.graph_changed.connect(self._on_changed)

    def _on_node_sel(self, node):
        if node: self.sidebar.show_node(node)
        elif self.sidebar._edge is None: self.sidebar.show_empty()

    def _on_edge_sel(self, edge):
        if edge: self.sidebar.show_edge(edge)
        elif self.sidebar._node is None: self.sidebar.show_empty()

    def _on_changed(self):
        self._dirty = True; self._update_status()

    def _on_zoom(self, z):
        self._zoom_lbl.setText(f"{int(z*100)}%"); self._update_status()

    def _update_status(self):
        n = len(self.scene.nodes); e = len(self.scene.edges)
        self.status.showMessage(f"  {self._file_path or 'unsaved'}{' ●' if self._dirty else ''}   │   {n} node{'s'*bool(n!=1)}  {e} edge{'s'*bool(e!=1)}   │   Scroll=zoom · Space+drag=pan · Del=delete")

    def _add_node_prompt(self):
        lbl, ok = QInputDialog.getText(self, "Add Node", "Label:")
        if ok and lbl:
            c = self.view.mapToScene(self.view.viewport().rect().center())
            self.scene.add_node(label=lbl, x=c.x(), y=c.y())

    def _start_connect(self):
        sel = [i for i in self.scene.selectedItems() if isinstance(i, NodeItem)]
        if sel: self.scene.start_connect(sel[0])

    def _toggle_layout(self):
        self._sim_btn.setText("⏸ Pause" if self.scene.toggle_layout() else "▶ Simulate")

    def _fit_view(self):
        if self.scene.nodes:
            self.view.fitInView(self.scene.itemsBoundingRect().adjusted(-80, -80, 80, 80), Qt.KeepAspectRatio)
            scl = self.view.transform().m11()
            if scl > self.view.MAX_ZOOM: self.view._set_zoom(self.view.MAX_ZOOM)
            elif scl < self.view.MIN_ZOOM: self.view._set_zoom(self.view.MIN_ZOOM)
            else: self.view._scale = scl; self.view.zoom_changed.emit(scl)
        else: self.view.resetTransform(); self.view._scale = 1.0

    def _toggle_grid(self): self.view._draw_grid = not self.view._draw_grid; self.view.viewport().update()
    def _toggle_sidebar(self): self.sidebar.setVisible(not self.sidebar.isVisible())

    def _toggle_theme(self):
        config.CURRENT_THEME = "dark" if config.CURRENT_THEME == "light" else "light"
        self._apply_global_style(); self.search_bar.apply_style(); self.sidebar.apply_style()
        for item in self.scene.items():
            if hasattr(item, "_refresh_text"): item._refresh_text()
            if hasattr(item, "_refresh_label_text"): item._refresh_label_text()
            item.update()
        self.view.viewport().update()
        if self.sidebar._node: self.sidebar.show_node(self.sidebar._node)
        elif self.sidebar._edge: self.sidebar.show_edge(self.sidebar._edge)
        else: self.sidebar.show_empty()

    def _open_settings(self):
        if SettingsDialog(self, self.scene).exec_():
            QApplication.instance().setFont(QFont("Segoe UI", SETTINGS["ui_font_size"]))
            self._apply_global_style(); self.search_bar.apply_style(); self.sidebar.apply_style()
            for item in self.scene.items():
                if hasattr(item, "_refresh_text"): item._refresh_text()
                if hasattr(item, "_refresh_label_text"): item._refresh_label_text()
                item.update()
            self.view.viewport().update()
            if self.sidebar._node: self.sidebar.show_node(self.sidebar._node)
            elif self.sidebar._edge: self.sidebar.show_edge(self.sidebar._edge)

    def _save(self):
        if not self._file_path:
            p, _ = QFileDialog.getSaveFileName(self, "Save", "graph.json", "JSON (*.json)")
            if not p: return
            self._file_path = p
        with open(self._file_path, "w") as f: json.dump(self.scene.to_dict(), f, indent=2)
        self._dirty = False; self._update_status()

    def _load(self):
        if self._dirty and QMessageBox.question(self, "Unsaved", "Discard and load?", QMessageBox.Yes | QMessageBox.Cancel) != QMessageBox.Yes: return
        p, _ = QFileDialog.getOpenFileName(self, "Open", "", "JSON (*.json)")
        if p:
            with open(p) as f: self.scene.load_dict(json.load(f))
            self._file_path = p; self._dirty = False; self._fit_view(); self._update_status(); self.sidebar.show_empty()

    def _new_graph(self):
        if self._dirty and QMessageBox.question(self, "Unsaved", "Discard?", QMessageBox.Yes | QMessageBox.Cancel) != QMessageBox.Yes: return
        self.scene.clear(); self.scene.nodes.clear(); self.scene.edges.clear()
        self._file_path = None; self._dirty = False; self.sidebar.show_empty(); self._update_status()

    def _clear_all(self):
        if QMessageBox.question(self, "Clear", "Remove all?", QMessageBox.Yes | QMessageBox.Cancel) == QMessageBox.Yes:
            self.scene.clear(); self.scene.nodes.clear(); self.scene.edges.clear()
            self._dirty = True; self.sidebar.show_empty(); self._update_status()

    def _load_sample(self):
        data = {
            "nodes": [
                {"id":"n1","label":"BCCI","x":0,"y":0,"node_type":"object","color":None,"properties":{"Type":"Organization","Founded":"1928"}},
                {"id":"n2","label":"Ms. Subramaniam","x":-200,"y":80,"node_type":"default","color":None,"properties":{"Role":"Member","Joined":"2010"}},
                {"id":"n3","label":"IPL","x":200,"y":80,"node_type":"event","color":None,"properties":{"Season":"2024","Teams":"10"}},
                {"id":"n4","label":"Sponsorship Deal","x":0,"y":200,"node_type":"note","color":None,"properties":{"Value":"₹500Cr","Year":"2023"}},
            ],
            "edges": [
                {"id":"e1","source":"n2","target":"n1","label":"MEMBER OF","direction":"→","edge_type":"relationship"},
                {"id":"e2","source":"n1","target":"n3","label":"ORGANISES","direction":"→","edge_type":"dependency"},
                {"id":"e3","source":"n4","target":"n3","label":"FUNDS","direction":"→","edge_type":"flow"},
                {"id":"e4","source":"n2","target":"n3","label":"PARTICIPATES","direction":"↔","edge_type":"relationship"},
            ],
        }
        self.scene.load_dict(data); self._dirty = False; QTimer.singleShot(120, self._fit_view); self._update_status()

    def closeEvent(self, event):
        if self._dirty:
            r = QMessageBox.question(self, "Unsaved", "Save before closing?", QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
            if r == QMessageBox.Save: self._save()
            elif r == QMessageBox.Cancel: event.ignore(); return
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv); app.setApplicationName("GraphCanvas")
    app.setFont(QFont("Segoe UI", SETTINGS["ui_font_size"]))
    w = MainWindow(); w.show(); sys.exit(app.exec_())