"""Right-hand detection list with type filter and actions."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QToolButton,
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
        self.setMinimumWidth(280)

        self._title = QLabel("탐지 목록")
        title_font = self._title.font()
        title_font.setBold(True)
        self._title.setFont(title_font)

        self._summary = QLabel("")
        self._summary.setStyleSheet("color: #666;")
        self._summary.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )

        self.filter_type = QComboBox()
        self.filter_type.setToolTip("유형 필터")
        self.filter_type.addItem("모든 유형", None)
        for ptype, label in PII_TYPE_LABELS.items():
            self.filter_type.addItem(label, ptype)
        self.filter_type.currentIndexChanged.connect(self._emit_refresh_needed)

        self.filter_status = QComboBox()
        self.filter_status.setToolTip("상태 필터")
        self.filter_status.addItem("활성만", "active")
        self.filter_status.addItem("모든 상태", "all")
        for st, label in STATUS_LABELS.items():
            self.filter_status.addItem(label, st)
        self.filter_status.currentIndexChanged.connect(self._emit_refresh_needed)

        self.list = QListWidget()
        self.list.currentItemChanged.connect(self._on_current_changed)

        # Primary review actions (horizontal)
        self.btn_confirm = QPushButton("확정")
        self.btn_confirm.setToolTip("선택 항목 마스킹 확정")
        self.btn_ignore = QPushButton("무시")
        self.btn_ignore.setToolTip("선택 항목 무시 (다음으로 이동)")
        self.btn_cancel = QPushButton("취소")
        self.btn_cancel.setToolTip("선택 마스킹 취소")

        self.btn_confirm.clicked.connect(self._confirm)
        self.btn_ignore.clicked.connect(self._ignore)
        self.btn_cancel.clicked.connect(self._cancel)

        # Batch actions as menu (keep QAction/QPushButton aliases for tests)
        self.act_confirm_all = self._make_batch_action(
            "대기 항목 모두 확정",
            lambda: self.confirm_all_requested.emit(),
        )
        self.act_cancel_type = self._make_batch_action(
            "선택 유형 전부 취소", self._cancel_type
        )
        self.act_ignore_type = self._make_batch_action(
            "선택 유형 무시", self._ignore_type
        )

        batch_menu = QMenu(self)
        batch_menu.addAction(self.act_confirm_all)
        batch_menu.addAction(self.act_cancel_type)
        batch_menu.addAction(self.act_ignore_type)

        self.btn_batch = QToolButton()
        self.btn_batch.setText("일괄 ▾")
        self.btn_batch.setToolTip("일괄 작업")
        self.btn_batch.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.btn_batch.setMenu(batch_menu)
        self.btn_batch.setSizePolicy(
            self.btn_confirm.sizePolicy().horizontalPolicy(),
            self.btn_confirm.sizePolicy().verticalPolicy(),
        )

        # Aliases so existing tests can call .click() on batch actions
        self.btn_confirm_all = _ActionClickProxy(self.act_confirm_all)
        self.btn_cancel_type = _ActionClickProxy(self.act_cancel_type)
        self.btn_ignore_type = _ActionClickProxy(self.act_ignore_type)

        self._refresh_needed_cb = None

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.addWidget(self._title)
        header.addWidget(self._summary, stretch=1)

        filters = QHBoxLayout()
        filters.setContentsMargins(0, 0, 0, 0)
        filters.setSpacing(6)
        filters.addWidget(self.filter_type, stretch=1)
        filters.addWidget(self.filter_status, stretch=1)

        primary = QHBoxLayout()
        primary.setContentsMargins(0, 0, 0, 0)
        primary.setSpacing(6)
        primary.addWidget(self.btn_confirm, stretch=1)
        primary.addWidget(self.btn_ignore, stretch=1)
        primary.addWidget(self.btn_cancel, stretch=1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        layout.addLayout(header)
        layout.addLayout(filters)
        layout.addWidget(self.list, stretch=1)
        layout.addLayout(primary)
        layout.addWidget(self.btn_batch)

        self._hint = QLabel("항목을 선택하거나 뷰어에서 박스를 클릭하세요.")
        self._hint.setWordWrap(True)
        self._hint.setStyleSheet("color: #666;")
        layout.addWidget(self._hint)

        self.set_summary(0, 0, 0)

    @staticmethod
    def _make_batch_action(text: str, slot) -> object:
        from PySide6.QtGui import QAction

        act = QAction(text)
        # triggered(bool) — ignore the checked arg so Signal.emit() stays clean
        act.triggered.connect(lambda _checked=False: slot())
        return act

    def set_refresh_callback(self, cb) -> None:
        self._refresh_needed_cb = cb

    def set_summary(self, pending: int, confirmed: int, total: int) -> None:
        if total <= 0:
            self._summary.setText("")
            return
        self._summary.setText(f"대기 {pending} · 확정 {confirmed}")

    def _emit_refresh_needed(self) -> None:
        if self._refresh_needed_cb:
            self._refresh_needed_cb()

    def filter_pii_type(self) -> PiiType | None:
        return self.filter_type.currentData()

    def filter_status_value(self):
        return self.filter_status.currentData()

    def show_all_types(self) -> None:
        """Switch the type filter to 모든 유형 (fires refresh callback)."""
        if self.filter_type.currentIndex() != 0:
            self.filter_type.setCurrentIndex(0)

    def show_all_statuses(self) -> None:
        """Switch the status filter to 모든 상태 (fires refresh callback)."""
        idx = self.filter_status.findData("all")
        if idx >= 0 and self.filter_status.currentIndex() != idx:
            self.filter_status.setCurrentIndex(idx)

    def populate(self, items: list[DetectionItem], selected_id: str | None = None) -> None:
        self.list.blockSignals(True)
        self.list.clear()
        select_row = -1
        for i, item in enumerate(items):
            text = (
                f"p{item.unit_index + 1} · {item.type_label} · {item.snippet}\n"
                f"{item.source_label} · {item.status_label} · {item.confidence:.0%}"
            )
            lw = QListWidgetItem(text)
            lw.setData(Qt.ItemDataRole.UserRole, item.id)
            self.list.addItem(lw)
            if selected_id and item.id == selected_id:
                select_row = i
        # Keep signals blocked while restoring the selection: emitting
        # selection_changed here re-enters the main window's refresh and
        # recurses back into populate() until the stack overflows.
        if select_row >= 0:
            self.list.setCurrentRow(select_row)
            self.list.scrollToItem(self.list.item(select_row))
        self.list.blockSignals(False)

    def current_id(self) -> str | None:
        item = self.list.currentItem()
        if not item:
            return None
        return item.data(Qt.ItemDataRole.UserRole)

    def ordered_ids(self) -> list[str]:
        """Item ids in current display order (top to bottom)."""
        return [
            self.list.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(self.list.count())
        ]

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
        ptype = self.filter_pii_type()
        if ptype is None:
            self.cancel_type_requested.emit(None)
        else:
            self.cancel_type_requested.emit(ptype)

    def _ignore_type(self) -> None:
        ptype = self.filter_pii_type()
        self.ignore_type_requested.emit(ptype)


class _ActionClickProxy:
    """Thin stand-in so tests can call ``.click()`` on menu-backed batch actions."""

    def __init__(self, action) -> None:
        self._action = action

    def click(self) -> None:
        self._action.trigger()
