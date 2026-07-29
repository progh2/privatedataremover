"""Export option dialogs."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)


class RasterExportDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("페이지 이미지화 후 PDF로 저장")
        self.dpi_combo = QComboBox()
        for dpi in (150, 200, 300):
            self.dpi_combo.addItem(f"{dpi} DPI", dpi)
        self.dpi_combo.setCurrentIndex(1)

        form = QFormLayout()
        form.addRow(
            QLabel(
                "각 페이지를 이미지로 변환한 PDF를 만듭니다.\n"
                "텍스트 레이어가 없어 검색·복사가 되지 않습니다."
            )
        )
        form.addRow("해상도", self.dpi_combo)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def dpi(self) -> int:
        return int(self.dpi_combo.currentData())
