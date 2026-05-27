#!/usr/bin/env python3
"""
GraphCanvas — Node-based graph editor (v4)
Changes vs v3:
  NEW  – Edge Type Color Schemas (Settings tab fully supports Edge Colors).
  NEW  – Individual Edge Color overrides via Context Menu & Sidebar.
  FIX  – Click on Edge/Node text labels to select the underlying item.
  FIX  – Canvas label size correctly propagates geometry updates instantly.
"""

import sys, json, math, uuid, copy
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGraphicsScene, QGraphicsView, QGraphicsItem, QGraphicsLineItem,
    QGraphicsTextItem, QSplitter, QLabel, QLineEdit, QPushButton,
    QScrollArea, QFrame, QFileDialog, QInputDialog, QMessageBox,
    QToolBar, QAction, QStatusBar, QGraphicsPathItem, QComboBox,
    QDialog, QDialogButtonBox, QFormLayout, QMenu, QColorDialog,
    QSpinBox, QGroupBox, QGridLayout, QSizePolicy, QShortcut,
    QTabWidget, QListWidget, QListWidgetItem, QAbstractItemView
)
from PyQt5.QtCore import Qt, QPointF, QRectF, QLineF, pyqtSignal, QTimer, QSize
from PyQt5.QtGui import (
    QPainter, QPen, QBrush, QColor, QFont, QPainterPath,
    QLinearGradient, QKeySequence, QPalette, QCursor, QPixmap, QIcon
)

# ─────────────────────────────────────────────────────────────────────────────
#  Global theme / settings  (mutable at runtime)
# ─────────────────────────────────────────────────────────────────────────────
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

# Dynamic Configs (Serialised into save files)
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

# ─────────────────────────────────────────────────────────────────────────────
#  Edge
# ─────────────────────────────────────────────────────────────────────────────
class EdgeItem(QGraphicsPathItem):
    def __init__(self, src, tgt, label="", edge_id=None, direction="→", edge_type="relationship", color=None):
        super().__init__()
        self.edge_id     = edge_id or new_id()
        self.source_node = src
        self.target_node = tgt
        self.label       = label
        self.direction   = direction
        self.edge_type   = edge_type
        self.color       = color or EDGE_TYPE_COLORS.get(edge_type, "#adb5bd")

        self.setZValue(0)
        self.setFlag(QGraphicsItem.ItemIsSelectable)

        self._label_item = QGraphicsTextItem("", self)
        self._label_item.setFlag(QGraphicsItem.ItemIgnoresTransformations)
        self._refresh_label_text()

    def _refresh_label_text(self):
        parts = []
        if self.edge_type != "relationship":
            parts.append(f"[{self.edge_type}]")
        if self.label:
            parts.append(self.label)
        display = "  ".join(parts) if parts else ""
        self._label_item.setPlainText(display)
        
        # Link label font explicitly to the canvas UI font setting minus 1
        font = QFont("Segoe UI", SETTINGS["ui_font_size"] - 1)
        self._label_item.setFont(font)
        self._label_item.setDefaultTextColor(QColor(self.color))
        self.update_path() # Required to recalculate midpoint center properly

    def set_label(self, text):
        self.label = text
        self._refresh_label_text()

    def set_direction(self, d):
        self.direction = d
        self.update_path()

    def set_edge_type(self, t):
        self.edge_type = t
        self.color = EDGE_TYPE_COLORS.get(t, self.color)
        self._refresh_label_text()

    def update_path(self):
        sp = self.source_node.scenePos()
        tp = self.target_node.scenePos()
        r_s = self.source_node.radius
        r_t = self.target_node.radius

        dx = tp.x() - sp.x(); dy = tp.y() - sp.y()
        dist = math.hypot(dx, dy) or 1
        src_pt = QPointF(sp.x() + dx/dist * r_s, sp.y() + dy/dist * r_s)
        tgt_pt = QPointF(tp.x() - dx/dist * r_t, tp.y() - dy/dist * r_t)

        path = QPainterPath(src_pt)
        path.lineTo(tgt_pt)

        angle = math.atan2(dy, dx)
        arrow_len = 9

        def arrow_at(pt, ang):
            a1, a2 = ang + math.pi*0.82, ang - math.pi*0.82
            arr = QPainterPath()
            arr.moveTo(pt)
            arr.lineTo(pt + QPointF(math.cos(a1)*arrow_len, math.sin(a1)*arrow_len))
            arr.moveTo(pt)
            arr.lineTo(pt + QPointF(math.cos(a2)*arrow_len, math.sin(a2)*arrow_len))
            return arr

        if self.direction == "→": path.addPath(arrow_at(tgt_pt, angle))
        elif self.direction == "←": path.addPath(arrow_at(src_pt, angle + math.pi))
        elif self.direction == "↔": path.addPath(arrow_at(tgt_pt, angle)); path.addPath(arrow_at(src_pt, angle + math.pi))

        self.setPath(path)
        if self._label_item.toPlainText():
            mid = QPointF((src_pt.x()+tgt_pt.x())/2, (src_pt.y()+tgt_pt.y())/2)
            br  = self._label_item.boundingRect()
            self._label_item.setPos(mid - QPointF(br.width()/2, br.height()))

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        style = Qt.DashLine if self.edge_type == "dependency" else Qt.DotLine if self.edge_type == "note" else Qt.SolidLine
        col = qc("ACCENT") if self.isSelected() else QColor(self.color)
        pen = QPen(col, 2.0 if self.isSelected() else 1.2, style)
        self.setPen(pen)
        super().paint(painter, option, widget)

    def to_dict(self):
        return {"id": self.edge_id, "source": self.source_node.node_id, "target": self.target_node.node_id,
                "label": self.label, "direction": self.direction, "edge_type": self.edge_type, "color": self.color}

# ─────────────────────────────────────────────────────────────────────────────
#  Node
# ─────────────────────────────────────────────────────────────────────────────
class NodeItem(QGraphicsItem):
    def __init__(self, node_id=None, label="Node", x=0, y=0, node_type="default", color=None, properties=None):
        super().__init__()
        self.node_id    = node_id or new_id()
        self.label      = label
        self.node_type  = node_type
        self.color      = color or NODE_TYPE_COLORS.get(node_type, NODE_TYPE_COLORS.get("default", "#888888"))
        self.properties = properties or {}
        self.edges      = []
        self.radius     = 14

        self._inject_schema()

        self.setFlag(QGraphicsItem.ItemIsMovable)
        self.setFlag(QGraphicsItem.ItemIsSelectable)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges)
        self.setPos(x, y)
        self.setZValue(1)

        self._text = QGraphicsTextItem("", self)
        self._text.setFlag(QGraphicsItem.ItemIgnoresTransformations)
        self._refresh_text()

    def _inject_schema(self):
        expected = PROPERTY_SCHEMA.get("__universal__", []) + PROPERTY_SCHEMA.get(self.node_type, [])
        for k in expected:
            if k not in self.properties:
                self.properties[k] = ""

    def _refresh_text(self):
        self.prepareGeometryChange() # Notify canvas of text size shifts
        self._text.setPlainText(self.label)
        sz = SETTINGS["ui_font_size"]
        self._text.setFont(QFont("Segoe UI", sz, QFont.Medium))
        self._text.setDefaultTextColor(qc(self.color))
        br = self._text.boundingRect()
        self._text.setPos(self.radius + 5, -br.height() / 2)

    def boundingRect(self):
        p = 5
        return QRectF(-self.radius-p, -self.radius-p, self.radius*2+p*2, self.radius*2+p*2)

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        r = self.radius
        col = qc("ACCENT") if self.isSelected() else QColor(self.color)
        painter.setBrush(QBrush(col))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QPointF(0, 0), r, r)
        if self.isSelected():
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(col.lighter(150), 2))
            painter.drawEllipse(QPointF(0, 0), r+4, r+4)
        
        filled_props = sum(1 for v in self.properties.values() if str(v).strip() != "")
        if filled_props > 0:
            br = QRectF(r-6, -r-2, 12, 10)
            painter.setBrush(QBrush(QColor("#ff6584")))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(br, 3, 3)
            painter.setPen(QPen(Qt.white))
            painter.setFont(QFont("Segoe UI", 6, QFont.Bold))
            painter.drawText(br, Qt.AlignCenter, str(filled_props))

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionHasChanged:
            for e in self.edges: e.update_path()
        return super().itemChange(change, value)

    def add_edge(self, e):
        if e not in self.edges:
            self.edges.append(e); self._update_size()

    def remove_edge(self, e):
        if e in self.edges:
            self.edges.remove(e); self._update_size()

    def _update_size(self):
        self.prepareGeometryChange()
        self.radius = 14 + len(self.edges) * 2
        self._refresh_text()
        for e in self.edges: e.update_path()
        self.update()

    def to_dict(self):
        return {"id": self.node_id, "label": self.label, "x": self.x(), "y": self.y(),
                "node_type": self.node_type, "color": self.color, "properties": self.properties}

# ─────────────────────────────────────────────────────────────────────────────
#  Scene & View
# ─────────────────────────────────────────────────────────────────────────────
class GraphScene(QGraphicsScene):
    node_selected = pyqtSignal(object)
    edge_selected = pyqtSignal(object)
    graph_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSceneRect(-100000, -100000, 200000, 200000)
        self.setBackgroundBrush(QBrush(qc("BG_DARK")))
        self.nodes = {}
        self.edges = {}
        self._connecting = False; self._conn_source = None; self._conn_line = None
        self.layout_timer = QTimer(); self.layout_timer.timeout.connect(self._layout_step)
        self.layout_active = False

    def toggle_layout(self):
        self.layout_active = not self.layout_active
        if self.layout_active: self.layout_timer.start(20)
        else: self.layout_timer.stop()
        return self.layout_active

    def _layout_step(self):
        forces = {nid: QPointF(0, 0) for nid in self.nodes}
        nl = list(self.nodes.values())
        C_REP, C_ATT, IDEAL = 3000.0, 0.04, 150.0
        for i in range(len(nl)):
            for j in range(i+1, len(nl)):
                a, b = nl[i], nl[j]
                dx = a.x() - b.x(); dy = a.y() - b.y()
                d  = math.hypot(dx, dy) or 0.1
                if d > 1000: continue
                f = C_REP / (d*d); fx, fy = f*dx/d, f*dy/d
                forces[a.node_id] += QPointF(fx, fy); forces[b.node_id] -= QPointF(fx, fy)
        for e in self.edges.values():
            a, b = e.source_node, e.target_node
            dx = b.x()-a.x(); dy = b.y()-a.y()
            d = math.hypot(dx, dy) or 0.1
            f = C_ATT * (d - IDEAL); fx, fy = f*dx/d, f*dy/d
            forces[a.node_id] += QPointF(fx, fy); forces[b.node_id] -= QPointF(fx, fy)
        cap = 12.0
        for node in nl:
            if node.isSelected(): continue
            f = forces[node.node_id]
            mx = max(-cap, min(cap, f.x())); my = max(-cap, min(cap, f.y()))
            if abs(mx) > 0.05 or abs(my) > 0.05: node.setPos(node.pos() + QPointF(mx, my))

    def add_node(self, label="Node", x=0, y=0, node_type=None, color=None, properties=None, node_id=None):
        nt = node_type or SETTINGS["default_node_type"]
        if nt not in NODE_TYPE_COLORS: nt = list(NODE_TYPE_COLORS.keys())[0] if NODE_TYPE_COLORS else "default"
        n = NodeItem(node_id=node_id, label=label, x=x, y=y, node_type=nt, color=color, properties=properties)
        self.nodes[n.node_id] = n
        self.addItem(n)
        self.graph_changed.emit()
        return n

    def delete_node(self, node):
        for e in list(node.edges): self.delete_edge(e)
        self.nodes.pop(node.node_id, None); self.removeItem(node); self.graph_changed.emit()

    def add_edge(self, src, tgt, label="", edge_id=None, direction=None, edge_type=None, color=None):
        direction = direction or SETTINGS["default_direction"]
        edge_type = edge_type or SETTINGS["default_edge_type"]
        if edge_type not in EDGE_TYPE_COLORS: edge_type = list(EDGE_TYPE_COLORS.keys())[0] if EDGE_TYPE_COLORS else "relationship"
        for e in src.edges:
            if e.source_node is src and e.target_node is tgt and e.direction == direction: return None
        e = EdgeItem(src, tgt, label=label, edge_id=edge_id, direction=direction, edge_type=edge_type, color=color)
        self.edges[e.edge_id] = e
        self.addItem(e); src.add_edge(e); tgt.add_edge(e)
        self.graph_changed.emit()
        return e

    def delete_edge(self, edge):
        edge.source_node.remove_edge(edge); edge.target_node.remove_edge(edge)
        self.edges.pop(edge.edge_id, None); self.removeItem(edge); self.graph_changed.emit()

    def start_connect(self, src):
        self._connecting = True; self._conn_source = src
        self._conn_line = self.addLine(QLineF(), QPen(qc("ACCENT"), 1.5, Qt.DashLine))

    def abort_connect(self):
        self._connecting = False; self._conn_source = None
        if self._conn_line: self.removeItem(self._conn_line); self._conn_line = None

    def to_dict(self):
        return {
            "types": {
                "nodes": NODE_TYPE_COLORS,
                "edges": EDGE_TYPE_COLORS,
                "schema": PROPERTY_SCHEMA,
                "settings": SETTINGS
            },
            "nodes": [n.to_dict() for n in self.nodes.values()],
            "edges": [e.to_dict() for e in self.edges.values()],
        }

    def load_dict(self, data):
        self.clear(); self.nodes.clear(); self.edges.clear()
        
        types = data.get("types", {})
        if "nodes" in types: NODE_TYPE_COLORS.clear(); NODE_TYPE_COLORS.update(types["nodes"])
        if "edges" in types: 
            EDGE_TYPE_COLORS.clear()
            # Backward compat for JSONs saved as list
            if isinstance(types["edges"], list):
                for et in types["edges"]: EDGE_TYPE_COLORS[et] = "#adb5bd"
            else:
                EDGE_TYPE_COLORS.update(types["edges"])
        if "schema" in types: PROPERTY_SCHEMA.clear(); PROPERTY_SCHEMA.update(types["schema"])
        if "settings" in types: SETTINGS.update(types["settings"])

        # Fallbacks for raw loaded items missing their type logic
        for nd in data.get("nodes", []):
            nt = nd.get("node_type", "default")
            if nt not in NODE_TYPE_COLORS: NODE_TYPE_COLORS[nt] = nd.get("color", "#888888")
        for ed in data.get("edges", []):
            et = ed.get("edge_type", "relationship")
            if et not in EDGE_TYPE_COLORS: EDGE_TYPE_COLORS[et] = ed.get("color", "#adb5bd")

        for nd in data.get("nodes", []):
            self.add_node(label=nd["label"], x=nd["x"], y=nd["y"], node_type=nd.get("node_type"), 
                          color=nd.get("color"), properties=nd.get("properties", {}), node_id=nd["id"])
        for ed in data.get("edges", []):
            s = self.nodes.get(ed["source"]); t = self.nodes.get(ed["target"])
            if s and t:
                self.add_edge(s, t, label=ed.get("label",""), edge_id=ed["id"],
                              direction=ed.get("direction","→"), edge_type=ed.get("edge_type","relationship"),
                              color=ed.get("color"))

    def mouseMoveEvent(self, event):
        if self._connecting and self._conn_line and self._conn_source:
            self._conn_line.setLine(QLineF(self._conn_source.scenePos(), event.scenePos()))
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._connecting:
            tgt = next((i for i in self.items(event.scenePos()) if isinstance(i, NodeItem) and i is not self._conn_source), None)
            if tgt:
                label, ok = QInputDialog.getText(None, "Edge Label", "Label (optional):")
                self.add_edge(self._conn_source, tgt, label=label if ok else "")
            self.abort_connect()
            return
        super().mouseReleaseEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            items = self.items(event.scenePos())
            clicked = None
            # Allow text label clicking to resolve to the parent Node/Edge
            for i in items:
                if isinstance(i, NodeItem) or isinstance(i, EdgeItem):
                    clicked = i
                    break
                elif isinstance(i, QGraphicsTextItem):
                    parent = i.parentItem()
                    if isinstance(parent, NodeItem) or isinstance(parent, EdgeItem):
                        clicked = parent
                        break

            if isinstance(clicked, NodeItem):
                self.node_selected.emit(clicked); self.edge_selected.emit(None)
            elif isinstance(clicked, EdgeItem):
                self.edge_selected.emit(clicked); self.node_selected.emit(None)
            else:
                self.node_selected.emit(None); self.edge_selected.emit(None)
                
        super().mousePressEvent(event)

class CanvasView(QGraphicsView):
    zoom_changed = pyqtSignal(float)
    MIN_ZOOM, MAX_ZOOM = 0.05, 8.0

    def __init__(self, scene):
        super().__init__(scene)
        self.setRenderHint(QPainter.Antialiasing); self.setRenderHint(QPainter.SmoothPixmapTransform)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse); self.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff); self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setFrameShape(QFrame.NoFrame)
        self._draw_grid = True; self._panning = False; self._pan_start = None
        self._space_held = False; self._scale = 1.0

    def drawBackground(self, painter, rect):
        super().drawBackground(painter, rect)
        if not self._draw_grid: return
        painter.setRenderHint(QPainter.Antialiasing, False)
        grid = 40; is_dark = CURRENT_THEME == "dark"
        pen_minor = QPen(QColor(128, 128, 128, 12 if is_dark else 10), 0)
        pen_major = QPen(QColor(128, 128, 128, 25 if is_dark else 20), 0)
        l = int(rect.left()) - (int(rect.left()) % grid); t = int(rect.top()) - (int(rect.top()) % grid)
        r = int(rect.right()) + grid; b = int(rect.bottom()) + grid
        for x in range(l, r, grid):
            painter.setPen(pen_major if x % (grid*5) == 0 else pen_minor)
            painter.drawLine(x, int(rect.top()), x, int(rect.bottom()))
        for y in range(t, b, grid):
            painter.setPen(pen_major if y % (grid*5) == 0 else pen_minor)
            painter.drawLine(int(rect.left()), y, int(rect.right()), y)

    def wheelEvent(self, event):
        factor = 1.15 if event.angleDelta().y() > 0 else 1/1.15
        new_scale = self._scale * factor
        if not (self.MIN_ZOOM <= new_scale <= self.MAX_ZOOM): return
        self._scale = new_scale; self.scale(factor, factor); self.zoom_changed.emit(self._scale)

    def _set_zoom(self, z):
        z = max(self.MIN_ZOOM, min(self.MAX_ZOOM, z))
        factor = z / self._scale; self._scale = z
        self.scale(factor, factor); self.zoom_changed.emit(self._scale)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Space and not event.isAutoRepeat():
            self._space_held = True; self.setDragMode(QGraphicsView.NoDrag); self.setCursor(Qt.OpenHandCursor)
        elif event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            for item in list(self.scene().selectedItems()):
                if isinstance(item, NodeItem): self.scene().delete_node(item)
                elif isinstance(item, EdgeItem): self.scene().delete_edge(item)
        elif event.key() == Qt.Key_Escape:
            self.scene().abort_connect(); self._space_held = False
            self.setDragMode(QGraphicsView.RubberBandDrag); self.setCursor(Qt.ArrowCursor)
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key_Space and not event.isAutoRepeat():
            self._space_held = False; self._panning = False; self._pan_start = None
            self.setDragMode(QGraphicsView.RubberBandDrag); self.setCursor(Qt.ArrowCursor)
        super().keyReleaseEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MiddleButton or (event.button() == Qt.LeftButton and self._space_held):
            self._panning = True; self._pan_start = event.pos(); self.setCursor(Qt.ClosedHandCursor); return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._panning and self._pan_start is not None:
            delta = event.pos() - self._pan_start; self._pan_start = event.pos()
            self.setTransformationAnchor(QGraphicsView.NoAnchor); self.translate(delta.x(), delta.y())
            self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse); return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._panning and (event.button() == Qt.MiddleButton or event.button() == Qt.LeftButton):
            self._panning = False; self._pan_start = None
            self.setCursor(Qt.OpenHandCursor if self._space_held else Qt.ArrowCursor)
            if not self._space_held: self.setDragMode(QGraphicsView.RubberBandDrag)
            return
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event):
        scene_pos = self.mapToScene(event.pos())
        items = self.scene().items(scene_pos)
        node = next((i for i in items if isinstance(i, NodeItem)), None)
        edge = next((i for i in items if isinstance(i, EdgeItem)), None)
        menu = QMenu(self); menu.setStyleSheet(self._menu_style())

        if node:
            a_conn = menu.addAction("🔗  Connect from here"); a_edit = menu.addAction("✏️  Rename")
            a_col = menu.addAction("🎨  Change colour"); menu.addSeparator()
            a_copy = menu.addAction("📋  Copy  (Ctrl+C)"); menu.addSeparator()
            a_del = menu.addAction("🗑️  Delete node")
            ch = menu.exec_(event.globalPos())
            if ch == a_conn: self.scene().start_connect(node)
            elif ch == a_edit:
                t, ok = QInputDialog.getText(self, "Rename", "New label:", text=node.label)
                if ok and t: node.label = t; node._refresh_text(); self.scene().graph_changed.emit()
            elif ch == a_col:
                c = QColorDialog.getColor(QColor(node.color), self)
                if c.isValid(): node.color = c.name(); node._refresh_text(); self.scene().update(); self.scene().graph_changed.emit()
            elif ch == a_copy: self._copy_selected()
            elif ch == a_del: self.scene().delete_node(node)
        elif edge:
            a_lbl = menu.addAction("🏷️  Edit label")
            a_col = menu.addAction("🎨  Change colour")
            a_dir = menu.addMenu("↔  Direction"); dir_acts = {a_dir.addAction(("✓ " if d == edge.direction else "    ") + d): d for d in EDGE_DIRECTIONS}
            a_typ = menu.addMenu("⬡  Edge type"); typ_acts = {a_typ.addAction(("✓ " if t == edge.edge_type else "    ") + t): t for t in EDGE_TYPE_COLORS}
            menu.addSeparator(); a_del = menu.addAction("🗑️  Delete edge")
            ch = menu.exec_(event.globalPos())
            if ch == a_lbl:
                t, ok = QInputDialog.getText(self, "Edge Label", "Label:", text=edge.label)
                if ok: edge.set_label(t); self.scene().graph_changed.emit()
            elif ch == a_col:
                c = QColorDialog.getColor(QColor(edge.color), self)
                if c.isValid(): edge.color = c.name(); edge._refresh_label_text(); self.scene().update(); self.scene.graph_changed.emit()
            elif ch in dir_acts: edge.set_direction(dir_acts[ch]); self.scene().graph_changed.emit()
            elif ch in typ_acts: edge.set_edge_type(typ_acts[ch]); self.scene().graph_changed.emit()
            elif ch == a_del: self.scene().delete_edge(edge)
        else:
            a_add = menu.addAction("➕  Add node here"); a_paste = menu.addAction("📋  Paste  (Ctrl+V)")
            ch = menu.exec_(event.globalPos())
            if ch == a_add:
                lbl, ok = QInputDialog.getText(self, "New Node", "Label:")
                if ok and lbl: self.scene().add_node(label=lbl, x=scene_pos.x(), y=scene_pos.y())
            elif ch == a_paste: self._paste(scene_pos)

    def _menu_style(self):
        return f""" QMenu {{ background:{gc('BG_PANEL')}; color:{gc('TEXT_PRIMARY')}; border:1px solid {gc('BORDER')}; border-radius:6px; padding:4px; }}
            QMenu::item {{ padding:6px 20px; border-radius:4px; }}
            QMenu::item:selected {{ background:{gc('ACCENT')}; color:white; }}
            QMenu::separator {{ background:{gc('BORDER')}; height:1px; margin:4px 8px; }} """

    def _copy_selected(self):
        self._clipboard = [n.to_dict() for n in self.scene().selectedItems() if isinstance(n, NodeItem)]

    def _paste(self, at=None):
        if not getattr(self, "_clipboard", None): return
        id_map = {}; offset = QPointF(30, 30)
        for nd in self._clipboard:
            new_nid = new_id(); id_map[nd["id"]] = new_nid
            base = QPointF(nd["x"], nd["y"]); pos = (at + offset) if at else (base + offset)
            self.scene().add_node(label=nd["label"], x=pos.x(), y=pos.y(), node_type=nd.get("node_type"),
                color=nd.get("color"), properties=copy.deepcopy(nd.get("properties", {})), node_id=new_nid)
        self.scene().clearSelection()

# ─────────────────────────────────────────────────────────────────────────────
#  Prop row widget
# ─────────────────────────────────────────────────────────────────────────────
class PropRow(QFrame):
    deleted = pyqtSignal(str)
    changed = pyqtSignal(str, str)

    def __init__(self, key, value, is_schema=False):
        super().__init__()
        self.key_name = key
        self.setStyleSheet(f"QFrame {{ background:{gc('BG_CARD')}; border-radius:6px; border:1px solid {gc('BORDER')}; }}")
        lay = QHBoxLayout(self); lay.setContentsMargins(8, 4, 4, 4); lay.setSpacing(6)

        self.key_lbl = QLabel(key); self.key_lbl.setFixedWidth(86); self.key_lbl.setWordWrap(True)
        self.key_lbl.setStyleSheet(f"color:{gc('ACCENT') if is_schema else gc('TEXT_PRIMARY')}; font-weight:bold; font-size:{SETTINGS['sidebar_font_size']-1}px; border:none; background:transparent;")
        if is_schema: self.key_lbl.setToolTip("Schema Property")

        self.val_edit = QLineEdit(str(value))
        self.val_edit.setStyleSheet(f"QLineEdit {{ background:{gc('BG_PANEL')}; color:{gc('TEXT_PRIMARY')}; border:1px solid {gc('BORDER')}; border-radius:4px; padding:3px 6px; font-size:{SETTINGS['sidebar_font_size']-1}px; }} QLineEdit:focus {{ border-color:{gc('ACCENT')}; }}")
        self.val_edit.editingFinished.connect(lambda: self.changed.emit(self.key_name, self.val_edit.text()))

        db = QPushButton("⎚" if is_schema else "✕"); db.setFixedSize(22, 22)
        db.setToolTip("Clear Value" if is_schema else "Delete Property")
        db.setStyleSheet(f"QPushButton {{ background:transparent; color:{gc('TEXT_MUTED') if is_schema else gc('ACCENT2')}; border:none; font-weight:bold; }} QPushButton:hover {{ background:{gc('BORDER') if is_schema else gc('ACCENT2')}; color:{'white' if not is_schema else gc('TEXT_PRIMARY')}; border-radius:4px; }}")
        
        if is_schema: db.clicked.connect(lambda: (self.val_edit.setText(""), self.changed.emit(self.key_name, "")))
        else: db.clicked.connect(lambda: self.deleted.emit(self.key_name))

        lay.addWidget(self.key_lbl); lay.addWidget(self.val_edit); lay.addWidget(db)

# ─────────────────────────────────────────────────────────────────────────────
#  Sidebar & Search 
# ─────────────────────────────────────────────────────────────────────────────
class Sidebar(QWidget):
    def __init__(self, scene):
        super().__init__()
        self.scene = scene; self._node = None; self._edge = None; self.setFixedWidth(290)
        self._root = QVBoxLayout(self); self._root.setContentsMargins(0, 0, 0, 0); self._root.setSpacing(0)
        self.header = QLabel("Properties"); self._root.addWidget(self.header)
        self.scroll = QScrollArea(); self.scroll.setWidgetResizable(True); self.scroll.setFrameShape(QFrame.NoFrame)
        self.content = QWidget(); self.cl = QVBoxLayout(self.content); self.cl.setContentsMargins(12, 12, 12, 12); self.cl.setSpacing(8); self.cl.addStretch()
        self.scroll.setWidget(self.content); self._root.addWidget(self.scroll)
        self.apply_style(); self.show_empty()

    def apply_style(self):
        sf = SETTINGS["sidebar_font_size"]
        self.setStyleSheet(f"background:{gc('BG_PANEL')};")
        self.header.setStyleSheet(f"QLabel {{ background:{gc('BG_DARK')}; color:{gc('TEXT_PRIMARY')}; font-size:{sf+3}px; font-weight:bold; padding:14px 16px; border-bottom:1px solid {gc('BORDER')}; }}")
        self.scroll.setStyleSheet(f"QScrollArea {{ background:transparent; border:none; }} QScrollBar:vertical {{ background:{gc('BG_DARK')}; width:6px; border-radius:3px; }} QScrollBar::handle:vertical {{ background:{gc('BORDER')}; border-radius:3px; min-height:20px; }}")
        self.content.setStyleSheet(f"background:{gc('BG_PANEL')};")

    def _clear(self):
        while self.cl.count():
            it = self.cl.takeAt(0)
            if it.widget(): it.widget().deleteLater()

    def show_empty(self):
        self._node = self._edge = None; self._clear(); self.header.setText("Properties")
        lbl = QLabel("Click a node or edge\nto view its properties.")
        lbl.setStyleSheet(f"color:{gc('TEXT_MUTED')}; font-size:{SETTINGS['sidebar_font_size']}px; padding:20px 0; background:transparent;")
        lbl.setAlignment(Qt.AlignCenter); self.cl.addWidget(lbl); self.cl.addStretch()

    def show_node(self, node):
        self._node = node; self._edge = None; self._clear(); self.header.setText(f"Node  ·  {node.node_id}")
        self._build_node_ui(node); self.cl.addStretch()

    def show_edge(self, edge):
        self._edge = edge; self._node = None; self._clear(); self.header.setText(f"Edge  ·  {edge.edge_id}")
        self._build_edge_ui(edge); self.cl.addStretch()

    def _section(self, title):
        lbl = QLabel(title.upper())
        lbl.setStyleSheet(f"color:{gc('TEXT_MUTED')}; font-size:{SETTINGS['sidebar_font_size']-3}px; font-weight:bold; letter-spacing:1.5px; padding:6px 0 2px 0; background:transparent;")
        self.cl.addWidget(lbl)

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
            node.node_type = t; node.color = NODE_TYPE_COLORS.get(t, node.color)
            node._inject_schema(); node._refresh_text(); self.scene.update(); self.scene.graph_changed.emit()
            self.show_node(node)
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
            is_schema = k in expected_keys
            row = PropRow(k, v, is_schema=is_schema)
            def _del(key, n=node):
                del n.properties[key]; self.scene.graph_changed.emit(); self.show_node(n)
            def _chg(key, val, n=node):
                n.properties[key] = val; self.scene.graph_changed.emit()
            row.deleted.connect(_del); row.changed.connect(_chg); self.cl.addWidget(row)
        
        row = QFrame(); row.setStyleSheet("background:transparent;"); lay = QHBoxLayout(row); lay.setContentsMargins(0,0,0,0); lay.setSpacing(4)
        ki = QLineEdit(); ki.setPlaceholderText("key"); ki.setStyleSheet(self._inp())
        vi = QLineEdit(); vi.setPlaceholderText("value"); vi.setStyleSheet(self._inp())
        ab = QPushButton("+"); ab.setFixedSize(28,28); ab.setStyleSheet(self._btn(gc("ACCENT3")))
        def _add():
            k = ki.text().strip(); v = vi.text().strip()
            if k: node.properties[k] = v; self.scene.graph_changed.emit(); self.show_node(node)
        ab.clicked.connect(_add); ki.returnPressed.connect(_add); vi.returnPressed.connect(_add)
        lay.addWidget(ki); lay.addWidget(vi); lay.addWidget(ab); self.cl.addWidget(row)

        db = QPushButton("🗑  Delete Node"); db.setStyleSheet(self._btn(gc("ACCENT2")))
        db.clicked.connect(lambda: (self.scene.delete_node(node), self.show_empty())); self.cl.addWidget(db)

    def _build_edge_ui(self, edge):
        self._section("Direction")
        dc = QComboBox(); dc.addItems(EDGE_DIRECTIONS); dc.setCurrentText(edge.direction); dc.setStyleSheet(self._combo())
        dc.currentTextChanged.connect(lambda d: (edge.set_direction(d), self.scene.graph_changed.emit())); self.cl.addWidget(dc)

        self._section("Edge Type")
        etc = QComboBox(); etc.addItems(list(EDGE_TYPE_COLORS.keys())); etc.setCurrentText(edge.edge_type); etc.setStyleSheet(self._combo())
        etc.currentTextChanged.connect(lambda t: (edge.set_edge_type(t), self.scene.graph_changed.emit())); self.cl.addWidget(etc)

        # Edge Colour overrides
        col_row = QFrame(); col_row.setStyleSheet("background:transparent;"); col_lay = QHBoxLayout(col_row); col_lay.setContentsMargins(0,0,0,0)
        self._edge_swatch = QPushButton(); self._edge_swatch.setFixedSize(28, 28); self._edge_swatch.setStyleSheet(f"background:{edge.color}; border-radius:14px; border:none;")
        col_lbl = QLabel("Custom colour"); col_lbl.setStyleSheet(f"color:{gc('TEXT_MUTED')}; background:transparent; font-size:{SETTINGS['sidebar_font_size']-1}px;")
        def _pick_col():
            c = QColorDialog.getColor(QColor(edge.color), self)
            if c.isValid():
                edge.color = c.name(); self._edge_swatch.setStyleSheet(f"background:{edge.color}; border-radius:14px; border:none;")
                edge._refresh_label_text(); self.scene.update(); self.scene.graph_changed.emit()
        self._edge_swatch.clicked.connect(_pick_col)
        col_lay.addWidget(self._edge_swatch); col_lay.addWidget(col_lbl); col_lay.addStretch(); self.cl.addWidget(col_row)

        self._section("Label")
        le = QLineEdit(edge.label); le.setStyleSheet(self._inp())
        le.editingFinished.connect(lambda: (edge.set_label(le.text()), self.scene.graph_changed.emit())); self.cl.addWidget(le)

        db = QPushButton("🗑  Delete Edge"); db.setStyleSheet(self._btn(gc("ACCENT2")))
        db.clicked.connect(lambda: (self.scene.delete_edge(edge), self.show_empty())); self.cl.addWidget(db)

class SearchBar(QWidget):
    def __init__(self, scene, view):
        super().__init__()
        self.scene = scene; self.view = view; self._matches = []; self._match_idx = 0
        lay = QHBoxLayout(self); lay.setContentsMargins(12, 7, 12, 7); lay.setSpacing(6)
        self.icon = QLabel("🔍"); lay.addWidget(self.icon)
        self.edit = QLineEdit(); self.edit.setPlaceholderText("Search nodes… (Ctrl+F)"); self.edit.textChanged.connect(self._search)
        self.edit.installEventFilter(self); lay.addWidget(self.edit)
        self.prev_btn = QPushButton("◀"); self.next_btn = QPushButton("▶")
        for b in (self.prev_btn, self.next_btn): b.setFixedWidth(28)
        self.prev_btn.clicked.connect(lambda: self._centre_on(self._match_idx - 1)); self.next_btn.clicked.connect(lambda: self._centre_on(self._match_idx + 1))
        lay.addWidget(self.prev_btn); lay.addWidget(self.next_btn)
        self.result_lbl = QLabel(""); lay.addWidget(self.result_lbl)
        self.clear_btn = QPushButton("✕"); self.clear_btn.setFixedWidth(24); self.clear_btn.clicked.connect(self.edit.clear); lay.addWidget(self.clear_btn)
        self.apply_style()

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
        self._match_idx = idx % len(self._matches); self.view.centerOn(self._matches[self._match_idx])
        self.result_lbl.setText(f"{self._match_idx+1}/{len(self._matches)}")

# ─────────────────────────────────────────────────────────────────────────────
#  Settings dialog 
# ─────────────────────────────────────────────────────────────────────────────
class SettingsDialog(QDialog):
    def __init__(self, parent, scene):
        super().__init__(parent)
        self.scene = scene
        self.setWindowTitle("Settings")
        self.setMinimumSize(500, 450)
        
        self.temp_colors = copy.deepcopy(NODE_TYPE_COLORS)
        self.temp_edges = copy.deepcopy(EDGE_TYPE_COLORS)
        self.temp_schema = copy.deepcopy(PROPERTY_SCHEMA)
        self.temp_settings = copy.deepcopy(SETTINGS)

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

        main_lay = QVBoxLayout(self)
        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_general_tab(), "General")
        self.tabs.addTab(self._build_types_tab(), "Node & Edge Types")
        self.tabs.addTab(self._build_props_tab(), "Property Schema")
        main_lay.addWidget(self.tabs)

        bb = QDialogButtonBox(QDialogButtonBox.Apply | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Apply).setText("Save Settings")
        bb.accepted.connect(self._apply)
        bb.rejected.connect(self.reject)
        bb.setStyleSheet(f'QDialogButtonBox QPushButton[text="Cancel"] {{ background:{gc("BG_CARD")}; color:{gc("TEXT_PRIMARY")}; border:1px solid {gc("BORDER")}; }}')
        main_lay.addWidget(bb)

    def _build_general_tab(self):
        w = QWidget(); lay = QVBoxLayout(w); lay.setSpacing(12)
        grp_font = QGroupBox("Eye Comfort"); gfl = QFormLayout(grp_font)
        self.ui_font_spin = QSpinBox(); self.ui_font_spin.setRange(7, 24); self.ui_font_spin.setValue(self.temp_settings["ui_font_size"])
        self.sb_font_spin = QSpinBox(); self.sb_font_spin.setRange(8, 24); self.sb_font_spin.setValue(self.temp_settings["sidebar_font_size"])
        gfl.addRow("Canvas label size:", self.ui_font_spin); gfl.addRow("Sidebar font size:", self.sb_font_spin)
        lay.addWidget(grp_font)

        grp_def = QGroupBox("Defaults"); gdl = QFormLayout(grp_def)
        self.def_node_type = QComboBox(); self.def_node_type.addItems(list(self.temp_colors.keys())); self.def_node_type.setCurrentText(self.temp_settings["default_node_type"])
        self.def_edge_type = QComboBox(); self.def_edge_type.addItems(list(self.temp_edges.keys())); self.def_edge_type.setCurrentText(self.temp_settings["default_edge_type"])
        self.def_direction = QComboBox(); self.def_direction.addItems(EDGE_DIRECTIONS); self.def_direction.setCurrentText(self.temp_settings["default_direction"])
        gdl.addRow("Default node type:", self.def_node_type); gdl.addRow("Default edge type:", self.def_edge_type); gdl.addRow("Default direction:", self.def_direction)
        lay.addWidget(grp_def); lay.addStretch(); return w

    def _build_types_tab(self):
        w = QWidget(); lay = QHBoxLayout(w)
        
        # Node Types Panel
        nt_grp = QGroupBox("Node Types"); nt_lay = QVBoxLayout(nt_grp)
        self.nt_list = QListWidget()
        for nt, col in self.temp_colors.items(): self._add_nt_list_item(nt, col)
        
        nt_btns = QHBoxLayout()
        btn_add_nt = QPushButton("+ Add"); btn_col_nt = QPushButton("🎨 Colour"); btn_del_nt = QPushButton("- Delete")
        btn_del_nt.setStyleSheet(f"background:{gc('ACCENT2')}; color:white; border-radius:4px; padding:6px 12px; font-weight:bold;")
        btn_add_nt.clicked.connect(self._add_node_type); btn_col_nt.clicked.connect(self._change_node_color); btn_del_nt.clicked.connect(self._delete_node_type)
        nt_btns.addWidget(btn_add_nt); nt_btns.addWidget(btn_col_nt); nt_btns.addWidget(btn_del_nt)
        nt_lay.addWidget(self.nt_list); nt_lay.addLayout(nt_btns); lay.addWidget(nt_grp)

        # Edge Types Panel
        et_grp = QGroupBox("Edge Types"); et_lay = QVBoxLayout(et_grp)
        self.et_list = QListWidget()
        for et, col in self.temp_edges.items(): self._add_et_list_item(et, col)
        
        et_btns = QHBoxLayout()
        btn_add_et = QPushButton("+ Add"); btn_col_et = QPushButton("🎨 Colour"); btn_del_et = QPushButton("- Delete")
        btn_del_et.setStyleSheet(btn_del_nt.styleSheet())
        btn_add_et.clicked.connect(self._add_edge_type); btn_col_et.clicked.connect(self._change_edge_color); btn_del_et.clicked.connect(self._delete_edge_type)
        et_btns.addWidget(btn_add_et); et_btns.addWidget(btn_col_et); et_btns.addWidget(btn_del_et)
        et_lay.addWidget(self.et_list); et_lay.addLayout(et_btns); lay.addWidget(et_grp)
        
        return w

    def _add_nt_list_item(self, nt, col):
        item = QListWidgetItem(nt); pix = QPixmap(14, 14); pix.fill(QColor(col)); item.setIcon(QIcon(pix)); item.setData(Qt.UserRole, nt); self.nt_list.addItem(item)

    def _add_et_list_item(self, et, col):
        item = QListWidgetItem(et); pix = QPixmap(14, 14); pix.fill(QColor(col)); item.setIcon(QIcon(pix)); item.setData(Qt.UserRole, et); self.et_list.addItem(item)

    def _add_node_type(self):
        nt, ok = QInputDialog.getText(self, "New Node Type", "Type Name:")
        if ok and nt and nt not in self.temp_colors:
            col = QColorDialog.getColor(Qt.gray, self)
            if col.isValid():
                self.temp_colors[nt] = col.name(); self._add_nt_list_item(nt, col.name()); self.def_node_type.addItem(nt)

    def _add_edge_type(self):
        et, ok = QInputDialog.getText(self, "New Edge Type", "Type Name:")
        if ok and et and et not in self.temp_edges:
            col = QColorDialog.getColor(QColor("#adb5bd"), self)
            if col.isValid():
                self.temp_edges[et] = col.name(); self._add_et_list_item(et, col.name()); self.def_edge_type.addItem(et)

    def _change_node_color(self):
        item = self.nt_list.currentItem()
        if not item: return
        nt = item.data(Qt.UserRole)
        c = QColorDialog.getColor(QColor(self.temp_colors[nt]), self)
        if c.isValid(): self.temp_colors[nt] = c.name(); pix = QPixmap(14, 14); pix.fill(c); item.setIcon(QIcon(pix))

    def _change_edge_color(self):
        item = self.et_list.currentItem()
        if not item: return
        et = item.data(Qt.UserRole)
        c = QColorDialog.getColor(QColor(self.temp_edges[et]), self)
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
        idx = self.def_node_type.findText(nt); self.def_node_type.removeItem(idx)

    def _delete_edge_type(self):
        item = self.et_list.currentItem()
        if not item: return
        et = item.data(Qt.UserRole)
        if et == "relationship": return QMessageBox.warning(self, "Denied", "Cannot delete the 'relationship' edge type.")
        if any(e.edge_type == et for e in self.scene.edges.values()): return QMessageBox.warning(self, "In Use", f"Cannot delete '{et}': It is in use by edges on the canvas.")
        
        del self.temp_edges[et]
        self.et_list.takeItem(self.et_list.row(item))
        idx = self.def_edge_type.findText(et); self.def_edge_type.removeItem(idx)

    def _build_props_tab(self):
        w = QWidget(); lay = QVBoxLayout(w)
        ctrl_lay = QHBoxLayout(); ctrl_lay.addWidget(QLabel("Target Type:"))
        self.schema_combo = QComboBox()
        self.schema_combo.addItems(["__universal__"] + list(self.temp_colors.keys()))
        self.schema_combo.currentTextChanged.connect(self._load_schema_list)
        ctrl_lay.addWidget(self.schema_combo); lay.addLayout(ctrl_lay)
        self.schema_list = QListWidget(); lay.addWidget(self.schema_list)
        btn_lay = QHBoxLayout(); add_p = QPushButton("+ Add Property"); del_p = QPushButton("- Delete Property")
        del_p.setStyleSheet(f"background:{gc('ACCENT2')}; color:white; border-radius:4px; padding:6px 12px; font-weight:bold;")
        add_p.clicked.connect(self._add_schema_prop); del_p.clicked.connect(self._del_schema_prop)
        btn_lay.addWidget(add_p); btn_lay.addWidget(del_p); lay.addLayout(btn_lay)
        self._load_schema_list(self.schema_combo.currentText())
        return w

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
        global NODE_TYPE_COLORS, EDGE_TYPE_COLORS, PROPERTY_SCHEMA, SETTINGS

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

# ─────────────────────────────────────────────────────────────────────────────
#  Main Window
# ─────────────────────────────────────────────────────────────────────────────
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
        global CURRENT_THEME
        CURRENT_THEME = "dark" if CURRENT_THEME == "light" else "light"
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
            app.setFont(QFont("Segoe UI", SETTINGS["ui_font_size"])) # Enforce globally to standard elements 
            self._apply_global_style(); self.search_bar.apply_style(); self.sidebar.apply_style()
            # Force geometric recalculations for explicit drawn text on the canvas
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