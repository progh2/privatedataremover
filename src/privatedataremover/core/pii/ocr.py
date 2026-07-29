"""Tesseract OCR helpers."""

from __future__ import annotations

from dataclasses import dataclass

from privatedataremover.core.adapters.base import BBox, ExtractedSpan


@dataclass
class OcrAvailability:
    available: bool
    message: str


def check_tesseract(tesseract_cmd: str = "") -> OcrAvailability:
    try:
        import pytesseract
        from pytesseract import TesseractNotFoundError
    except ImportError:
        return OcrAvailability(False, "pytesseract가 설치되어 있지 않습니다.")

    if tesseract_cmd.strip():
        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd.strip()
    try:
        ver = pytesseract.get_tesseract_version()
        return OcrAvailability(True, f"Tesseract {ver}")
    except TesseractNotFoundError:
        return OcrAvailability(
            False,
            "Tesseract를 찾을 수 없습니다. 설치 후 PATH에 추가하거나 설정에서 경로를 지정하세요.",
        )
    except Exception as exc:  # noqa: BLE001
        return OcrAvailability(False, f"Tesseract 확인 실패: {exc}")


def ocr_png_to_spans(
    png_bytes: bytes,
    *,
    unit_index: int,
    scale: float,
    languages: str = "kor+eng",
    tesseract_cmd: str = "",
) -> list[ExtractedSpan]:
    """OCR a rendered page PNG; map word boxes back to PDF page coords."""
    from io import BytesIO

    import pytesseract
    from PIL import Image

    if tesseract_cmd.strip():
        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd.strip()

    image = Image.open(BytesIO(png_bytes))
    data = pytesseract.image_to_data(
        image, lang=languages or "kor+eng", output_type=pytesseract.Output.DICT
    )
    spans: list[ExtractedSpan] = []
    n = len(data.get("text", []))
    for i in range(n):
        text = (data["text"][i] or "").strip()
        if not text:
            continue
        conf = data.get("conf", ["-1"])[i]
        try:
            if float(conf) < 0:
                continue
        except (TypeError, ValueError):
            pass
        x, y, w, h = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
        # Image coords are at `scale`; convert to page points.
        inv = 1.0 / scale if scale else 1.0
        bbox = BBox(x * inv, y * inv, (x + w) * inv, (y + h) * inv)
        spans.append(
            ExtractedSpan(
                unit_index=unit_index,
                text=text,
                bbox=bbox,
                from_ocr=True,
            )
        )
    return spans
