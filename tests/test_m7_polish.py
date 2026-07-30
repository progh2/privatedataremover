"""Extra coverage for HWPX namespaces, Excel residual check, factory."""

from __future__ import annotations

import zipfile
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, tostring

import pytest

from privatedataremover.core.adapters.base import BBox, MaskMode, MaskRegion, MaskSource, PiiType
from privatedataremover.core.adapters.factory import adapter_for_path, supported_extensions
from privatedataremover.core.adapters.hwpx import HwpxAdapter
from privatedataremover.core.adapters.xlsx import XlsxAdapter
from privatedataremover.core.export_utils import find_residual_in_xlsx


NS = "http://www.hancom.co.kr/hwpml/2011/paragraph"


def test_supported_extensions() -> None:
    exts = supported_extensions()
    assert ".pdf" in exts
    assert ".xlsx" in exts
    assert ".hwpx" in exts


def test_adapter_for_path_rejects_unknown() -> None:
    with pytest.raises(ValueError):
        adapter_for_path(Path("a.docx"))


def test_hwpx_namespaced_t_and_header(tmp_path: Path) -> None:
    path = tmp_path / "ns.hwpx"
    # Namespaced hp:t text + separate header
    sec = Element(f"{{{NS}}}p")
    t = SubElement(sec, f"{{{NS}}}t")
    t.text = "여권 M1234567"
    sec_xml = tostring(sec, encoding="utf-8")

    header = Element(f"{{{NS}}}hdr")
    ht = SubElement(header, f"{{{NS}}}t")
    ht.text = "기밀 header@corp.test"
    hdr_xml = tostring(header, encoding="utf-8")

    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("mimetype", "application/hwp+zip")
        zf.writestr("Contents/header.xml", hdr_xml)
        zf.writestr("Contents/section0.xml", sec_xml)

    adapter = HwpxAdapter()
    adapter.open(path)
    try:
        units = list(adapter.iter_units())
        assert len(units) == 2
        assert any(u.meta.get("kind") == "header/footer" for u in units)
        all_text = []
        for u in units:
            all_text.extend(s.text for s in adapter.extract_spans(u.index))
        joined = " ".join(all_text)
        assert "M1234567" in joined
        assert "header@corp.test" in joined
    finally:
        adapter.close()


def test_xlsx_residual_helper(tmp_path: Path) -> None:
    openpyxl = pytest.importorskip("openpyxl")
    src = tmp_path / "in.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws["A1"] = "010-0000-1111"
    wb.save(src)
    wb.close()

    adapter = XlsxAdapter()
    adapter.open(src)
    try:
        dest = tmp_path / "out.xlsx"
        mask = MaskRegion(
            id="1",
            unit_index=0,
            bbox=BBox(0, 0, 1, 1),
            mode=MaskMode.DELETE_AND_BOX,
            pii_type=PiiType.PHONE,
            source=MaskSource.MANUAL,
            label="010-0000-1111",
        )
        adapter.export_safe(dest, [mask])
        assert find_residual_in_xlsx(dest, ["010-0000-1111"]) == []
        # control: original still has it
        assert find_residual_in_xlsx(src, ["010-0000-1111"])
    finally:
        adapter.close()
