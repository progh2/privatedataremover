"""PDF adapter implemented with PyMuPDF."""

from __future__ import annotations

from pathlib import Path
from typing import Iterator, Sequence

from privatedataremover.core.adapters.base import (
    BBox,
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
        self._doc = None  # fitz.Document | None
        self._original_mtime: float | None = None

    @property
    def path(self) -> Path | None:
        return self._path

    @property
    def page_count(self) -> int:
        if self._doc is None:
            return 0
        return self._doc.page_count

    def open(self, path: Path) -> None:
        import fitz

        path = Path(path)
        if not path.is_file():
            raise FileNotFoundError(path)
        self.close()
        doc = fitz.open(path)
        if doc.is_encrypted:
            # Try empty password; otherwise fail clearly.
            if not doc.authenticate(""):
                doc.close()
                raise PermissionError("암호로 보호된 PDF는 현재 지원하지 않습니다.")
        self._doc = doc
        self._path = path
        self._original_mtime = path.stat().st_mtime

    def close(self) -> None:
        if self._doc is not None:
            self._doc.close()
        self._doc = None
        self._path = None
        self._original_mtime = None

    def assert_original_untouched(self) -> None:
        if self._path is None or self._original_mtime is None:
            return
        current = self._path.stat().st_mtime
        if current != self._original_mtime:
            raise RuntimeError(f"원본 PDF가 변경되었습니다: {self._path}")

    def iter_units(self) -> Iterator[DocumentUnit]:
        self._require_doc()
        for i, page in enumerate(self._doc):  # type: ignore[union-attr]
            rect = page.rect
            yield DocumentUnit(
                index=i,
                label=f"페이지 {i + 1}",
                width=float(rect.width),
                height=float(rect.height),
            )

    def extract_spans(self, unit_index: int) -> Sequence[ExtractedSpan]:
        self._require_doc()
        page = self._doc[unit_index]  # type: ignore[index]
        spans: list[ExtractedSpan] = []
        # "dict" gives block/line/span with bboxes
        data = page.get_text("dict")
        for block in data.get("blocks", []):
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = (span.get("text") or "").strip()
                    if not text:
                        continue
                    x0, y0, x1, y1 = span["bbox"]
                    spans.append(
                        ExtractedSpan(
                            unit_index=unit_index,
                            text=text,
                            bbox=BBox(float(x0), float(y0), float(x1), float(y1)),
                            from_ocr=False,
                        )
                    )
        return spans

    def render_unit_preview(self, unit_index: int, scale: float = 1.0) -> bytes:
        import fitz

        self._require_doc()
        page = self._doc[unit_index]  # type: ignore[index]
        matrix = fitz.Matrix(scale, scale)
        pix = page.get_pixmap(matrix=matrix, alpha=False)
        return pix.tobytes("png")

    def export_safe(
        self,
        dest: Path,
        masks: Sequence[MaskRegion],
        *,
        text_remove: bool = True,
        draw_black_boxes: bool = True,
    ) -> None:
        raise NotImplementedError("안전 저장은 마일스톤 M4에서 구현됩니다.")

    def export_rasterized(
        self,
        dest: Path,
        masks: Sequence[MaskRegion],
        *,
        dpi: int = 200,
    ) -> None:
        raise NotImplementedError("이미지화 저장은 마일스톤 M4에서 구현됩니다.")

    def _require_doc(self) -> None:
        if self._doc is None:
            raise RuntimeError("PDF가 열려 있지 않습니다.")
