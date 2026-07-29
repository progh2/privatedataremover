"""Right-hand detection list with type filter and actions."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from privatedataremover.core.adapters.base import PiiType
from privatedataremover.core.pii import (
    DetectionItem,
    DetectionStatus,
    PII_TYPE_LABELS,
    STATUS_LABELS,
)


class DetectionPanel(QWidget):
    selection_changed = Signal(str)
    confirm_requested = Signal(str)
    ignore_requested = Signal(str)
    cancel_requested = Signal(str)
    confirm_all_requested = Signal()
    cancel_type_requested = Signal(object)  # PiiType
    ignore_type_requested = Signal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumWidth(260)

        self.filter_type = QComboBox()
        self.filter_type.addItem("모든 유형", None)
        for ptype, label in PII_TYPE_LABELS.items():
            self.filter_type.addItem(label, ptype)
        self.filter_type.currentIndexChanged.connect(self._emit_refresh_needed)

        self.filter_status = QComboBox()
        self.filter_status.addItem("활성만", "active")
        self.filter_status.addItem("모든 상태", "all")
        for st, label in STATUS_LABELS.items():
            self.filter_status.addItem(label, st)
        self.filter_status.currentIndexChanged.connect(self._emit_refresh_needed)

        self.list = QListWidget()
        self.list.currentItemChanged.connect(self._on_current_changed)

        self.btn_confirm = QPushButton("마스킹 확정")
        self.btn_ignore = QPushButton("무시")
        self.btn_cancel = QPushButton("마스킹 취소")
        self.btn_confirm_all = QPushButton("대기 항목 모두 확정")
        self.btn_cancel_type = QPushButton("선택 유형 전부 취소")
        self.btn_ignore_type = QPushButton("선택 유형 무시")

        self.btn_confirm.clicked.connect(self._confirm)
        self.btn_ignore.clicked.connect(self._ignore)
        self.btn_cancel.clicked.connect(self._cancel)
        self.btn_confirm_all.clicked.connect(self.confirm_all_requested.emit)
        self.btn_cancel_type.clicked.connect(self._cancel_type)
        self.btn_ignore_type.clicked.connect(self._ignore_type)

        self._refresh_needed_cb = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.addWidget(QLabel("탐지 목록"))
        layout.addWidget(QLabel("유형 필터"))
        layout.addWidget(self.filter_type)
        layout.addWidget(QLabel("상태 필터"))
        layout.addWidget(self.filter_status)
        layout.addWidget(self.list, stretch=1)

        for btn in (
            self.btn_confirm,
            self.btn_ignore,
            self.btn_cancel,
            self.btn_confirm_all,
            self.btn_cancel_type,
            self.btn_ignore_type,
        ):
            layout.addWidget(btn)

        self._hint = QLabel("항목을 선택하거나 뷰어에서 박스를 클릭하세요.")
        self._hint.setWordWrap(True)
        layout.addWidget(self._hint)

    def set_refresh_callback(self, cb) -> None:
        self._refresh_needed_cb = cb

    def _emit_refresh_needed(self) -> None:
        if self._refresh_needed_cb:
            self._refresh_needed_cb()

    def filter_pii_type(self) -> PiiType | None:
        return self.filter_type.currentData()

    def filter_status_value(self):
        return self.filter_status.currentData()

    def populate(self, items: list[DetectionItem], selected_id: str | None = None) -> None:
        self.list.blockSignals(True)
        self.list.clear()
        select_row = -1
        for i, item in enumerate(items):
            text = (
                f"[p{item.unit_index + 1}] {item.type_label} · {item.snippet}\n"
                f"{item.source_label} · {item.status_label} · {item.confidence:.0%}"
            )
            lw = QListWidgetItem(text)
            lw.setData(Qt.ItemDataRole.UserRole, item.id)
            self.list.addItem(lw)
            if selected_id and item.id == selected_id:
                select_row = i
        self.list.blockSignals(False)
        if select_row >= 0:
            self.list.setCurrentRow(select_row)

    def current_id(self) -> str | None:
        item = self.list.currentItem()
        if not item:
            return None
        return item.data(Qt.ItemDataRole.UserRole)

    def _on_current_changed(self, current: QListWidgetItem | None, _prev) -> None:
        if current:
            self.selection_changed.emit(current.data(Qt.ItemDataRole.UserRole))

    def _confirm(self) -> None:
        cid = self.current_id()
        if cid:
            self.confirm_requested.emit(cid)

    def _ignore(self) -> None:
        cid = self.current_id()
        if cid:
            self.ignore_requested.emit(cid)

    def _cancel(self) -> None:
        cid = self.current_id()
        if cid:
            self.cancel_requested.emit(cid)

    def _cancel_type(self) -> None:
        # Prefer filter type; else infer from selection via parent callback using signal object
        ptype = self.filter_pii_type()
        if ptype is None:
            # Parent should resolve from selection; emit None and let main window use selected item type
            self.cancel_type_requested.emit(None)
        else:
            self.cancel_type_requested.emit(ptype)

    def _ignore_type(self) -> None:
        ptype = self.filter_pii_type()
        self.ignore_type_requested.emit(ptype)
