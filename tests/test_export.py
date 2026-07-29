"""Export: safe redaction, raster PDF, residual check, original integrity."""

from __future__ import annotations

from pathlib import Path

import fitz
import pytest

from privatedataremover.core.adapters.base import BBox, MaskMode, MaskRegion, MaskSource, PiiType
from privatedataremover.core.adapters.pdf import PdfAdapter
from privatedataremover.core.export_utils import file_sha256, find_residual_texts


@pytest.fixture()
def pii_pdf(tmp_path: Path) -> Path:
    path = tmp_path / "pii.pdf"
    doc = fitz.open()
    page = doc.new_page()
    secret = "010-1234-5678"
    page.insert_text((72, 72), f"Phone {secret}")
    page.insert_text((72, 120), "Name Hong")
    doc.save(path)
    doc.close()
    return path


def _mask_for_phone(page: fitz.Page, needle: str = "010-1234-5678") -> MaskRegion:
    areas = page.search_for(needle)
    assert areas, "fixture text not found"
    r = areas[0]
    return MaskRegion(
        id="m1",
        unit_index=0,
        bbox=BBox(r.x0, r.y0, r.x1, r.y1),
        mode=MaskMode.DELETE_AND_BOX,
        pii_type=PiiType.PHONE,
        source=MaskSource.MANUAL,
        label=needle,
    )


def test_export_safe_removes_text_and_keeps_original(pii_pdf: Path, tmp_path: Path) -> None:
    original_hash = file_sha256(pii_pdf)
    adapter = PdfAdapter()
    adapter.open(pii_pdf)
    try:
        page = fitz.open(pii_pdf)[0]
        mask = _mask_for_phone(page)
        page.parent.close()

        dest = tmp_path / "safe.pdf"
        adapter.export_safe(dest, [mask])
        assert dest.is_file()
        assert file_sha256(pii_pdf) == original_hash
        adapter.assert_original_untouched()

        hits = find_residual_texts(dest, ["010-1234-5678"])
        assert hits == []
        # Other text may remain
        doc = fitz.open(dest)
        text = doc[0].get_text()
        doc.close()
        assert "010-1234-5678" not in text
    finally:
        adapter.close()


def test_export_rasterized_has_no_secret(pii_pdf: Path, tmp_path: Path) -> None:
    original_hash = file_sha256(pii_pdf)
    adapter = PdfAdapter()
    adapter.open(pii_pdf)
    try:
        page = fitz.open(pii_pdf)[0]
        mask = _mask_for_phone(page)
        page.parent.close()

        dest = tmp_path / "raster.pdf"
        adapter.export_rasterized(dest, [mask], dpi=150)
        assert file_sha256(pii_pdf) == original_hash
        hits = find_residual_texts(dest, ["010-1234-5678", "Hong"])
        # Raster pages typically have empty extractable text
        assert all(h.text != "010-1234-5678" for h in hits)
        doc = fitz.open(dest)
        assert doc.page_count == 1
        # Image-only page: little or no text
        assert "010-1234-5678" not in (doc[0].get_text() or "")
        doc.close()
    finally:
        adapter.close()


def test_refuse_overwrite_original(pii_pdf: Path) -> None:
    adapter = PdfAdapter()
    adapter.open(pii_pdf)
    try:
        with pytest.raises(ValueError):
            adapter.export_safe(pii_pdf, [])
    finally:
        adapter.close()
