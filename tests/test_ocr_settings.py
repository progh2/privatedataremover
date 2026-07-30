"""OCR / Tesseract helper tests."""

from __future__ import annotations

from privatedataremover.core.pii.ocr import (
    check_tesseract,
    common_tesseract_candidates,
    install_guide_text,
)


def test_install_guide_mentions_tesseract() -> None:
    text = install_guide_text()
    assert "Tesseract" in text or "tesseract" in text
    assert "설치" in text


def test_common_candidates_is_list() -> None:
    paths = common_tesseract_candidates()
    assert isinstance(paths, list)
    assert all(isinstance(p, str) for p in paths)


def test_check_tesseract_returns_availability() -> None:
    result = check_tesseract("")
    assert isinstance(result.available, bool)
    assert result.message
    if result.available:
        assert result.version
