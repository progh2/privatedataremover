# Changelog

## 0.2.1 — 2026-07-30

### 수정 (안정성)
- 무시 영역/마스킹 그리기 시 크래시 수정 (Qt 시그널 커스텀 타입 → `Signal(object)`)
- 대용량 PDF 분석 시 앱 멈춤·크래시 수정: 분석·저장을 백그라운드 스레드로 분리, 페이지별 진행률 + 취소 지원
- 분석 완료 직후 크래시 수정 (실행 중 QThread 참조 조기 해제 → 부모 지정 + 종료 후 해제)
- 마스킹 취소 후 화면 클릭 시 크래시 수정 (탐지 목록 갱신 무한 재귀 차단)
- 「선택 유형 전부 취소/무시」 크래시 수정 (`PiiType`이 시그널 통과 시 str로 변환되는 문제)
- LLM 프로바이더 설정 str/enum 왕복 문제 수정 (`coerce_provider`)

### 추가 (탐지)
- 이름·주소 규칙 탐지: 라벨(성명/주소 등) 기반 + 성씨/시·구·동·로·길 휴리스틱
- 페이지 통합 텍스트 재검사로 OCR로 쪼개진 필드도 탐지, bbox 매핑 개선
- LLM 프롬프트 한국어 전면 개편 (이름·주소 강조, `{"items":[...]}` JSON 스키마, 한글 유형명 별칭 파싱)

### 추가 (UI/UX)
- Ollama 설치 모델 목록 조회·선택 (설정 → 「모델 목록 불러오기」)
- 빠른 검토: 확정/무시/취소 시 다음 항목 자동 선택
- 실행 취소 피드백: 상태바에 되돌린 작업 표시, 버튼 활성화 상태 반영
- 미리보기 마스킹 클릭 시 탐지 목록에서 해당 항목 자동 표시 (필터 자동 완화 + 스크롤)
- 실행 스크립트 추가: `run.cmd`(CP949) / `run.ps1`(UTF-8 BOM) / `run.sh`

### 개선
- HWPX: `hp:t` 네임스페이스 텍스트 우선 추출, header/footer 단위 분리
- Excel: 저장 후 셀 잔존 문자열 검사 (`find_residual_in_xlsx`)
- UI: 시트/섹션 목록 툴팁에 숨김·경로 메타 표시
- README: 동작 원리 UML(mermaid) 문서화

## 0.2.0 — 2026-07-29

### 추가
- Excel (`.xlsx`) adapter: 셀 PII, 숨긴 시트/행/열, export 치환+검정 채우기
- HWPX adapter MVP: 섹션 텍스트 추출, XML 문자열 치환 export
- `docs/adapters.md`, `docs/HWPX_SPIKE.md`
- 문서 열기 통합 (PDF / Excel / HWPX)

## 0.1.0 — 2026-07-29

첫 공개 MVP 릴리스.

### 기능
- PySide6 크로스플랫폼 GUI (Windows / macOS / Linux)
- PDF 열기·미리보기·줌, 드래그앤드롭
- OCR (Tesseract), 규칙 기반 PII 탐지, 선택적 LLM (Ollama / OpenAI / Claude)
- 개인정보 유형 표시·필터, 수동 마스킹, 항목/유형 확정·무시·취소
- 유사 페이지 패턴 일괄 적용, Undo/Redo, 무시 영역
- 안전 저장 (텍스트 삭제 + 검정 박스), 페이지 이미지화 PDF
- 잔존 텍스트 검사, 원본 파일 무결성 보호

### 문서
- README, PRD, 사용 가이드, 빌드 가이드, 라이선스 결정 (PyMuPDF AGPL 수용)

### 제한
- Excel / HWPX는 adapter 스텁만 제공 (M6+)
- GUI 자동화 E2E 테스트는 미포함
