"""Orchestrate extract → OCR → rules → optional LLM."""

from __future__ import annotations

from dataclasses import dataclass

from privatedataremover.core.adapters.pdf import PdfAdapter
from privatedataremover.core.llm.analyze import analyze_page_with_llm
from privatedataremover.core.pii import DetectionItem
from privatedataremover.core.pii.ocr import check_tesseract, ocr_png_to_spans
from privatedataremover.core.pii.rules import detect_in_spans
from privatedataremover.core.settings import AppSettings


@dataclass
class AnalyzeResult:
    items: list[DetectionItem]
    used_ocr: bool
    ocr_message: str
    llm_error: str = ""


def analyze_document(
    adapter: PdfAdapter,
    settings: AppSettings,
    *,
    use_ocr: bool = True,
    use_llm: bool = False,
    ocr_if_sparse: bool = True,
    sparse_char_threshold: int = 40,
) -> AnalyzeResult:
    """Analyze all pages; returns merged detection items (pending)."""
    all_items: list[DetectionItem] = []
    used_ocr = False
    ocr_message = ""
    llm_error = ""

    ocr_ok = check_tesseract(settings.tesseract_cmd)
    if use_ocr and not ocr_ok.available:
        ocr_message = ocr_ok.message

    for unit in adapter.iter_units():
        spans = list(adapter.extract_spans(unit.index))
        native_text = " ".join(s.text for s in spans)
        page_used_ocr = False

        need_ocr = use_ocr and ocr_ok.available and (
            not ocr_if_sparse or len(native_text.strip()) < sparse_char_threshold
        )
        if need_ocr:
            try:
                png = adapter.render_unit_preview(unit.index, scale=2.0)
                ocr_spans = ocr_png_to_spans(
                    png,
                    unit_index=unit.index,
                    scale=2.0,
                    languages=settings.ocr_languages,
                    tesseract_cmd=settings.tesseract_cmd,
                )
                if ocr_spans:
                    spans = list(spans) + list(ocr_spans)
                    page_used_ocr = True
                    used_ocr = True
            except Exception as exc:  # noqa: BLE001
                ocr_message = f"OCR 오류(페이지 {unit.index + 1}): {exc}"

        all_items.extend(detect_in_spans(spans))

        if use_llm:
            page_text = " ".join(s.text for s in spans)
            try:
                all_items.extend(
                    analyze_page_with_llm(
                        settings,
                        unit_index=unit.index,
                        page_text=page_text,
                        spans=list(spans),
                    )
                )
            except Exception as exc:  # noqa: BLE001
                llm_error = str(exc)

        _ = page_used_ocr  # reserved for per-page reporting

    if used_ocr and not ocr_message:
        ocr_message = ocr_ok.message

    return AnalyzeResult(
        items=all_items,
        used_ocr=used_ocr,
        ocr_message=ocr_message,
        llm_error=llm_error,
    )
