"""HWPX adapter smoke tests."""

from __future__ import annotations

import zipfile
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, tostring

import pytest

from privatedataremover.core.adapters.base import BBox, MaskMode, MaskRegion, MaskSource, PiiType
from privatedataremover.core.adapters.factory import open_document
from privatedataremover.core.adapters.hwpx import HwpxAdapter
from privatedataremover.core.export_utils import file_sha256


def _minimal_hwpx(path: Path) -> None:
    # Minimal zip with one section containing a phone number
    section = Element("sec")
    t = SubElement(section, "t")
    t.text = "연락처 010-7777-8888"
    xml = tostring(section, encoding="utf-8")
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("mimetype", "application/hwp+zip")
        zf.writestr("Contents/section0.xml", xml)


@pytest.fixture()
def sample_hwpx(tmp_path: Path) -> Path:
    path = tmp_path / "sample.hwpx"
    _minimal_hwpx(path)
    return path


def test_hwpx_extract_and_export(sample_hwpx: Path, tmp_path: Path) -> None:
    original = file_sha256(sample_hwpx)
    adapter = HwpxAdapter()
    adapter.open(sample_hwpx)
    try:
        units = list(adapter.iter_units())
        assert len(units) >= 1
        spans = list(adapter.extract_spans(0))
        assert any("010-7777-8888" in s.text for s in spans)
        png = adapter.render_unit_preview(0)
        assert png[:8] == b"\x89PNG\r\n\x1a\n"

        mask = MaskRegion(
            id="1",
            unit_index=0,
            bbox=BBox(0, 0, 1, 1),
            mode=MaskMode.DELETE_AND_BOX,
            pii_type=PiiType.PHONE,
            source=MaskSource.MANUAL,
            label="010-7777-8888",
        )
        dest = tmp_path / "out.hwpx"
        adapter.export_safe(dest, [mask])
        assert file_sha256(sample_hwpx) == original
        with zipfile.ZipFile(dest) as zf:
            data = zf.read("Contents/section0.xml").decode("utf-8")
        assert "010-7777-8888" not in data
        assert "***" in data
    finally:
        adapter.close()


def test_factory_opens_hwpx(sample_hwpx: Path) -> None:
    adapter = open_document(sample_hwpx)
    try:
        assert adapter.format_id == "hwpx"
    finally:
        adapter.close()
