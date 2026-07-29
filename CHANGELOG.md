# Changelog

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
