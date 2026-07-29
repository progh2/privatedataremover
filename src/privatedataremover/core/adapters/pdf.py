"""PDF adapter implemented with PyMuPDF."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Iterator, Sequence

from privatedataremover.core.adapters.base import (
    BBox,
    DocumentAdapter,
    DocumentUnit,
    ExtractedSpan,
    MaskRegion,
)
from privatedataremover.core.export_utils import TempWorkspace, file_sha256


class PdfAdapter(DocumentAdapter):
    """PDF implementation of DocumentAdapter."""

    format_id = "pdf"

    def __init__(self) -> None:
        self._path: Path | None = None
        self._doc = None  # fitz.Document | None
        self._original_mtime: float | None = None
        self._original_sha256: str | None = None
        self._temp = TempWorkspace()

    @property
    def path(self) -> Path | None:
        return self._path

    @property
    def page_count(self) -> int:
        if self._doc is None:
            return 0
        return self._doc.page_count

    @property
    def unit_count(self) -> int:
        return self.page_count

    def open(self, path: Path) -> None:
        import fitz

        path = Path(path)
        if not path.is_file():
            raise FileNotFoundError(path)
        self.close()
        self._temp = TempWorkspace()
        doc = fitz.open(path)
        if doc.is_encrypted:
            if not doc.authenticate(""):
                doc.close()
                raise PermissionError("암호로 보호된 PDF는 현재 지원하지 않습니다.")
        self._doc = doc
        self._path = path
        self._original_mtime = path.stat().st_mtime
        self._original_sha256 = file_sha256(path)

    def close(self) -> None:
        if self._doc is not None:
            self._doc.close()
        self._doc = None
        self._path = None
        self._original_mtime = None
        self._original_sha256 = None
        if hasattr(self, "_temp") and self._temp is not None:
            self._temp.cleanup()

    def assert_original_untouched(self) -> None:
        if self._path is None:
            return
        if self._original_mtime is not None:
            if self._path.stat().st_mtime != self._original_mtime:
                raise RuntimeError(f"원본 PDF가 변경되었습니다: {self._path}")
        if self._original_sha256 is not None:
            if file_sha256(self._path) != self._original_sha256:
                raise RuntimeError(f"원본 PDF 내용이 변경되었습니다: {self._path}")

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
        pad: float = 1.0,
    ) -> None:
        """Copy PDF to dest with redactions (text removal + black fill)."""
        import fitz

        self._require_doc()
        dest = Path(dest)
        if self._path and dest.resolve() == self._path.resolve():
            raise ValueError("원본 파일과 같은 경로로는 저장할 수 없습니다.")

        # Work on an independent open so the viewer document stays pristine.
        working = fitz.open(self._path)
        try:
            by_page: dict[int, list[MaskRegion]] = defaultdict(list)
            for mask in masks:
                by_page[mask.unit_index].append(mask)

            for page_index, page_masks in by_page.items():
                if page_index < 0 or page_index >= working.page_count:
                    continue
                page = working[page_index]
                for mask in page_masks:
                    box = mask.bbox.padded(pad)
                    rect = fitz.Rect(box.x0, box.y0, box.x1, box.y1)
                    # Always redact text under the box and fill black for safe export.
                    page.add_redact_annot(rect, fill=(0, 0, 0))
                    _ = (text_remove, draw_black_boxes)  # API flags reserved for future modes

            for page in working:
                page.apply_redactions(images=0)

            working.save(dest, garbage=4, deflate=True, clean=True)
        finally:
            working.close()
        self.assert_original_untouched()

    def export_rasterized(
        self,
        dest: Path,
        masks: Sequence[MaskRegion],
        *,
        dpi: int = 200,
        pad: float = 1.0,
    ) -> None:
        """Rasterize each page (with masks baked in) into a new image-only PDF."""
        import fitz

        self._require_doc()
        dest = Path(dest)
        if self._path and dest.resolve() == self._path.resolve():
            raise ValueError("원본 파일과 같은 경로로는 저장할 수 없습니다.")
        dpi = max(72, min(int(dpi), 600))
        scale = dpi / 72.0

        # First build a safely redacted temp PDF, then rasterize pages.
        tmp_safe = self._temp.tempfile("safe_for_raster.pdf")
        self.export_safe(
            tmp_safe,
            masks,
            text_remove=True,
            draw_black_boxes=True,
            pad=pad,
        )

        redacted = fitz.open(tmp_safe)
        out = fitz.open()
        try:
            for page in redacted:
                pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
                # Page size in points matching the pixmap at given dpi
                width = pix.width * 72 / dpi
                height = pix.height * 72 / dpi
                new_page = out.new_page(width=width, height=height)
                new_page.insert_image(new_page.rect, pixmap=pix)
            out.save(dest, garbage=4, deflate=True)
        finally:
            out.close()
            redacted.close()
            try:
                tmp_safe.unlink(missing_ok=True)
            except OSError:
                pass
        self.assert_original_untouched()

    def _require_doc(self) -> None:
        if self._doc is None:
            raise RuntimeError("PDF가 열려 있지 않습니다.")
