"""Rule-based Korean/common PII detectors."""

from __future__ import annotations

import re
from dataclasses import dataclass

from privatedataremover.core.adapters.base import BBox, ExtractedSpan, MaskSource, PiiType
from privatedataremover.core.pii import DetectionItem, DetectionStatus, new_id


@dataclass(frozen=True)
class RulePattern:
    pii_type: PiiType
    pattern: re.Pattern[str]
    confidence: float = 0.9
    # If set, use this group as the detected value (exclude labels).
    capture_group: int | None = None


# Common Korean surnames for heuristic name detection (confidence lower).
_SURNAMES = (
    "김|이|박|최|정|강|조|윤|장|임|한|오|서|신|권|황|안|송|전|홍|유|고|문|양|손|배|"
    "백|허|남|심|노|하|곽|성|차|주|우|구|민|류|나|진|채|원|천|방|공|함|변|염|여|"
    "추|도|소|석|선|설|마|길|연|표|명|기|반"
)

# Avoid treating common non-name words / place fragments as person names.
_NAME_DENY = frozenset(
    {
        "이름",
        "이상",
        "이후",
        "이전",
        "이외",
        "이용",
        "이동",
        "이유",
        "이번",
        "이곳",
        "이날",
        "이거",
        "이런",
        "이렇",
        "이라",
        "이면",
        "이었",
        "이에",
        "이로",
        "이쪽",
        "이길",
        "이자",
        "이내",
        "이미",
        "이하",
        "이관",
        "이수",
        "이슈",
        "박수",
        "박스",
        "발표",
        "방문",
        "방법",
        "방향",
        "배포",
        "변경",
        "법적",
        "정수",
        "정도",
        "정확",
        "정보",
        "정부",
        "정식",
        "정의",
        "정책",
        "정작",
        "정기",
        "강남",
        "강도",
        "강제",
        "강조",
        "강사",
        "강습",
        "조성",
        "조사",
        "조건",
        "조직",
        "조항",
        "조회",
        "윤곽",
        "윤리",
        "장관",
        "장소",
        "장점",
        "장비",
        "임원",
        "임명",
        "한자",
        "한국",
        "한글",
        "한도",
        "오후",
        "오전",
        "오늘",
        "요구",
        "요청",
        "서로",
        "서버",
        "서명",
        "신고",
        "신청",
        "신문",
        "신경",
        "권한",
        "권리",
        "황금",
        "안전",
        "안내",
        "송장",
        "전송",
        "전화",
        "전부",
        "전체",
        "홍보",
        "유사",
        "유도",
        "고객",
        "고요",
        "고장",
        "문의",
        "문서",
        "문제",
        "양자",
        "양식",
        "손수",
        "배달",
        "배경",
        "백서",
        "허위",
        "남부",
        "심사",
        "신장",
        "노출",
        "하는",
        "하다",
        "성명",
        "성공",
        "성적",
        "차량",
        "주소",
        "주민",
        "주기",
        "우편",
        "구역",
        "국민",
        "민원",
        "진술",
        "진행",
        "채택",
        "원리",
        "원격",
        "천장",
        "공부",
        "함양",
        "여부",
        "추후",
        "도서",
        "소속",
        "석사",
        "선생",
        "설명",
        "마감",
        "길이",
        "연락",
        "연결",
    }
)

_SIDO = (
    r"(?:서울(?:특별시)?|부산(?:광역시)?|대구(?:광역시)?|인천(?:광역시)?|"
    r"광주(?:광역시)?|대전(?:광역시)?|울산(?:광역시)?|세종(?:특별자치시)?|"
    r"경기(?:도)?|강원(?:특별자치도|도)?|충북|충청북도|충남|충청남도|"
    r"전북(?:특별자치도)?|전라북도|전남|전라남도|경북|경상북도|경남|경상남도|"
    r"제주(?:특별자치도)?)"
)

# Order matters: more specific first.
_RULES: list[RulePattern] = [
    RulePattern(
        PiiType.RRN,
        re.compile(r"(?<!\d)\d{6}\s*[-–]?\s*[1-4]\d{6}(?!\d)"),
        0.95,
    ),
    RulePattern(
        PiiType.CARD,
        re.compile(r"(?<!\d)(?:\d{4}[-\s]?){3}\d{4}(?!\d)"),
        0.85,
    ),
    RulePattern(
        PiiType.PHONE,
        re.compile(
            r"(?<!\d)(?:0\d{1,2}|01[016789])[-\s]?\d{3,4}[-\s]?\d{4}(?!\d)"
        ),
        0.9,
    ),
    RulePattern(
        PiiType.EMAIL,
        re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
        0.95,
    ),
    RulePattern(
        PiiType.ACCOUNT,
        re.compile(r"(?<!\d)\d{2,6}[-\s]\d{2,6}[-\s]\d{2,8}(?!\d)"),
        0.7,
    ),
    RulePattern(
        PiiType.BIRTHDATE,
        re.compile(
            r"(?<!\d)(?:19|20)\d{2}[.\-/년]\s*\d{1,2}[.\-/월]\s*\d{1,2}일?(?!\d)"
        ),
        0.75,
    ),
    # --- Name (라벨 + 휴리스틱) ---
    RulePattern(
        PiiType.NAME,
        re.compile(
            r"(?:성\s*명|이\s*름|성명|이름|신청인|수신인|보호자|대표자|담당자|"
            r"고객명|회원명|환자명|계약자|피보험자|예금주|입금자|"
            r"성\s*·?\s*명|Name)\s*[:：=\-]?\s*"
            r"([가-힣]{2,4}(?:\s+[A-Za-z][A-Za-z.\-']*)?|"
            r"[A-Za-z][A-Za-z.\-']+(?:\s+[A-Za-z][A-Za-z.\-']+){0,3})"
        ),
        0.92,
        capture_group=1,
    ),
    RulePattern(
        PiiType.NAME,
        re.compile(r"(?<![가-힣A-Za-z])([가-힣]{2,4})\s*(?:님|氏|씨)"),
        0.85,
        capture_group=1,
    ),
    RulePattern(
        PiiType.NAME,
        re.compile(rf"(?<![가-힣])((?:{_SURNAMES})[가-힣]{{1,2}})(?![가-힣])"),
        0.62,
        capture_group=1,
    ),
    # --- Address (라벨 + 시·구·동/로·길) ---
    RulePattern(
        PiiType.ADDRESS,
        re.compile(
            r"(?:주\s*소|거주지|배송지|소재지|근무지|자택|등록지|"
            r"사업장\s*소재지|Address)\s*[:：=\-]?\s*"
            r"([^\n\r]{4,100}?)"
            r"(?=(?:\s{2,}|\t|$|[|]|전화번호|연락처|성명|이름|이메일|전화))"
        ),
        0.9,
        capture_group=1,
    ),
    RulePattern(
        PiiType.ADDRESS,
        re.compile(
            rf"{_SIDO}\s*"
            r"[가-힣0-9]+(?:시|군|구)"
            r"(?:\s*[가-힣0-9]+(?:읍|면|동|리))?"
            r"(?:\s*[가-힣0-9]+(?:로|길))?"
            r"(?:\s*\d+(?:-\d+)?)?"
            r"(?:\s*(?:\d+동)?\s*\d+호)?"
        ),
        0.88,
    ),
    RulePattern(
        PiiType.ADDRESS,
        re.compile(
            r"(?<![가-힣0-9])[가-힣0-9]{1,20}(?:로|길)\s*\d+(?:-\d+)?"
            r"(?:\s*(?:번지|호))?"
        ),
        0.7,
    ),
]


def _value_from_match(rule: RulePattern, match: re.Match[str]) -> str:
    if rule.capture_group is not None:
        raw = match.group(rule.capture_group)
    else:
        raw = match.group(0)
    return (raw or "").strip(" \t\r\n·:：=-")


def _accept_match(rule: RulePattern, value: str) -> bool:
    if not value or len(value) < 2:
        return False
    if rule.pii_type == PiiType.NAME:
        compact = re.sub(r"\s+", "", value)
        if compact in _NAME_DENY:
            return False
        if re.fullmatch(r"[가-힣]+", compact) and not (2 <= len(compact) <= 4):
            return False
    if rule.pii_type == PiiType.ADDRESS:
        if len(value) < 4:
            return False
        if not re.search(
            r"(시|군|구|읍|면|동|리|로|길|번지|호|아파트|빌딩)", value
        ):
            return False
    return True


def detect_in_text(
    text: str,
    *,
    unit_index: int,
    bbox: BBox | None,
    enabled: set[PiiType] | None = None,
) -> list[DetectionItem]:
    """Find rule matches in a single text blob (optionally with one bbox)."""
    found: list[DetectionItem] = []
    for rule in _RULES:
        if enabled is not None and rule.pii_type not in enabled:
            continue
        for match in rule.pattern.finditer(text):
            value = _value_from_match(rule, match)
            if not _accept_match(rule, value):
                continue
            found.append(
                DetectionItem(
                    id=new_id(),
                    unit_index=unit_index,
                    bbox=bbox or BBox(0, 0, 0, 0),
                    text=value,
                    pii_type=rule.pii_type,
                    source=MaskSource.RULE,
                    status=DetectionStatus.PENDING,
                    confidence=rule.confidence,
                )
            )
    return found


def bbox_for_snippet(snippet: str, spans: list[ExtractedSpan]) -> BBox | None:
    """Map a text snippet onto span bounding boxes (exact, then partial)."""
    needle = snippet.strip()
    if not needle:
        return None
    needle_ns = re.sub(r"\s+", "", needle)

    for span in spans:
        if needle in span.text and span.bbox is not None:
            return span.bbox

    parts: list[BBox] = []
    for span in spans:
        st = span.text.strip()
        if not st or span.bbox is None:
            continue
        if st in needle or (len(st) >= 2 and st in needle_ns):
            parts.append(span.bbox)
        elif needle in span.text or needle_ns in re.sub(r"\s+", "", span.text):
            parts.append(span.bbox)
    if parts:
        return BBox(
            min(b.x0 for b in parts),
            min(b.y0 for b in parts),
            max(b.x1 for b in parts),
            max(b.y1 for b in parts),
        )

    for span in spans:
        st = span.text.strip()
        if span.bbox is None or len(st) < 2:
            continue
        if needle.startswith(st) or needle.endswith(st) or st.startswith(needle[:2]):
            if st in needle or needle[: max(2, len(st))] in st:
                return span.bbox
    return None


def detect_in_spans(
    spans: list[ExtractedSpan],
    *,
    enabled: set[PiiType] | None = None,
) -> list[DetectionItem]:
    """Run rules per span and on joined page text (helps OCR / split fields)."""
    items: list[DetectionItem] = []
    seen: set[tuple[int, str, str]] = set()

    def _add(item: DetectionItem) -> None:
        key = (item.unit_index, item.pii_type.value, item.text)
        if key in seen:
            return
        seen.add(key)
        items.append(item)

    for span in spans:
        for item in detect_in_text(
            span.text,
            unit_index=span.unit_index,
            bbox=span.bbox,
            enabled=enabled,
        ):
            _add(item)

    if not spans:
        return items

    by_unit: dict[int, list[ExtractedSpan]] = {}
    for span in spans:
        by_unit.setdefault(span.unit_index, []).append(span)

    for unit_index, unit_spans in by_unit.items():
        joined = " ".join(s.text for s in unit_spans)
        for item in detect_in_text(
            joined,
            unit_index=unit_index,
            bbox=None,
            enabled=enabled,
        ):
            mapped = bbox_for_snippet(item.text, unit_spans)
            if mapped is not None:
                item.bbox = mapped
            _add(item)

    return items
