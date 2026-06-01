"""
canvas.py — GraphicsScene, NodeItem, EdgeItem, CanvasView
"""
import math, copy
from PyQt5.QtWidgets import (
    QGraphicsScene, QGraphicsView, QGraphicsItem, QGraphicsTextItem,
    QGraphicsPathItem, QInputDialog, QMenu, QColorDialog, QFrame
)
from PyQt5.QtCore import Qt, QPointF, QRectF, QLineF, pyqtSignal, QTimer
from PyQt5.QtGui import QPainter, QPen, QBrush, QColor, QFont, QPainterPath

import config
from config import gc, qc, new_id


# ─────────────────────────────────────────────────────────────────────────────
#  EdgeItem
# ─────────────────────────────────────────────────────────────────────────────
class EdgeItem(QGraphicsPathItem):
    def __init__(self, src, tgt, label="", edge_id=None,
                 direction="→", edge_type="relationship", color=None):
        super().__init__()
        self.edge_id     = edge_id or new_id()
        self.source_node = src
        self.target_node = tgt
        self.label       = label
        self.direction   = direction
        self.edge_type   = edge_type
        self.color       = color or config.EDGE_TYPE_COLORS.get(edge_type, "#adb5bd")

        self.setZValue(0)
        self.setFlag(QGraphicsItem.ItemIsSelectable)

        self._label_item = QGraphicsTextItem("", self)
        self._label_item.setFlag(QGraphicsItem.ItemIgnoresTransformations)
        self._refresh_label_text()

    def _refresh_label_text(self):
        parts = []
        if self.edge_type and self.edge_type != "relationship":
            parts.append(f"[{self.edge_type}]")
        if self.label:
            parts.append(self.label)
        self._label_item.setPlainText("  ".join(parts) if parts else "")
        self._label_item.setFont(QFont("Segoe UI", config.SETTINGS["ui_font_size"] - 1))
        self._label_item.setDefaultTextColor(QColor(self.color))
        self.update_path()

    def set_label(self, text):
        self.label = text
        self._refresh_label_text()

    def set_direction(self, d):
        self.direction = d
        self.update_path()

    def set_edge_type(self, t):
        self.edge_type = t
        # sync colour to type default only if user hasn't overridden
        self.color = config.EDGE_TYPE_COLORS.get(t, self.color)
        self._refresh_label_text()

    def update_path(self):
        sp = self.source_node.scenePos()
        tp = self.target_node.scenePos()
        r_s = self.source_node.radius
        r_t = self.target_node.radius
        dx = tp.x() - sp.x()
        dy = tp.y() - sp.y()
        dist = math.hypot(dx, dy) or 1

        src_pt = QPointF(sp.x() + dx / dist * r_s, sp.y() + dy / dist * r_s)
        tgt_pt = QPointF(tp.x() - dx / dist * r_t, tp.y() - dy / dist * r_t)

        path = QPainterPath(src_pt)
        path.lineTo(tgt_pt)

        angle = math.atan2(dy, dx)
        arrow_len = 9

        def arrow_at(pt, ang):
            a1, a2 = ang + math.pi * 0.82, ang - math.pi * 0.82
            arr = QPainterPath()
            arr.moveTo(pt)
            arr.lineTo(pt + QPointF(math.cos(a1) * arrow_len, math.sin(a1) * arrow_len))
            arr.moveTo(pt)
            arr.lineTo(pt + QPointF(math.cos(a2) * arrow_len, math.sin(a2) * arrow_len))
            return arr

        if self.direction == "→":
            path.addPath(arrow_at(tgt_pt, angle))
        elif self.direction == "←":
            path.addPath(arrow_at(src_pt, angle + math.pi))
        elif self.direction == "↔":
            path.addPath(arrow_at(tgt_pt, angle))
            path.addPath(arrow_at(src_pt, angle + math.pi))
        # "—" → no arrow

        self.setPath(path)

        if self._label_item.toPlainText():
            mid = QPointF((src_pt.x() + tgt_pt.x()) / 2,
                          (src_pt.y() + tgt_pt.y()) / 2)
            br = self._label_item.boundingRect()
            self._label_item.setPos(mid - QPointF(br.width() / 2, br.height()))

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        style = (Qt.DashLine if self.edge_type == "dependency"
                 else Qt.DotLine if self.edge_type == "note"
                 else Qt.SolidLine)
        pen = QPen(
            qc("ACCENT") if self.isSelected() else QColor(self.color),
            2.0 if self.isSelected() else 1.2,
            style,
        )
        self.setPen(pen)
        super().paint(painter, option, widget)

    def to_dict(self):
        return {
            "id":        self.edge_id,
            "source":    self.source_node.node_id,
            "target":    self.target_node.node_id,
            "label":     self.label,
            "direction": self.direction,
            "edge_type": self.edge_type,
            "color":     self.color,
        }


# ─────────────────────────────────────────────────────────────────────────────
#  NodeItem
# ─────────────────────────────────────────────────────────────────────────────
class NodeItem(QGraphicsItem):
    def __init__(self, node_id=None, label="Node", x=0, y=0,
                 node_type="default", color=None, properties=None,
                 notes="", sticky_text="", sticky_visible=False,
                 sticky_dock="right"):
        super().__init__()
        self.node_id    = node_id or new_id()
        self.label      = label
        self.node_type  = node_type
        self.color      = color or config.NODE_TYPE_COLORS.get(
            node_type, config.NODE_TYPE_COLORS.get("default", "#888888"))
        self.properties = properties if properties is not None else {}
        self.notes      = notes
        self.sticky_text = sticky_text
        self.sticky_visible = sticky_visible
        self.sticky_dock = sticky_dock
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
        self._sticky_item = QGraphicsTextItem("", self)
        self._sticky_item.setFlag(QGraphicsItem.ItemIgnoresTransformations)
        self._sticky_item.setAcceptedMouseButtons(Qt.NoButton)
        self._sticky_item.setTextInteractionFlags(Qt.NoTextInteraction)
        self._sticky_item.setZValue(-1)
        self._refresh_text()

    def _inject_schema(self):
        """Add any schema-defined keys that are missing (empty string default)."""
        expected = (config.PROPERTY_SCHEMA.get("__universal__", [])
                    + config.PROPERTY_SCHEMA.get(self.node_type, []))
        for k in expected:
            if k not in self.properties:
                self.properties[k] = ""

    def _refresh_text(self):
        self.prepareGeometryChange()
        self._text.setPlainText(self.label)
        self._text.setFont(QFont("Segoe UI", config.SETTINGS["ui_font_size"], QFont.Medium))
        self._text.setDefaultTextColor(QColor(self.color))
        br = self._text.boundingRect()
        self._text.setPos(self.radius + 5, -br.height() / 2)
        self._refresh_sticky_text()

    def _refresh_sticky_text(self):
        text = self.sticky_text.strip()
        self._sticky_item.setVisible(bool(text and self.sticky_visible))
        self._sticky_item.setPlainText(text)
        self._sticky_item.setTextWidth(180)
        self._sticky_item.setFont(QFont("Segoe UI", config.SETTINGS["ui_font_size"] - 1))
        self._sticky_item.setDefaultTextColor(QColor(self.color))

        br = self._sticky_item.boundingRect()
        gap = 10
        dock = self.sticky_dock
        if dock == "left":
            pos = QPointF(-self.radius - gap - br.width(), -br.height() / 2)
        elif dock == "above":
            pos = QPointF(-br.width() / 2, -self.radius - gap - br.height())
        elif dock == "below":
            pos = QPointF(-br.width() / 2, self.radius + gap)
        else:
            pos = QPointF(self.radius + gap, -br.height() / 2)
        self._sticky_item.setPos(pos)

    def set_notes(self, text):
        self.notes = text

    def set_sticky_text(self, text):
        self.sticky_text = text
        self._refresh_sticky_text()

    def set_sticky_visible(self, visible):
        self.sticky_visible = visible
        self._refresh_sticky_text()

    def set_sticky_dock(self, dock):
        self.sticky_dock = dock
        self._refresh_sticky_text()

    def boundingRect(self):
        p = 5
        return QRectF(-self.radius - p, -self.radius - p,
                      self.radius * 2 + p * 2, self.radius * 2 + p * 2)

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        r   = self.radius
        col = qc("ACCENT") if self.isSelected() else QColor(self.color)
        painter.setBrush(QBrush(col))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QPointF(0, 0), r, r)
        if self.isSelected():
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(col.lighter(150), 2))
            painter.drawEllipse(QPointF(0, 0), r + 4, r + 4)

        filled = sum(1 for v in self.properties.values() if str(v).strip())
        if filled:
            br = QRectF(r - 6, -r - 2, 12, 10)
            painter.setBrush(QBrush(QColor("#ff6584")))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(br, 3, 3)
            painter.setPen(QPen(Qt.white))
            painter.setFont(QFont("Segoe UI", 6, QFont.Bold))
            painter.drawText(br, Qt.AlignCenter, str(filled))

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionHasChanged:
            for e in self.edges:
                e.update_path()
        return super().itemChange(change, value)

    def add_edge(self, e):
        if e not in self.edges:
            self.edges.append(e)
            self._update_size()

    def remove_edge(self, e):
        if e in self.edges:
            self.edges.remove(e)
            self._update_size()

    def _update_size(self):
        self.prepareGeometryChange()
        self.radius = 14 + len(self.edges) * 2
        self._refresh_text()
        for e in self.edges:
            e.update_path()
        self.update()

    def to_dict(self):
        return {
            "id":         self.node_id,
            "label":      self.label,
            "x":          self.x(),
            "y":          self.y(),
            "node_type":  self.node_type,
            "color":      self.color,
            "properties": dict(self.properties),
            "notes":      self.notes,
            "sticky_text": self.sticky_text,
            "sticky_visible": self.sticky_visible,
            "sticky_dock": self.sticky_dock,
        }


# ─────────────────────────────────────────────────────────────────────────────
#  GraphScene
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
        self._connecting   = False
        self._conn_source  = None
        self._conn_line    = None
        self.layout_active = False
        self.layout_timer  = QTimer()
        self.layout_timer.timeout.connect(self._layout_step)

    # ── Force layout ──────────────────────────────────────────────────────────
    def toggle_layout(self):
        self.layout_active = not self.layout_active
        if self.layout_active:
            self.layout_timer.start(20)
        else:
            self.layout_timer.stop()
        return self.layout_active

    def _layout_step(self):
        forces = {nid: QPointF(0, 0) for nid in self.nodes}
        nl = list(self.nodes.values())
        C_REP, C_ATT, IDEAL = 3000.0, 0.04, 150.0
        for i in range(len(nl)):
            for j in range(i + 1, len(nl)):
                a, b = nl[i], nl[j]
                dx = a.x() - b.x()
                dy = a.y() - b.y()
                d  = math.hypot(dx, dy) or 0.1
                if d > 1000:
                    continue
                f  = C_REP / (d * d)
                fx, fy = f * dx / d, f * dy / d
                forces[a.node_id] += QPointF(fx, fy)
                forces[b.node_id] -= QPointF(fx, fy)
        for e in self.edges.values():
            a, b = e.source_node, e.target_node
            dx = b.x() - a.x()
            dy = b.y() - a.y()
            d  = math.hypot(dx, dy) or 0.1
            f  = C_ATT * (d - IDEAL)
            fx, fy = f * dx / d, f * dy / d
            forces[a.node_id] += QPointF(fx, fy)
            forces[b.node_id] -= QPointF(fx, fy)
        cap = 12.0
        for node in nl:
            if node.isSelected():
                continue
            f  = forces[node.node_id]
            mx = max(-cap, min(cap, f.x()))
            my = max(-cap, min(cap, f.y()))
            if abs(mx) > 0.05 or abs(my) > 0.05:
                node.setPos(node.pos() + QPointF(mx, my))

    # ── CRUD ──────────────────────────────────────────────────────────────────
    def add_node(self, label="Node", x=0, y=0, node_type=None,
                 color=None, properties=None, node_id=None,
                 notes="", sticky_text="", sticky_visible=False,
                 sticky_dock="right"):
        nt = node_type or config.SETTINGS["default_node_type"]
        if nt not in config.NODE_TYPE_COLORS:
            nt = next(iter(config.NODE_TYPE_COLORS), "default")
        n = NodeItem(node_id=node_id, label=label, x=x, y=y,
                     node_type=nt, color=color, properties=properties,
                     notes=notes, sticky_text=sticky_text,
                     sticky_visible=sticky_visible, sticky_dock=sticky_dock)
        self.nodes[n.node_id] = n
        self.addItem(n)
        self.graph_changed.emit()
        return n

    def delete_node(self, node):
        for e in list(node.edges):
            self.delete_edge(e)
        self.nodes.pop(node.node_id, None)
        self.removeItem(node)
        self.graph_changed.emit()

    def add_edge(self, src, tgt, label="", edge_id=None,
                 direction=None, edge_type=None, color=None):
        direction = direction or config.SETTINGS["default_direction"]
        edge_type = edge_type or config.SETTINGS["default_edge_type"]
        if edge_type not in config.EDGE_TYPE_COLORS:
            edge_type = next(iter(config.EDGE_TYPE_COLORS), "relationship")
        # prevent exact duplicate
        for e in src.edges:
            if (e.source_node is src and e.target_node is tgt
                    and e.direction == direction):
                return None
        e = EdgeItem(src, tgt, label=label, edge_id=edge_id,
                     direction=direction, edge_type=edge_type, color=color)
        self.edges[e.edge_id] = e
        self.addItem(e)
        src.add_edge(e)
        tgt.add_edge(e)
        self.graph_changed.emit()
        return e

    def delete_edge(self, edge):
        edge.source_node.remove_edge(edge)
        edge.target_node.remove_edge(edge)
        self.edges.pop(edge.edge_id, None)
        self.removeItem(edge)
        self.graph_changed.emit()

    def start_connect(self, src):
        self._connecting  = True
        self._conn_source = src
        self._conn_line   = self.addLine(QLineF(), QPen(qc("ACCENT"), 1.5, Qt.DashLine))

    def abort_connect(self):
        self._connecting  = False
        self._conn_source = None
        if self._conn_line:
            self.removeItem(self._conn_line)
            self._conn_line = None

    # ── Serialise ─────────────────────────────────────────────────────────────
    def to_dict(self):
        return {
            "schema": config.schema_block(),          # full type/settings state
            "nodes":  [n.to_dict() for n in self.nodes.values()],
            "edges":  [e.to_dict() for e in self.edges.values()],
        }

    def load_dict(self, data):
        self.clear()
        self.nodes.clear()
        self.edges.clear()

        # Restore schema first so node/edge fallbacks use correct types
        if "schema" in data:
            config.restore_schema_block(data["schema"])
        elif "types" in data:
            # backwards-compat with older save format
            config.restore_schema_block(data["types"])

        # Ensure any node/edge types referenced in the file exist in the registry
        for nd in data.get("nodes", []):
            nt = nd.get("node_type", "default")
            if nt not in config.NODE_TYPE_COLORS:
                config.NODE_TYPE_COLORS[nt] = nd.get("color", "#888888")
        for ed in data.get("edges", []):
            et = ed.get("edge_type", "relationship")
            if et not in config.EDGE_TYPE_COLORS:
                config.EDGE_TYPE_COLORS[et] = ed.get("color", "#adb5bd")

        for nd in data.get("nodes", []):
            self.add_node(
                label=nd["label"], x=nd["x"], y=nd["y"],
                node_type=nd.get("node_type"), color=nd.get("color"),
                properties=nd.get("properties", {}), node_id=nd["id"],
                notes=nd.get("notes", ""),
                sticky_text=nd.get("sticky_text", ""),
                sticky_visible=nd.get("sticky_visible", False),
                sticky_dock=nd.get("sticky_dock", "right"),
            )
        for ed in data.get("edges", []):
            s = self.nodes.get(ed["source"])
            t = self.nodes.get(ed["target"])
            if s and t:
                self.add_edge(
                    s, t,
                    label=ed.get("label", ""),
                    edge_id=ed["id"],
                    direction=ed.get("direction", "→"),
                    edge_type=ed.get("edge_type", "relationship"),
                    color=ed.get("color"),
                )

    # ── Mouse ─────────────────────────────────────────────────────────────────
    def mouseMoveEvent(self, event):
        if self._connecting and self._conn_line and self._conn_source:
            self._conn_line.setLine(
                QLineF(self._conn_source.scenePos(), event.scenePos()))
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._connecting:
            tgt = next(
                (i for i in self.items(event.scenePos())
                 if isinstance(i, NodeItem) and i is not self._conn_source),
                None,
            )
            if tgt:
                label, ok = QInputDialog.getText(
                    None, "Edge Label", "Label (optional):")
                self.add_edge(self._conn_source, tgt,
                              label=label if ok else "")
            self.abort_connect()
            return
        super().mouseReleaseEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            items   = self.items(event.scenePos())
            clicked = None
            for i in items:
                if isinstance(i, (NodeItem, EdgeItem)):
                    clicked = i
                    break
                elif isinstance(i, QGraphicsTextItem):
                    p = i.parentItem()
                    if isinstance(p, (NodeItem, EdgeItem)):
                        clicked = p
                        break
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


# ─────────────────────────────────────────────────────────────────────────────
#  CanvasView
# ─────────────────────────────────────────────────────────────────────────────
class CanvasView(QGraphicsView):
    zoom_changed = pyqtSignal(float)
    MIN_ZOOM, MAX_ZOOM = 0.05, 8.0

    def __init__(self, scene):
        super().__init__(scene)
        self.setRenderHint(QPainter.Antialiasing)
        self.setRenderHint(QPainter.SmoothPixmapTransform)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setFrameShape(QFrame.NoFrame)

        self._draw_grid   = True
        self._panning     = False
        self._pan_start   = None
        self._space_held  = False
        self._scale       = 1.0
        # clipboard stores {nodes: [...], edges: [...]} dicts
        self._clipboard   = {"nodes": [], "edges": []}

    # ── Grid ─────────────────────────────────────────────────────────────────
    def drawBackground(self, painter, rect):
        super().drawBackground(painter, rect)
        if not self._draw_grid:
            return
        painter.setRenderHint(QPainter.Antialiasing, False)
        grid    = 40
        is_dark = config.CURRENT_THEME == "dark"
        pm = QPen(QColor(128, 128, 128, 12 if is_dark else 10), 0)
        pM = QPen(QColor(128, 128, 128, 25 if is_dark else 20), 0)
        l = int(rect.left())  - (int(rect.left())  % grid)
        t = int(rect.top())   - (int(rect.top())   % grid)
        r = int(rect.right()) + grid
        b = int(rect.bottom())+ grid
        for x in range(l, r, grid):
            painter.setPen(pM if x % (grid * 5) == 0 else pm)
            painter.drawLine(x, int(rect.top()), x, int(rect.bottom()))
        for y in range(t, b, grid):
            painter.setPen(pM if y % (grid * 5) == 0 else pm)
            painter.drawLine(int(rect.left()), y, int(rect.right()), y)

    # ── Zoom ─────────────────────────────────────────────────────────────────
    def wheelEvent(self, event):
        factor    = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        new_scale = self._scale * factor
        if not (self.MIN_ZOOM <= new_scale <= self.MAX_ZOOM):
            return
        self._scale = new_scale
        self.scale(factor, factor)
        self.zoom_changed.emit(self._scale)

    def _set_zoom(self, z):
        z      = max(self.MIN_ZOOM, min(self.MAX_ZOOM, z))
        factor = z / self._scale
        self._scale = z
        self.scale(factor, factor)
        self.zoom_changed.emit(self._scale)

    # ── Keyboard ─────────────────────────────────────────────────────────────
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Space and not event.isAutoRepeat():
            self._space_held = True
            self.setDragMode(QGraphicsView.NoDrag)
            self.setCursor(Qt.OpenHandCursor)
        elif event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            for item in list(self.scene().selectedItems()):
                if isinstance(item, NodeItem):
                    self.scene().delete_node(item)
                elif isinstance(item, EdgeItem):
                    self.scene().delete_edge(item)
        elif event.key() == Qt.Key_Escape:
            self.scene().abort_connect()
            self._space_held = False
            self.setDragMode(QGraphicsView.RubberBandDrag)
            self.setCursor(Qt.ArrowCursor)
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key_Space and not event.isAutoRepeat():
            self._space_held = False
            self._panning    = False
            self._pan_start  = None
            self.setDragMode(QGraphicsView.RubberBandDrag)
            self.setCursor(Qt.ArrowCursor)
        super().keyReleaseEvent(event)

    # ── Pan ──────────────────────────────────────────────────────────────────
    def mousePressEvent(self, event):
        if (event.button() == Qt.MiddleButton
                or (event.button() == Qt.LeftButton and self._space_held)):
            self._panning   = True
            self._pan_start = event.pos()
            self.setCursor(Qt.ClosedHandCursor)
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._panning and self._pan_start is not None:
            delta           = event.pos() - self._pan_start
            self._pan_start = event.pos()
            self.setTransformationAnchor(QGraphicsView.NoAnchor)
            self.translate(delta.x(), delta.y())
            self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._panning and event.button() in (Qt.MiddleButton, Qt.LeftButton):
            self._panning   = False
            self._pan_start = None
            self.setCursor(Qt.OpenHandCursor if self._space_held else Qt.ArrowCursor)
            if not self._space_held:
                self.setDragMode(QGraphicsView.RubberBandDrag)
            return
        super().mouseReleaseEvent(event)

    # ── Copy / Paste ──────────────────────────────────────────────────────────
    def _copy_selected(self):
        """
        Copy selected nodes AND any edges whose both endpoints are selected.
        Clipboard stores serialised dicts so nothing holds live references.
        """
        selected_nodes = {
            n.node_id: n
            for n in self.scene().selectedItems()
            if isinstance(n, NodeItem)
        }
        if not selected_nodes:
            return

        node_dicts = [n.to_dict() for n in selected_nodes.values()]

        # Only copy edges where BOTH source and target are in the selection
        edge_dicts = [
            e.to_dict()
            for e in self.scene().edges.values()
            if (e.source_node.node_id in selected_nodes
                and e.target_node.node_id in selected_nodes)
        ]

        self._clipboard = {"nodes": node_dicts, "edges": edge_dicts}

    def _paste(self, scene_pos=None):
        """
        Paste clipboard at scene_pos (right-click location) or at the current
        viewport centre if called from Ctrl+V.  Nodes are placed so their
        centroid lands at the target position, preserving relative layout.
        Edges between copied nodes are also recreated.
        """
        if not self._clipboard.get("nodes"):
            return

        node_dicts = self._clipboard["nodes"]
        edge_dicts = self._clipboard["edges"]

        # Compute centroid of the original positions
        cx = sum(nd["x"] for nd in node_dicts) / len(node_dicts)
        cy = sum(nd["y"] for nd in node_dicts) / len(node_dicts)

        # Target: scene_pos if given, else centre of current viewport
        if scene_pos is None:
            vp_center   = self.viewport().rect().center()
            scene_pos   = self.mapToScene(vp_center)

        dx = scene_pos.x() - cx
        dy = scene_pos.y() - cy

        # Paste nodes, building old_id → new_node map for edge rewiring
        id_map = {}   # old node_id -> new NodeItem
        self.scene().clearSelection()
        for nd in node_dicts:
            new_node = self.scene().add_node(
                label=nd["label"],
                x=nd["x"] + dx,
                y=nd["y"] + dy,
                node_type=nd.get("node_type"),
                color=nd.get("color"),
                properties=copy.deepcopy(nd.get("properties", {})),
                node_id=new_id(),
                notes=nd.get("notes", ""),
                sticky_text=nd.get("sticky_text", ""),
                sticky_visible=nd.get("sticky_visible", False),
                sticky_dock=nd.get("sticky_dock", "right"),
            )
            id_map[nd["id"]] = new_node
            new_node.setSelected(True)

        # Recreate edges between the pasted nodes
        for ed in edge_dicts:
            src = id_map.get(ed["source"])
            tgt = id_map.get(ed["target"])
            if src and tgt:
                self.scene().add_edge(
                    src, tgt,
                    label=ed.get("label", ""),
                    direction=ed.get("direction", "→"),
                    edge_type=ed.get("edge_type", "relationship"),
                    color=ed.get("color"),
                )

    # ── Context menu ──────────────────────────────────────────────────────────
    def contextMenuEvent(self, event):
        scene_pos = self.mapToScene(event.pos())
        items     = self.scene().items(scene_pos)
        node  = next((i for i in items if isinstance(i, NodeItem)), None)
        edge  = next((i for i in items if isinstance(i, EdgeItem)), None)
        menu  = QMenu(self)
        menu.setStyleSheet(self._menu_style())

        if node:
            a_conn = menu.addAction("🔗  Connect from here")
            a_edit = menu.addAction("✏️  Rename")
            a_col  = menu.addAction("🎨  Change colour")
            menu.addSeparator()
            a_copy = menu.addAction("📋  Copy  (Ctrl+C)")
            menu.addSeparator()
            a_del  = menu.addAction("🗑️  Delete node")
            ch = menu.exec_(event.globalPos())
            if ch == a_conn:
                self.scene().start_connect(node)
            elif ch == a_edit:
                t, ok = QInputDialog.getText(self, "Rename", "New label:", text=node.label)
                if ok and t:
                    node.label = t
                    node._refresh_text()
                    self.scene().graph_changed.emit()
            elif ch == a_col:
                c = QColorDialog.getColor(QColor(node.color), self)
                if c.isValid():
                    node.color = c.name()
                    node._refresh_text()
                    self.scene().update()
                    self.scene().graph_changed.emit()
            elif ch == a_copy:
                if not node.isSelected():
                    self.scene().clearSelection()
                    node.setSelected(True)
                self._copy_selected()
            elif ch == a_del:
                self.scene().delete_node(node)

        elif edge:
            a_lbl  = menu.addAction("🏷️  Edit label")
            a_col  = menu.addAction("🎨  Change colour")
            a_dir  = menu.addMenu("↔  Direction")
            dir_acts = {
                a_dir.addAction(("✓ " if d == edge.direction else "    ") + d): d
                for d in config.EDGE_DIRECTIONS
            }
            a_typ  = menu.addMenu("⬡  Edge type")
            typ_acts = {
                a_typ.addAction(("✓ " if t == edge.edge_type else "    ") + t): t
                for t in config.EDGE_TYPE_COLORS
            }
            menu.addSeparator()
            a_del = menu.addAction("🗑️  Delete edge")
            ch = menu.exec_(event.globalPos())
            if ch == a_lbl:
                t, ok = QInputDialog.getText(self, "Edge Label", "Label:", text=edge.label)
                if ok:
                    edge.set_label(t)
                    self.scene().graph_changed.emit()
            elif ch == a_col:
                c = QColorDialog.getColor(QColor(edge.color), self)
                if c.isValid():
                    edge.color = c.name()
                    edge._refresh_label_text()
                    self.scene().update()
                    self.scene().graph_changed.emit()
            elif ch in dir_acts:
                edge.set_direction(dir_acts[ch])
                self.scene().graph_changed.emit()
            elif ch in typ_acts:
                edge.set_edge_type(typ_acts[ch])
                self.scene().graph_changed.emit()
            elif ch == a_del:
                self.scene().delete_edge(edge)

        else:
            a_add   = menu.addAction("➕  Add node here")
            a_paste = menu.addAction("📋  Paste  (Ctrl+V)")
            ch = menu.exec_(event.globalPos())
            if ch == a_add:
                lbl, ok = QInputDialog.getText(self, "New Node", "Label:")
                if ok and lbl:
                    self.scene().add_node(label=lbl, x=scene_pos.x(), y=scene_pos.y())
            elif ch == a_paste:
                self._paste(scene_pos)

    def _menu_style(self):
        return (f"QMenu {{ background:{gc('BG_PANEL')}; color:{gc('TEXT_PRIMARY')};"
                f" border:1px solid {gc('BORDER')}; border-radius:6px; padding:4px; }}"
                f" QMenu::item {{ padding:6px 20px; border-radius:4px; }}"
                f" QMenu::item:selected {{ background:{gc('ACCENT')}; color:white; }}"
                f" QMenu::separator {{ background:{gc('BORDER')}; height:1px; margin:4px 8px; }}")
