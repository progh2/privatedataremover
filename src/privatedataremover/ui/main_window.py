"""Main application window."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QDragEnterEvent, QDropEvent, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QStatusBar,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from privatedataremover import __version__
from privatedataremover.core.adapters.pdf import PdfAdapter
from privatedataremover.core.settings import AppSettings, load_settings, save_settings
from privatedataremover.ui.pdf_view import PdfPreview
from privatedataremover.ui.settings_dialog import SettingsDialog


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Private Data Remover")
        self.resize(1100, 720)
        self.setAcceptDrops(True)

        self.settings: AppSettings = load_settings()
        self.adapter = PdfAdapter()
        self._page_index = 0

        self.page_list = QListWidget()
        self.page_list.setMinimumWidth(140)
        self.page_list.currentRowChanged.connect(self._on_page_selected)

        self.preview = PdfPreview()
        self.preview.zoom_changed.connect(self._on_zoom_changed)

        self.side_panel = QLabel(
            "탐지 목록\n\n(M2에서 개인정보 유형·필터가 표시됩니다.)"
        )
        self.side_panel.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.side_panel.setWordWrap(True)
        self.side_panel.setMinimumWidth(200)
        self.side_panel.setStyleSheet("padding: 8px;")

        splitter = QSplitter()
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(QLabel("페이지"))
        left_layout.addWidget(self.page_list)
        splitter.addWidget(left)
        splitter.addWidget(self.preview)
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.addWidget(self.side_panel)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        splitter.setSizes([160, 700, 220])

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

    def _build_menus(self) -> None:
        file_menu = self.menuBar().addMenu("파일")
        file_menu.addAction(self.act_open)
        file_menu.addSeparator()
        file_menu.addAction(self.act_safe_save)
        file_menu.addAction(self.act_raster_save)
        file_menu.addSeparator()
        file_menu.addAction(self.act_exit)

        view_menu = self.menuBar().addMenu("보기")
        view_menu.addAction(self.act_zoom_in)
        view_menu.addAction(self.act_zoom_out)
        view_menu.addSeparator()
        view_menu.addAction(self.act_prev)
        view_menu.addAction(self.act_next)

        tools_menu = self.menuBar().addMenu("도구")
        tools_menu.addAction(self.act_settings)

        help_menu = self.menuBar().addMenu("도움말")
        help_menu.addAction(self.act_about)

    def _build_toolbar(self) -> None:
        bar = QToolBar("메인")
        bar.setMovable(False)
        self.addToolBar(bar)
        bar.addAction(self.act_open)
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

        self.page_list.clear()
        for unit in self.adapter.iter_units():
            item = QListWidgetItem(unit.label)
            item.setData(Qt.ItemDataRole.UserRole, unit.index)
            self.page_list.addItem(item)

        self.setWindowTitle(f"Private Data Remover — {path.name}")
        export_ready = False  # M4
        self.act_safe_save.setEnabled(export_ready)
        self.act_raster_save.setEnabled(export_ready)
        if self.page_list.count():
            self.page_list.setCurrentRow(0)
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

    # --- navigation / zoom ---

    def _on_page_selected(self, row: int) -> None:
        if row < 0:
            return
        self._page_index = row
        self._render_current_page()

    def _goto_page(self, index: int) -> None:
        if self.adapter.page_count == 0:
            return
        index = max(0, min(index, self.adapter.page_count - 1))
        self.page_list.setCurrentRow(index)

    def _bump_zoom(self, factor: float) -> None:
        self.preview.set_scale(self.preview.scale * factor)

    def _on_zoom_changed(self, _scale: float) -> None:
        # Ctrl+wheel already updated scale; re-render from PDF for sharpness.
        self._render_current_page()

    def _render_current_page(self) -> None:
        if self.adapter.page_count == 0:
            self.preview.clear_preview()
            return
        try:
            png = self.adapter.render_unit_preview(self._page_index, scale=self.preview.scale)
            # Avoid feedback loop: show without emitting zoom
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
            "저장 기능은 마일스톤 M4에서 구현됩니다.",
        )

    def _update_status(self) -> None:
        provider = self.settings.llm_provider.value
        local = "로컬 전용" if self.settings.local_only else "외부 API 허용"
        if self.adapter.page_count:
            page = f"{self._page_index + 1}/{self.adapter.page_count}"
            zoom = f"{self.preview.scale * 100:.0f}%"
            text = f"페이지 {page} · 확대 {zoom} · LLM: {provider} · {local}"
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
