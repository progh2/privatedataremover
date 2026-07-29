"""Integration-ish tests using shared sample_form_pdf fixture."""

from __future__ import annotations

from pathlib import Path

from privatedataremover.core.adapters.pdf import PdfAdapter
from privatedataremover.core.pattern import find_similar_pages, page_fingerprint
from privatedataremover.core.pii.pipeline import analyze_document
from privatedataremover.core.pii.session import DetectionSession
from privatedataremover.core.settings import AppSettings


def test_sample_form_detect_and_pattern(sample_form_pdf: Path) -> None:
    adapter = PdfAdapter()
    adapter.open(sample_form_pdf)
    try:
        result = analyze_document(adapter, AppSettings(), use_ocr=False, use_llm=False)
        session = DetectionSession()
        session.add_items(result.items)
        assert any(i.pii_type.value == "phone" for i in session.items)
        assert any(i.pii_type.value == "email" for i in session.items)

        units = {u.index: u for u in adapter.iter_units()}
        fps = {
            idx: page_fingerprint(list(adapter.extract_spans(idx)), units[idx])
            for idx in units
        }
        similar = find_similar_pages(fps, 0, threshold=0.5)
        assert len(similar) >= 1
    finally:
        adapter.close()
