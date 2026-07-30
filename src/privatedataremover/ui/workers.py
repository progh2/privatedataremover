"""Background workers so long jobs do not block the Qt UI thread."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal

from privatedataremover.core.adapters.base import MaskRegion
from privatedataremover.core.adapters.factory import open_document
from privatedataremover.core.pii.pipeline import AnalyzeResult, analyze_document
from privatedataremover.core.settings import AppSettings


class AnalyzeWorker(QObject):
    """Open a private adapter copy and analyze off the UI thread."""

    progress = Signal(int, int, str)  # current, total, message
    finished = Signal(object)  # AnalyzeResult
    failed = Signal(str)

    def __init__(
        self,
        path: Path,
        settings: AppSettings,
        *,
        use_ocr: bool,
        use_llm: bool,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._path = Path(path)
        self._settings = settings
        self._use_ocr = use_ocr
        self._use_llm = use_llm
        self._cancel = False

    def request_cancel(self) -> None:
        self._cancel = True

    def run(self) -> None:
        adapter = None
        try:
            adapter = open_document(self._path)
            result = analyze_document(
                adapter,
                self._settings,
                use_ocr=self._use_ocr,
                use_llm=self._use_llm,
                on_progress=lambda cur, tot, msg: self.progress.emit(cur, tot, msg),
                should_cancel=lambda: self._cancel,
            )
            self.finished.emit(result)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))
        finally:
            if adapter is not None:
                try:
                    adapter.close()
                except Exception:  # noqa: BLE001
                    pass


class ExportWorker(QObject):
    """Export safe or rasterized output on a background thread."""

    finished = Signal(object)  # Path
    failed = Signal(str)
    progress = Signal(str)

    def __init__(
        self,
        path: Path,
        dest: Path,
        masks: list[MaskRegion],
        *,
        mode: str,
        dpi: int = 150,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._path = Path(path)
        self._dest = Path(dest)
        self._masks = list(masks)
        self._mode = mode
        self._dpi = dpi

    def run(self) -> None:
        adapter = None
        try:
            self.progress.emit("문서 여는 중…")
            adapter = open_document(self._path)
            if self._mode == "safe":
                self.progress.emit("안전 저장 중…")
                adapter.export_safe(self._dest, self._masks)
            elif self._mode == "raster":
                self.progress.emit("페이지 이미지화 저장 중…")
                adapter.export_rasterized(self._dest, self._masks, dpi=self._dpi)
            else:
                raise ValueError(f"Unknown export mode: {self._mode}")
            self.finished.emit(self._dest)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))
        finally:
            if adapter is not None:
                try:
                    adapter.close()
                except Exception:  # noqa: BLE001
                    pass


def start_worker(
    worker: QObject, *, parent: QObject | None = None, slot_name: str = "run"
) -> QThread:
    """Move worker to a new QThread, start it, auto-quit when finished/failed.

    Give the thread a parent so it is not garbage-collected (and its C++
    object destroyed) while still running — that kills the whole process.
    """
    thread = QThread(parent)
    worker.moveToThread(thread)
    thread.started.connect(getattr(worker, slot_name))

    def _cleanup() -> None:
        thread.quit()

    if hasattr(worker, "finished"):
        worker.finished.connect(_cleanup)
    if hasattr(worker, "failed"):
        worker.failed.connect(_cleanup)
    thread.finished.connect(worker.deleteLater)
    thread.start()
    return thread
