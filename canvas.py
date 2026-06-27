"""
canvas.py — GraphicsScene, NodeItem, EdgeItem, CanvasView
"""
import math, copy
from PyQt5.QtWidgets import (
    QGraphicsScene, QGraphicsView, QGraphicsItem, QGraphicsTextItem,
    QGraphicsPathItem, QGraphicsRectItem, QInputDialog, QMenu, QColorDialog, QFrame
)
# QGraphicsRectItem kept — used for StickyOverlay background pill
from PyQt5.QtCore import Qt, QPointF, QRectF, QLineF, pyqtSignal, QTimer
from PyQt5.QtGui import QPainter, QPen, QBrush, QColor, QFont, QPainterPath,QPainterPathStroker,QTextOption,QFontMetricsF

import config
from config import gc, qc, new_id
from utils import *




# ─────────────────────────────────────────────────────────────────────────────
#  EdgeItem
# ─────────────────────────────────────────────────────────────────────────────
class EdgeItem(QGraphicsPathItem):
    # Valid line styles
    LINE_STYLES = {"solid": Qt.SolidLine, "dashed": Qt.DashLine, "dotted": Qt.DotLine}

    def __init__(self, src, tgt, label="", edge_id=None,
                 direction="→", edge_type="relationship", color=None,
                 line_style="solid"):
        super().__init__()
        self.edge_id     = edge_id or new_id()
        self.source_node = src
        self.target_node = tgt
        self.label       = label
        self.direction   = direction
        self.edge_type   = edge_type
        self.color       = color or config.EDGE_TYPE_COLORS.get(edge_type, "#adb5bd")
        self.line_style  = line_style if line_style in self.LINE_STYLES else "solid"

        self.setZValue(0)
        self.setFlag(QGraphicsItem.ItemIsSelectable)

        self._label_item = QGraphicsTextItem("", self)
        self._label_item.setAcceptedMouseButtons(Qt.NoButton)
        self._label_item.setFlag(QGraphicsItem.ItemIsSelectable, False)
        self._label_item.setFlag(QGraphicsItem.ItemIgnoresTransformations)
        self._refresh_label_text()

    def _refresh_label_text(self):
        # Only show the user-provided label — no [type] prefix clutter
        self._label_item.setVisible(not config.SETTINGS.get("hide_edge_labels", False))
        self._label_item.setPlainText(self.label)
        self._label_item.setFont(QFont("Segoe UI", config.SETTINGS["edge_label_size"]))
        self._label_item.setDefaultTextColor(graph_color((self.color)))
        self.update_path()

    def shape(self):
        """Fat invisible hit-zone so edges are easy to click without
        needing pixel-precision on the visible line."""
        stroker = QPainterPathStroker()
        stroker.setWidth(12)   # 12 scene-units total = ~6px halo each side
        return stroker.createStroke(self.path())

    def set_label(self, text):
        self.label = text
        self._refresh_label_text()

    def set_direction(self, d):
        self.direction = d
        self.update_path()

    def set_edge_type(self, t):
        self.edge_type = t
        self.color = config.EDGE_TYPE_COLORS.get(t, self.color)
        self._refresh_label_text()

    def set_line_style(self, style):
        if style in self.LINE_STYLES:
            self.line_style = style
            self.update()

    def update_path(self):
        sp = self.source_node.scenePos()
        tp = self.target_node.scenePos()
        r_s = self.source_node.connection_radius()
        r_t = self.target_node.connection_radius()
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
        qt_style = self.LINE_STYLES.get(self.line_style, Qt.SolidLine)
        pen = QPen(
            qc("ACCENT") if self.isSelected() else graph_color(self.color),
            2.0 if self.isSelected() else 1.2,
            qt_style,
        )
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        # self.setPen(pen)
        painter.drawPath(self.path())
        # super().paint(painter, option, widget)

    def to_dict(self):
        return {
            "id":         self.edge_id,
            "source":     self.source_node.node_id,
            "target":     self.target_node.node_id,
            "label":      self.label,
            "direction":  self.direction,
            "edge_type":  self.edge_type,
            "color":      self.color,
            "line_style": self.line_style,
        }


# ─────────────────────────────────────────────────────────────────────────────
#  StickyOverlay — a pair of scene-level items (background + text) that shadow
#  a NodeItem.  Living directly in the scene (not as children of the node)
#  means their positions are plain scene coordinates, so zoom / pan can never
#  corrupt the layout the way ItemIgnoresTransformations on a child can.
# ─────────────────────────────────────────────────────────────────────────────
class StickyOverlay:
    """Owns only a text item — no background box, no border."""

    GAP   = 10    # scene-unit gap between node edge and text
    WIDTH = 160   # max text width before wrapping

    def __init__(self, scene):
        self._scene = scene

        self._txt = QGraphicsTextItem()
        self._txt.setAcceptedMouseButtons(Qt.NoButton)
        self._txt.setTextInteractionFlags(Qt.NoTextInteraction)
        
        self._txt.setZValue(11)
        self._txt.setVisible(False)
        scene.addItem(self._txt)

    def update(self, node):
        """Recompute scene position + styling from *node* state."""
        text = node.sticky_text.strip()
        visible = bool(text and node.sticky_visible)
        self._txt.setVisible(visible)
        if not visible:
            return

        # ── Binary color scheme: black on light theme, white on dark theme ──
        text_color = QColor("#111111") if config.CURRENT_THEME == "light" else QColor("#f0f0f0")
        self._txt.setPlainText(text)
        self._txt.setFont(QFont("Segoe UI", config.SETTINGS["ui_font_size"] - 1))
        self._txt.document().setDefaultTextOption(QTextOption(Qt.AlignHCenter))
        self._txt.setDefaultTextColor(text_color)

        fm = QFontMetricsF(self._txt.font())
        lines = text.split("\n")
        content_w = max(fm.horizontalAdvance(line) for line in lines)
        content_w = min(content_w, self.WIDTH)   # never exceed wrap width

        # ── Position in scene space, centered tight against the node ──────────
        cx = node.scenePos().x()
        cy = node.scenePos().y()
        r  = node.radius
        br = self._txt.boundingRect()
        w  = content_w
        h  = br.height()
        g  = self.GAP

        dock = node.sticky_dock
        if dock == "left":
            tx = cx - r - g - w
            ty = cy - h / 2
        elif dock == "above":
            tx = cx - w / 2
            ty = cy - r - g - h
        elif dock == "below":
            tx = cx - w / 2
            ty = cy + r + g
        else:  # right (default)
            tx = cx + r + g
            ty = cy - h / 2

        self._txt.setPos(tx, ty)

    def remove(self):
        """Remove the text item from the scene (call when node is deleted)."""
        if self._txt.scene():
            self._scene.removeItem(self._txt)


# Node label can support node dragging
class NodeLabelItem(QGraphicsTextItem):

    def __init__(self, parent_node):
        super().__init__("", parent_node)
        self.parent_node = parent_node
        self._drag_start = None

    def mousePressEvent(self, event):
        self._drag_start = event.scenePos()
        event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_start is None:
            return

        delta = event.scenePos() - self._drag_start

        self.parent_node.setPos(
            self.parent_node.pos() + delta
        )

        self._drag_start = event.scenePos()
        event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_start = None
        event.accept()


#  NodeItem
# ─────────────────────────────────────────────────────────────────────────────
class NodeItem(QGraphicsItem):
    def __init__(self, node_id=None, label="Node", x=0, y=0,
                 node_type="default", color=None, properties=None,
                 notes="", sticky_text="", sticky_visible=False,
                 sticky_dock="right",node_label_dock="right",body_visible_override=None):
        super().__init__()
        self.node_id    = node_id or new_id()
        self.label      = label
        self.node_type  = node_type
        self.color      = color or config.NODE_TYPE_COLORS.get(
            node_type, config.NODE_TYPE_COLORS.get("default", "#888888"))
        self.properties = properties if properties is not None else {}
        self.notes      = notes
        self.sticky_text    = sticky_text
        self.sticky_visible = sticky_visible
        self.sticky_dock    = sticky_dock
        self.node_label_dock = node_label_dock
        self.body_visible_override = body_visible_override
        self.edges  = []
        self.radius = 14

        # StickyOverlay is created after the node is added to the scene
        # (scene is not available in __init__).  GraphScene.add_node sets it.
        self._sticky = None  # type: StickyOverlay | None

        self._inject_schema()

        self._text = NodeLabelItem( self)
    

        # Debounce sticky overlay updates during drag — updating every pixel
        # is expensive; 30ms after the last position change is imperceptible.
        self._sticky_timer = QTimer()
        self._sticky_timer.setSingleShot(True)
        self._sticky_timer.setInterval(2)
        self._sticky_timer.timeout.connect(self._refresh_sticky)

        self.setFlag(QGraphicsItem.ItemIsMovable)
        self.setFlag(QGraphicsItem.ItemIsSelectable)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges)
        self.setPos(x, y)
        self.setZValue(1)
        self._refresh_text()

    # ── Schema / text ─────────────────────────────────────────────────────────
    def _inject_schema(self):
        expected = (config.PROPERTY_SCHEMA.get("__universal__", [])
                    + config.PROPERTY_SCHEMA.get(self.node_type, []))
        for k in expected:
            if k not in self.properties:
                self.properties[k] = ""

    def _refresh_text(self, view_scale=1.0):
        self.prepareGeometryChange()
        nominal_pt  = config.SETTINGS["ui_font_size"]
        MIN_SCREEN_PX = 11
        # Compute minimum scene-unit font size to stay ≥11px on screen
        min_scene_pt = MIN_SCREEN_PX / max(view_scale, 0.001)
        effective_pt = max(nominal_pt, min_scene_pt)

        self._text.setVisible(not config.SETTINGS.get("hide_node_labels", False))
        self._text.setPlainText(self.label)
        font = QFont("Segoe UI", max(1, int(round(effective_pt))), QFont.Medium)
        self._text.setFont(font) #That is why setFont() must happen before you measure w and h.
        self._text.setDefaultTextColor(graph_color(self.color))
        self._update_label_position()
        self._refresh_sticky()

    def update_label_scale(self, view_scale: float):
        """Called by CanvasView on zoom change — updates font size only, no geometry change."""
        nominal_pt  = config.SETTINGS["ui_font_size"]
        MIN_SCREEN_PX = 11
        min_scene_pt = MIN_SCREEN_PX / max(view_scale, 0.001)
        effective_pt = max(nominal_pt, min_scene_pt)
        cur_font = self._text.font()
        if abs(cur_font.pointSizeF() - effective_pt) > 0.5:
            f = QFont(
                "Segoe UI",
                max(1, int(round(effective_pt))),
                QFont.Medium
            )
            self._text.setFont(f)
            self._update_label_position()

    def _update_label_position(self):
        br = self._text.boundingRect()
        w = br.width()
        h = br.height()
        g = 5

        dock = self.node_label_dock

        if dock == "left":
            x = -self.radius - g - w
            y = -h / 2
        elif dock == "above":
            x = -w / 2
            y = -self.radius - g - h
        elif dock == "below":
            x = -w / 2
            y = self.radius + g
        else:
            x = self.radius + g
            y = -h / 2

        self._text.setPos(x, y)

    def _refresh_sticky(self):
        if self._sticky is not None:
            self._sticky.update(self)

    # ── Sticky setters (called from sidebar) ──────────────────────────────────
    def set_notes(self, text):
        self.notes = text

    def set_sticky_text(self, text):
        self.sticky_text = text
        self._refresh_sticky()

    def set_sticky_visible(self, visible):
        self.sticky_visible = visible
        self._refresh_sticky()

    def set_sticky_dock(self, dock):
        self.sticky_dock = dock
        self._refresh_sticky()

    # ── Graphics ──────────────────────────────────────────────────────────────
    def boundingRect(self):
        p = 5
        return QRectF(-self.radius - p, -self.radius - p,
                      self.radius * 2 + p * 2, self.radius * 2 + p * 2)

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        r   = self.radius
        col = qc("ACCENT") if self.isSelected() else graph_color(self.color)

        # Fade circle at very low zoom so the label (child QGraphicsTextItem) stays
        # readable against the background even when the circle itself is tiny.
        # We read zoom from the view transform — read-only, no item mutation.
        view_scale = painter.worldTransform().m11()
        node_alpha = min(255, int(view_scale * 255 * 2))
        if node_alpha < 255:
            draw_col = QColor(col)
            draw_col.setAlpha(node_alpha)
        else:
            draw_col = col
        body_visible = self.body_visible()
        draw_body = body_visible or self.isSelected()

        if draw_body:

            # Hidden nodes temporarily reappear as ghosts when selected.
            if not body_visible:
                draw_col = QColor(draw_col)
                draw_col.setAlpha(min(draw_col.alpha(), 120))

            painter.setBrush(QBrush(draw_col))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QPointF(0, 0), r, r)

            if self.isSelected():
                ring = QColor(col.lighter(150))

                # Ghost nodes also get a softer selection ring.
                if not body_visible:
                    ring.setAlpha(180)

                painter.setBrush(Qt.NoBrush)
                painter.setPen(QPen(ring, 2))
                painter.drawEllipse(QPointF(0, 0), r + 4, r + 4)

            # Property count badge.
            filled = sum(
                1 for v in self.properties.values()
                if str(v).strip()
            )

            if filled:
                badge = QRectF(r - 6, -r - 2, 12, 10)
                painter.setBrush(QBrush(QColor("#ff6584")))
                painter.setPen(Qt.NoPen)
                painter.drawRoundedRect(badge, 3, 3)

                painter.setPen(QPen(Qt.white))
                painter.setFont(QFont("Segoe UI", 6, QFont.Bold))
                painter.drawText(
                    badge,
                    Qt.AlignCenter,
                    str(filled)
                )
        

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionHasChanged:
            for e in self.edges:
                e.update_path()
            # Debounce sticky overlay — don't recompute every drag pixel
            self._sticky_timer.start()
        return super().itemChange(change, value)

    # ── Edge book-keeping ─────────────────────────────────────────────────────
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

    def body_visible(self):
        if self.body_visible_override is not None:
            return self.body_visible_override
        return not config.SETTINGS.get("hide_node_bodies", False)

    
    def mousePressEvent(self, event):
        return super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        return super().mouseMoveEvent(event)

    def connection_radius(self):
        return self.radius if self.body_visible() else 2

    # ── Serialisation ─────────────────────────────────────────────────────────
    def to_dict(self):
        return {
            "id":             self.node_id,
            "label":          self.label,
            "x":              self.x(),
            "y":              self.y(),
            "node_type":      self.node_type,
            "color":          self.color,
            "properties":     dict(self.properties),
            "notes":          self.notes,
            "sticky_text":    self.sticky_text,
            "sticky_visible": self.sticky_visible,
            "sticky_dock":    self.sticky_dock,
            "node_label_dock": self.node_label_dock,
            "body_visible_override": self.body_visible_override
        }


# ─────────────────────────────────────────────────────────────────────────────
#  CanvasTextItem — free-floating, draggable text label for the canvas
# ─────────────────────────────────────────────────────────────────────────────
class CanvasTextItem(QGraphicsItem):
    """A resizable, styled text block the user can place anywhere on the canvas.
    Font, size and colour are independent of global settings — they are stored
    per-item and survive theme / font-size changes.
    """

    def __init__(self, text="Text", x=0, y=0,
                 color="#e8eaf6", font_size=18, bold=False, italic=False,
                 item_id=None):
        super().__init__()
        self.item_id   = item_id or new_id()
        self.text      = text
        self.color     = color
        self.font_size = font_size
        self.bold      = bold
        self.italic    = italic

        self.setFlag(QGraphicsItem.ItemIsMovable)
        self.setFlag(QGraphicsItem.ItemIsSelectable)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges)
        self.setPos(x, y)
        self.setZValue(0.5)          # between edges (0) and nodes (1)

        self._txt = QGraphicsTextItem("", self)
        self._refresh()

    def _refresh(self):
        self.prepareGeometryChange()
        self._txt.setPlainText(self.text)
        self._txt.setDefaultTextColor(graph_color(self.color))
        w = QFont.Bold if self.bold else QFont.Normal
        f = QFont("Segoe UI", self.font_size, w)
        f.setItalic(self.italic)
        self._txt.setFont(f)
        self._txt.setTextWidth(-1)   # natural width

    def boundingRect(self):
        br = self._txt.boundingRect()
        pad = 6
        return QRectF(-pad, -pad, br.width() + pad * 2, br.height() + pad * 2)

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        if self.isSelected():
            pen = QPen(qc("ACCENT"), 1.5, Qt.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(self.boundingRect(), 4, 4)
        self._txt.setPos(6, 6)

    def to_dict(self):
        return {
            "id":        self.item_id,
            "text":      self.text,
            "x":         self.x(),
            "y":         self.y(),
            "color":     self.color,
            "font_size": self.font_size,
            "bold":      self.bold,
            "italic":    self.italic,
        }

    def refresh_theme(self):
        self._txt.setDefaultTextColor(
            graph_color(self.color)
        )


# ─────────────────────────────────────────────────────────────────────────────
#  NodeGroup — a visual bounding-box grouping item
# ─────────────────────────────────────────────────────────────────────────────
class NodeGroup(QGraphicsItem):
    """
    Represents a named group of NodeItems.  Renders as a rounded translucent
    rect with a title in the top-left corner.  Members move with the group
    when the group itself is dragged.
    """

    CORNER_R = 12
    PAD      = 24
    HANDLE_R = 5
    _TL, _TC, _TR = 0, 1, 2
    _ML,      _MR = 3,    4
    _BL, _BC, _BR = 5, 6, 7  # padding around member bounding-boxes

    def __init__(self, group_id=None, name="Group", color=None, member_ids=None):
        super().__init__()
        self.group_id   = group_id or new_id()
        self.name       = name
        self.color      = color or "#6c63ff"
        self.member_ids = list(member_ids or [])
        # ── resize state (new) ──
        self._resizing         = False
        self._drag_handle      = None
        self._drag_start_pos   = None
        self._drag_start_rect  = None

        self.setFlag(QGraphicsItem.ItemIsMovable)
        self.setFlag(QGraphicsItem.ItemIsSelectable)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges)
        self.setZValue(-0.5)   # behind nodes/edges, in front of grid

        self._rect = QRectF(-60, -30, 120, 60)   # overwritten by fit_to_members

    # ── Geometry ──────────────────────────────────────────────────────────────
    def fit_to_members(self, members):
        """Recompute position and size so the rect wraps all member nodes."""
        if not members:
            return
        xs = [n.scenePos().x() for n in members]
        ys = [n.scenePos().y() for n in members]
        rs = [n.radius for n in members]
        pad = self.PAD
        min_x = min(x - r for x, r in zip(xs, rs)) - pad
        min_y = min(y - r for y, r in zip(ys, rs)) - pad
        max_x = max(x + r for x, r in zip(xs, rs)) + pad
        max_y = max(y + r for y, r in zip(ys, rs)) + pad

        self.prepareGeometryChange()
        self.setPos(min_x, min_y)
        self._rect = QRectF(0, 0, max_x - min_x, max_y - min_y)

    def boundingRect(self):
        extra = self.HANDLE_R + 2 if self._resizing else 2
        return self._rect.adjusted(-extra, -extra, extra, extra)
    
    def enter_resize_mode(self):
        self._resizing = True
        self.setFlag(QGraphicsItem.ItemIsMovable, False)
        self.prepareGeometryChange()
        self.update()
        self.setCursor(Qt.SizeAllCursor)

    def leave_resize_mode(self):
        self._resizing = False
        self._drag_handle = None
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.prepareGeometryChange()
        self.update()
        self.unsetCursor()
        if self.scene():
            self.scene().graph_changed.emit()

    def _handle_points(self):
        r = self._rect
        cx, cy = r.center().x(), r.center().y()
        return [
            QPointF(r.left(),  r.top()), QPointF(cx, r.top()), QPointF(r.right(), r.top()),
            QPointF(r.left(),  cy),                            QPointF(r.right(), cy),
            QPointF(r.left(),  r.bottom()), QPointF(cx, r.bottom()), QPointF(r.right(), r.bottom()),
        ]

    def _handle_cursor(self, idx):
        cursors = {
            self._TL: Qt.SizeFDiagCursor, self._BR: Qt.SizeFDiagCursor,
            self._TR: Qt.SizeBDiagCursor, self._BL: Qt.SizeBDiagCursor,
            self._TC: Qt.SizeVerCursor,   self._BC: Qt.SizeVerCursor,
            self._ML: Qt.SizeHorCursor,   self._MR: Qt.SizeHorCursor,
        }
        return cursors.get(idx, Qt.SizeAllCursor)

    def _hit_handle(self, pos):
        r2 = (self.HANDLE_R + 3) ** 2
        for i, hp in enumerate(self._handle_points()):
            dx, dy = pos.x() - hp.x(), pos.y() - hp.y()
            if dx * dx + dy * dy <= r2:
                return i
        return -1

    def mousePressEvent(self, event):
        if self._resizing and event.button() == Qt.LeftButton:
            idx = self._hit_handle(event.pos())
            if idx >= 0:
                self._drag_handle     = idx
                self._drag_start_pos  = event.scenePos()
                self._drag_start_rect = QRectF(self._rect)
            else:
                self.leave_resize_mode()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._resizing:
            idx = self._hit_handle(event.pos())
            self.setCursor(self._handle_cursor(idx) if idx >= 0 else Qt.ArrowCursor)

            if self._drag_handle is not None and self._drag_start_pos is not None:
                delta = event.scenePos() - self._drag_start_pos
                dx, dy = delta.x(), delta.y()
                r = QRectF(self._drag_start_rect)
                h = self._drag_handle
                MIN = 40
                if h in (self._TL, self._TC, self._TR):
                    nt = r.top() + dy
                    if r.bottom() - nt >= MIN: r.setTop(nt)
                if h in (self._BL, self._BC, self._BR):
                    nb = r.bottom() + dy
                    if nb - r.top() >= MIN: r.setBottom(nb)
                if h in (self._TL, self._ML, self._BL):
                    nl = r.left() + dx
                    if r.right() - nl >= MIN: r.setLeft(nl)
                if h in (self._TR, self._MR, self._BR):
                    nr = r.right() + dx
                    if nr - r.left() >= MIN: r.setRight(nr)

                self.prepareGeometryChange()
                self._rect = r
                self.update()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._resizing and self._drag_handle is not None:
            self._drag_handle = self._drag_start_pos = self._drag_start_rect = None
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if self._resizing and event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Escape):
            self.leave_resize_mode()
            event.accept()
            return
        super().keyPressEvent(event)

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        col = graph_color(self.color)

        painter.setBrush(Qt.NoBrush)   # fully transparent — was a translucent fill

        border = QColor(col)
        border.setAlpha(180 if self.isSelected() or self._resizing else 100)
        pen_width = 2.0 if self.isSelected() or self._resizing else 1.4
        pen = QPen(border, pen_width, Qt.SolidLine if self._resizing else Qt.DashLine)
        painter.setPen(pen)
        painter.drawRoundedRect(self._rect, self.CORNER_R, self.CORNER_R)

        title_col = QColor(col); title_col.setAlpha(200)
        painter.setPen(QPen(title_col))
        f = QFont("Segoe UI", config.SETTINGS["ui_font_size"] - 1, QFont.Bold)
        painter.setFont(f)
        painter.drawText(
            QRectF(self._rect.x() + 10, self._rect.y() + 6, self._rect.width() - 20, 20),
            Qt.AlignLeft | Qt.AlignVCenter, self.name,
        )

        if self._resizing:
            painter.setPen(QPen(col, 1.5))
            painter.setBrush(QBrush(QColor(255, 255, 255, 200)))
            for hp in self._handle_points():
                painter.drawEllipse(hp, self.HANDLE_R, self.HANDLE_R)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionHasChanged and self.scene():
            # When group is dragged, move all member nodes by the same delta
            scene = self.scene()
            if hasattr(scene, "_group_drag_delta"):
                dx, dy = scene._group_drag_delta
                for nid in self.member_ids:
                    node = scene.nodes.get(nid)
                    if node:
                        node.setPos(node.pos() + QPointF(dx, dy))
        return super().itemChange(change, value)

    def to_dict(self):
        return {
            "id": self.group_id, "name": self.name, "color": self.color,
            "members": list(self.member_ids), "x": self.x(), "y": self.y(),
            "w": self._rect.width(), "h": self._rect.height(),   # new
        }


# ─────────────────────────────────────────────────────────────────────────────
#  GraphScene
# ─────────────────────────────────────────────────────────────────────────────
class GraphScene(QGraphicsScene):
    node_selected  = pyqtSignal(object)
    edge_selected  = pyqtSignal(object)
    group_selected = pyqtSignal(object)
    graph_changed  = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSceneRect(-100000, -100000, 200000, 200000)
        self.setBackgroundBrush(QBrush(qc("BG_DARK")))
        self.nodes  = {}
        self.edges  = {}
        self.texts  = {}
        self.groups = {}          # group_id → NodeGroup
        self._connecting   = False
        self._conn_source  = None
        self._conn_line    = None
        self._press_pos = None
        self.layout_active = False
        self.layout_timer  = QTimer()
        self.layout_timer.timeout.connect(self._layout_step)
        self._group_drag_prev = {}   # group_id → last QPointF position

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
                 sticky_dock="right",node_label_dock="right",body_visible_override=None):
        nt = node_type or config.SETTINGS["default_node_type"]
        if nt not in config.NODE_TYPE_COLORS:
            nt = next(iter(config.NODE_TYPE_COLORS), "default")
        n = NodeItem(node_id=node_id, label=label, x=x, y=y,
                     node_type=nt, color=color, properties=properties,
                     notes=notes, sticky_text=sticky_text,
                     sticky_visible=sticky_visible, sticky_dock=sticky_dock,node_label_dock=node_label_dock,body_visible_override=body_visible_override)
        self.nodes[n.node_id] = n
        self.addItem(n)
        # StickyOverlay must be created AFTER addItem so the scene is available
        n._sticky = StickyOverlay(self)
        n._refresh_sticky()          # draw initial state
        self.graph_changed.emit()
        return n


    def delete_node(self, node):
        for e in list(node.edges):
            self.delete_edge(e)

        for item in self.items():
            if isinstance(item, NodeGroup) and node.node_id in item.member_ids:
                item.member_ids = [nid for nid in item.member_ids if nid != node.node_id]
                item.update()

        if node._sticky is not None:
            node._sticky.remove()
            node._sticky = None

        # If this node was selected / being inspected, clear the selection state
        was_selected = node.isSelected()

        self.nodes.pop(node.node_id, None)
        self.removeItem(node)

        if was_selected:
            self.clearSelection()
            self.node_selected.emit(None)
            self.edge_selected.emit(None)
            self.group_selected.emit(None)

        self.graph_changed.emit()

    def add_edge(self, src, tgt, label="", edge_id=None,
                 direction=None, edge_type=None, color=None, line_style="solid"):
        direction = direction or config.SETTINGS["default_direction"]
        edge_type = edge_type or config.SETTINGS["default_edge_type"]
        if edge_type not in config.EDGE_TYPE_COLORS:
            edge_type = next(iter(config.EDGE_TYPE_COLORS), "relationship")
        for e in self.edges.values():
            same_pair = (e.source_node is src and e.target_node is tgt)
            reverse_pair = (e.source_node is tgt and e.target_node is src)

            if e.direction == direction:
                if direction in ("—", "↔"):
                    if same_pair or reverse_pair:
                        return None
                else:
                    if same_pair:
                        return None
        e = EdgeItem(src, tgt, label=label, edge_id=edge_id,
                     direction=direction, edge_type=edge_type, color=color,
                     line_style=line_style)
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

    def add_text(self, text="Text", x=0, y=0, color=None,
                 font_size=18, bold=False, italic=False, item_id=None):
        col = color or  get_neutral_color()
        t = CanvasTextItem(text=text, x=x, y=y, color=col,
                           font_size=font_size, bold=bold, italic=italic,
                           item_id=item_id)
        self.texts[t.item_id] = t
        self.addItem(t)
        self.graph_changed.emit()
        return t

    def delete_text(self, item):
        self.texts.pop(item.item_id, None)
        self.removeItem(item)
        self.graph_changed.emit()

    # ── Group CRUD ────────────────────────────────────────────────────────────
    def group_nodes(self, nodes, name="Group"):
        """Create a group from a list of NodeItems."""
        if len(nodes) < 2:
            return None
        g = NodeGroup(
            name=name,
            color=nodes[0].color,
            member_ids=[n.node_id for n in nodes],
        )
        g.fit_to_members(nodes)
        self.groups[g.group_id] = g
        self.addItem(g)
        self.graph_changed.emit()
        return g

    def ungroup(self, group):
        """Remove a group without deleting its member nodes."""
        self.groups.pop(group.group_id, None)
        self.removeItem(group)
        self.graph_changed.emit()

    def get_node_group(self, node):
        """Return the NodeGroup that contains node, or None."""
        for g in self.groups.values():
            if node.node_id in g.member_ids:
                return g
        return None

    def clear_all(self):
        """Remove all nodes (and their sticky overlays), edges, texts, groups, then clear."""
        for node in list(self.nodes.values()):
            if node._sticky is not None:
                node._sticky.remove()
                node._sticky = None
        self.clear()
        self.nodes.clear()
        self.edges.clear()
        self.texts.clear()
        self.groups.clear()

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
            "schema": config.schema_block(),
            "nodes":  [n.to_dict() for n in self.nodes.values()],
            "edges":  [e.to_dict() for e in self.edges.values()],
            "texts":  [t.to_dict() for t in self.texts.values()],
            "groups": [g.to_dict() for g in self.groups.values()],
        }

    def load_dict(self, data):

        #NOTE: prevents a lingering connecting state if file (re)load occurrs
        self.abort_connect()

        # Remove sticky overlays before scene.clear()
        for node in list(self.nodes.values()):
            if node._sticky is not None:
                node._sticky.remove()
                node._sticky = None
        self.clear()
        self.nodes.clear()
        self.edges.clear()
        self.texts.clear()
        self.groups.clear()

        if "schema" in data:
            config.restore_schema_block(data["schema"])
        elif "types" in data:
            config.restore_schema_block(data["types"])

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
                node_label_dock = nd.get("node_label_dock","right"),
                body_visible_override=nd.get("body_visible_override",None)
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
                    line_style=ed.get("line_style", "solid"),
                )
        for td in data.get("texts", []):
            self.add_text(
                text=td.get("text", ""),
                x=td["x"], y=td["y"],
                color=td.get("color"),
                font_size=td.get("font_size", 18),
                bold=td.get("bold", False),
                italic=td.get("italic", False),
                item_id=td.get("id"),
            )
        for gd in data.get("groups", []):
            members = [self.nodes[mid] for mid in gd.get("members", [])
                       if mid in self.nodes]
            if len(members) >= 2:
                g = NodeGroup(
                    group_id=gd.get("id"),
                    name=gd.get("name", "Group"),
                    color=gd.get("color"),
                    member_ids=gd.get("members", []),
                )
                if "w" in gd and "h" in gd:
                    g.prepareGeometryChange()
                    g.setPos(gd.get("x", 0), gd.get("y", 0))
                    g._rect = QRectF(0, 0, gd["w"], gd["h"])
                else:
                    g.fit_to_members(members)
                self.groups[g.group_id] = g
                self.addItem(g)

    # ── Mouse ─────────────────────────────────────────────────────────────────
    def mouseMoveEvent(self, event):
        if self._connecting and self._conn_line and self._conn_source:
            self._conn_line.setLine(
                QLineF(self._conn_source.scenePos(), event.scenePos()))
        # Track group drag delta so NodeGroup.itemChange can move members
        for gid, g in self.groups.items():
            prev = self._group_drag_prev.get(gid)
            cur  = g.pos()
            if prev is not None and g.isSelected():
                dx = cur.x() - prev.x()
                dy = cur.y() - prev.y()
                if dx != 0 or dy != 0:
                    self._group_drag_delta = (dx, dy)
                    for nid in g.member_ids:
                        node = self.nodes.get(nid)
                        if node:
                            node.setPos(node.pos() + QPointF(dx, dy))
                    self._group_drag_delta = (0, 0)
            self._group_drag_prev[gid] = QPointF(cur)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._connecting:
            tgt = None

            for item in self.items(event.scenePos()):
                node = self.resolve_node_item(item)
                if node and node is not self._conn_source:
                    tgt = node
                    break
            if tgt:
                label = ""
                if config.SETTINGS.get("ask_edge_label_before_add", True ):
                    label, ok = QInputDialog.getText(
                        None, "Edge Label", "Label (optional):")
                    if not ok:
                        label = ""
                self.add_edge(self._conn_source, tgt,
                                label=label)
            self.abort_connect()
            return

        if (
            self._press_pos is not None and
            QLineF(self._press_pos, event.scenePos()).length() > 5
        ):
            self._press_pos = None

            super().mouseReleaseEvent(event)
            selected = self.selectedItems()

            if len(selected) > 1:
                return
            return
        
        if event.button() == Qt.LeftButton:
            items   = self.items(event.scenePos())
            clicked = None

            for item in items:

                node = self.resolve_node_item(item)
                if node:
                    clicked = node
                    break

                if isinstance(item, (EdgeItem, CanvasTextItem, NodeGroup)):
                    clicked = item
                    break

                if isinstance(item, QGraphicsTextItem):
                    p = item.parentItem()

                    if isinstance(p, EdgeItem):

                        if not (event.modifiers() & Qt.ControlModifier):
                            self.clearSelection()

                        p.setSelected(True)

                        self.edge_selected.emit(p)
                        self.node_selected.emit(None)
                        self.group_selected.emit(None)

                        event.accept()
                        return
            if isinstance(clicked, NodeItem):
                if not (event.modifiers() & Qt.ControlModifier):
                    self.clearSelection()
                
                clicked.setSelected(True)

                self.node_selected.emit(clicked)
                self.edge_selected.emit(None)
                self.group_selected.emit(None)

            elif isinstance(clicked, EdgeItem):
                if not (event.modifiers() & Qt.ControlModifier):
                    self.clearSelection()
                clicked.setSelected(True)
                
                self.edge_selected.emit(clicked)
                self.node_selected.emit(None)
                self.group_selected.emit(None)

            elif isinstance(clicked, NodeGroup):
                if not (event.modifiers() & Qt.ControlModifier):
                    self.clearSelection()
                clicked.setSelected(True)

                self.group_selected.emit(clicked)
                self.node_selected.emit(None)
                self.edge_selected.emit(None)
            else:
                self.node_selected.emit(None)
                self.edge_selected.emit(None)
                self.group_selected.emit(None)
        
        super().mouseReleaseEvent(event)


    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._press_pos = event.scenePos()

        return super().mousePressEvent(event)

    def iter_nodes(self):
        return self.nodes.values()

    def iter_edges(self):
        return self.edges.values()
    
    def rename_node_type_everywhere(self, old_type, new_type):
        for node in self.iter_nodes():
            if node.node_type == old_type:
                node.node_type = new_type
                node._inject_schema()
                node._refresh_text()


    def rename_edge_type_everywhere(self, old_type, new_type):
        for edge in self.iter_edges():
            if edge.edge_type == old_type:
                edge.set_edge_type(new_type)


    def toggle_node_bodies(self, nodes):
        if not nodes:
            return

        # If any selected node is currently visible, hide all; otherwise show all
        any_visible = any(n.body_visible() for n in nodes)
        new_value = False if any_visible else True

        for n in nodes:
            n.body_visible_override = new_value
            n.update()

        self.graph_changed.emit()

    # helper for node body + label uniform interaction
    def resolve_node_item(self, item):
        while item is not None:
            if isinstance(item, NodeItem):
                return item
            item = item.parentItem()
        return None


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
        # clipboard stores {nodes: [...], edges: [...], texts: [...]} dicts
        self._clipboard   = {"nodes": [], "edges": [], "texts": []}

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
        self._update_node_label_scales()

    def _set_zoom(self, z):
        z      = max(self.MIN_ZOOM, min(self.MAX_ZOOM, z))
        factor = z / self._scale
        self._scale = z
        self.scale(factor, factor)
        self.zoom_changed.emit(self._scale)
        self._update_node_label_scales()

    def _update_node_label_scales(self):
        """Push current view scale to all node labels — zoom-aware font sizing."""
        s = self._scale
        for node in self.scene().nodes.values():
            node.update_label_scale(s)

    # ── Keyboard ─────────────────────────────────────────────────────────────
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Tab:
            
            mw = self.window()

            if hasattr(mw, "sidebar"):

                selected = self.scene().selectedItems()
                

                if len(selected) == 1:

                    item = selected[0]

                    if isinstance(item, NodeItem):
                        mw.sidebar.focus_node_label()
                        event.accept()
                        return

                    if isinstance(item, EdgeItem):
                        mw.sidebar.focus_edge_label()
                        event.accept()
                        return
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
                elif isinstance(item, CanvasTextItem):
                    self.scene().delete_text(item)
                elif isinstance(item, NodeGroup):
                    self.scene().ungroup(item)
        elif event.key() == Qt.Key_G and event.modifiers() & Qt.ControlModifier:
            if event.modifiers() & Qt.ShiftModifier:
                # Ctrl+Shift+G — ungroup selected groups
                for item in list(self.scene().selectedItems()):
                    if isinstance(item, NodeGroup):
                        self.scene().ungroup(item)
            else:
                # Ctrl+G — group selected nodes
                sel_nodes = [i for i in self.scene().selectedItems()
                             if isinstance(i, NodeItem)]
                if len(sel_nodes) >= 2:
                    name, ok = QInputDialog.getText(
                        self, "Group Name", "Name for this group:", text="Group")
                    if ok:
                        self.scene().group_nodes(sel_nodes, name=name or "Group")
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
        """Copy selected nodes+edges+texts. Returns True if anything was copied."""
        selected_nodes = {
            n.node_id: n
            for n in self.scene().selectedItems()
            if isinstance(n, NodeItem)
        }
        selected_texts = [
            t for t in self.scene().selectedItems()
            if isinstance(t, CanvasTextItem)
        ]
        if not selected_nodes and not selected_texts:
            return False

        node_dicts = [n.to_dict() for n in selected_nodes.values()]
        edge_dicts = [
            e.to_dict()
            for e in self.scene().edges.values()
            if (e.source_node.node_id in selected_nodes
                and e.target_node.node_id in selected_nodes)
        ]
        text_dicts = [t.to_dict() for t in selected_texts]

        self._clipboard = {"nodes": node_dicts, "edges": edge_dicts,
                           "texts": text_dicts}
        return True

    def _paste(self, scene_pos=None):
        """Paste clipboard at scene_pos, or viewport centre for Ctrl+V."""
        if not self._clipboard.get("nodes") and not self._clipboard.get("texts"):
            return

        node_dicts = self._clipboard.get("nodes", [])
        edge_dicts = self._clipboard.get("edges", [])
        text_dicts = self._clipboard.get("texts", [])

        # Compute centroid across all copied items
        all_xs = [nd["x"] for nd in node_dicts] + [td["x"] for td in text_dicts]
        all_ys = [nd["y"] for nd in node_dicts] + [td["y"] for td in text_dicts]
        if not all_xs:
            return
        cx = sum(all_xs) / len(all_xs)
        cy = sum(all_ys) / len(all_ys)

        if scene_pos is None:
            vp_center = self.viewport().rect().center()
            scene_pos = self.mapToScene(vp_center)

        dx = scene_pos.x() - cx
        dy = scene_pos.y() - cy

        self.scene().clearSelection()

        id_map = {}
        for nd in node_dicts:
            new_node = self.scene().add_node(
                label=nd["label"],
                x=nd["x"] + dx, y=nd["y"] + dy,
                node_type=nd.get("node_type"),
                color=nd.get("color"),
                properties=copy.deepcopy(nd.get("properties", {})),
                node_id=new_id(),
                notes=nd.get("notes", ""),
                sticky_text=nd.get("sticky_text", ""),
                sticky_visible=nd.get("sticky_visible", False),
                sticky_dock=nd.get("sticky_dock", "right"),
                node_label_dock = nd.get("node_label_dock","right"),
                body_visible_override=nd.get("body_visible_override",None)
            )
            id_map[nd["id"]] = new_node
            new_node.setSelected(True)

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

        for td in text_dicts:
            new_t = self.scene().add_text(
                text=td.get("text", ""),
                x=td["x"] + dx, y=td["y"] + dy,
                color=td.get("color"),
                font_size=td.get("font_size", 18),
                bold=td.get("bold", False),
                italic=td.get("italic", False),
                item_id=new_id(),
            )
            new_t.setSelected(True)

    # ── Context menu ──────────────────────────────────────────────────────────
    def contextMenuEvent(self, event):
        scene_pos = self.mapToScene(event.pos())
        items     = self.scene().items(scene_pos)

        # handles node body and label as well
        node = None
        for item in items:
            node = self.scene().resolve_node_item(item)
            if node:
                break

        edge  = next((i for i in items if isinstance(i, EdgeItem)), None)
        ctext = next((i for i in items if isinstance(i, CanvasTextItem)), None)
        group = next((i for i in items if isinstance(i, NodeGroup)), None)
        if not ctext:
            for i in items:
                if isinstance(i, QGraphicsTextItem) and isinstance(i.parentItem(), CanvasTextItem):
                    ctext = i.parentItem()
                    break
        # Nodes take priority over groups
        if node:
            group = None

        menu = QMenu(self)
        menu.setStyleSheet(self._menu_style())
        self.setStyleSheet(self._input_dialog_sytle_sheet())

        # ── Node context ──────────────────────────────────────────────────────
        if node:
            if not node.isSelected():
                self.scene().clearSelection()
                node.setSelected(True)
            n_selected = [n for n in self.scene().selectedItems()
                          if isinstance(n, NodeItem)]
            if len(n_selected) > 1:
                a_group = menu.addAction(f"⬡  Group {len(n_selected)} nodes  (Ctrl+G)")
                a_copy  = menu.addAction(f"📋  Copy {len(n_selected)} nodes  (Ctrl+C)")
                a_toggle_body = menu.addAction(f"⚪ Toggle node body for {len(n_selected)} nodes")
                menu.addSeparator()
                a_del   = menu.addAction(f"🗑️  Delete {len(n_selected)} nodes")
            else:
                a_conn  = menu.addAction("🔗  Connect from here")
                a_edit  = menu.addAction("✏️  Rename")
                a_col   = menu.addAction("🎨  Change colour")
                label_menu = menu.addMenu("🏷️ Label")
                a_toggle_body = menu.addAction("⚪ Toggle node body")
                act_left  = label_menu.addAction("Left")
                act_right = label_menu.addAction("Right")
                act_above = label_menu.addAction("Above")
                act_below = label_menu.addAction("Below")
                for act in [act_left, act_right, act_above, act_below]:
                    act.setCheckable(True)

                {
                    "left": act_left,
                    "right": act_right,
                    "above": act_above,
                    "below": act_below,
                }[node.node_label_dock].setChecked(True)
                menu.addSeparator()
                a_copy  = menu.addAction("📋  Copy  (Ctrl+C)")
                menu.addSeparator()
                a_del   = menu.addAction("🗑️  Delete node")
                a_group = None; a_conn  = locals().get("a_conn")

            ch = menu.exec_(event.globalPos())
            if ch is None:
                return
            if ch == locals().get("a_group"):
                name, ok = QInputDialog.getText(
                    self, "Group Name", "Name:", text="Group")
                if ok:
                    self.scene().group_nodes(n_selected, name=name or "Group")
            elif ch == locals().get("a_conn"):
                self.scene().start_connect(node)
            elif ch == locals().get("a_edit"):
                t, ok = QInputDialog.getText(self, "Rename", "New label:", text=node.label)
                if ok and t:
                    node.label = t; node._refresh_text()
                    self.scene().graph_changed.emit()
            elif ch == locals().get("a_col"):
                col = pick_color(
                    self,
                    node.color
                )

                if col:
                    node.color = col
                    node._refresh_text()
                    self.scene().update(); self.scene().graph_changed.emit()

                # c = QColorDialog.getColor(QColor(node.color), self)
                # if c.isValid():
                #     node.color = c.name(); node._refresh_text()
                #     self.scene().update(); self.scene().graph_changed.emit()
            elif ch == locals().get("act_left"):
                node.node_label_dock = "left"
                node._refresh_text()
                self.scene().graph_changed.emit()

            elif ch == locals().get("act_right"):
                node.node_label_dock = "right"
                node._refresh_text()
                self.scene().graph_changed.emit()

            elif ch == locals().get("act_above"):
                node.node_label_dock = "above"
                node._refresh_text()
                self.scene().graph_changed.emit()

            elif ch == locals().get("act_below"):
                node.node_label_dock = "below"
                node._refresh_text()
                self.scene().graph_changed.emit()

            elif ch == locals().get("a_toggle_body"):
                nodes = n_selected if len(n_selected) > 1 else [node]
                for n in nodes:

                    # First toggle creates an override
                    if getattr(n, "body_visible_override", None) is None:
                        n.body_visible_override = False

                    else:
                        n.body_visible_override = not n.body_visible_override

                    n.update()

                self.scene().graph_changed.emit()
                
            elif ch == a_copy:
                self._copy_selected()
            elif ch == a_del:
                for it in list(self.scene().selectedItems()):
                    if isinstance(it, NodeItem):
                        self.scene().delete_node(it)

        # ── Group context ─────────────────────────────────────────────────────
        elif group:
            a_rename  = menu.addAction("✏️  Rename group")
            a_col     = menu.addAction("🎨  Change group colour")
            a_resize = menu.addAction("⤢  Resize group")
            a_sel_mem = menu.addAction("☑️  Select all members")
            menu.addSeparator()
            a_ungroup = menu.addAction("⬡  Ungroup  (Ctrl+Shift+G)")
            ch = menu.exec_(event.globalPos())
            if ch is None:
                return
            if ch == a_rename:
                name, ok = QInputDialog.getText(
                    self, "Rename Group", "Name:", text=group.name)
                if ok and name:
                    group.name = name
                    group.update()
                    self.scene().graph_changed.emit()
            elif ch == a_col:

                c = pick_color(
                    self,
                    group.color
                )

                if c:
                    group.color = c
                    group.update()
                    self.scene().graph_changed.emit()
            elif ch == a_sel_mem:
                self.scene().clearSelection()
                for nid in group.member_ids:
                    node = self.scene().nodes.get(nid)
                    if node:
                        node.setSelected(True)
            elif ch == a_ungroup:
                self.scene().ungroup(group)
            elif ch == a_resize:
                self.scene().clearSelection()
                group.setSelected(True)
                group.enter_resize_mode()
                group.setFocus()

        # ── Canvas-text context ───────────────────────────────────────────────
        elif ctext:
            a_edit   = menu.addAction("✏️  Edit text")
            a_font   = menu.addMenu("🔤  Font size")
            size_acts = {}
            for sz in (10, 12, 14, 18, 24, 32, 48, 64):
                act = a_font.addAction(
                    ("✓ " if ctext.font_size == sz else "    ") + str(sz))
                size_acts[act] = sz
            a_bold   = menu.addAction("B  Bold")
            a_bold.setCheckable(True); a_bold.setChecked(ctext.bold)
            a_italic = menu.addAction("I  Italic")
            a_italic.setCheckable(True); a_italic.setChecked(ctext.italic)
            a_col    = menu.addAction("🎨  Colour")
            menu.addSeparator()
            a_copy   = menu.addAction("📋  Copy  (Ctrl+C)")
            a_del    = menu.addAction("🗑️  Delete text")

            ch = menu.exec_(event.globalPos())
            if ch is None:
                return
            if ch == a_edit:
                t, ok = QInputDialog.getMultiLineText(
                    self, "Edit Text", "Content:", ctext.text)
                if ok:
                    ctext.text = t; ctext._refresh()
                    self.scene().graph_changed.emit()
            elif ch in size_acts:
                ctext.font_size = size_acts[ch]; ctext._refresh()
                self.scene().graph_changed.emit()
            elif ch == a_bold:
                ctext.bold = a_bold.isChecked(); ctext._refresh()
                self.scene().graph_changed.emit()
            elif ch == a_italic:
                ctext.italic = a_italic.isChecked(); ctext._refresh()
                self.scene().graph_changed.emit()
            elif ch == a_col:
                col = pick_color(
                    self,
                    ctext.color
                )

                if col:
                    ctext.color = col
                    ctext._refresh()
                    self.scene().update()
                    self.scene().graph_changed.emit()
            elif ch == a_copy:
                if not ctext.isSelected():
                    self.scene().clearSelection()
                    ctext.setSelected(True)
                self._copy_selected()
            elif ch == a_del:
                self.scene().delete_text(ctext)

        # ── Edge context ──────────────────────────────────────────────────────
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
            a_sty  = menu.addMenu("〰  Line style")
            sty_acts = {
                a_sty.addAction(("✓ " if s == edge.line_style else "    ") + s.capitalize()): s
                for s in ("solid", "dashed", "dotted")
            }
            menu.addSeparator()
            a_del  = menu.addAction("🗑️  Delete edge")
            ch = menu.exec_(event.globalPos())
            if ch is None:
                return
            if ch == a_lbl:
                t, ok = QInputDialog.getText(self, "Edge Label", "Label:", text=edge.label)
                if ok:
                    edge.set_label(t); self.scene().graph_changed.emit()
            elif ch == a_col:
                col = pick_color(
                    self,
                    edge.color
                )

                if col:
                    edge.color = col
                    edge._refresh_label_text()
                    self.scene().update()
                    self.scene().graph_changed.emit()
            elif ch in dir_acts:
                edge.set_direction(dir_acts[ch]); self.scene().graph_changed.emit()
            elif ch in typ_acts:
                edge.set_edge_type(typ_acts[ch]); self.scene().graph_changed.emit()
            elif ch in sty_acts:
                edge.set_line_style(sty_acts[ch]); self.scene().graph_changed.emit()
            elif ch == a_del:
                self.scene().delete_edge(edge)

        # ── Empty canvas context ──────────────────────────────────────────────
        else:
            a_add   = menu.addAction("➕  Add node here")
            a_txt   = menu.addAction("🔤  Add text here")
            menu.addSeparator()
            sel_nodes = [i for i in self.scene().selectedItems()
                         if isinstance(i, (NodeItem, CanvasTextItem))]
            a_copy = None
            if sel_nodes:
                a_copy = menu.addAction(
                    f"📋  Copy selection ({len(sel_nodes)})  (Ctrl+C)")
            a_paste = menu.addAction("📋  Paste  (Ctrl+V)")

            ch = menu.exec_(event.globalPos())
            if ch is None:
                return
            if ch == a_add:
                lbl, ok = QInputDialog.getText(self, "New Node", "Label:")
                if ok and lbl:
                    self.scene().add_node(label=lbl, x=scene_pos.x(), y=scene_pos.y())
            elif ch == a_txt:
                txt, ok = QInputDialog.getMultiLineText(
                    self, "Add Text", "Content:", "Heading")
                if ok and txt.strip():
                    self.scene().add_text(text=txt, x=scene_pos.x(), y=scene_pos.y())
            elif a_copy and ch == a_copy:
                self._copy_selected()
            elif ch == a_paste:
                self._paste(scene_pos)

    def _menu_style(self):
        return (f"QMenu {{ background:{gc('BG_PANEL')}; color:{gc('TEXT_PRIMARY')};"
                f" border:1px solid {gc('BORDER')}; border-radius:6px; padding:4px; }}"
                f" QMenu::item {{ padding:6px 20px; border-radius:4px; }}"
                f" QMenu::item:selected {{ background:{gc('ACCENT')}; color:white; }}"
                f" QMenu::separator {{ background:{gc('BORDER')}; height:1px; margin:4px 8px; }}"
        )
    def _input_dialog_sytle_sheet(self):
        return (f"QInputDialog {{ "
                f"background:{gc('BG_PANEL')}; "
                f"color:{gc('TEXT_PRIMARY')}; "
                f"}}"

                f"QInputDialog QLabel {{ "
                f"color:{gc('TEXT_PRIMARY')}; "
                f"background:transparent; "
                f"}}"

                f"QInputDialog QLineEdit {{ "
                f"background:{gc('BG_CARD')}; "
                f"color:{gc('TEXT_PRIMARY')}; "
                f"border:1px solid {gc('BORDER')}; "
                f"border-radius:4px; "
                f"padding:4px; "
                f"}}"

                f"QInputDialog QPushButton {{ "
                f"background:{gc('BG_CARD')}; "
                f"color:{gc('TEXT_PRIMARY')}; "
                f"border:1px solid {gc('BORDER')}; "
                f"border-radius:4px; "
                f"padding:5px 14px; "
                f"}}"

                f"QInputDialog QPushButton:hover {{ "
                f"background:{gc('ACCENT')}; "
                f"color:white; "
                f"}}"

                f"QInputDialog QTextEdit {{ "
                f"background:{gc('BG_CARD')}; "
                f"color:{gc('TEXT_PRIMARY')}; "
                f"border:1px solid {gc('BORDER')}; "
                f"border-radius:4px; "
                f"padding:4px; "
                f"}}"

                f"QInputDialog QPlainTextEdit {{ "
                f"background:{gc('BG_CARD')}; "
                f"color:{gc('TEXT_PRIMARY')}; "
                f"border:1px solid {gc('BORDER')}; "
                f"border-radius:4px; "
                f"padding:4px; "
                f"}}"
                )
    def focusNextPrevChild(self, next):
        return False