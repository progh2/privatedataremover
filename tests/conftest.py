"""Shared pytest fixtures — sample PDFs for detection/export tests."""

from __future__ import annotations

from pathlib import Path

import fitz
import pytest


@pytest.fixture()
def sample_form_pdf(tmp_path: Path) -> Path:
    """Multi-page form-like PDF with repeated layout and PII-like values."""
    path = tmp_path / "sample_form.pdf"
    doc = fitz.open()
    for i in range(3):
        page = doc.new_page()
        page.insert_text((72, 72), "신청서 / Application Form")
        page.insert_text((72, 110), "성명: Hong Gildong")
        page.insert_text((72, 140), f"연락처: 010-1234-567{i}")
        page.insert_text((72, 170), "이메일: user@example.com")
        page.insert_text((72, 200), "주소: Seoul Jung-gu 1")
    doc.save(path)
    doc.close()
    return path


@pytest.fixture()
def fixtures_dir() -> Path:
    return Path(__file__).parent / "fixtures"
