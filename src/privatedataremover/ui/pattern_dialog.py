"""Dialog to preview and apply pattern masks to similar pages."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from privatedataremover.core.pattern.apply import CoordMode
from privatedataremover.core.pattern import PageSimilarity


class PatternApplyDialog(QDialog):
    def __init__(
        self,
        *,
        seed_index: int,
        seed_mask_count: int,
        similar: list[PageSimilarity],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("비슷한 페이지에 마스킹 적용")
        self.resize(480, 420)

        self._similar = similar
        info = QLabel(
            f"시드: 페이지 {seed_index + 1} · 확정/수동 마스크 {seed_mask_count}개\n"
            f"유사 페이지 {len(similar)}개를 찾았습니다. 적용할 페이지를 선택하세요."
        )
        info.setWordWrap(True)

        self.list = QListWidget()
        for sim in similar:
            item = QListWidgetItem(
                f"페이지 {sim.unit_index + 1}  (유사도 {sim.score:.0%})"
            )
            item.setData(Qt.ItemDataRole.UserRole, sim.unit_index)
            item.setCheckState(Qt.CheckState.Checked)
            self.list.addItem(item)

        self.radio_abs = QRadioButton("절대 좌표 (동일 위치)")
        self.radio_rel = QRadioButton("상대 좌표 (페이지 비율)")
        self.radio_abs.setChecked(True)

        select_row = QHBoxLayout()
        btn_all = QCheckBox("모두 선택")
        btn_all.setChecked(True)

        def toggle_all(checked: bool) -> None:
            state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
            for i in range(self.list.count()):
                self.list.item(i).setCheckState(state)

        btn_all.toggled.connect(toggle_all)

        form = QFormLayout()
        form.addRow(info)
        form.addRow(btn_all)
        form.addRow(self.list)
        form.addRow("좌표 모드", self.radio_abs)
        form.addRow("", self.radio_rel)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def selected_pages(self) -> list[int]:
        pages: list[int] = []
        for i in range(self.list.count()):
            item = self.list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                pages.append(int(item.data(Qt.ItemDataRole.UserRole)))
        return pages

    def coord_mode(self) -> CoordMode:
        return CoordMode.ABSOLUTE if self.radio_abs.isChecked() else CoordMode.RELATIVE
