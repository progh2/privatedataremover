"""PDF adapter tests with an in-memory fixture document."""

from __future__ import annotations

from pathlib import Path

import fitz
import pytest

from privatedataremover.core.adapters.pdf import PdfAdapter


@pytest.fixture()
def sample_pdf(tmp_path: Path) -> Path:
    path = tmp_path / "sample.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Hong Gildong 010-1234-5678")
    page2 = doc.new_page()
    page2.insert_text((72, 72), "page two")
    doc.save(path)
    doc.close()
    return path


def test_open_iter_render_extract(sample_pdf: Path) -> None:
    adapter = PdfAdapter()
    adapter.open(sample_pdf)
    try:
        units = list(adapter.iter_units())
        assert len(units) == 2
        assert units[0].label == "페이지 1"
        spans = adapter.extract_spans(0)
        joined = " ".join(s.text for s in spans)
        assert "010-1234-5678" in joined or "Hong" in joined
        png = adapter.render_unit_preview(0, scale=1.0)
        assert png[:8] == b"\x89PNG\r\n\x1a\n"
        mtime = sample_pdf.stat().st_mtime
        adapter.assert_original_untouched()
        assert sample_pdf.stat().st_mtime == mtime
    finally:
        adapter.close()


def test_missing_file() -> None:
    adapter = PdfAdapter()
    with pytest.raises(FileNotFoundError):
        adapter.open(Path("does-not-exist.pdf"))
