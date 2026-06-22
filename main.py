"""
main.py — MainWindow + entry point
"""
import sys, json, os
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QSplitter,
    QAction, QLabel, QFileDialog, QMessageBox, QInputDialog, QShortcut,
    QToolButton, QMenu, QFrame, QSizePolicy,
)
from PyQt5.QtCore import Qt, QTimer, QEvent, QPointF
from PyQt5.QtGui import QFont, QKeySequence, QBrush, QPainter

import config
from config import gc, qc
from canvas import GraphScene, CanvasView, NodeItem, EdgeItem, CanvasTextItem, NodeGroup
from ui import Sidebar, SearchBar, SettingsDialog, FileExplorer

class CanvasOverlayHost(QWidget):
    def __init__(self, view, sidebar, parent=None):
        super().__init__(parent)
        self.view = view
        self.sidebar = sidebar

        self.view.setParent(self)
        self.sidebar.setParent(self)

        self.view.show()
        self.sidebar.show()
        self.sidebar.raise_()

    def reflow(self):
        
        self.view.setGeometry(self.rect())

        if self.sidebar._collapsed:
            w = self.sidebar._collapsed_width
        else:
            w = self.sidebar.width()
        w = min(w, self.width())

        self.sidebar.setGeometry(self.width() - w, 0, w, self.height())
        self.sidebar.raise_()

    def resizeEvent(self, event):
        self.reflow()
        super().resizeEvent(event)

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
        
        app_ui_size = config.SETTINGS["app_ui_font_size"]
        self.setStyleSheet(f"""
            QMainWindow {{ background:{gc('BG_DARK')}; }}
            QToolBar {{
                background:{gc('BG_PANEL')}; border-bottom:1px solid {gc('BORDER')};
                spacing:4px; padding:4px 8px;
            }}
            QToolBar QToolButton {{
                background:transparent; color:{gc('TEXT_PRIMARY')}; border:none;
                border-radius:6px; padding:5px 10px; font-size:{app_ui_size}px;
            }}
            QToolBar QToolButton:hover   {{ background:{gc('BG_CARD')}; }}
            QToolBar QToolButton:pressed {{ background:{gc('ACCENT')}; color:white; }}
            QToolBar QToolButton:checked {{ background:{gc('ACCENT')}; color:white; }}
            QFrame#TopToolbar {{
                background:{gc('BG_PANEL')}; border-bottom:1px solid {gc('BORDER')};
            }}
            QFrame#TopToolbar QToolButton {{
                background:transparent; color:{gc('TEXT_PRIMARY')}; border:none;
                border-radius:6px; padding:5px 10px; font-size:{app_ui_size+1}px;
            }}
            QFrame#TopToolbar QToolButton:hover {{ background:{gc('BG_CARD')}; }}
            QFrame#TopToolbar QToolButton:pressed {{ background:{gc('ACCENT')}; color:white; }}
            QFrame#TopToolbar QToolButton:checked {{ background:{gc('ACCENT')}; color:white; }}
            QFrame#ToolbarSeparator {{
                background:{gc('BORDER')}; border:none;
            }}
            QStatusBar {{
                background:{gc('BG_PANEL')}; color:{gc('TEXT_MUTED')};
                font-size:{app_ui_size}px;
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
        self._root_layout = ml

        self.search_bar = SearchBar(self.scene, self.view)
        self.search_bar.hide()
        ml.addWidget(self.search_bar)

        # Left explorer stays as splitter
        self.outer_splitter = QSplitter(Qt.Horizontal)

        self.file_explorer = FileExplorer()
        self.file_explorer.open_file.connect(self._open_file_from_explorer)
        self.outer_splitter.addWidget(self.file_explorer)

        # Canvas + floating inspector overlay
        self.sidebar = Sidebar(self.scene)
        self.canvas_host = CanvasOverlayHost(self.view, self.sidebar)
        self.canvas_host.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.outer_splitter.addWidget(self.canvas_host)
        self.outer_splitter.setSizes([self.file_explorer._EXPANDED_W, 1390])
        self.outer_splitter.setHandleWidth(1)
        self.outer_splitter.setCollapsible(0, False)
        self.outer_splitter.setCollapsible(1, False)

        ml.addWidget(self.outer_splitter)

    def _build_toolbar(self):
        bar = QFrame()
        bar.setObjectName("TopToolbar")
        bar.setMinimumWidth(0)
        bar.setFixedHeight(40)
        bar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        bar.installEventFilter(self)

        self._toolbar = bar
        self._toolbar_items = []
        self._toolbar_hidden_actions = []
        self._toolbar_overflow_button = QToolButton(bar)
        self._toolbar_overflow_button.setText(">>")
        self._toolbar_overflow_button.setToolTip("More tools")
        self._toolbar_overflow_button.setAutoRaise(True)
        self._toolbar_overflow_button.setMinimumWidth(0)
        self._toolbar_overflow_button.clicked.connect(self._show_toolbar_overflow)

        def btn(text, tip, fn, sc=None):
            a = QAction(text, self)
            a.setToolTip(tip)
            a.triggered.connect(fn)
            if sc:
                a.setShortcut(sc)
            self.addAction(a)
            b = QToolButton(bar)
            b.setDefaultAction(a)
            b.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            b.setAutoRaise(True)
            b.setMinimumWidth(0)
            self._toolbar_items.append({"action": a, "widget": b, "separator": False})
            return a

        def sep():
            line = QFrame(bar)
            line.setObjectName("ToolbarSeparator")
            self._toolbar_items.append({"action": None, "widget": line, "separator": True})
            return line

        # ── File dropdown button ───────────────────────────────────────────────
        self._file_btn = QToolButton(bar)
        self._file_btn.setText("📁 File")
        self._file_btn.setToolTip("File operations")
        self._file_btn.setAutoRaise(True)
        self._file_btn.setPopupMode(QToolButton.InstantPopup)
        self._file_btn.setMinimumWidth(0)

        file_menu = QMenu(self._file_btn)
        file_menu.setStyleSheet(
            f"QMenu {{ background:{gc('BG_PANEL')}; color:{gc('TEXT_PRIMARY')};"
            f" border:1px solid {gc('BORDER')}; border-radius:6px; padding:4px; }}"
            f" QMenu::item {{ padding:7px 22px; border-radius:4px; }}"
            f" QMenu::item:selected {{ background:{gc('ACCENT')}; color:white; }}"
            f" QMenu::separator {{ background:{gc('BORDER')}; height:1px; margin:4px 8px; }}")

        act_open_file   = QAction("📄  Open File…",        self)
        act_open_folder = QAction("📁  Open Folder…",       self)
        act_save        = QAction("💾  Save  (.weave)",      self)
        act_save_as     = QAction("💾  Save As…",            self)
        act_export_img  = QAction("🖼️  Export as Image…",   self)
        act_exit        = QAction("✕   Exit",                self)

        act_open_file.setShortcut("Ctrl+O")
        act_save.setShortcut("Ctrl+S")
        act_save_as.setShortcut("Ctrl+Shift+S")

        act_open_file.triggered.connect(self._open_file)
        act_open_folder.triggered.connect(self._open_folder)
        act_save.triggered.connect(self._save)
        act_save_as.triggered.connect(self._save_as)
        act_export_img.triggered.connect(self._export_image)
        act_exit.triggered.connect(self.close)

        for a in (act_open_file, act_open_folder, act_save, act_save_as,
                  act_export_img, act_exit):
            self.addAction(a)

        file_menu.addAction(act_open_file)
        file_menu.addAction(act_open_folder)
        file_menu.addSeparator()
        file_menu.addAction(act_save)
        file_menu.addAction(act_save_as)
        file_menu.addSeparator()
        file_menu.addAction(act_export_img)
        file_menu.addSeparator()
        file_menu.addAction(act_exit)

        self._file_btn.setMenu(file_menu)
        self._toolbar_items.append(
            {"action": None, "widget": self._file_btn, "separator": False})

        sep()
        btn("➕ Node",    "Add node (N)",            self._add_node_prompt, "N")
        btn("🔗 Connect", "Connect selected (C)",     self._start_connect,   "C")
        sep()
        self._sim_btn = btn("▶ Simulate", "Force layout (L)", self._toggle_layout, "L")
        sep()

        # Search toggle
        self.search_act = QAction("🔍", self)
        self.search_act.setToolTip("Search (Ctrl+F)")
        self.search_act.setShortcut("Ctrl+F")
        self.search_act.setCheckable(True)
        self.search_act.toggled.connect(self._on_search_toggled)
        self.addAction(self.search_act)
        search_btn = QToolButton(bar)
        search_btn.setDefaultAction(self.search_act)
        search_btn.setAutoRaise(True)
        search_btn.setMinimumWidth(0)
        self._toolbar_items.append(
            {"action": self.search_act, "widget": search_btn, "separator": False})

        sep()
        btn("⛶ Fit",     "Fit all to view (F)",       self._fit_view,        "F")
        btn("🔲 Grid",    "Toggle grid",               self._toggle_grid)
        sep()
        btn("🌗 Theme",   "Toggle theme (T)",          self._toggle_theme,    "T")
        btn("⚙ Settings", "Settings",                 self._open_settings)
        sep()
        btn("🗑 Clear",   "Clear graph",               self._clear_all)

        self._root_layout.insertWidget(0, bar)
        QTimer.singleShot(0, self._update_toolbar_overflow)

    def eventFilter(self, obj, event):
        if obj is getattr(self, "_toolbar", None) and event.type() == QEvent.Resize:
            QTimer.singleShot(0, self._update_toolbar_overflow)
        return super().eventFilter(obj, event)

    def _update_toolbar_overflow(self):
        if not hasattr(self, "_toolbar"):
            return

        left_margin = 12
        right_margin = 8
        top_margin = 4
        spacing = 6
        button_height = 24

        for item in self._toolbar_items:
            item["widget"].setVisible(True)

        reserve = self._toolbar_overflow_button.sizeHint().width() + 18
        available = max(0, self._toolbar.width() - reserve
                        - left_margin - right_margin)
        used = 0
        hidden = []

        for item in self._toolbar_items:
            widget = item["widget"]
            width = 1 if item["separator"] else widget.sizeHint().width()
            if not item["separator"] and used + width > available:
                hidden.append(item["action"])
                widget.setVisible(False)
            else:
                used += width + spacing

        if hidden:
            visible_regular = [
                item for item in self._toolbar_items
                if not item["separator"] and item["widget"].isVisible()]
            seen_visible = False
            for idx, item in enumerate(self._toolbar_items):
                if not item["separator"]:
                    if item["widget"].isVisible():
                        seen_visible = True
                    continue
                next_visible = any(
                    not next_item["separator"] and next_item["widget"].isVisible()
                    for next_item in
                    self._toolbar_items[idx + 1:]
                )
                item["widget"].setVisible(bool(visible_regular)
                                          and seen_visible
                                          and next_visible)

        self._toolbar_hidden_actions = hidden
        self._toolbar_overflow_button.setVisible(bool(hidden))
        x = left_margin
        for item in self._toolbar_items:
            widget = item["widget"]
            if not widget.isVisible():
                continue
            width = 1 if item["separator"] else widget.sizeHint().width()
            widget.setGeometry(x, top_margin, width, button_height)
            x += width + spacing

        if hidden:
            width = self._toolbar_overflow_button.sizeHint().width()
            self._toolbar_overflow_button.setGeometry(
                x, top_margin, width, button_height)

    def _show_toolbar_overflow(self):
        if not self._toolbar_hidden_actions:
            self._update_toolbar_overflow()
        if not self._toolbar_hidden_actions:
            return

        menu = QMenu(self)
        action_map = {}
        for action in self._toolbar_hidden_actions:
            menu_action = QAction(action.text(), menu)
            menu_action.setToolTip(action.toolTip())
            menu_action.setEnabled(action.isEnabled())
            menu_action.setCheckable(action.isCheckable())
            menu_action.setChecked(action.isChecked())
            menu.addAction(menu_action)
            action_map[menu_action] = action

        pos = self._toolbar_overflow_button.mapToGlobal(
            self._toolbar_overflow_button.rect().bottomLeft())
        selected = menu.exec_(pos)
        if selected:
            self._trigger_overflow_action(
                action_map[selected],
                selected.isChecked() if selected.isCheckable() else False)

    def _trigger_overflow_action(self, action, checked=False):
        if action.isCheckable():
            action.setChecked(checked)
        else:
            action.trigger()
        QTimer.singleShot(0, self._update_toolbar_overflow)

    def _bind_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+C"), self.view,
                  activated=self.view._copy_selected)
        QShortcut(QKeySequence("Ctrl+V"), self.view,
                  activated=lambda: self.view._paste())
        QShortcut(QKeySequence("Ctrl+B"), self,
                  activated=self._toggle_sidebar)
        QShortcut(QKeySequence("Ctrl+E"), self,
                  activated=self._toggle_explorer)

    def _build_statusbar(self):
        self.status    = self.statusBar()
        self._zoom_lbl = QLabel("100%")
        self._zoom_lbl.setStyleSheet(f"color:{gc('TEXT_MUTED')}; padding:0 8px;")
        self.status.addPermanentWidget(self._zoom_lbl)
        self._update_status()

    def _connect_signals(self):
        self.scene.node_selected.connect(self._on_node_sel)
        self.scene.edge_selected.connect(self._on_edge_sel)
        self.scene.group_selected.connect(self._on_group_sel)
        self.scene.graph_changed.connect(self._on_changed)
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
            self._show_inspector(self.sidebar.show_node, node)
        elif self.sidebar._edge is None and self.sidebar._group is None:
            self._hide_inspector()

    def _on_edge_sel(self, edge):
        if edge:
            self._show_inspector(self.sidebar.show_edge, edge)
        elif self.sidebar._node is None and self.sidebar._group is None:
            self._hide_inspector()

    def _on_group_sel(self, group):
        if group:
            self._show_inspector(self.sidebar.show_group, group)
        elif self.sidebar._node is None and self.sidebar._edge is None:
            self._hide_inspector()

    def _on_changed(self):
        self._dirty = True
        self._update_status()

    def _on_zoom(self, z):
        self._zoom_lbl.setText(f"{int(z * 100)}%")
        self._update_status()

    def _update_status(self):
        n   = len(self.scene.nodes)
        e   = len(self.scene.edges)
        t   = len(self.scene.texts)
        dot = " ●" if self._dirty else ""
        fp  = os.path.basename(self._file_path) if self._file_path else "unsaved"
        txt_info = f"  {t} text{'s' * (t != 1)}" if t else ""
        self.status.showMessage(
            f"  {fp}{dot}   │   {n} node{'s' * (n != 1)}  {e} edge{'s' * (e != 1)}"
            f"{txt_info}"
            f"   │   Scroll=zoom · Space/Middle=pan · Ctrl+C/V=copy/paste"
            f" · Del=delete · F=fit · Ctrl+E=explorer")

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
        self.file_explorer.apply_style()
        for item in self.scene.items():
            if hasattr(item, "_refresh_text"):
                item._refresh_text()
            if hasattr(item, "_refresh_label_text"):
                item._refresh_label_text()
            item.update()
        self.view.viewport().update()
        if self.sidebar._node:
            self.sidebar.show_node(self.sidebar._node)
        elif self.sidebar._edge:
            self.sidebar.show_edge(self.sidebar._edge)
        elif self.sidebar._group:
            self.sidebar.show_group(self.sidebar._group)
        else:
            self.sidebar.show_empty()

    def _open_settings(self):
        dlg = SettingsDialog(self, self.scene)
        if dlg.exec_():
            # QApplication.instance().setFont(
            #     QFont("Segoe UI", config.SETTINGS["app_ui_font_size"]))
            self._refresh_all_styles()
            self._dirty = True
            self._update_status()

    def _toggle_explorer(self):
        self.file_explorer.toggle_collapsed()
        # Adjust outer splitter sizes when expanding
        if not self.file_explorer._collapsed:
            sizes = self.outer_splitter.sizes()
            if sizes[0] < self.file_explorer._EXPANDED_W:
                total = sum(sizes)
                self.outer_splitter.setSizes(
                    [self.file_explorer._EXPANDED_W,
                     total - self.file_explorer._EXPANDED_W])

    def _open_file(self):
        if self._dirty:
            r = QMessageBox.question(self, "Unsaved changes",
                                     "Discard and open?",
                                     QMessageBox.Yes | QMessageBox.Cancel)
            if r != QMessageBox.Yes:
                return
        p, _ = QFileDialog.getOpenFileName(
            self, "Open File", "",
            "Weave Files (*.weave *.bweave *.json);;All Files (*)")
        if not p:
            return
        self._load_path(p)
        self.file_explorer.load_single_file(p)
        if self.file_explorer._collapsed:
            self.file_explorer.set_collapsed(False)

    def _open_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Open Folder", "")
        if not folder:
            return
        self.file_explorer.load_folder(folder)
        if self.file_explorer._collapsed:
            self.file_explorer.set_collapsed(False)

    def _open_file_from_explorer(self, path: str):
        if self._dirty:
            r = QMessageBox.question(self, "Unsaved changes",
                                     "Discard and open?",
                                     QMessageBox.Yes | QMessageBox.Cancel)
            if r != QMessageBox.Yes:
                return
        self._load_path(path)

    def _load_path(self, path: str):
        try:
            if path.endswith(".bweave"):
                with open(path, "rb") as f:
                    data = self._decode_bweave(f.read())
            else:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
        except Exception as e:
            QMessageBox.critical(self, "Load error", str(e))
            return
        self.scene.load_dict(data)
        self._file_path = path
        self._dirty     = False
        self._fit_view()
        self._update_status()
        self.sidebar.show_empty()
        self._refresh_all_styles()

    def _save(self):
        if not self._file_path:
            self._save_as()
            return
        self._write(self._file_path)

    def _save_as(self):
        start = self._file_path or "graph.weave"
        p, _ = QFileDialog.getSaveFileName(
            self, "Save As", start,
            "Weave Graph — JSON (*.weave);;"
            "Binary Weave — compact binary (*.bweave);;"
            "Plain JSON (*.json)")
        if not p:
            return
        self._file_path = p
        self._write(p)
        self.file_explorer.load_single_file(p)
        if self.file_explorer._collapsed:
            self.file_explorer.set_collapsed(False)

    def _write(self, path: str):
        try:
            data = self.scene.to_dict()
            if path.endswith(".bweave"):
                with open(path, "wb") as f:
                    f.write(self._encode_bweave(data))
            else:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
            self._dirty = False
            self._update_status()
        except Exception as e:
            QMessageBox.critical(self, "Save error", str(e))

    @staticmethod
    def _encode_bweave(data: dict) -> bytes:
        import zlib
        raw = json.dumps(data, separators=(",", ":")).encode("utf-8")
        return b"BWVE" + zlib.compress(raw, level=9)

    @staticmethod
    def _decode_bweave(blob: bytes) -> dict:
        import zlib
        if blob[:4] != b"BWVE":
            raise ValueError("Not a valid .bweave file")
        return json.loads(zlib.decompress(blob[4:]).decode("utf-8"))

    def _export_image(self):
        from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout,
                                     QGroupBox, QRadioButton, QDoubleSpinBox,
                                     QSpinBox, QDialogButtonBox)
        from PyQt5.QtGui import QImage, QPainter as _P
        from PyQt5.QtCore import QRectF, QPointF

        if not self.scene.nodes and not self.scene.texts:
            QMessageBox.information(self, "Export", "Nothing to export.")
            return

        dlg = QDialog(self)
        dlg.setWindowTitle("Export as Image")
        dlg.setMinimumWidth(400)
        dlg.setStyleSheet(
            f"QDialog {{ background:{gc('BG_PANEL')}; color:{gc('TEXT_PRIMARY')}; }}"
            f" QLabel {{ color:{gc('TEXT_PRIMARY')}; background:transparent; }}"
            f" QGroupBox {{ color:{gc('TEXT_MUTED')}; border:1px solid {gc('BORDER')};"
            f" border-radius:6px; margin-top:8px; padding:10px 8px; }}"
            f" QGroupBox::title {{ subcontrol-origin:margin; left:10px; }}"
            f" QRadioButton {{ color:{gc('TEXT_PRIMARY')}; background:transparent; }}"
            f" QDoubleSpinBox, QSpinBox {{ background:{gc('BG_CARD')};"
            f" color:{gc('TEXT_PRIMARY')}; border:1px solid {gc('BORDER')};"
            f" border-radius:4px; padding:3px 6px; }}")

        lay = QVBoxLayout(dlg); lay.setSpacing(10)

        grp_bg = QGroupBox("Background")
        bl = QHBoxLayout(grp_bg)
        rb_match = QRadioButton("Match theme"); rb_match.setChecked(True)
        rb_light = QRadioButton("Light")
        rb_dark  = QRadioButton("Dark")
        rb_trans = QRadioButton("Transparent")
        for rb in (rb_match, rb_light, rb_dark, rb_trans): bl.addWidget(rb)
        lay.addWidget(grp_bg)

        grp_fmt = QGroupBox("Format")
        fl = QHBoxLayout(grp_fmt)
        rb_png = QRadioButton("PNG"); rb_png.setChecked(True)
        rb_jpg = QRadioButton("JPG")
        rb_svg = QRadioButton("SVG")
        for rb in (rb_png, rb_jpg, rb_svg): fl.addWidget(rb)
        lay.addWidget(grp_fmt)

        grp_sc = QGroupBox("Scale  (scene units → pixels)")
        sl = QHBoxLayout(grp_sc)
        from PyQt5.QtWidgets import QLabel as _QL
        sl.addWidget(_QL("Scale:"))
        sc_spin = QDoubleSpinBox()
        sc_spin.setRange(0.5, 8.0); sc_spin.setValue(2.0); sc_spin.setSingleStep(0.5)
        sl.addWidget(sc_spin); sl.addStretch()
        lay.addWidget(grp_sc)

        grp_mg = QGroupBox("Border margin  (scene units)")
        ml = QHBoxLayout(grp_mg)
        ml.addWidget(_QL("Margin:"))
        mg_spin = QSpinBox()
        mg_spin.setRange(0, 400); mg_spin.setValue(60)
        ml.addWidget(mg_spin); ml.addStretch()
        lay.addWidget(grp_mg)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.setStyleSheet(
            f"QPushButton {{ background:{gc('ACCENT')}; color:white; border:none;"
            f" border-radius:5px; padding:6px 16px; font-weight:bold; }}"
            f" QPushButton[text='Cancel'] {{ background:{gc('BG_CARD')};"
            f" color:{gc('TEXT_PRIMARY')}; border:1px solid {gc('BORDER')}; }}")
        bb.accepted.connect(dlg.accept); bb.rejected.connect(dlg.reject)
        lay.addWidget(bb)

        if dlg.exec_() != QDialog.Accepted:
            return

        bg = (None if rb_trans.isChecked() else
              "#f0f2f5" if rb_light.isChecked() else
              "#0f1117" if rb_dark.isChecked() else
              gc("BG_DARK"))
        scale  = sc_spin.value()
        margin = mg_spin.value()
        fmt    = "svg" if rb_svg.isChecked() else "jpg" if rb_jpg.isChecked() else "png"
        content_rect = self.scene.itemsBoundingRect().adjusted(
            -margin, -margin, margin, margin)

        base = os.path.splitext(self._file_path)[0] if self._file_path else "export"
        p, _ = QFileDialog.getSaveFileName(
            self, "Export Image", f"{base}.{fmt}", f"{fmt.upper()} (*.{fmt})")
        if not p:
            return
        try:
            from PyQt5.QtGui import QPainter as QPainterExp
            if fmt == "svg":
                from PyQt5.QtSvg import QSvgGenerator
                from PyQt5.QtCore import QSize
                gen = QSvgGenerator()
                gen.setFileName(p)
                sz = content_rect.size() * scale
                gen.setSize(QSize(int(sz.width()), int(sz.height())))
                gen.setViewBox(QRectF(0, 0, sz.width(), sz.height()))
                pntr = QPainterExp(gen)
                self.scene.render(pntr, source=content_rect)
                pntr.end()
            else:
                from PyQt5.QtGui import QColor as _QCol
                w, h = int(content_rect.width() * scale), int(content_rect.height() * scale)
                img = QImage(w, h,
                             QImage.Format_ARGB32 if fmt == "png" else QImage.Format_RGB32)
                img.fill(_QCol(bg) if bg else Qt.transparent)
                pntr = QPainterExp(img)
                pntr.setRenderHint(QPainterExp.Antialiasing)
                pntr.setRenderHint(QPainterExp.SmoothPixmapTransform)
                self.scene.render(pntr, source=content_rect)
                pntr.end()
                img.save(p)
            QMessageBox.information(self, "Exported", f"Saved to:\n{p}")
        except Exception as e:
            QMessageBox.critical(self, "Export error", str(e))

    def _new_graph(self):
        if self._dirty:
            r = QMessageBox.question(self, "Unsaved changes",
                                     "Discard?",
                                     QMessageBox.Yes | QMessageBox.Cancel)
            if r != QMessageBox.Yes:
                return
        self.scene.clear_all()
        self._file_path = None
        self._dirty     = False
        self.sidebar.show_empty()
        self._update_status()

    def _clear_all(self):
        r = QMessageBox.question(self, "Clear graph",
                                 "Remove all nodes and edges?",
                                 QMessageBox.Yes | QMessageBox.Cancel)
        if r == QMessageBox.Yes:
            self.scene.clear_all()
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

    def _show_inspector(self, fn, obj):
        if self.sidebar._collapsed:
            self.sidebar.set_collapsed(False)
        fn(obj)

    def _hide_inspector(self):
        self.sidebar.show_empty()
        self.sidebar.set_collapsed(True)


# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Load user's saved defaults before building any UI
    config.load_defaults()

    app = QApplication(sys.argv)
    app.setApplicationName("GraphCanvas")
    app.setFont(QFont("Segoe UI", config.SETTINGS["app_ui_font_size"]))

    w = MainWindow()
    w.show()
    sys.exit(app.exec_())