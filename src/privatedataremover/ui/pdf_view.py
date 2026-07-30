"""PDF preview with overlay highlights and manual mask drawing."""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QColor, QImage, QMouseEvent, QPainter, QPen, QPixmap, QWheelEvent
from PySide6.QtWidgets import QLabel, QScrollArea, QSizePolicy

from privatedataremover.core.adapters.base import BBox, PiiType
from privatedataremover.core.pii import DetectionItem, DetectionStatus

TYPE_COLORS: dict[PiiType, QColor] = {
    PiiType.PHONE: QColor(220, 80, 60, 90),
    PiiType.EMAIL: QColor(60, 120, 220, 90),
    PiiType.RRN: QColor(180, 40, 40, 110),
    PiiType.NAME: QColor(80, 160, 80, 90),
    PiiType.ADDRESS: QColor(160, 120, 40, 90),
    PiiType.CUSTOM: QColor(40, 40, 40, 120),
}


def _color_for(item: DetectionItem) -> QColor:
    base = TYPE_COLORS.get(item.pii_type, QColor(120, 80, 180, 90))
    if item.status == DetectionStatus.CONFIRMED:
        return QColor(0, 0, 0, 200)
    if item.status in (DetectionStatus.IGNORED, DetectionStatus.CANCELLED):
        return QColor(160, 160, 160, 50)
    return base


EMPTY_PREVIEW_HINT = "문서를 열거나 여기로 끌어다 놓으세요. (PDF / Excel / HWPX)"


class OverlayLabel(QLabel):
    """Pixmap label that paints detection overlays and supports drag-rect."""

    region_drawn = Signal(object)  # BBox in page coordinates (object avoids Qt metatype crash)
    overlay_clicked = Signal(str)  # item id

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._scale = 1.25
        self._items: list[DetectionItem] = []
        self._draw_mode = False
        self._origin: QPoint | None = None
        self._current: QRect | None = None
        self._selected_id: str | None = None

    def set_scale(self, scale: float) -> None:
        self._scale = scale

    def set_items(self, items: list[DetectionItem], selected_id: str | None = None) -> None:
        self._items = items
        self._selected_id = selected_id
        self.update()

    def set_draw_mode(self, enabled: bool) -> None:
        self._draw_mode = enabled
        self.setCursor(
            Qt.CursorShape.CrossCursor if enabled else Qt.CursorShape.ArrowCursor
        )

    def paintEvent(self, event) -> None:  # noqa: N802
        super().paintEvent(event)
        if self.pixmap() is None or self.pixmap().isNull():
            return
        painter = QPainter(self)
        pix = self.pixmap()
        # Centered pixmap offset inside label
        ox = (self.width() - pix.width()) // 2
        oy = (self.height() - pix.height()) // 2

        for item in self._items:
            if item.bbox.x1 <= item.bbox.x0:
                continue
            rect = QRect(
                int(item.bbox.x0 * self._scale) + ox,
                int(item.bbox.y0 * self._scale) + oy,
                int((item.bbox.x1 - item.bbox.x0) * self._scale),
                int((item.bbox.y1 - item.bbox.y0) * self._scale),
            )
            color = _color_for(item)
            painter.fillRect(rect, color)
            pen = QPen(QColor(0, 0, 0) if item.status == DetectionStatus.CONFIRMED else color.darker(150))
            if item.id == self._selected_id:
                pen.setWidth(3)
                pen.setColor(QColor(0, 90, 200))
            else:
                pen.setWidth(1)
            painter.setPen(pen)
            painter.drawRect(rect)

        if self._current is not None:
            painter.setPen(QPen(QColor(0, 0, 0), 2, Qt.PenStyle.DashLine))
            painter.fillRect(self._current, QColor(0, 0, 0, 80))
            painter.drawRect(self._current)
        painter.end()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton:
            return
        if self._draw_mode:
            self._origin = event.position().toPoint()
            self._current = QRect(self._origin, self._origin)
            self.update()
            return
        # Hit-test overlays (top-most last item wins)
        hit = self._hit_test(event.position().toPoint())
        if hit:
            self.overlay_clicked.emit(hit)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._draw_mode and self._origin is not None:
            self._current = QRect(self._origin, event.position().toPoint()).normalized()
            self.update()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._draw_mode and self._origin is not None and self._current is not None:
            bbox = self._rect_to_page_bbox(self._current)
            self._origin = None
            self._current = None
            self.update()
            if bbox and (bbox.x1 - bbox.x0) > 2 and (bbox.y1 - bbox.y0) > 2:
                self.region_drawn.emit(bbox)
            return
        super().mouseReleaseEvent(event)

    def _pixmap_offset(self) -> tuple[int, int]:
        pix = self.pixmap()
        if pix is None or pix.isNull():
            return 0, 0
        return (self.width() - pix.width()) // 2, (self.height() - pix.height()) // 2

    def _rect_to_page_bbox(self, rect: QRect) -> BBox | None:
        ox, oy = self._pixmap_offset()
        inv = 1.0 / self._scale if self._scale else 1.0
        x0 = (rect.left() - ox) * inv
        y0 = (rect.top() - oy) * inv
        x1 = (rect.right() - ox) * inv
        y1 = (rect.bottom() - oy) * inv
        return BBox(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))

    def _hit_test(self, pos: QPoint) -> str | None:
        ox, oy = self._pixmap_offset()
        for item in reversed(self._items):
            if item.status in (DetectionStatus.IGNORED, DetectionStatus.CANCELLED):
                continue
            rect = QRect(
                int(item.bbox.x0 * self._scale) + ox,
                int(item.bbox.y0 * self._scale) + oy,
                int((item.bbox.x1 - item.bbox.x0) * self._scale),
                int((item.bbox.y1 - item.bbox.y0) * self._scale),
            )
            if rect.contains(pos):
                return item.id
        return None


class PdfPreview(QScrollArea):
    """Scrollable page image with zoom, overlay, and draw mode."""

    zoom_changed = Signal(float)
    region_drawn = Signal(object)  # BBox (object avoids Qt metatype crash)
    overlay_clicked = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label = OverlayLabel()
        self._label.setText(EMPTY_PREVIEW_HINT)
        self.setWidget(self._label)
        self._scale = 1.25
        self._png: bytes | None = None
        self._label.region_drawn.connect(self.region_drawn.emit)
        self._label.overlay_clicked.connect(self.overlay_clicked.emit)

    @property
    def scale(self) -> float:
        return self._scale

    def set_scale(self, scale: float) -> None:
        self._scale = max(0.25, min(scale, 4.0))
        self._label.set_scale(self._scale)
        self.zoom_changed.emit(self._scale)

    def set_draw_mode(self, enabled: bool) -> None:
        self._label.set_draw_mode(enabled)

    def set_overlays(
        self, items: list[DetectionItem], selected_id: str | None = None
    ) -> None:
        self._label.set_items(items, selected_id)

    def clear_preview(self, message: str = EMPTY_PREVIEW_HINT) -> None:
        self._png = None
        self._label.setPixmap(QPixmap())
        self._label.setText(message)
        self._label.set_items([])

    def show_png(self, png: bytes) -> None:
        self._png = png
        self._label.setText("")
        image = QImage.fromData(png, "PNG")
        if image.isNull():
            self._label.setText("미리보기를 표시할 수 없습니다.")
            return
        self._label.set_scale(self._scale)
        self._label.setPixmap(QPixmap.fromImage(image))
        self._label.adjustSize()

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            factor = 1.1 if delta > 0 else (1 / 1.1)
            self.set_scale(self._scale * factor)
            event.accept()
            return
        super().wheelEvent(event)
