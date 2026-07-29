"""PDF adapter (PyMuPDF). Stub until M1/M4 implementation issues land."""

from __future__ import annotations

from pathlib import Path
from typing import Iterator, Sequence

from privatedataremover.core.adapters.base import (
    DocumentAdapter,
    DocumentUnit,
    ExtractedSpan,
    MaskRegion,
)


class PdfAdapter(DocumentAdapter):
    """PDF implementation of DocumentAdapter."""

    format_id = "pdf"

    def __init__(self) -> None:
        self._path: Path | None = None
        self._doc = None

    def open(self, path: Path) -> None:
        self._path = Path(path)
        # Lazy: full PyMuPDF wiring in milestone M1/M4 issues.
        raise NotImplementedError("PdfAdapter.open — see GitHub issue: PDF open & preview")

    def close(self) -> None:
        self._doc = None
        self._path = None

    def iter_units(self) -> Iterator[DocumentUnit]:
        raise NotImplementedError

    def extract_spans(self, unit_index: int) -> Sequence[ExtractedSpan]:
        raise NotImplementedError

    def render_unit_preview(self, unit_index: int, scale: float = 1.0) -> bytes:
        raise NotImplementedError

    def export_safe(
        self,
        dest: Path,
        masks: Sequence[MaskRegion],
        *,
        text_remove: bool = True,
        draw_black_boxes: bool = True,
    ) -> None:
        raise NotImplementedError

    def export_rasterized(
        self,
        dest: Path,
        masks: Sequence[MaskRegion],
        *,
        dpi: int = 200,
    ) -> None:
        raise NotImplementedError
