"""Tests for analysis progress / cancel and worker helpers."""

from __future__ import annotations

from pathlib import Path

import fitz

from privatedataremover.core.adapters.factory import open_document
from privatedataremover.core.pii.pipeline import analyze_document
from privatedataremover.core.settings import AppSettings


def _make_multipage_pdf(path: Path, pages: int = 5) -> None:
    doc = fitz.open()
    for i in range(pages):
        page = doc.new_page()
        page.insert_text((72, 72), f"연락처 010-1234-567{i} 페이지{i}")
    doc.save(path)
    doc.close()


def test_analyze_progress_and_cancel(tmp_path: Path) -> None:
    pdf = tmp_path / "multi.pdf"
    _make_multipage_pdf(pdf, pages=6)
    adapter = open_document(pdf)
    seen: list[tuple[int, int]] = []
    cancel_after = 2

    def on_progress(cur: int, tot: int, _msg: str) -> None:
        seen.append((cur, tot))

    def should_cancel() -> bool:
        return len(seen) >= cancel_after

    try:
        result = analyze_document(
            adapter,
            AppSettings(),
            use_ocr=False,
            use_llm=False,
            on_progress=on_progress,
            should_cancel=should_cancel,
        )
    finally:
        adapter.close()

    assert result.cancelled is True
    assert len(seen) >= cancel_after
    assert seen[0][1] == 6
    # Partial results from pages before cancel may exist
    assert isinstance(result.items, list)


def test_analyze_completes_with_progress(tmp_path: Path) -> None:
    pdf = tmp_path / "ok.pdf"
    _make_multipage_pdf(pdf, pages=3)
    adapter = open_document(pdf)
    ticks: list[int] = []
    try:
        result = analyze_document(
            adapter,
            AppSettings(),
            use_ocr=False,
            use_llm=False,
            on_progress=lambda c, t, m: ticks.append(c),
        )
    finally:
        adapter.close()
    assert result.cancelled is False
    assert ticks == [1, 2, 3]
    assert any(i.text for i in result.items)
