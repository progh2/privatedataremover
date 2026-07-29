# DocumentAdapter 계약

이 문서는 `privatedataremover.core.adapters.base.DocumentAdapter`의 구현 계약입니다.  
PDF는 참조 구현이며, Excel(`.xlsx`) / HWPX(`.hwpx`)는 동일 인터페이스로 확장합니다.

## 원칙

1. **원본 비수정** — `open` 이후 원본 경로에 write 하지 않습니다. export는 항상 `dest` 사본만 만듭니다.
2. **단위(unit)** — PDF=페이지, Excel=시트(+숨김 메타), HWPX=섹션.
3. **좌표** — PDF는 페이지 포인트. Excel은 `BBox(col, row, col+1, row+1)` (0-based). HWPX는 논리 인덱스 bbox.
4. **추출** — `extract_spans`는 규칙/LLM PII 파이프라인에 들어갈 텍스트+위치를 반환합니다.
5. **미리보기** — `render_unit_preview`는 UI용 PNG 바이트를 반환합니다.
6. **내보내기**
   - `export_safe`: 포맷 네이티브 비식별(엑셀 셀 삭제/치환, PDF 레닥션 등)
   - `export_rasterized`: 가능하면 이미지 PDF; 미지원 시 `NotImplementedError`와 안내

## 필수 메서드

| 메서드 | 설명 |
|--------|------|
| `open(path)` | 로드. 암호/손상 시 명확한 예외 |
| `close()` | 리소스·임시파일 해제 |
| `iter_units()` | `DocumentUnit` (index, label, width, height, meta) |
| `extract_spans(i)` | `ExtractedSpan` 목록 |
| `render_unit_preview(i, scale)` | PNG bytes |
| `export_safe(dest, masks, ...)` | 마스킹 반영 사본 |
| `export_rasterized(dest, masks, dpi=...)` | 래스터 PDF 또는 NotImplemented |

## DocumentUnit.meta (권장 키)

| 키 | 포맷 | 의미 |
|----|------|------|
| `hidden` | xlsx | 시트 숨김 여부 |
| `very_hidden` | xlsx | veryHidden |
| `hidden_rows` | xlsx | 숨긴 행 번호 목록(요약) |
| `hidden_cols` | xlsx | 숨긴 열 번호 목록(요약) |
| `sheet_name` | xlsx | 시트명 |
| `section` | hwpx | 섹션 파일명 |

## 팩토리

`privatedataremover.core.adapters.factory.open_document(path) -> DocumentAdapter`

확장자 `.pdf` / `.xlsx` / `.xlsm` / `.hwpx`를 지원합니다.

## 검증

- PDF: `tests/test_pdf_adapter.py`, `tests/test_export.py`
- Excel: `tests/test_xlsx_adapter.py`
- HWPX: `tests/test_hwpx_adapter.py` (최소)
