"""Excel adapter tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from privatedataremover.core.adapters.base import BBox, MaskMode, MaskRegion, MaskSource, PiiType
from privatedataremover.core.adapters.xlsx import XlsxAdapter
from privatedataremover.core.export_utils import file_sha256
from privatedataremover.core.pii.rules import detect_in_spans


@pytest.fixture()
def sample_xlsx(tmp_path: Path) -> Path:
    openpyxl = pytest.importorskip("openpyxl")
    path = tmp_path / "sample.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "공개"
    ws["A1"] = "이름"
    ws["B1"] = "Hong"
    ws["A2"] = "전화"
    ws["B2"] = "010-2222-3333"

    hidden = wb.create_sheet("비밀")
    hidden.sheet_state = "hidden"
    hidden["A1"] = "secret@example.com"

    ws.row_dimensions[5].hidden = True
    ws["A5"] = "숨긴행데이터"
    ws.column_dimensions["C"].hidden = True
    ws["C1"] = "숨긴열"

    wb.save(path)
    wb.close()
    return path


def test_xlsx_hidden_meta_and_spans(sample_xlsx: Path) -> None:
    adapter = XlsxAdapter()
    adapter.open(sample_xlsx)
    try:
        units = list(adapter.iter_units())
        assert len(units) == 2
        hidden_unit = next(u for u in units if u.meta.get("hidden"))
        assert hidden_unit.meta.get("sheet_name") == "비밀"
        public = next(u for u in units if u.meta.get("sheet_name") == "공개")
        assert public.meta.get("hidden_row_count", 0) >= 1
        assert public.meta.get("hidden_col_count", 0) >= 1

        spans = list(adapter.extract_spans(public.index))
        texts = " ".join(s.text for s in spans)
        assert "010-2222-3333" in texts
        assert "숨긴행" in texts or "숨긴행데이터" in texts

        secret_spans = list(adapter.extract_spans(hidden_unit.index))
        assert any("secret@example.com" in s.text for s in secret_spans)

        png = adapter.render_unit_preview(public.index)
        assert png[:8] == b"\x89PNG\r\n\x1a\n"

        items = detect_in_spans(list(adapter.extract_spans(public.index)))
        assert any(i.pii_type == PiiType.PHONE for i in items)
    finally:
        adapter.close()


def test_xlsx_export_safe(sample_xlsx: Path, tmp_path: Path) -> None:
    openpyxl = pytest.importorskip("openpyxl")
    original = file_sha256(sample_xlsx)
    adapter = XlsxAdapter()
    adapter.open(sample_xlsx)
    try:
        # B2 is phone on sheet 0
        mask = MaskRegion(
            id="1",
            unit_index=0,
            bbox=BBox(1, 1, 2, 2),  # col B row 2
            mode=MaskMode.DELETE_AND_BOX,
            pii_type=PiiType.PHONE,
            source=MaskSource.MANUAL,
            label="010-2222-3333",
        )
        dest = tmp_path / "out.xlsx"
        adapter.export_safe(dest, [mask])
        assert file_sha256(sample_xlsx) == original
        wb = openpyxl.load_workbook(dest)
        assert wb["공개"]["B2"].value == "***"
        wb.close()
    finally:
        adapter.close()
