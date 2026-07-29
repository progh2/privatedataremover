"""Main application window."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QDragEnterEvent, QDropEvent, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
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
from privatedataremover.core.adapters.base import BBox, MaskSource, PiiType
from privatedataremover.core.adapters.pdf import PdfAdapter
from privatedataremover.core.history import HistoryStack, restore_session, snapshot_from_session
from privatedataremover.core.pattern import find_similar_pages, page_fingerprint
from privatedataremover.core.pattern.apply import PatternProposal, SeedMask, build_pattern_items
from privatedataremover.core.pii import DetectionStatus, new_id
from privatedataremover.core.pii.pipeline import analyze_document
from privatedataremover.core.pii.session import DetectionSession
from privatedataremover.core.settings import AppSettings, load_settings, save_settings
from privatedataremover.ui.detection_panel import DetectionPanel
from privatedataremover.ui.pattern_dialog import PatternApplyDialog
from privatedataremover.ui.pdf_view import PdfPreview
from privatedataremover.ui.settings_dialog import SettingsDialog


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Private Data Remover")
        self.resize(1200, 760)
        self.setAcceptDrops(True)

        self.settings: AppSettings = load_settings()
        self.adapter = PdfAdapter()
        self.session = DetectionSession()
        self.history = HistoryStack()
        self._page_index = 0
        self._selected_id: str | None = None
        self._draw_mode = False
        self._ignore_region_mode = False
        self._last_pattern_id: str | None = None

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
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(QLabel("페이지"))
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
        layout.setContentsMargins(4, 4, 4, 4)
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
        self.act_open.triggered.connect(self.open_file_dialog)

        self.act_safe_save = QAction("안전 저장…", self)
        self.act_safe_save.setEnabled(False)
        self.act_safe_save.setToolTip("M4에서 구현 예정")
        self.act_safe_save.triggered.connect(self._not_ready_export)

        self.act_raster_save = QAction("페이지 이미지화 후 PDF로 저장…", self)
        self.act_raster_save.setEnabled(False)
        self.act_raster_save.setToolTip("M4에서 구현 예정")
        self.act_raster_save.triggered.connect(self._not_ready_export)

        self.act_exit = QAction("종료", self)
        self.act_exit.setShortcut(QKeySequence.StandardKey.Quit)
        self.act_exit.triggered.connect(self.close)

        self.act_settings = QAction("설정…", self)
        self.act_settings.triggered.connect(self.open_settings)

        self.act_analyze = QAction("개인정보 분석", self)
        self.act_analyze.setShortcut("Ctrl+R")
        self.act_analyze.triggered.connect(self.run_analysis)

        self.act_draw = QAction("마스킹 그리기", self)
        self.act_draw.setCheckable(True)
        self.act_draw.setShortcut("M")
        self.act_draw.toggled.connect(self._toggle_draw_mode)

        self.act_ignore_region = QAction("무시 영역 그리기", self)
        self.act_ignore_region.setCheckable(True)
        self.act_ignore_region.setToolTip("드래그한 영역은 이후 탐지에서 제외됩니다.")
        self.act_ignore_region.toggled.connect(self._toggle_ignore_region_mode)

        self.act_apply_pattern = QAction("비슷한 페이지에 적용…", self)
        self.act_apply_pattern.setShortcut("Ctrl+Shift+A")
        self.act_apply_pattern.triggered.connect(self.apply_pattern_to_similar)

        self.act_rollback_pattern = QAction("마지막 패턴 적용 취소", self)
        self.act_rollback_pattern.triggered.connect(self.rollback_last_pattern)

        self.act_undo = QAction("실행 취소", self)
        self.act_undo.setShortcut(QKeySequence.StandardKey.Undo)
        self.act_undo.triggered.connect(self.undo)

        self.act_redo = QAction("다시 실행", self)
        self.act_redo.setShortcut(QKeySequence.StandardKey.Redo)
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

        self.act_prev = QAction("이전 페이지", self)
        self.act_prev.setShortcut(QKeySequence.StandardKey.MoveToPreviousPage)
        self.act_prev.triggered.connect(lambda: self._goto_page(self._page_index - 1))

        self.act_next = QAction("다음 페이지", self)
        self.act_next.setShortcut(QKeySequence.StandardKey.MoveToNextPage)
        self.act_next.triggered.connect(lambda: self._goto_page(self._page_index + 1))

        self.act_about = QAction("정보", self)
        self.act_about.triggered.connect(self._about)

        self.chk_use_llm = QCheckBox("LLM 사용")
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
        self.addToolBar(bar)
        bar.addAction(self.act_open)
        bar.addSeparator()
        bar.addAction(self.act_analyze)
        bar.addWidget(self.chk_use_ocr)
        bar.addWidget(self.chk_use_llm)
        bar.addSeparator()
        bar.addAction(self.act_undo)
        bar.addAction(self.act_redo)
        bar.addAction(self.act_draw)
        bar.addAction(self.act_ignore_region)
        bar.addAction(self.act_apply_pattern)
        bar.addAction(self.act_delete)
        bar.addSeparator()
        bar.addAction(self.act_prev)
        bar.addAction(self.act_next)
        bar.addSeparator()
        bar.addAction(self.act_zoom_out)
        bar.addAction(self.act_zoom_in)
        bar.addSeparator()
        bar.addAction(self.act_settings)

    # --- file / drag-drop ---

    def open_file_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "PDF 열기",
            "",
            "PDF Files (*.pdf);;All Files (*)",
        )
        if path:
            self.open_pdf(Path(path))

    def open_pdf(self, path: Path) -> None:
        try:
            self.adapter.open(path)
        except PermissionError as exc:
            QMessageBox.critical(self, "PDF 열기 실패", str(exc))
            return
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "PDF 열기 실패", f"{path}\n\n{exc}")
            return

        self.session.clear()
        self.history.clear()
        self._last_pattern_id = None
        self._selected_id = None
        self.page_list.clear()
        for unit in self.adapter.iter_units():
            item = QListWidgetItem(unit.label)
            item.setData(Qt.ItemDataRole.UserRole, unit.index)
            self.page_list.addItem(item)

        self.setWindowTitle(f"Private Data Remover — {path.name}")
        if self.page_list.count():
            self.page_list.setCurrentRow(0)
        self._refresh_detection_ui()
        self._update_status()

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.toLocalFile().lower().endswith(".pdf"):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802
        for url in event.mimeData().urls():
            local = url.toLocalFile()
            if local.lower().endswith(".pdf"):
                self.open_pdf(Path(local))
                event.acceptProposedAction()
                return

    # --- analysis ---

    def run_analysis(self) -> None:
        if self.adapter.page_count == 0:
            QMessageBox.information(self, "분석", "먼저 PDF를 열어 주세요.")
            return

        progress = QProgressDialog("개인정보를 분석하는 중…", "취소", 0, 0, self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.show()
        QApplication.processEvents()

        try:
            result = analyze_document(
                self.adapter,
                self.settings,
                use_ocr=self.chk_use_ocr.isChecked(),
                use_llm=self.chk_use_llm.isChecked(),
            )
        except Exception as exc:  # noqa: BLE001
            progress.close()
            QMessageBox.critical(self, "분석 실패", str(exc))
            return
        progress.close()

        self._push_history("analyze")
        added = self.session.add_items(result.items)
        msg_parts = [f"새 후보 {added}건 (전체 탐지 {len(result.items)}건)"]
        if result.used_ocr:
            msg_parts.append(f"OCR 사용: {result.ocr_message or 'OK'}")
        elif self.chk_use_ocr.isChecked() and result.ocr_message:
            msg_parts.append(result.ocr_message)
        if result.llm_error:
            msg_parts.append(f"LLM 오류: {result.llm_error}")

        self._refresh_detection_ui()
        self._update_status()
        QMessageBox.information(self, "분석 완료", "\n".join(msg_parts))

    # --- detection actions ---

    def _refresh_detection_ui(self) -> None:
        ptype = self.detection_panel.filter_pii_type()
        status_filter = self.detection_panel.filter_status_value()
        hide_terminal = status_filter == "active"
        status = status_filter if isinstance(status_filter, DetectionStatus) else None

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
                if i.status in (DetectionStatus.PENDING, DetectionStatus.CONFIRMED)
            ]

        self.detection_panel.populate(items, self._selected_id)
        page_items = [
            i
            for i in self.session.items
            if i.unit_index == self._page_index
            and i.status not in (DetectionStatus.IGNORED,)
        ]
        self.preview.set_overlays(page_items, self._selected_id)

    def _on_detection_selected(self, item_id: str) -> None:
        self._selected_id = item_id
        item = self.session.get(item_id)
        if item and item.unit_index != self._page_index:
            self.page_list.setCurrentRow(item.unit_index)
        else:
            self._refresh_detection_ui()

    def _on_overlay_clicked(self, item_id: str) -> None:
        self._selected_id = item_id
        self._refresh_detection_ui()

    def _push_history(self, label: str = "") -> None:
        self.history.push(snapshot_from_session(self.session, label=label))

    def undo(self) -> None:
        current = snapshot_from_session(self.session)
        prev = self.history.undo(current)
        if prev is None:
            self.statusBar().showMessage("되돌릴 작업이 없습니다.", 2000)
            return
        restore_session(self.session, prev)
        self._selected_id = None
        self._refresh_detection_ui()
        self._update_status()

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

    def apply_pattern_to_similar(self) -> None:
        if self.adapter.page_count == 0:
            QMessageBox.information(self, "패턴", "먼저 PDF를 열어 주세요.")
            return
        seeds = self.session.confirmed_on_page(self._page_index)
        if not seeds:
            QMessageBox.information(
                self,
                "패턴",
                "현재 페이지에 확정/수동 마스킹이 없습니다.\n"
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

    def _confirm_item(self, item_id: str) -> None:
        self._push_history("confirm")
        self.session.confirm(item_id)
        self._refresh_detection_ui()
        self._update_status()

    def _ignore_item(self, item_id: str) -> None:
        self._push_history("ignore")
        self.session.ignore(item_id)
        self._refresh_detection_ui()
        self._update_status()

    def _cancel_item(self, item_id: str) -> None:
        self._push_history("cancel")
        self.session.cancel_mask(item_id)
        self._refresh_detection_ui()
        self._update_status()

    def _confirm_all(self) -> None:
        self._push_history("confirm_all")
        n = self.session.confirm_all_pending()
        self._refresh_detection_ui()
        self._update_status()
        self.statusBar().showMessage(f"{n}건 마스킹 확정", 3000)

    def _cancel_type(self, ptype: PiiType | None) -> None:
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
        self.statusBar().showMessage(f"{ptype.value} {n}건 마스킹 취소", 3000)

    def _ignore_type(self, ptype: PiiType | None) -> None:
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

    def _on_region_drawn(self, bbox: BBox) -> None:
        if self._ignore_region_mode:
            self._push_history("ignore_region")
            self.session.add_ignore_region(self._page_index, bbox)
            self.statusBar().showMessage("무시 영역을 추가했습니다.", 3000)
            return
        self._push_history("manual_mask")
        item = self.session.add_manual(self._page_index, bbox)
        self._selected_id = item.id
        self._refresh_detection_ui()
        self._update_status()

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
        if self.adapter.page_count == 0:
            return
        index = max(0, min(index, self.adapter.page_count - 1))
        self.page_list.setCurrentRow(index)

    def _bump_zoom(self, factor: float) -> None:
        self.preview.set_scale(self.preview.scale * factor)

    def _on_zoom_changed(self, _scale: float) -> None:
        self._render_current_page()

    def _render_current_page(self) -> None:
        if self.adapter.page_count == 0:
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

    def _not_ready_export(self) -> None:
        QMessageBox.information(
            self,
            "준비 중",
            "저장 기능은 마일스톤 M4에서 구현됩니다.\n"
            f"현재 확정 마스크: {len(self.session.masks())}개",
        )

    def _update_status(self) -> None:
        provider = self.settings.llm_provider.value
        local = "로컬 전용" if self.settings.local_only else "외부 API 허용"
        pending = sum(1 for i in self.session.items if i.status == DetectionStatus.PENDING)
        masked = len(self.session.masks())
        if self.adapter.page_count:
            page = f"{self._page_index + 1}/{self.adapter.page_count}"
            zoom = f"{self.preview.scale * 100:.0f}%"
            text = (
                f"페이지 {page} · 확대 {zoom} · 대기 {pending} · 마스킹 {masked} · "
                f"LLM: {provider} · {local}"
            )
        else:
            text = f"문서 없음 · LLM: {provider} · {local}"
        self.statusBar().showMessage(text)

    def closeEvent(self, event) -> None:  # noqa: N802
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
