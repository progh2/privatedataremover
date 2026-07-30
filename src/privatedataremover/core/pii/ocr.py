"""Tesseract OCR helpers."""

from __future__ import annotations

import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path

from privatedataremover.core.adapters.base import BBox, ExtractedSpan


@dataclass
class OcrAvailability:
    available: bool
    message: str
    version: str = ""
    languages: list[str] = field(default_factory=list)
    resolved_cmd: str = ""


def common_tesseract_candidates() -> list[str]:
    """Likely install paths (OS-specific), first existing wins for auto-detect."""
    found: list[str] = []
    which = shutil.which("tesseract")
    if which:
        found.append(which)
    if sys.platform.startswith("win"):
        for base in (
            Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
            Path(r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"),
            Path.home() / r"AppData\Local\Programs\Tesseract-OCR\tesseract.exe",
        ):
            if base.is_file():
                found.append(str(base))
    elif sys.platform == "darwin":
        for p in (
            "/opt/homebrew/bin/tesseract",
            "/usr/local/bin/tesseract",
        ):
            if Path(p).is_file():
                found.append(p)
    else:
        for p in ("/usr/bin/tesseract", "/usr/local/bin/tesseract"):
            if Path(p).is_file():
                found.append(p)
    seen: set[str] = set()
    out: list[str] = []
    for p in found:
        key = p.lower()
        if key not in seen:
            seen.add(key)
            out.append(p)
    return out


def install_guide_text() -> str:
    """Short Korean install tips for the settings dialog."""
    if sys.platform.startswith("win"):
        return (
            "<b>Windows 설치 안내</b><br>"
            "1. "
            '<a href="https://github.com/UB-Mannheim/tesseract/wiki">'
            "UB Mannheim Tesseract 설치 패키지</a>를 받아 설치하세요.<br>"
            "2. 설치 시 <b>Additional language data</b>에서 "
            "<code>Korean</code>·<code>English</code>를 함께 선택하세요.<br>"
            "3. 기본 경로 예: "
            "<code>C:\\Program Files\\Tesseract-OCR\\tesseract.exe</code><br>"
            "4. PATH에 추가했거나 위 경로를 「찾아보기」로 지정한 뒤 "
            "「Tesseract 확인」을 누르세요."
        )
    if sys.platform == "darwin":
        return (
            "<b>macOS 설치 안내</b><br>"
            "<code>brew install tesseract tesseract-lang</code><br>"
            "설치 후 「Tesseract 확인」으로 언어 팩(kor, eng)을 확인하세요."
        )
    return (
        "<b>Linux 설치 안내</b><br>"
        "Debian/Ubuntu: "
        "<code>sudo apt install tesseract-ocr tesseract-ocr-kor</code><br>"
        "설치 후 「Tesseract 확인」을 누르세요."
    )


def check_tesseract(tesseract_cmd: str = "") -> OcrAvailability:
    try:
        import pytesseract
        from pytesseract import TesseractNotFoundError
    except ImportError:
        return OcrAvailability(
            False,
            "pytesseract가 설치되어 있지 않습니다. pip install pytesseract",
        )

    cmd = tesseract_cmd.strip()
    if not cmd:
        candidates = common_tesseract_candidates()
        cmd = candidates[0] if candidates else ""
    if cmd:
        pytesseract.pytesseract.tesseract_cmd = cmd

    try:
        ver = str(pytesseract.get_tesseract_version())
    except TesseractNotFoundError:
        return OcrAvailability(
            False,
            "Tesseract를 찾을 수 없습니다. 아래 설치 안내를 참고하거나 "
            "설정에서 실행 파일 경로를 지정하세요.",
        )
    except Exception as exc:  # noqa: BLE001
        return OcrAvailability(False, f"Tesseract 확인 실패: {exc}")

    langs: list[str] = []
    try:
        langs = sorted(pytesseract.get_languages(config=""))
    except Exception:  # noqa: BLE001
        langs = []

    missing = [code for code in ("kor", "eng") if langs and code not in langs]
    msg = f"Tesseract {ver} 인식됨"
    if langs:
        preview = ", ".join(langs[:12])
        more = f" 외 {len(langs) - 12}개" if len(langs) > 12 else ""
        msg += f" · 언어 {len(langs)}개 ({preview}{more})"
    if missing:
        msg += f" · 주의: {', '.join(missing)} 언어 팩이 없습니다"

    return OcrAvailability(
        True,
        msg,
        version=ver,
        languages=langs,
        resolved_cmd=cmd or (shutil.which("tesseract") or ""),
    )


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
