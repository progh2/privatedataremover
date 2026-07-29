"""Future Excel (.xlsx) adapter — hidden sheets, hidden rows/cols, cell PII."""

from __future__ import annotations

from pathlib import Path
from typing import Iterator, Sequence

from privatedataremover.core.adapters.base import (
    DocumentAdapter,
    DocumentUnit,
    ExtractedSpan,
    MaskRegion,
)


class XlsxAdapter(DocumentAdapter):
    """Placeholder for M6 Excel support (PRD F-EXT-02)."""

    format_id = "xlsx"

    def open(self, path: Path) -> None:
        raise NotImplementedError("Excel adapter planned for milestone M6")

    def close(self) -> None:
        return

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
