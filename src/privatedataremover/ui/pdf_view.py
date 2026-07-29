"""PDF page preview widget."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QImage, QPixmap, QWheelEvent
from PySide6.QtWidgets import QLabel, QScrollArea, QSizePolicy


class PdfPreview(QScrollArea):
    """Scrollable page image with zoom via Ctrl+wheel."""

    zoom_changed = Signal(float)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label = QLabel("PDF를 열어 주세요.")
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setWidget(self._label)
        self._scale = 1.25
        self._png: bytes | None = None

    @property
    def scale(self) -> float:
        return self._scale

    def set_scale(self, scale: float) -> None:
        self._scale = max(0.25, min(scale, 4.0))
        # Parent re-renders from PDF at the new scale for sharp output.
        self.zoom_changed.emit(self._scale)

    def clear_preview(self, message: str = "PDF를 열어 주세요.") -> None:
        self._png = None
        self._label.setPixmap(QPixmap())
        self._label.setText(message)

    def show_png(self, png: bytes) -> None:
        self._png = png
        self._label.setText("")
        self._apply_pixmap(png)

    def _apply_pixmap(self, png: bytes) -> None:
        image = QImage.fromData(png, "PNG")
        if image.isNull():
            self._label.setText("미리보기를 표시할 수 없습니다.")
            return
        pix = QPixmap.fromImage(image)
        self._label.setPixmap(pix)
        self._label.adjustSize()

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            factor = 1.1 if delta > 0 else (1 / 1.1)
            # Parent window should re-render at new scale; emit only.
            self.set_scale(self._scale * factor)
            event.accept()
            return
        super().wheelEvent(event)
