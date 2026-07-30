"""Orchestrate extract → OCR → rules → optional LLM."""

from __future__ import annotations

import gc
from collections.abc import Callable
from dataclasses import dataclass

from privatedataremover.core.adapters.base import DocumentAdapter
from privatedataremover.core.llm.analyze import analyze_page_with_llm
from privatedataremover.core.pii import DetectionItem
from privatedataremover.core.pii.ocr import check_tesseract, ocr_png_to_spans
from privatedataremover.core.pii.rules import detect_in_spans
from privatedataremover.core.settings import AppSettings

ProgressCallback = Callable[[int, int, str], None]
CancelCallback = Callable[[], bool]


class AnalysisCancelled(Exception):
    """Raised when the user cancels a long-running analysis."""


@dataclass
class AnalyzeResult:
    items: list[DetectionItem]
    used_ocr: bool
    ocr_message: str
    llm_error: str = ""
    notes: str = ""
    cancelled: bool = False


def analyze_document(
    adapter: DocumentAdapter,
    settings: AppSettings,
    *,
    use_ocr: bool = True,
    use_llm: bool = False,
    ocr_if_sparse: bool = True,
    sparse_char_threshold: int = 40,
    on_progress: ProgressCallback | None = None,
    should_cancel: CancelCallback | None = None,
) -> AnalyzeResult:
    """Analyze all units; returns merged detection items (pending).

    ``on_progress(current, total, message)`` is called once per unit (1-based).
    ``should_cancel()`` returning True stops early with ``cancelled=True``.
    """
    all_items: list[DetectionItem] = []
    used_ocr = False
    ocr_message = ""
    llm_error = ""
    notes_parts: list[str] = []

    if adapter.format_id == "xlsx" and hasattr(adapter, "list_hidden_sheet_summary"):
        summary = adapter.list_hidden_sheet_summary()  # type: ignore[attr-defined]
        if summary:
            notes_parts.append(
                "숨김/구조: "
                + ", ".join(
                    f"{s.get('name')}(hidden={s.get('hidden')}, rows={s.get('hidden_rows')}, cols={s.get('hidden_cols')})"
                    for s in summary
                )
            )

    ocr_ok = check_tesseract(settings.tesseract_cmd)
    allow_ocr = use_ocr and adapter.format_id == "pdf"
    if use_ocr and not allow_ocr:
        ocr_message = "OCR은 PDF에 적용됩니다 (현재 형식에서는 건너뜀)."
    elif use_ocr and not ocr_ok.available:
        ocr_message = ocr_ok.message

    units = list(adapter.iter_units())
    total = len(units)

    for i, unit in enumerate(units):
        if should_cancel and should_cancel():
            return AnalyzeResult(
                items=all_items,
                used_ocr=used_ocr,
                ocr_message=ocr_message,
                llm_error=llm_error,
                notes="\n".join(notes_parts + ["사용자가 분석을 취소했습니다."]),
                cancelled=True,
            )

        if on_progress:
            on_progress(i + 1, total, f"단위 {i + 1}/{total} 분석 중…")

        spans = list(adapter.extract_spans(unit.index))
        native_text = " ".join(s.text for s in spans)

        need_ocr = allow_ocr and ocr_ok.available and (
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
                del png
                if ocr_spans:
                    spans = list(spans) + list(ocr_spans)
                    used_ocr = True
            except Exception as exc:  # noqa: BLE001
                ocr_message = f"OCR 오류(단위 {unit.index + 1}): {exc}"

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

        # Free page buffers periodically on large documents
        if (i + 1) % 10 == 0:
            gc.collect()

    if used_ocr and not ocr_message:
        ocr_message = ocr_ok.message

    return AnalyzeResult(
        items=all_items,
        used_ocr=used_ocr,
        ocr_message=ocr_message,
        llm_error=llm_error,
        notes="\n".join(notes_parts),
        cancelled=False,
    )
