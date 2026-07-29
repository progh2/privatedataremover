# 사용 가이드 (v0.1.0)

스크린샷은 릴리스 노트·위키에 추가할 수 있습니다. 아래는 핵심 흐름입니다.

## 1. 설치

```bash
git clone https://github.com/progh2/privatedataremover.git
cd privatedataremover
python -m venv .venv
# Windows: .venv\Scripts\activate
pip install -e .
```

선택: [Tesseract](https://github.com/tesseract-ocr/tesseract) (OCR), [Ollama](https://ollama.com/) (로컬 LLM)

## 2. 실행

```bash
python -m privatedataremover
```

## 3. 설정

**도구 → 설정**

| 항목 | 설명 |
|------|------|
| 프로바이더 | Ollama / OpenAI / Claude |
| 로컬 전용 | 켜면 외부 API 차단 |
| Tesseract 경로 | Windows에서 PATH에 없을 때 |

**연결 테스트**로 동작을 확인합니다.

## 4. PDF 열기 · 분석

1. **파일 → 열기** 또는 드래그앤드롭
2. 툴바 **OCR** / **LLM 사용** 선택
3. **개인정보 분석** (Ctrl+R)
4. 우측 목록에서 유형·상태를 확인, 뷰어 오버레이 확인

## 5. 검토 · 마스킹

| 동작 | 방법 |
|------|------|
| 확정 | 목록에서 항목 선택 → 마스킹 확정 |
| 무시 | 무시 / 유형 무시 |
| 취소 | 마스킹 취소, Delete |
| 수동 | **마스킹 그리기**(M) 후 드래그 |
| 무시 영역 | **무시 영역 그리기** 후 드래그 |

## 6. 비슷한 페이지에 적용

1. 시드 페이지에 확정/수동 마스크 준비
2. **편집 → 비슷한 페이지에 적용…** (Ctrl+Shift+A)
3. 유사 페이지·좌표 모드 확인 후 적용
4. 필요 시 **마지막 패턴 적용 취소** 또는 **실행 취소**

## 7. 저장

| 메뉴 | 결과 |
|------|------|
| 안전 저장… | 텍스트 삭제 + 검정 박스 사본 |
| 페이지 이미지화 후 PDF로 저장… | 이미지 전용 PDF (DPI 선택) |

- 원본은 수정되지 않습니다.
- 저장 후 잔존 텍스트 검사가 수행됩니다.
- 미확정 탐지가 있으면 경고합니다.

## 8. 면책

완전 비식별을 법적으로 보장하지 않습니다. 중요 문서는 사람이 최종 확인하세요.
