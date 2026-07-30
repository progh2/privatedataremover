"""Main application window."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt, QThread
from PySide6.QtGui import QAction, QDragEnterEvent, QDropEvent, QKeySequence
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressDialog,
    QSplitter,
    QStatusBar,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from privatedataremover import __version__
from privatedataremover.core.adapters.base import BBox, DocumentAdapter, MaskSource, PiiType
from privatedataremover.core.adapters.factory import open_document, supported_extensions
from privatedataremover.core.export_utils import find_residual_in_xlsx, find_residual_texts
from privatedataremover.core.history import HistoryStack, restore_session, snapshot_from_session
from privatedataremover.core.pattern import find_similar_pages, page_fingerprint
from privatedataremover.core.pattern.apply import PatternProposal, SeedMask, build_pattern_items
from privatedataremover.core.pii import DetectionStatus, PII_TYPE_LABELS, new_id
from privatedataremover.core.pii.pipeline import AnalyzeResult
from privatedataremover.core.pii.session import DetectionSession
from privatedataremover.core.settings import AppSettings, load_settings, save_settings
from privatedataremover.ui.detection_panel import DetectionPanel
from privatedataremover.ui.export_dialog import RasterExportDialog
from privatedataremover.ui.pattern_dialog import PatternApplyDialog
from privatedataremover.ui.pdf_view import PdfPreview
from privatedataremover.ui.settings_dialog import SettingsDialog
from privatedataremover.ui.workers import AnalyzeWorker, ExportWorker, start_worker


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Private Data Remover")
        self.resize(1200, 760)
        self.setAcceptDrops(True)

        self.settings: AppSettings = load_settings()
        self.adapter: DocumentAdapter | None = None
        self.session = DetectionSession()
        self.history = HistoryStack()
        self._page_index = 0
        self._selected_id: str | None = None
        self._draw_mode = False
        self._ignore_region_mode = False
        self._last_pattern_id: str | None = None
        self._job_thread: QThread | None = None
        self._job_worker = None
        self._progress: QProgressDialog | None = None

        self.page_list = QListWidget()
        self.page_list.setMinimumWidth(140)
        self.page_list.currentRowChanged.connect(self._on_page_selected)

        self.preview = PdfPreview()
        self.preview.zoom_changed.connect(self._on_zoom_changed)
        self.preview.region_drawn.connect(self._on_region_drawn)
        self.preview.overlay_clicked.connect(self._on_overlay_clicked)

        self.detection_panel = DetectionPanel()
        self.detection_panel.set_refresh_callback(self._refresh_detection_ui)
        self.detection_panel.selection_changed.connect(self._on_detection_selected)
        self.detection_panel.confirm_requested.connect(self._confirm_item)
        self.detection_panel.ignore_requested.connect(self._ignore_item)
        self.detection_panel.cancel_requested.connect(self._cancel_item)
        self.detection_panel.confirm_all_requested.connect(self._confirm_all)
        self.detection_panel.cancel_type_requested.connect(self._cancel_type)
        self.detection_panel.ignore_type_requested.connect(self._ignore_type)

        splitter = QSplitter()
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(8, 8, 4, 8)
        left_layout.setSpacing(6)
        page_title = QLabel("페이지")
        page_font = page_title.font()
        page_font.setBold(True)
        page_title.setFont(page_font)
        left_layout.addWidget(page_title)
        left_layout.addWidget(self.page_list)
        splitter.addWidget(left)
        splitter.addWidget(self.preview)
        splitter.addWidget(self.detection_panel)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        splitter.setSizes([160, 720, 280])

        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(splitter)
        self.setCentralWidget(container)

        self._build_actions()
        self._build_menus()
        self._build_toolbar()
        self.setStatusBar(QStatusBar())
        self._update_status()

    def _build_actions(self) -> None:
        self.act_open = QAction("열기…", self)
        self.act_open.setShortcut(QKeySequence.StandardKey.Open)
        self.act_open.setToolTip("문서 열기 (Ctrl+O)")
        self.act_open.triggered.connect(self.open_file_dialog)

        self.act_safe_save = QAction("안전 저장…", self)
        self.act_safe_save.setEnabled(False)
        self.act_safe_save.setShortcut(QKeySequence.StandardKey.Save)
        self.act_safe_save.setToolTip("텍스트 삭제 + 검정 박스로 사본 저장 (Ctrl+S)")
        self.act_safe_save.triggered.connect(self.save_safe)

        self.act_raster_save = QAction("페이지 이미지화 후 PDF로 저장…", self)
        self.act_raster_save.setEnabled(False)
        self.act_raster_save.setToolTip("페이지 전체를 이미지로 구운 PDF 저장")
        self.act_raster_save.triggered.connect(self.save_rasterized)

        self.act_exit = QAction("종료", self)
        self.act_exit.setShortcut(QKeySequence.StandardKey.Quit)
        self.act_exit.triggered.connect(self.close)

        self.act_settings = QAction("설정…", self)
        self.act_settings.setToolTip("LLM·OCR 설정")
        self.act_settings.triggered.connect(self.open_settings)

        self.act_analyze = QAction("개인정보 분석", self)
        self.act_analyze.setShortcut("Ctrl+R")
        self.act_analyze.setToolTip("개인정보 분석 (Ctrl+R)")
        self.act_analyze.triggered.connect(self.run_analysis)

        self.act_draw = QAction("마스킹 그리기", self)
        self.act_draw.setCheckable(True)
        self.act_draw.setShortcut("M")
        self.act_draw.setToolTip("마스킹 그리기 (M)")
        self.act_draw.toggled.connect(self._toggle_draw_mode)

        self.act_ignore_region = QAction("무시 영역 그리기", self)
        self.act_ignore_region.setCheckable(True)
        self.act_ignore_region.setToolTip("드래그한 영역은 이후 탐지에서 제외됩니다.")
        self.act_ignore_region.toggled.connect(self._toggle_ignore_region_mode)

        self.act_apply_pattern = QAction("비슷한 페이지에 적용…", self)
        self.act_apply_pattern.setShortcut("Ctrl+Shift+A")
        self.act_apply_pattern.setToolTip("확정 마스크를 비슷한 페이지에 일괄 적용 (Ctrl+Shift+A)")
        self.act_apply_pattern.triggered.connect(self.apply_pattern_to_similar)

        self.act_rollback_pattern = QAction("마지막 패턴 적용 취소", self)
        self.act_rollback_pattern.triggered.connect(self.rollback_last_pattern)

        self.act_undo = QAction("실행 취소", self)
        self.act_undo.setShortcut(QKeySequence.StandardKey.Undo)
        self.act_undo.setToolTip("방금 한 작업 되돌리기 (Ctrl+Z)")
        self.act_undo.triggered.connect(self.undo)

        self.act_redo = QAction("다시 실행", self)
        self.act_redo.setShortcut(QKeySequence.StandardKey.Redo)
        self.act_redo.setToolTip("되돌린 작업 다시 실행 (Ctrl+Y)")
        self.act_redo.triggered.connect(self.redo)

        self.act_delete = QAction("선택 마스킹 삭제", self)
        self.act_delete.setShortcut(QKeySequence.StandardKey.Delete)
        self.act_delete.triggered.connect(self._delete_selected)

        self.act_clear_page = QAction("현재 페이지 마스킹 모두 지우기", self)
        self.act_clear_page.triggered.connect(self._clear_page_masks)

        self.act_zoom_in = QAction("확대", self)
        self.act_zoom_in.setShortcut(QKeySequence.StandardKey.ZoomIn)
        self.act_zoom_in.triggered.connect(lambda: self._bump_zoom(1.1))

        self.act_zoom_out = QAction("축소", self)
        self.act_zoom_out.setShortcut(QKeySequence.StandardKey.ZoomOut)
        self.act_zoom_out.triggered.connect(lambda: self._bump_zoom(1 / 1.1))

        self.act_prev = QAction("이전", self)
        self.act_prev.setShortcut(QKeySequence.StandardKey.MoveToPreviousPage)
        self.act_prev.setToolTip("이전 페이지")
        self.act_prev.triggered.connect(lambda: self._goto_page(self._page_index - 1))

        self.act_next = QAction("다음", self)
        self.act_next.setShortcut(QKeySequence.StandardKey.MoveToNextPage)
        self.act_next.setToolTip("다음 페이지")
        self.act_next.triggered.connect(lambda: self._goto_page(self._page_index + 1))

        self.act_about = QAction("정보", self)
        self.act_about.triggered.connect(self._about)

        self.chk_use_llm = QCheckBox("LLM")
        self.chk_use_llm.setToolTip("규칙 탐지에 더해 설정한 LLM으로 추가 분석합니다.")
        self.chk_use_ocr = QCheckBox("OCR")
        self.chk_use_ocr.setChecked(True)
        self.chk_use_ocr.setToolTip("텍스트가 적으면 Tesseract OCR을 사용합니다.")

    def _build_menus(self) -> None:
        file_menu = self.menuBar().addMenu("파일")
        file_menu.addAction(self.act_open)
        file_menu.addSeparator()
        file_menu.addAction(self.act_safe_save)
        file_menu.addAction(self.act_raster_save)
        file_menu.addSeparator()
        file_menu.addAction(self.act_exit)

        edit_menu = self.menuBar().addMenu("편집")
        edit_menu.addAction(self.act_undo)
        edit_menu.addAction(self.act_redo)
        edit_menu.addSeparator()
        edit_menu.addAction(self.act_draw)
        edit_menu.addAction(self.act_ignore_region)
        edit_menu.addSeparator()
        edit_menu.addAction(self.act_delete)
        edit_menu.addAction(self.act_clear_page)
        edit_menu.addSeparator()
        edit_menu.addAction(self.act_apply_pattern)
        edit_menu.addAction(self.act_rollback_pattern)

        view_menu = self.menuBar().addMenu("보기")
        view_menu.addAction(self.act_zoom_in)
        view_menu.addAction(self.act_zoom_out)
        view_menu.addSeparator()
        view_menu.addAction(self.act_prev)
        view_menu.addAction(self.act_next)

        tools_menu = self.menuBar().addMenu("도구")
        tools_menu.addAction(self.act_analyze)
        tools_menu.addAction(self.act_settings)

        help_menu = self.menuBar().addMenu("도움말")
        help_menu.addAction(self.act_about)

    def _build_toolbar(self) -> None:
        bar = QToolBar("메인")
        bar.setMovable(False)
        bar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.addToolBar(bar)
        # 파일
        bar.addAction(self.act_open)
        bar.addAction(self.act_safe_save)
        bar.addSeparator()
        # 분석
        bar.addAction(self.act_analyze)
        bar.addWidget(self.chk_use_ocr)
        bar.addWidget(self.chk_use_llm)
        bar.addSeparator()
        # 검토
        bar.addAction(self.act_undo)
        bar.addAction(self.act_draw)
        bar.addSeparator()
        # 탐색
        bar.addAction(self.act_prev)
        bar.addAction(self.act_next)
        bar.addSeparator()
        # 기타
        bar.addAction(self.act_settings)

    # --- file / drag-drop ---

    def open_file_dialog(self) -> None:
        exts = " ".join(f"*{e}" for e in supported_extensions())
        path, _ = QFileDialog.getOpenFileName(
            self,
            "문서 열기",
            "",
            f"Supported ({exts});;PDF (*.pdf);;Excel (*.xlsx *.xlsm);;HWPX (*.hwpx);;All Files (*)",
        )
        if path:
            self.open_document_path(Path(path))

    def _is_busy(self) -> bool:
        thread = self._job_thread
        if thread is None:
            return False
        try:
            return thread.isRunning()
        except RuntimeError:  # C++ object already deleted
            self._job_thread = None
            return False

    def open_document_path(self, path: Path) -> None:
        if self._is_busy():
            QMessageBox.information(
                self, "작업 중", "분석/저장이 끝날 때까지 기다려 주세요."
            )
            return
        try:
            if self.adapter is not None:
                self.adapter.close()
            self.adapter = open_document(path)
        except PermissionError as exc:
            QMessageBox.critical(self, "열기 실패", str(exc))
            return
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "열기 실패", f"{path}\n\n{exc}")
            return

        self.session.clear()
        self.history.clear()
        self._last_pattern_id = None
        self._selected_id = None
        self.page_list.clear()
        assert self.adapter is not None
        for unit in self.adapter.iter_units():
            item = QListWidgetItem(unit.label)
            item.setData(Qt.ItemDataRole.UserRole, unit.index)
            tips: list[str] = []
            meta = unit.meta or {}
            if meta.get("hidden"):
                tips.append("숨긴 시트" + (" (veryHidden)" if meta.get("very_hidden") else ""))
            if meta.get("hidden_row_count"):
                tips.append(f"숨긴 행 {meta['hidden_row_count']}개")
            if meta.get("hidden_col_count"):
                tips.append(f"숨긴 열 {meta['hidden_col_count']}개")
            if meta.get("section"):
                tips.append(str(meta["section"]))
            if meta.get("kind"):
                tips.append(str(meta["kind"]))
            if tips:
                item.setToolTip(" · ".join(tips))
            self.page_list.addItem(item)

        self.setWindowTitle(f"Private Data Remover — {path.name}")
        self.act_safe_save.setEnabled(True)
        self.act_raster_save.setEnabled(True)
        left_label = "페이지" if self.adapter.format_id == "pdf" else "시트/섹션"
        # Update left column caption if present
        for child in self.findChildren(QLabel):
            if child.text() in ("페이지", "시트/섹션"):
                child.setText(left_label)
                break
        if self.page_list.count():
            self.page_list.setCurrentRow(0)
        self._refresh_detection_ui()
        self._update_status()

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                suffix = Path(url.toLocalFile()).suffix.lower()
                if suffix in supported_extensions():
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802
        for url in event.mimeData().urls():
            local = url.toLocalFile()
            if Path(local).suffix.lower() in supported_extensions():
                self.open_document_path(Path(local))
                event.acceptProposedAction()
                return

    # --- analysis ---

    def _unit_count(self) -> int:
        if self.adapter is None:
            return 0
        return self.adapter.unit_count

    def run_analysis(self) -> None:
        if self.adapter is None or self._unit_count() == 0:
            QMessageBox.information(self, "분석", "먼저 문서를 열어 주세요.")
            return
        if self._is_busy():
            QMessageBox.information(self, "분석", "이미 작업이 진행 중입니다.")
            return
        path = self.adapter.path
        if path is None:
            QMessageBox.warning(self, "분석", "문서 경로를 알 수 없습니다.")
            return

        total = self._unit_count()
        progress = QProgressDialog(
            "개인정보를 분석하는 중…", "취소", 0, max(total, 1), self
        )
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.setAutoClose(False)
        progress.setAutoReset(False)
        progress.setValue(0)
        progress.show()
        self._progress = progress

        worker = AnalyzeWorker(
            path,
            self.settings,
            use_ocr=self.chk_use_ocr.isChecked(),
            use_llm=self.chk_use_llm.isChecked(),
        )
        # Lambda runs in the GUI thread and sets a plain bool; a queued slot
        # would never be delivered while worker.run() blocks its event loop.
        progress.canceled.connect(lambda: worker.request_cancel())
        worker.progress.connect(self._on_analyze_progress)
        worker.finished.connect(self._on_analyze_finished)
        worker.failed.connect(self._on_analyze_failed)

        self.act_analyze.setEnabled(False)
        self._start_job(worker)

    def _start_job(self, worker) -> None:
        """Start worker on a parented QThread; release refs only when it ends."""
        self._job_worker = worker
        thread = start_worker(worker, parent=self)
        thread.finished.connect(self._on_job_thread_finished)
        self._job_thread = thread

    def _on_job_thread_finished(self) -> None:
        thread = self._job_thread
        self._job_thread = None
        self._job_worker = None
        if thread is not None:
            thread.deleteLater()

    def _on_analyze_progress(self, current: int, total: int, message: str) -> None:
        progress = self._progress
        if progress is None:
            return
        if total > 0 and progress.maximum() != total:
            progress.setMaximum(total)
        # setValue() on a modal QProgressDialog processes events, so the
        # finished handler may run here and null out self._progress.
        progress.setValue(min(current, total))
        if self._progress is not progress:
            return
        progress.setLabelText(message)
        self.statusBar().showMessage(message, 0)

    def _on_analyze_finished(self, result: object) -> None:
        self._clear_job_ui()
        if not isinstance(result, AnalyzeResult):
            return
        if result.cancelled:
            if result.items:
                self._push_history("analyze")
                added = self.session.add_items(result.items)
                self._refresh_detection_ui()
                self._update_status()
                QMessageBox.information(
                    self,
                    "분석 취소",
                    f"취소되었습니다. 지금까지 찾은 후보 {added}건을 반영했습니다.",
                )
            else:
                self.statusBar().showMessage("분석이 취소되었습니다.", 4000)
            return

        self._push_history("analyze")
        added = self.session.add_items(result.items)
        msg_parts = [f"새 후보 {added}건 (전체 탐지 {len(result.items)}건)"]
        if result.notes:
            msg_parts.append(result.notes)
        if result.used_ocr:
            msg_parts.append(f"OCR 사용: {result.ocr_message or 'OK'}")
        elif self.chk_use_ocr.isChecked() and result.ocr_message:
            msg_parts.append(result.ocr_message)
        if result.llm_error:
            msg_parts.append(f"LLM 오류: {result.llm_error}")

        self._refresh_detection_ui()
        self._update_status()
        QMessageBox.information(self, "분석 완료", "\n".join(msg_parts))

    def _on_analyze_failed(self, message: str) -> None:
        self._clear_job_ui()
        QMessageBox.critical(self, "분석 실패", message)

    def _clear_job_ui(self) -> None:
        # Do NOT drop thread/worker refs here: the thread is still running at
        # this point and losing the last Python reference destroys the C++
        # QThread mid-flight, crashing the app. Refs are released in
        # _on_job_thread_finished once the thread has fully stopped.
        if self._progress is not None:
            self._progress.close()
            self._progress = None
        self.act_analyze.setEnabled(True)
        self.act_safe_save.setEnabled(self.adapter is not None)
        self.act_raster_save.setEnabled(self.adapter is not None)

    # --- detection actions ---

    def _refresh_detection_ui(self) -> None:
        # Re-entrancy guard: populate()/setCurrentRow can fire selection
        # signals that call back into this method and recurse until crash.
        if getattr(self, "_refreshing_ui", False):
            return
        self._refreshing_ui = True
        try:
            ptype = self.detection_panel.filter_pii_type()
            status_filter = self.detection_panel.filter_status_value()
            hide_terminal = status_filter == "active"
            status = (
                status_filter if isinstance(status_filter, DetectionStatus) else None
            )

            items = self.session.filtered(
                pii_type=ptype,
                status=status,
                hide_terminal=hide_terminal,
            )
            # When "active", show pending+confirmed
            if hide_terminal:
                items = [
                    i
                    for i in self.session.filtered(pii_type=ptype)
                    if i.status
                    in (DetectionStatus.PENDING, DetectionStatus.CONFIRMED)
                ]

            self.detection_panel.populate(items, self._selected_id)
            pending = sum(
                1 for i in self.session.items if i.status == DetectionStatus.PENDING
            )
            confirmed = sum(
                1 for i in self.session.items if i.status == DetectionStatus.CONFIRMED
            )
            self.detection_panel.set_summary(
                pending, confirmed, len(self.session.items)
            )
            page_items = [
                i
                for i in self.session.items
                if i.unit_index == self._page_index
                and i.status not in (DetectionStatus.IGNORED,)
            ]
            self.preview.set_overlays(page_items, self._selected_id)
        finally:
            self._refreshing_ui = False

    def _on_detection_selected(self, item_id: str) -> None:
        self._selected_id = item_id
        item = self.session.get(item_id)
        if item and item.unit_index != self._page_index:
            self.page_list.setCurrentRow(item.unit_index)
        else:
            self._refresh_detection_ui()

    def _on_overlay_clicked(self, item_id: str) -> None:
        self._selected_id = item_id
        item = self.session.get(item_id)
        if item is not None:
            panel = self.detection_panel
            # Make sure the clicked item is visible in the list: relax the
            # type filter (모든 유형), and the status filter if it hides it.
            ptype = panel.filter_pii_type()
            if ptype is not None and ptype != item.pii_type:
                panel.show_all_types()
            status_filter = panel.filter_status_value()
            hidden = (
                isinstance(status_filter, DetectionStatus)
                and status_filter != item.status
            ) or (
                status_filter == "active"
                and item.status
                not in (DetectionStatus.PENDING, DetectionStatus.CONFIRMED)
            )
            if hidden:
                panel.show_all_statuses()
        self._refresh_detection_ui()

    _HISTORY_LABELS = {
        "analyze": "분석",
        "pattern_apply": "패턴 적용",
        "pattern_rollback": "패턴 적용 취소",
        "confirm": "마스킹 확정",
        "ignore": "무시",
        "cancel": "마스킹 취소",
        "confirm_all": "모두 확정",
        "cancel_type": "유형 전체 취소",
        "ignore_type": "유형 무시",
        "ignore_region": "무시 영역 추가",
        "manual_mask": "수동 마스킹",
        "delete": "마스킹 삭제",
        "clear_page": "페이지 마스킹 지우기",
    }

    def _history_label(self, key: str) -> str:
        return self._HISTORY_LABELS.get(key, key or "작업")

    def _push_history(self, label: str = "") -> None:
        self.history.push(snapshot_from_session(self.session, label=label))

    def undo(self) -> None:
        current = snapshot_from_session(self.session)
        prev = self.history.undo(current)
        if prev is None:
            self.statusBar().showMessage("되돌릴 작업이 없습니다.", 2000)
            return
        # Carry the action name onto the redo snapshot so redo can show it.
        current.label = prev.label
        restore_session(self.session, prev)
        self._selected_id = None
        self._refresh_detection_ui()
        self._update_status()
        self.statusBar().showMessage(
            f"실행 취소: {self._history_label(prev.label)}", 3000
        )

    def redo(self) -> None:
        current = snapshot_from_session(self.session)
        nxt = self.history.redo(current)
        if nxt is None:
            self.statusBar().showMessage("다시 실행할 작업이 없습니다.", 2000)
            return
        restore_session(self.session, nxt)
        self._selected_id = None
        self._refresh_detection_ui()
        self._update_status()
        self.statusBar().showMessage(
            f"다시 실행: {self._history_label(nxt.label)}", 3000
        )

    def apply_pattern_to_similar(self) -> None:
        if self.adapter is None or self._unit_count() == 0:
            QMessageBox.information(self, "패턴", "먼저 문서를 열어 주세요.")
            return
        seeds = self.session.confirmed_on_page(self._page_index)
        if not seeds:
            QMessageBox.information(
                self,
                "패턴",
                "현재 단위에 확정/수동 마스킹이 없습니다.\n"
                "먼저 마스크를 그린 뒤 다시 시도하세요.",
            )
            return

        units = {u.index: u for u in self.adapter.iter_units()}
        fingerprints: dict[int, str] = {}
        for idx in units:
            spans = list(self.adapter.extract_spans(idx))
            fingerprints[idx] = page_fingerprint(spans, units[idx])

        similar = find_similar_pages(fingerprints, self._page_index)
        if not similar:
            QMessageBox.information(
                self,
                "패턴",
                "비슷한 페이지를 찾지 못했습니다.\n"
                "레이아웃이 다른 문서이거나 텍스트가 거의 없을 수 있습니다.",
            )
            return

        dlg = PatternApplyDialog(
            seed_index=self._page_index,
            seed_mask_count=len(seeds),
            similar=similar,
            parent=self,
        )
        if not dlg.exec():
            return
        targets = dlg.selected_pages()
        if not targets:
            return

        pattern_id = new_id()
        proposal = PatternProposal(
            pattern_id=pattern_id,
            seed_index=self._page_index,
            target_indices=targets,
            seeds=[
                SeedMask(
                    bbox=s.bbox,
                    pii_type=s.pii_type,
                    text=s.text,
                    mode=s.mode.value,
                )
                for s in seeds
            ],
            coord_mode=dlg.coord_mode(),
            scores={s.unit_index: s.score for s in similar},
        )
        items = build_pattern_items(proposal, units=units)
        self._push_history("pattern_apply")
        added = self.session.apply_pattern_items(items)
        self._last_pattern_id = pattern_id
        self._refresh_detection_ui()
        self._update_status()
        QMessageBox.information(
            self,
            "패턴 적용",
            f"{len(targets)}개 페이지에 마스크 {added}개를 적용했습니다.\n"
            "「마지막 패턴 적용 취소」또는 실행 취소로 되돌릴 수 있습니다.",
        )

    def rollback_last_pattern(self) -> None:
        if not self._last_pattern_id:
            QMessageBox.information(self, "패턴 취소", "취소할 패턴 적용이 없습니다.")
            return
        self._push_history("pattern_rollback")
        n = self.session.rollback_pattern(self._last_pattern_id)
        self._last_pattern_id = None
        self._refresh_detection_ui()
        self._update_status()
        self.statusBar().showMessage(f"패턴 마스크 {n}개 제거", 3000)

    def _next_selection_after(self, item_id: str) -> str | None:
        """Pick the item below (or above, at the end) for fast review flow."""
        ids = self.detection_panel.ordered_ids()
        if item_id not in ids:
            return self._selected_id
        idx = ids.index(item_id)
        if idx + 1 < len(ids):
            return ids[idx + 1]
        if idx > 0:
            return ids[idx - 1]
        return None

    def _confirm_item(self, item_id: str) -> None:
        self._push_history("confirm")
        nxt = self._next_selection_after(item_id)
        self.session.confirm(item_id)
        self._selected_id = nxt
        self._refresh_detection_ui()
        self._update_status()

    def _ignore_item(self, item_id: str) -> None:
        self._push_history("ignore")
        nxt = self._next_selection_after(item_id)
        self.session.ignore(item_id)
        self._selected_id = nxt
        self._refresh_detection_ui()
        self._update_status()

    def _cancel_item(self, item_id: str) -> None:
        self._push_history("cancel")
        nxt = self._next_selection_after(item_id)
        self.session.cancel_mask(item_id)
        self._selected_id = nxt
        self._refresh_detection_ui()
        self._update_status()

    def _confirm_all(self) -> None:
        self._push_history("confirm_all")
        n = self.session.confirm_all_pending()
        self._refresh_detection_ui()
        self._update_status()
        self.statusBar().showMessage(f"{n}건 마스킹 확정", 3000)

    @staticmethod
    def _coerce_pii_type(value) -> PiiType | None:
        """PiiType is a str Enum, so Signal(object) delivers it as plain str."""
        if value is None or isinstance(value, PiiType):
            return value
        try:
            return PiiType(value)
        except ValueError:
            return None

    def _cancel_type(self, ptype) -> None:
        ptype = self._coerce_pii_type(ptype)
        if ptype is None:
            item = self.session.get(self._selected_id) if self._selected_id else None
            if not item:
                QMessageBox.information(
                    self, "유형 취소", "유형 필터를 고르거나 항목을 선택하세요."
                )
                return
            ptype = item.pii_type
        self._push_history("cancel_type")
        n = self.session.cancel_by_type(ptype)
        self._refresh_detection_ui()
        self._update_status()
        label = PII_TYPE_LABELS.get(ptype, ptype.value)
        self.statusBar().showMessage(f"{label} {n}건 마스킹 취소", 3000)

    def _ignore_type(self, ptype) -> None:
        ptype = self._coerce_pii_type(ptype)
        if ptype is None:
            item = self.session.get(self._selected_id) if self._selected_id else None
            if not item:
                QMessageBox.information(
                    self, "유형 무시", "유형 필터를 고르거나 항목을 선택하세요."
                )
                return
            ptype = item.pii_type
        self._push_history("ignore_type")
        self.session.ignore_type(ptype)
        self._refresh_detection_ui()
        self._update_status()
        label = PII_TYPE_LABELS.get(ptype, ptype.value)
        self.statusBar().showMessage(f"{label} 유형을 무시합니다.", 3000)

    def _toggle_draw_mode(self, enabled: bool) -> None:
        if enabled and self.act_ignore_region.isChecked():
            self.act_ignore_region.blockSignals(True)
            self.act_ignore_region.setChecked(False)
            self.act_ignore_region.blockSignals(False)
            self._ignore_region_mode = False
        self._draw_mode = enabled
        self.preview.set_draw_mode(enabled or self._ignore_region_mode)
        if enabled:
            self.statusBar().showMessage("마스킹 그리기 모드: 드래그로 영역을 지정하세요.", 0)
        elif not self._ignore_region_mode:
            self.statusBar().showMessage("", 1)

    def _toggle_ignore_region_mode(self, enabled: bool) -> None:
        if enabled and self.act_draw.isChecked():
            self.act_draw.blockSignals(True)
            self.act_draw.setChecked(False)
            self.act_draw.blockSignals(False)
            self._draw_mode = False
        self._ignore_region_mode = enabled
        self.preview.set_draw_mode(enabled or self._draw_mode)
        if enabled:
            self.statusBar().showMessage(
                "무시 영역 모드: 드래그한 구간은 이후 분석에서 제외됩니다.", 0
            )
        elif not self._draw_mode:
            self.statusBar().showMessage("", 1)

    def _on_region_drawn(self, bbox_obj) -> None:
        try:
            if not isinstance(bbox_obj, BBox):
                return
            bbox = bbox_obj
            if self._ignore_region_mode:
                self._push_history("ignore_region")
                self.session.add_ignore_region(self._page_index, bbox)
                self.statusBar().showMessage(
                    f"무시 영역 추가 (페이지 {self._page_index + 1})", 3000
                )
                return
            self._push_history("manual_mask")
            item = self.session.add_manual(self._page_index, bbox)
            self._selected_id = item.id
            self._refresh_detection_ui()
            self._update_status()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "영역 처리 오류", str(exc))

    def _delete_selected(self) -> None:
        if not self._selected_id:
            return
        item = self.session.get(self._selected_id)
        if not item:
            return
        self._push_history("delete")
        if item.status == DetectionStatus.CONFIRMED:
            self.session.cancel_mask(item.id)
        elif item.source == MaskSource.MANUAL:
            self.session.remove_item(item.id)
        else:
            self.session.ignore(item.id)
        self._selected_id = None
        self._refresh_detection_ui()
        self._update_status()

    def _clear_page_masks(self) -> None:
        self._push_history("clear_page")
        n = self.session.clear_page_masks(self._page_index)
        self._refresh_detection_ui()
        self._update_status()
        self.statusBar().showMessage(f"페이지 마스킹 {n}개 지움", 3000)

    # --- navigation / zoom ---

    def _on_page_selected(self, row: int) -> None:
        if row < 0:
            return
        self._page_index = row
        self._render_current_page()
        self._refresh_detection_ui()

    def _goto_page(self, index: int) -> None:
        if self._unit_count() == 0:
            return
        index = max(0, min(index, self._unit_count() - 1))
        self.page_list.setCurrentRow(index)

    def _bump_zoom(self, factor: float) -> None:
        self.preview.set_scale(self.preview.scale * factor)

    def _on_zoom_changed(self, _scale: float) -> None:
        self._render_current_page()

    def _render_current_page(self) -> None:
        if self.adapter is None or self._unit_count() == 0:
            self.preview.clear_preview()
            return
        try:
            png = self.adapter.render_unit_preview(self._page_index, scale=self.preview.scale)
            self.preview.blockSignals(True)
            self.preview.show_png(png)
            self.preview.blockSignals(False)
            self.adapter.assert_original_untouched()
        except Exception as exc:  # noqa: BLE001
            self.preview.clear_preview(f"렌더 오류: {exc}")
        self._update_status()

    # --- settings / about ---

    def open_settings(self) -> None:
        dlg = SettingsDialog(self.settings, self)
        if dlg.exec():
            self.settings = dlg.result_settings()
            save_settings(self.settings)
            self._update_status()
            QMessageBox.information(self, "설정", "설정을 저장했습니다.")

    def _about(self) -> None:
        QMessageBox.about(
            self,
            "Private Data Remover",
            f"Private Data Remover {__version__}\n\n"
            "PDF 개인정보 탐지·마스킹 데스크탑 앱\n"
            "Apache-2.0 · docs/PRD.md 참고",
        )

    def _confirm_before_export(self) -> bool:
        pending = sum(
            1 for i in self.session.items if i.status == DetectionStatus.PENDING
        )
        masks = self.session.masks()
        if not masks:
            reply = QMessageBox.question(
                self,
                "저장",
                "확정된 마스킹이 없습니다. 그대로 사본을 저장할까요?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            return reply == QMessageBox.StandardButton.Yes
        if pending:
            reply = QMessageBox.warning(
                self,
                "미확정 항목",
                f"아직 확정하지 않은 탐지 항목이 {pending}건 있습니다.\n"
                "확정된 마스킹만 반영하여 저장할까요?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            return reply == QMessageBox.StandardButton.Yes
        return True

    def _default_save_name(self, suffix: str) -> str:
        if self.adapter and self.adapter.path:
            stem = self.adapter.path.stem
            ext = self.adapter.path.suffix or ".pdf"
            if self.adapter.format_id == "pdf" or suffix.startswith("_raster"):
                return f"{stem}{suffix}.pdf"
            return f"{stem}{suffix}{ext}"
        return f"redacted{suffix}.pdf"

    def _verify_export(self, dest: Path) -> None:
        forbidden = [
            m.label
            for m in self.session.masks()
            if m.label and m.label not in ("(수동 마스킹)", "(패턴 마스킹)")
        ]
        for item in self.session.items:
            if item.status == DetectionStatus.CONFIRMED and item.text.strip():
                if item.text not in ("(수동 마스킹)", "(패턴 마스킹)"):
                    forbidden.append(item.text.strip())
        hits = find_residual_texts(dest, forbidden)
        if hits:
            sample = ", ".join(repr(h.text[:30]) for h in hits[:5])
            QMessageBox.warning(
                self,
                "잔존 텍스트 경고",
                f"저장본에서 확정 문자열 {len(hits)}건이 여전히 추출됩니다.\n"
                f"예: {sample}\n\n"
                "「페이지 이미지화 후 PDF로 저장」을 권장합니다.",
            )
        else:
            self.statusBar().showMessage("잔존 텍스트 검사 통과", 4000)

    def save_safe(self) -> None:
        if self.adapter is None or self._unit_count() == 0:
            return
        if self._is_busy():
            QMessageBox.information(self, "저장", "이미 작업이 진행 중입니다.")
            return
        if not self._confirm_before_export():
            return
        src = self.adapter.path
        if src is None:
            return
        fmt = self.adapter.format_id
        filters = {
            "pdf": "PDF Files (*.pdf)",
            "xlsx": "Excel Files (*.xlsx)",
            "hwpx": "HWPX Files (*.hwpx)",
        }.get(fmt, "All Files (*)")
        path, _ = QFileDialog.getSaveFileName(
            self,
            "안전 저장",
            self._default_save_name("_safe"),
            filters,
        )
        if not path:
            return
        self._start_export(src, Path(path), mode="safe", dpi=150, verify_fmt=fmt)

    def save_rasterized(self) -> None:
        if self.adapter is None or self._unit_count() == 0:
            return
        if self._is_busy():
            QMessageBox.information(self, "저장", "이미 작업이 진행 중입니다.")
            return
        if not self._confirm_before_export():
            return
        src = self.adapter.path
        if src is None:
            return
        opts = RasterExportDialog(self)
        if not opts.exec():
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "페이지 이미지화 후 PDF로 저장",
            self._default_save_name("_raster"),
            "PDF Files (*.pdf)",
        )
        if not path:
            return
        self._start_export(
            src, Path(path), mode="raster", dpi=opts.dpi(), verify_fmt="pdf"
        )

    def _start_export(
        self,
        src: Path,
        dest: Path,
        *,
        mode: str,
        dpi: int,
        verify_fmt: str,
    ) -> None:
        progress = QProgressDialog(
            "안전 저장 중…" if mode == "safe" else "이미지화 저장 중…",
            None,
            0,
            0,
            self,
        )
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.show()
        self._progress = progress
        self._export_verify_fmt = verify_fmt

        worker = ExportWorker(
            src,
            dest,
            self.session.masks(),
            mode=mode,
            dpi=dpi,
        )
        worker.progress.connect(lambda msg: progress.setLabelText(msg))
        worker.finished.connect(self._on_export_finished)
        worker.failed.connect(self._on_export_failed)

        self.act_analyze.setEnabled(False)
        self.act_safe_save.setEnabled(False)
        self.act_raster_save.setEnabled(False)
        self._start_job(worker)

    def _on_export_finished(self, dest_obj: object) -> None:
        self._clear_job_ui()
        dest = Path(str(dest_obj))
        try:
            if getattr(self, "_export_verify_fmt", "") == "pdf":
                self._verify_export(dest)
            if self.adapter is not None:
                self.adapter.assert_original_untouched()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "저장 후 검사", str(exc))
        QMessageBox.information(self, "저장 완료", f"저장했습니다:\n{dest}")

    def _on_export_failed(self, message: str) -> None:
        self._clear_job_ui()
        QMessageBox.critical(self, "저장 실패", message)

    def _update_status(self) -> None:
        self.act_undo.setEnabled(self.history.can_undo)
        self.act_redo.setEnabled(self.history.can_redo)
        provider = self.settings.provider.value
        local = "로컬 전용" if self.settings.local_only else "외부 API 허용"
        pending = sum(1 for i in self.session.items if i.status == DetectionStatus.PENDING)
        masked = len(self.session.masks())
        fmt = self.adapter.format_id if self.adapter else "-"
        if self._unit_count():
            page = f"{self._page_index + 1}/{self._unit_count()}"
            zoom = f"{self.preview.scale * 100:.0f}%"
            text = (
                f"{fmt} · 단위 {page} · 확대 {zoom} · 대기 {pending} · 마스킹 {masked} · "
                f"LLM: {provider} · {local}"
            )
        else:
            text = f"문서 없음 · LLM: {provider} · {local}"
        self.statusBar().showMessage(text)

    def closeEvent(self, event) -> None:  # noqa: N802
        if self._is_busy():
            QMessageBox.information(
                self,
                "작업 중",
                "분석/저장이 진행 중입니다. 취소하거나 완료된 뒤 종료해 주세요.",
            )
            event.ignore()
            return
        if self.adapter is not None:
            self.adapter.close()
        super().closeEvent(event)


def run_app() -> int:
    """Start the Qt event loop."""
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:
        print(
            "PySide6 is required. Install with: pip install -e .\n"
            "See README.md for full setup.",
            file=sys.stderr,
        )
        return 1

    app = QApplication(sys.argv)
    app.setApplicationName("Private Data Remover")
    app.setOrganizationName("privatedataremover")
    app.setApplicationVersion(__version__)

    window = MainWindow()
    window.show()
    return app.exec()
