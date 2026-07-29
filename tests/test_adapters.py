"""Basic tests for adapter contracts."""

from __future__ import annotations

from privatedataremover.core.adapters.base import BBox, MaskMode, PiiType
from privatedataremover.core.adapters.pdf import PdfAdapter
from privatedataremover.core.adapters.xlsx import XlsxAdapter
from privatedataremover.core.adapters.hwpx import HwpxAdapter


def test_bbox_padded() -> None:
    box = BBox(10, 20, 30, 40)
    padded = box.padded(2)
    assert padded == BBox(8, 18, 32, 42)


def test_pdf_adapter_format_id() -> None:
    assert PdfAdapter.format_id == "pdf"


def test_future_adapters_registered() -> None:
    assert XlsxAdapter.format_id == "xlsx"
    assert HwpxAdapter.format_id == "hwpx"


def test_enums() -> None:
    assert PiiType.PHONE.value == "phone"
    assert MaskMode.DELETE_AND_BOX.value == "delete_and_box"
