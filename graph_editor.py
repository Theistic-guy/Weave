#!/usr/bin/env python3
"""
GraphCanvas — A node-based graph editor with properties sidebar,
edge labels, drag-and-drop, search, save/load, and custom properties.
(GraphCommons Minimalist Style)
"""

import sys
import json
import math
import uuid
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGraphicsScene, QGraphicsView, QGraphicsItem, QGraphicsEllipseItem,
    QGraphicsLineItem, QGraphicsTextItem, QGraphicsRectItem,
    QSplitter, QLabel, QLineEdit, QPushButton, QScrollArea,
    QFrame, QFileDialog, QInputDialog, QMessageBox, QToolBar,
    QAction, QStatusBar, QShortcut, QGraphicsPathItem, QComboBox,
    QSizePolicy, QDialog, QDialogButtonBox, QFormLayout, QMenu,
    QGraphicsProxyWidget, QColorDialog
)
from PyQt5.QtCore import (
    Qt, QPointF, QRectF, QLineF, pyqtSignal, QObject, QTimer, QSize
)
from PyQt5.QtGui import (
    QPainter, QPen, QBrush, QColor, QFont, QFontMetrics, QPainterPath,
    QLinearGradient, QRadialGradient, QKeySequence, QIcon, QPixmap,
    QTransform, QPalette
)

# ── Colour Palette & Themes ──────────────────────────────────────────────────
THEMES = {
    "light": {
        "BG_DARK":       "#ffffff",
        "BG_PANEL":      "#f8f9fa",
        "BG_CARD":       "#ffffff",
        "ACCENT":        "#4c84ff",
        "ACCENT2":       "#ff6b6b",
        "ACCENT3":       "#51cf66",
        "TEXT_PRIMARY":  "#495057",
        "TEXT_MUTED":    "#adb5bd",
        "BORDER":        "#e9ecef",
        "NODE_DEFAULT":  "#d81b60",
        "EDGE_COLOR":    "#ced4da",
        "EDGE_LABEL_BG": "#ffffff"
    },
    "dark": {
        "BG_DARK":       "#0f1117",
        "BG_PANEL":      "#1a1d27",
        "BG_CARD":       "#21253a",
        "ACCENT":        "#6c63ff",
        "ACCENT2":       "#ff6584",
        "ACCENT3":       "#43e97b",
        "TEXT_PRIMARY":  "#e8eaf6",
        "TEXT_MUTED":    "#7986cb",
        "BORDER":        "#2d3154",
        "NODE_DEFAULT":  "#252a42",
        "EDGE_COLOR":    "#4a5080",
        "EDGE_LABEL_BG": "#1e2236"
    }
}

CURRENT_THEME = "light"

def get_col(key):
    return THEMES[CURRENT_THEME].get(key, "#ff00ff")

def qcolor(key):
    if key.startswith("#"):
        return QColor(key)
    return QColor(get_col(key))

NODE_COLORS = {
    "default": "#d81b60",
    "process": "#1e88e5",
    "data":    "#43a047",
    "event":   "#fb8c00",
    "note":    "#8d6e63",
    "object":  "#8d5524"
}

# ── Utilities ────────────────────────────────────────────────────────────────
def new_id():
    return str(uuid.uuid4())[:8]

# ── Edge Item (GraphCommons Style) ───────────────────────────────────────────
class EdgeItem(QGraphicsPathItem):
    def __init__(self, source_node, target_node, label="", edge_id=None):
        super().__init__()
        self.edge_id     = edge_id or new_id()
        self.source_node = source_node
        self.target_node = target_node
        self.label       = label

        self.setZValue(0)
        self.setFlag(QGraphicsItem.ItemIsSelectable)
        
        # Scale-invariant text child
        self._label_item = QGraphicsTextItem(self.label, self)
        self._label_item.setFlag(QGraphicsItem.ItemIgnoresTransformations)
        font = QFont("Segoe UI", 8)
        self._label_item.setFont(font)
        
        self.update_path()

    def set_label(self, text):
        self.label = text
        self._label_item.setPlainText(text)
        self.update_path()

    def update_path(self):
        sp = self.source_node.scenePos()
        tp = self.target_node.scenePos()

        # Straight line path
        path = QPainterPath(sp)
        path.lineTo(tp)
        
        # Arrow head
        angle = math.atan2(tp.y() - sp.y(), tp.x() - sp.x())
        arrow_len = 8
        target_offset = tp - QPointF(math.cos(angle) * (self.target_node.radius + 2), 
                                     math.sin(angle) * (self.target_node.radius + 2))
        
        a1 = angle + math.pi * 0.85
        a2 = angle - math.pi * 0.85
        arr = QPainterPath()
        arr.moveTo(target_offset)
        arr.lineTo(target_offset + QPointF(math.cos(a1) * arrow_len, math.sin(a1) * arrow_len))
        arr.moveTo(target_offset)
        arr.lineTo(target_offset + QPointF(math.cos(a2) * arrow_len, math.sin(a2) * arrow_len))
        path.addPath(arr)
        
        self.setPath(path)

        # Reposition scale-invariant label to the midpoint
        if self.label:
            mid = QPointF((sp.x() + tp.x())/2, (sp.y() + tp.y())/2)
            self._label_item.setPos(mid)
            self._update_text_style()

    def _update_text_style(self):
        self._label_item.setDefaultTextColor(qcolor("TEXT_MUTED"))

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        if self.isSelected():
            pen = QPen(qcolor("ACCENT"), 2.0)
        else:
            pen = QPen(qcolor("EDGE_COLOR"), 1.2)
        self.setPen(pen)
        super().paint(painter, option, widget)

    def to_dict(self):
        return {
            "id":     self.edge_id,
            "source": self.source_node.node_id,
            "target": self.target_node.node_id,
            "label":  self.label,
        }

# ── Node Item (GraphCommons Style) ───────────────────────────────────────────
class NodeItem(QGraphicsItem):
    def __init__(self, node_id=None, label="Node", x=0, y=0,
                 node_type="default", color=None, properties=None):
        super().__init__()
        self.node_id    = node_id or new_id()
        self.label      = label
        self.node_type  = node_type
        self.color      = color or NODE_COLORS.get(node_type, NODE_COLORS["default"])
        self.properties = properties or {}
        self.edges      = []
        
        self.radius     = 10
        self._selected_color = "ACCENT"

        self.setFlag(QGraphicsItem.ItemIsMovable)
        self.setFlag(QGraphicsItem.ItemIsSelectable)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges)
        self.setPos(x, y)
        self.setZValue(1)

        # Scale-invariant text child
        self.text_item = QGraphicsTextItem(self.label, self)
        self.text_item.setFlag(QGraphicsItem.ItemIgnoresTransformations)
        font = QFont("Segoe UI", 9, QFont.Medium)
        self.text_item.setFont(font)
        self._update_text_style()
        self._position_text()

    def _update_text_style(self):
        self.text_item.setDefaultTextColor(qcolor(self.color))
        self.text_item.setPlainText(self.label)
        
    def _position_text(self):
        br = self.text_item.boundingRect()
        self.text_item.setPos(self.radius + 4, -br.height() / 2)

    def boundingRect(self):
        pad = 4
        return QRectF(-self.radius - pad, -self.radius - pad, 
                      self.radius*2 + pad*2, self.radius*2 + pad*2)

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        selected = self.isSelected()
        
        rect = QRectF(-self.radius, -self.radius, self.radius*2, self.radius*2)
        base_color = qcolor("ACCENT") if selected else qcolor(self.color)
        
        painter.setBrush(QBrush(base_color))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(rect)

        if selected:
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(base_color, 2))
            painter.drawEllipse(rect.adjusted(-4, -4, 4, 4))

        self._update_text_style()
        self._position_text()

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionHasChanged:
            for e in self.edges:
                e.update_path()
        return super().itemChange(change, value)

    def to_dict(self):
        return {
            "id":         self.node_id,
            "label":      self.label,
            "x":          self.x(),
            "y":          self.y(),
            "node_type":  self.node_type,
            "color":      self.color,
            "properties": self.properties,
        }

    def add_edge(self, edge):
        if edge not in self.edges:
            self.edges.append(edge)
            self._update_size()

    def remove_edge(self, edge):
        if edge in self.edges:
            self.edges.remove(edge)
            self._update_size()

    def _update_size(self):
        # Must call this before changing radius so Qt knows the bounding box changed
        self.prepareGeometryChange() 
        
        # Base size of 10, plus 2.5 for every connected edge
        self.radius = 10 + (len(self.edges) * 2.5)
        
        # Re-center the text next to the new larger radius
        self._position_text()
        
        # Tell connected edges to update their arrows to the new perimeter
        for e in self.edges:
            e.update_path()
        self.update()

# ── Graph Scene ──────────────────────────────────────────────────────────────
class GraphScene(QGraphicsScene):
    node_selected   = pyqtSignal(object)
    edge_selected   = pyqtSignal(object)
    graph_changed   = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setBackgroundBrush(QBrush(qcolor("BG_DARK")))
        self.nodes = {}
        self.edges = {}
        self._connecting = False
        self._conn_source = None
        self._conn_line   = None

        self.layout_timer = QTimer()
        self.layout_timer.timeout.connect(self.do_layout_step)
        self.layout_active = False

    
    def toggle_layout(self):
        self.layout_active = not self.layout_active
        if self.layout_active:
            self.layout_timer.start(20) # 50 FPS
        else:
            self.layout_timer.stop()
        return self.layout_active

    def do_layout_step(self):
        forces = {node.node_id: QPointF(0, 0) for node in self.nodes.values()}
        
        # 1. Repulsion (Nodes push each other away)
        c_rep = 2500.0 # Adjust to make them spread further
        nodes_list = list(self.nodes.values())
        for i in range(len(nodes_list)):
            for j in range(i + 1, len(nodes_list)):
                n1, n2 = nodes_list[i], nodes_list[j]
                p1, p2 = n1.scenePos(), n2.scenePos()
                dx = p1.x() - p2.x()
                dy = p1.y() - p2.y()
                dist = math.hypot(dx, dy)
                
                if dist < 0.1: dist = 0.1
                if dist > 800: continue # Optimization: ignore distant nodes
                
                force = c_rep / (dist * dist)
                fx, fy = force * (dx / dist), force * (dy / dist)
                
                forces[n1.node_id] += QPointF(fx, fy)
                forces[n2.node_id] -= QPointF(fx, fy)

        # 2. Attraction (Edges act as springs)
        c_attr = 0.05 # Spring stiffness
        ideal_len = 120.0 # Preferred distance between connected nodes
        for edge in self.edges.values():
            n1, n2 = edge.source_node, edge.target_node
            p1, p2 = n1.scenePos(), n2.scenePos()
            dx = p2.x() - p1.x()
            dy = p2.y() - p1.y()
            dist = math.hypot(dx, dy)
            if dist < 0.1: dist = 0.1
            
            force = c_attr * (dist - ideal_len)
            fx, fy = force * (dx / dist), force * (dy / dist)
            
            forces[n1.node_id] += QPointF(fx, fy)
            forces[n2.node_id] -= QPointF(fx, fy)

        # 3. Apply forces
        max_move = 10.0 # Velocity cap
        for node in self.nodes.values():
            if node.isSelected(): continue # Don't move nodes the user is currently holding
            
            f = forces[node.node_id]
            mx = min(max_move, max(-max_move, f.x()))
            my = min(max_move, max(-max_move, f.y()))
            
            if abs(mx) > 0.1 or abs(my) > 0.1:
                node.setPos(node.scenePos() + QPointF(mx, my))

    def add_node(self, label="Node", x=100, y=100, node_type="default", color=None, properties=None, node_id=None):
        node = NodeItem(node_id=node_id, label=label, x=x, y=y,
                        node_type=node_type, color=color, properties=properties)
        self.nodes[node.node_id] = node
        self.addItem(node)
        self.graph_changed.emit()
        return node

    def delete_node(self, node):
        for e in list(node.edges):
            self.delete_edge(e)
        self.nodes.pop(node.node_id, None)
        self.removeItem(node)
        self.graph_changed.emit()

    def add_edge(self, source, target, label="", edge_id=None):
        for e in source.edges:
            if (e.source_node is source and e.target_node is target) or \
               (e.source_node is target and e.target_node is source):
                return None
        edge = EdgeItem(source, target, label=label, edge_id=edge_id)
        self.edges[edge.edge_id] = edge
        self.addItem(edge)
        source.add_edge(edge)
        target.add_edge(edge)
        self.graph_changed.emit()
        return edge

    def delete_edge(self, edge):
        edge.source_node.remove_edge(edge)
        edge.target_node.remove_edge(edge)
        self.edges.pop(edge.edge_id, None)
        self.removeItem(edge)
        self.graph_changed.emit()

    def start_connect(self, source_node):
        self._connecting   = True
        self._conn_source  = source_node
        pen = QPen(qcolor("ACCENT"), 2, Qt.DashLine)
        self._conn_line = self.addLine(QLineF(), pen)

    def abort_connect(self):
        self._connecting = False
        self._conn_source = None
        if self._conn_line:
            self.removeItem(self._conn_line)
            self._conn_line = None

    def to_dict(self):
        return {
            "nodes": [n.to_dict() for n in self.nodes.values()],
            "edges": [e.to_dict() for e in self.edges.values()],
        }

    def load_dict(self, data):
        self.clear()
        self.nodes.clear()
        self.edges.clear()
        for nd in data.get("nodes", []):
            self.add_node(
                label=nd["label"], x=nd["x"], y=nd["y"],
                node_type=nd.get("node_type","default"),
                color=nd.get("color"), properties=nd.get("properties",{}),
                node_id=nd["id"]
            )
        for ed in data.get("edges", []):
            s = self.nodes.get(ed["source"])
            t = self.nodes.get(ed["target"])
            if s and t:
                self.add_edge(s, t, label=ed.get("label",""), edge_id=ed["id"])

    def mouseMoveEvent(self, event):
        if self._connecting and self._conn_line and self._conn_source:
            sp = self._conn_source.scenePos()
            self._conn_line.setLine(QLineF(sp, event.scenePos()))
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._connecting:
            items = self.items(event.scenePos())
            target = next((i for i in items if isinstance(i, NodeItem) and i is not self._conn_source), None)
            if target:
                label, ok = QInputDialog.getText(None, "Edge Label", "Label for this edge (optional):")
                self.add_edge(self._conn_source, target, label=label if ok else "")
            self.abort_connect()
            return
        super().mouseReleaseEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            items = self.items(event.scenePos())
            clicked = next((i for i in items if isinstance(i, (NodeItem, EdgeItem))), None)
            if isinstance(clicked, NodeItem):
                self.node_selected.emit(clicked)
                self.edge_selected.emit(None)
            elif isinstance(clicked, EdgeItem):
                self.edge_selected.emit(clicked)
                self.node_selected.emit(None)
            else:
                self.node_selected.emit(None)
                self.edge_selected.emit(None)
        super().mousePressEvent(event)

# ── Canvas View ──────────────────────────────────────────────────────────────
class CanvasView(QGraphicsView):
    def __init__(self, scene):
        super().__init__(scene)
        self.setRenderHint(QPainter.Antialiasing)
        self.setRenderHint(QPainter.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setBackgroundBrush(QBrush(qcolor("BG_DARK")))
        self.setFrameShape(QFrame.NoFrame)
        self._pan_start = None
        self._panning   = False
        self.setSceneRect(-4000, -4000, 8000, 8000)
        self._draw_grid = True

    def drawBackground(self, painter, rect):
        super().drawBackground(painter, rect)
        if not self._draw_grid:
            return
        painter.setRenderHint(QPainter.Antialiasing, False)
        grid = 40
        
        # Subtle grid dependent on theme
        grid_col = QColor(0, 0, 0, 8) if CURRENT_THEME == "light" else QColor(255, 255, 255, 8)
        pen_minor = QPen(grid_col, 0.5)
        pen_major = QPen(QColor(grid_col.red(), grid_col.green(), grid_col.blue(), 18), 0.8)

        left   = int(rect.left())   - (int(rect.left())   % grid)
        top    = int(rect.top())    - (int(rect.top())    % grid)
        right  = int(rect.right())  + grid
        bottom = int(rect.bottom()) + grid

        for x in range(left, right, grid):
            painter.setPen(pen_major if x % (grid*5)==0 else pen_minor)
            painter.drawLine(x, int(rect.top()), x, int(rect.bottom()))
        for y in range(top, bottom, grid):
            painter.setPen(pen_major if y % (grid*5)==0 else pen_minor)
            painter.drawLine(int(rect.left()), y, int(rect.right()), y)

    def wheelEvent(self, event):
        factor = 1.15 if event.angleDelta().y() > 0 else 1/1.15
        self.scale(factor, factor)

    def mousePressEvent(self, event):
        if event.button() == Qt.MiddleButton:
            self._pan_start = event.pos()
            self._panning = True
            self.setCursor(Qt.ClosedHandCursor)
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._panning and self._pan_start:
            delta = event.pos() - self._pan_start
            self._pan_start = event.pos()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MiddleButton:
            self._panning = False
            self.setCursor(Qt.ArrowCursor)
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Delete or event.key() == Qt.Key_Backspace:
            for item in self.scene().selectedItems():
                if isinstance(item, NodeItem):
                    self.scene().delete_node(item)
                elif isinstance(item, EdgeItem):
                    self.scene().delete_edge(item)
        elif event.key() == Qt.Key_Escape:
            self.scene().abort_connect()
        super().keyPressEvent(event)

    def contextMenuEvent(self, event):
        scene_pos = self.mapToScene(event.pos())
        items = self.scene().items(scene_pos)
        node = next((i for i in items if isinstance(i, NodeItem)), None)
        edge = next((i for i in items if isinstance(i, EdgeItem)), None)

        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{ background:{get_col('BG_PANEL')}; color:{get_col('TEXT_PRIMARY')}; border:1px solid {get_col('BORDER')};
                     border-radius:6px; padding:4px; }}
            QMenu::item {{ padding:6px 18px; border-radius:4px; }}
            QMenu::item:selected {{ background:{get_col('ACCENT')}; color: white; }}
        """)

        if node:
            act_conn = menu.addAction("🔗 Connect from here")
            act_edit = menu.addAction("✏️ Rename")
            act_col  = menu.addAction("🎨 Change colour")
            menu.addSeparator()
            act_del  = menu.addAction("🗑️ Delete node")
            chosen = menu.exec_(event.globalPos())
            if chosen == act_conn:
                self.scene().start_connect(node)
                self.setDragMode(QGraphicsView.NoDrag)
                QTimer.singleShot(0, lambda: self.setDragMode(QGraphicsView.RubberBandDrag))
            elif chosen == act_edit:
                text, ok = QInputDialog.getText(self, "Rename", "New label:", text=node.label)
                if ok and text:
                    node.label = text
                    node._update_text_style()
                    self.scene().update()
                    self.scene().graph_changed.emit()
            elif chosen == act_col:
                col = QColorDialog.getColor(QColor(node.color), self, "Pick node colour")
                if col.isValid():
                    node.color = col.name()
                    node._update_text_style()
                    self.scene().update()
                    self.scene().graph_changed.emit()
            elif chosen == act_del:
                self.scene().delete_node(node)
        elif edge:
            act_label = menu.addAction("🏷️ Edit label")
            act_del   = menu.addAction("🗑️ Delete edge")
            chosen = menu.exec_(event.globalPos())
            if chosen == act_label:
                text, ok = QInputDialog.getText(self, "Edge Label", "Label:", text=edge.label)
                if ok:
                    edge.set_label(text)
                    self.scene().graph_changed.emit()
            elif chosen == act_del:
                self.scene().delete_edge(edge)
        else:
            act_add = menu.addAction("➕ Add node here")
            chosen = menu.exec_(event.globalPos())
            if chosen == act_add:
                label, ok = QInputDialog.getText(self, "New Node", "Label:")
                if ok and label:
                    self.scene().add_node(label=label, x=scene_pos.x(), y=scene_pos.y())

# ── Properties Sidebar ───────────────────────────────────────────────────────
class PropRow(QFrame):
    deleted = pyqtSignal(str)
    changed = pyqtSignal(str, str)

    def __init__(self, key, value):
        super().__init__()
        self.key_name = key
        self.val = value
        self.apply_style()
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 4, 4)
        layout.setSpacing(6)

        self.key_lbl = QLabel(key)
        self.key_lbl.setFixedWidth(90)
        self.key_lbl.setWordWrap(True)

        self.val_edit = QLineEdit(str(value))
        self.val_edit.editingFinished.connect(
            lambda: self.changed.emit(self.key_name, self.val_edit.text()))

        self.del_btn = QPushButton("✕")
        self.del_btn.setFixedSize(22, 22)
        self.del_btn.clicked.connect(lambda: self.deleted.emit(self.key_name))

        layout.addWidget(self.key_lbl)
        layout.addWidget(self.val_edit)
        layout.addWidget(self.del_btn)
        self.update_children_style()

    def apply_style(self):
        self.setStyleSheet(f"""
            QFrame {{ background:{get_col('BG_CARD')}; border-radius:6px; border:1px solid {get_col('BORDER')}; }}
        """)

    def update_children_style(self):
        self.key_lbl.setStyleSheet(f"color:{get_col('ACCENT')}; font-weight:bold; font-size:11px; border:none; background:transparent;")
        self.val_edit.setStyleSheet(f"""
            QLineEdit {{
                background:{get_col('BG_PANEL')}; color:{get_col('TEXT_PRIMARY')}; border:1px solid {get_col('BORDER')};
                border-radius:4px; padding:3px 6px; font-size:11px;
            }}
            QLineEdit:focus {{ border-color:{get_col('ACCENT')}; }}
        """)
        self.del_btn.setStyleSheet(f"""
            QPushButton {{ background:transparent; color:{get_col('ACCENT2')}; border:none; font-weight:bold; }}
            QPushButton:hover {{ background:{get_col('ACCENT2')}; color:white; border-radius:4px; }}
        """)

class Sidebar(QWidget):
    def __init__(self, scene):
        super().__init__()
        self.scene = scene
        self._node = None
        self._edge = None
        self.setFixedWidth(280)

        self.root = QVBoxLayout(self)
        self.root.setContentsMargins(0, 0, 0, 0)
        self.root.setSpacing(0)

        self.header = QLabel("Properties")
        self.root.addWidget(self.header)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        
        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(12, 12, 12, 12)
        self.content_layout.setSpacing(8)
        self.content_layout.addStretch()
        
        self.scroll.setWidget(self.content)
        self.root.addWidget(self.scroll)

        self.apply_style()
        self.show_empty()

    def apply_style(self):
        self.setStyleSheet(f"background:{get_col('BG_PANEL')};")
        self.header.setStyleSheet(f"""
            QLabel {{
                background:{get_col('BG_DARK')}; color:{get_col('TEXT_PRIMARY')};
                font-size:14px; font-weight:bold;
                padding:14px 16px; border-bottom:1px solid {get_col('BORDER')};
            }}
        """)
        self.scroll.setStyleSheet(f"""
            QScrollArea {{ background:transparent; border:none; }}
            QScrollBar:vertical {{ background:{get_col('BG_DARK')}; width:6px; border-radius:3px; }}
            QScrollBar::handle:vertical {{ background:{get_col('BORDER')}; border-radius:3px; min-height:20px; }}
        """)
        self.content.setStyleSheet(f"background:{get_col('BG_PANEL')};")

    def _clear(self):
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def show_empty(self):
        self._node = None
        self._edge = None
        self._clear()
        lbl = QLabel("Select a node or edge\nto view its properties.")
        lbl.setStyleSheet(f"color:{get_col('TEXT_MUTED')}; font-size:12px; padding:20px 0; background:transparent;")
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setWordWrap(True)
        self.content_layout.addWidget(lbl)
        self.content_layout.addStretch()
        self.header.setText("Properties")

    def show_node(self, node: NodeItem):
        self._node = node
        self._edge = None
        self._clear()
        self.header.setText(f"Node · {node.node_id}")
        self._build_node_ui(node)
        self.content_layout.addStretch()

    def show_edge(self, edge: EdgeItem):
        self._edge = edge
        self._node = None
        self._clear()
        self.header.setText(f"Edge · {edge.edge_id}")
        self._build_edge_ui(edge)
        self.content_layout.addStretch()

    def _section(self, title):
        lbl = QLabel(title.upper())
        lbl.setStyleSheet(f"""
            color:{get_col('TEXT_MUTED')}; font-size:9px; font-weight:bold;
            letter-spacing:1.5px; padding:6px 0 2px 0; background:transparent;
        """)
        self.content_layout.addWidget(lbl)

    def _build_node_ui(self, node):
        self._section("Identity")

        label_edit = QLineEdit(node.label)
        label_edit.setPlaceholderText("Node label")
        label_edit.setStyleSheet(self._input_style())
        def update_label():
            node.label = label_edit.text()
            node._update_text_style()
            self.scene.update()
            self.scene.graph_changed.emit()
        label_edit.editingFinished.connect(update_label)
        self.content_layout.addWidget(label_edit)

        type_combo = QComboBox()
        type_combo.addItems(list(NODE_COLORS.keys()))
        type_combo.setCurrentText(node.node_type)
        type_combo.setStyleSheet(self._combo_style())
        def update_type(t):
            node.node_type = t
            node.color = NODE_COLORS.get(t, NODE_COLORS["default"])
            node._update_text_style()
            self.scene.update()
            self.scene.graph_changed.emit()
        type_combo.currentTextChanged.connect(update_type)
        self.content_layout.addWidget(type_combo)

        self._section("Custom Properties")
        self._render_prop_rows(node)

        add_row = QFrame()
        add_row.setStyleSheet("background:transparent;")
        add_rl = QHBoxLayout(add_row)
        add_rl.setContentsMargins(0, 0, 0, 0)
        add_rl.setSpacing(4)
        key_in  = QLineEdit()
        key_in.setPlaceholderText("key")
        key_in.setStyleSheet(self._input_style())
        val_in  = QLineEdit()
        val_in.setPlaceholderText("value")
        val_in.setStyleSheet(self._input_style())
        add_btn = QPushButton("+")
        add_btn.setFixedSize(28, 28)
        add_btn.setStyleSheet(self._btn_style(get_col("ACCENT3")))
        
        def add_prop():
            k = key_in.text().strip()
            v = val_in.text().strip()
            if k:
                node.properties[k] = v
                self.scene.graph_changed.emit()
                self.show_node(node)
        
        add_btn.clicked.connect(add_prop)
        key_in.returnPressed.connect(add_prop)
        val_in.returnPressed.connect(add_prop)
        add_rl.addWidget(key_in)
        add_rl.addWidget(val_in)
        add_rl.addWidget(add_btn)
        self.content_layout.addWidget(add_row)

        self._section(f"Edges ({len(node.edges)})")
        for e in node.edges:
            other = e.target_node if e.source_node is node else e.source_node
            direction = "→" if e.source_node is node else "←"
            lbl_text = f"{direction} {other.label}"
            if e.label: lbl_text += f" [{e.label}]"
            el = QLabel(lbl_text)
            el.setStyleSheet(f"""
                color:{get_col('TEXT_PRIMARY')}; font-size:11px; padding:4px 8px;
                background:{get_col('BG_CARD')}; border-radius:4px; border:1px solid {get_col('BORDER')};
            """)
            self.content_layout.addWidget(el)

        del_btn = QPushButton("🗑 Delete Node")
        del_btn.setStyleSheet(self._btn_style(get_col("ACCENT2")))
        del_btn.clicked.connect(lambda: (self.scene.delete_node(node), self.show_empty()))
        self.content_layout.addWidget(del_btn)

    def _render_prop_rows(self, node):
        for k, v in node.properties.items():
            row = PropRow(k, v)
            def on_delete(key, n=node):
                del n.properties[key]
                self.scene.graph_changed.emit()
                self.show_node(n)
            def on_change(key, val, n=node):
                n.properties[key] = val
                self.scene.graph_changed.emit()
            row.deleted.connect(on_delete)
            row.changed.connect(on_change)
            self.content_layout.addWidget(row)

    def _build_edge_ui(self, edge):
        self._section("Edge Label")
        label_edit = QLineEdit(edge.label)
        label_edit.setPlaceholderText("Edge label (optional)")
        label_edit.setStyleSheet(self._input_style())
        def update_label():
            edge.set_label(label_edit.text())
            self.scene.graph_changed.emit()
        label_edit.editingFinished.connect(update_label)
        self.content_layout.addWidget(label_edit)

        self._section("Connection")
        info = QLabel(f"From: {edge.source_node.label}\nTo:   {edge.target_node.label}")
        info.setStyleSheet(f"color:{get_col('TEXT_PRIMARY')}; font-size:12px; padding:6px; background:transparent;")
        self.content_layout.addWidget(info)

        del_btn = QPushButton("🗑 Delete Edge")
        del_btn.setStyleSheet(self._btn_style(get_col("ACCENT2")))
        del_btn.clicked.connect(lambda: (self.scene.delete_edge(edge), self.show_empty()))
        self.content_layout.addWidget(del_btn)

    def _input_style(self):
        return f"""
            QLineEdit {{
                background:{get_col('BG_CARD')}; color:{get_col('TEXT_PRIMARY')}; border:1px solid {get_col('BORDER')};
                border-radius:6px; padding:6px 10px; font-size:12px;
            }}
            QLineEdit:focus {{ border-color:{get_col('ACCENT')}; }}
        """

    def _combo_style(self):
        return f"""
            QComboBox {{
                background:{get_col('BG_CARD')}; color:{get_col('TEXT_PRIMARY')}; border:1px solid {get_col('BORDER')};
                border-radius:6px; padding:5px 10px; font-size:12px;
            }}
            QComboBox::drop-down {{ border:none; }}
            QComboBox QAbstractItemView {{
                background:{get_col('BG_PANEL')}; color:{get_col('TEXT_PRIMARY')}; border:1px solid {get_col('BORDER')};
                selection-background-color:{get_col('ACCENT')};
            }}
        """

    def _btn_style(self, color):
        return f"""
            QPushButton {{
                background:{color}; color:white; border:none;
                border-radius:6px; padding:7px 12px; font-size:12px; font-weight:bold;
            }}
            QPushButton:hover {{ background:{QColor(color).lighter(120).name()}; }}
        """

# ── Search Bar ───────────────────────────────────────────────────────────────
class SearchBar(QWidget):
    def __init__(self, scene, view):
        super().__init__()
        self.scene = scene
        self.view  = view
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(6)

        self.icon = QLabel("🔍")
        layout.addWidget(self.icon)

        self.edit = QLineEdit()
        self.edit.setPlaceholderText("Search nodes… (Ctrl+F)")
        self.edit.textChanged.connect(self._search)
        layout.addWidget(self.edit)

        self.result_lbl = QLabel("")
        layout.addWidget(self.result_lbl)
        
        self.apply_style()

    def apply_style(self):
        self.setStyleSheet(f"background:{get_col('BG_PANEL')}; border-bottom:1px solid {get_col('BORDER')};")
        self.icon.setStyleSheet("font-size:14px; background:transparent; border:none;")
        self.edit.setStyleSheet(f"""
            QLineEdit {{
                background:{get_col('BG_CARD')}; color:{get_col('TEXT_PRIMARY')}; border:1px solid {get_col('BORDER')};
                border-radius:6px; padding:6px 10px; font-size:12px;
            }}
            QLineEdit:focus {{ border-color:{get_col('ACCENT')}; }}
        """)
        self.result_lbl.setStyleSheet(f"color:{get_col('TEXT_MUTED')}; font-size:11px; background:transparent; border:none;")

    def _search(self, text):
        text = text.strip().lower()
        matches = []
        for node in self.scene.nodes.values():
            if text in node.label.lower() or any(
                text in str(v).lower() for v in node.properties.values()):
                matches.append(node)

        for node in self.scene.nodes.values():
            node.setSelected(False)
        for node in matches:
            node.setSelected(True)

        if matches and text:
            self.view.centerOn(matches[0])
            self.result_lbl.setText(f"{len(matches)} found")
        elif text:
            self.result_lbl.setText("No matches")
        else:
            self.result_lbl.setText("")

# ── Main Window ──────────────────────────────────────────────────────────────
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GraphCanvas - GA Prep")
        self.resize(1400, 860)
        self._file_path = None
        self._dirty = False

        self._build_scene()
        self._build_ui()
        self._build_toolbar()
        self._build_statusbar()
        self._connect_signals()
        
        # Apply themes to everything at boot
        self._apply_global_style()
        self._load_sample()

    def _apply_global_style(self):
        self.setStyleSheet(f"""
            QMainWindow {{ background:{get_col('BG_DARK')}; }}
            QToolBar {{
                background:{get_col('BG_PANEL')}; border-bottom:1px solid {get_col('BORDER')};
                spacing:4px; padding:4px 8px;
            }}
            QToolBar QToolButton {{
                background:transparent; color:{get_col('TEXT_PRIMARY')}; border:none;
                border-radius:6px; padding:5px 10px; font-size:12px;
            }}
            QToolBar QToolButton:hover {{ background:{get_col('BG_CARD')}; }}
            QToolBar QToolButton:pressed {{ background:{get_col('ACCENT')}; color:white; }}
            QStatusBar {{ background:{get_col('BG_PANEL')}; color:{get_col('TEXT_MUTED')}; font-size:11px; }}
            QSplitter::handle {{ background:{get_col('BORDER')}; width:1px; }}
        """)

    def _build_scene(self):
        self.scene = GraphScene()
        self.view  = CanvasView(self.scene)

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.search_bar = SearchBar(self.scene, self.view)
        main_layout.addWidget(self.search_bar)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self.view)

        self.sidebar = Sidebar(self.scene)
        splitter.addWidget(self.sidebar)
        splitter.setSizes([1100, 280])
        splitter.setHandleWidth(1)
        main_layout.addWidget(splitter)

    def _build_toolbar(self):
        tb = self.addToolBar("Main")
        tb.setMovable(False)
        tb.setIconSize(QSize(18, 18))

        def btn(text, tip, fn, shortcut=None):
            act = QAction(text, self)
            act.setToolTip(tip)
            if shortcut: act.setShortcut(shortcut)
            act.triggered.connect(fn)
            tb.addAction(act)
            return act

        btn("➕ Node", "Add node (N)", self._add_node_prompt, "N")
        btn("🔗 Connect", "Start connecting (C)", self._start_connect, "C")
        tb.addSeparator()
        self.btn_layout = btn("▶️ Simulate", "Toggle force layout (Space)", self._toggle_layout, "Space")
        tb.addSeparator()
        btn("🔍 Search", "Focus search (Ctrl+F)", lambda: self.search_bar.edit.setFocus(), "Ctrl+F")
        tb.addSeparator()
        btn("💾 Save", "Save (Ctrl+S)", self._save, "Ctrl+S")
        btn("📂 Load", "Load (Ctrl+O)", self._load, "Ctrl+O")
        btn("🆕 New", "New graph (Ctrl+N)", self._new_graph, "Ctrl+N")
        tb.addSeparator()
        btn("⛶ Fit", "Fit view (F)", self._fit_view, "F")
        btn("🔲 Grid", "Toggle grid", self._toggle_grid)
        tb.addSeparator()
        btn("🌗 Theme", "Toggle Theme (T)", self._toggle_theme, "T")
        tb.addSeparator()
        btn("🗑 Clear", "Clear all", self._clear_all)

    def _toggle_layout(self):
        is_active = self.scene.toggle_layout()
        if is_active:
            self.btn_layout.setText("⏸ Pause")
            self.status.showMessage("Simulation running...", 2000)
        else:
            self.btn_layout.setText("▶️ Simulate")
            self.status.showMessage("Simulation paused.", 2000)

    def _build_statusbar(self):
        self.status = self.statusBar()
        self._update_status()

    def _connect_signals(self):
        self.scene.node_selected.connect(self._on_node_selected)
        self.scene.edge_selected.connect(self._on_edge_selected)
        self.scene.graph_changed.connect(self._on_graph_changed)

    def _on_node_selected(self, node):
        if node: self.sidebar.show_node(node)
        else:
            if self.sidebar._edge is None: self.sidebar.show_empty()

    def _on_edge_selected(self, edge):
        if edge: self.sidebar.show_edge(edge)
        else:
            if self.sidebar._node is None: self.sidebar.show_empty()

    def _on_graph_changed(self):
        self._dirty = True
        self._update_status()

    def _update_status(self):
        n = len(self.scene.nodes)
        e = len(self.scene.edges)
        dirty = " ●" if self._dirty else ""
        fp = self._file_path or "unsaved"
        self.status.showMessage(
            f"  {fp}{dirty}   │   {n} node{'s' if n!=1 else ''}   {e} edge{'s' if e!=1 else ''}"
            f"   │   Scroll: zoom   Middle-drag: pan   Del: delete")

    def _toggle_theme(self):
        global CURRENT_THEME
        CURRENT_THEME = "dark" if CURRENT_THEME == "light" else "light"
        
        self._apply_global_style()
        self.search_bar.apply_style()
        self.sidebar.apply_style()
        
        self.scene.setBackgroundBrush(QBrush(qcolor("BG_DARK")))
        self.view.setBackgroundBrush(QBrush(qcolor("BG_DARK")))
        
        for item in self.scene.items():
            if hasattr(item, '_update_text_style'):
                item._update_text_style()
            item.update()
            
        self.view.viewport().update()
        
        if self.sidebar._node:
            self.sidebar.show_node(self.sidebar._node)
        elif self.sidebar._edge:
            self.sidebar.show_edge(self.sidebar._edge)
        else:
            self.sidebar.show_empty()

    def _add_node_prompt(self):
        label, ok = QInputDialog.getText(self, "Add Node", "Label:")
        if ok and label:
            center = self.view.mapToScene(self.view.viewport().rect().center())
            self.scene.add_node(label=label, x=center.x(), y=center.y())

    def _start_connect(self):
        selected = [i for i in self.scene.selectedItems() if isinstance(i, NodeItem)]
        if selected: self.scene.start_connect(selected[0])
        else: self.status.showMessage("Select a source node first, then press C", 3000)

    def _fit_view(self):
        if self.scene.nodes:
            rect = self.scene.itemsBoundingRect().adjusted(-60, -60, 60, 60)
            self.view.fitInView(rect, Qt.KeepAspectRatio)
        else: self.view.resetTransform()

    def _toggle_grid(self):
        self.view._draw_grid = not self.view._draw_grid
        self.view.viewport().update()

    def _save(self):
        if not self._file_path:
            path, _ = QFileDialog.getSaveFileName(self, "Save Graph", "graph.json", "JSON Files (*.json)")
            if not path: return
            self._file_path = path
        with open(self._file_path, "w") as f:
            json.dump(self.scene.to_dict(), f, indent=2)
        self._dirty = False
        self._update_status()

    def _load(self):
        if self._dirty:
            r = QMessageBox.question(self, "Unsaved changes", "Discard current graph and load?", QMessageBox.Yes | QMessageBox.Cancel)
            if r != QMessageBox.Yes: return
        path, _ = QFileDialog.getOpenFileName(self, "Open Graph", "", "JSON Files (*.json)")
        if path:
            with open(path) as f: data = json.load(f)
            self.scene.load_dict(data)
            self._file_path = path
            self._dirty = False
            self._fit_view()
            self._update_status()
            self.sidebar.show_empty()

    def _new_graph(self):
        if self._dirty:
            r = QMessageBox.question(self, "Unsaved changes", "Discard current graph?", QMessageBox.Yes | QMessageBox.Cancel)
            if r != QMessageBox.Yes: return
        self.scene.clear()
        self.scene.nodes.clear()
        self.scene.edges.clear()
        self._file_path = None
        self._dirty = False
        self.sidebar.show_empty()
        self._update_status()

    def _clear_all(self):
        r = QMessageBox.question(self, "Clear graph", "Remove all nodes and edges?", QMessageBox.Yes | QMessageBox.Cancel)
        if r == QMessageBox.Yes:
            self.scene.clear()
            self.scene.nodes.clear()
            self.scene.edges.clear()
            self._dirty = True
            self.sidebar.show_empty()
            self._update_status()

    def _load_sample(self):
        data = {
            "nodes": [
                {"id":"n1","label":"BCCI","x":80,"y":-80,
                 "node_type":"object","color":None,
                 "properties":{"Type":"Organization","Founded":"1928"}},
                {"id":"n2","label":"Ms. Subramaniam","x":-80,"y":20,
                 "node_type":"default","color":None,
                 "properties":{"Role":"Member"}},
            ],
            "edges": [
                {"id":"e1","source":"n2","target":"n1","label":"RELATED"},
            ]
        }
        self.scene.load_dict(data)
        self._dirty = False
        QTimer.singleShot(100, self._fit_view)
        self._update_status()

    def closeEvent(self, event):
        if self._dirty:
            r = QMessageBox.question(self, "Unsaved changes", "Save before closing?", QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
            if r == QMessageBox.Save: self._save()
            elif r == QMessageBox.Cancel:
                event.ignore()
                return
        event.accept()

# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("GraphCanvas GA")
    font = QFont("Segoe UI", 10)
    app.setFont(font)
    
    # Let widget styling handle colors instead of full palette overrides 
    # to avoid conflicting with the dynamic theme engine
    
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())