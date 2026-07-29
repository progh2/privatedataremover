#!/usr/bin/env python3
"""Generate sample PDFs under tests/fixtures for manual QA."""

from __future__ import annotations

from pathlib import Path

import fitz


def main() -> None:
    root = Path(__file__).resolve().parents[1] / "tests" / "fixtures"
    root.mkdir(parents=True, exist_ok=True)

    form = root / "sample_form.pdf"
    doc = fitz.open()
    for i in range(3):
        page = doc.new_page()
        page.insert_text((72, 72), "신청서 / Application Form")
        page.insert_text((72, 110), "성명: Hong Gildong")
        page.insert_text((72, 140), f"연락처: 010-1234-567{i}")
        page.insert_text((72, 170), "이메일: user@example.com")
        page.insert_text((72, 200), "주소: Seoul Jung-gu 1")
    doc.save(form)
    doc.close()
    print("Wrote", form)

    simple = root / "sample_phone.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Phone 010-9999-8888")
    doc.save(simple)
    doc.close()
    print("Wrote", simple)


if __name__ == "__main__":
    main()
