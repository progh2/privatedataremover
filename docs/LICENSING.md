# Packaging / Licensing Decision — PyMuPDF (AGPL)

| 항목 | 내용 |
|------|------|
| 결정일 | 2026-07-29 |
| 이슈 | #4 |
| 결정 | **오픈소스 배포에서 PyMuPDF AGPL-3.0을 수용**한다 |

## 배경

Private Data Remover의 PDF 엔진으로 PyMuPDF를 사용한다.  
PyMuPDF는 AGPL-3.0 또는 Artifex 상용 라이선스이다.

## 결정

1. 본 프로젝트는 **오픈소스(Apache-2.0 앱 코드 + 의존성 고지)** 로 공개한다.
2. PyMuPDF를 AGPL로 링크·배포할 때 **배포물 전체에 AGPL 의무가 적용될 수 있음**을 README / THIRD_PARTY_NOTICES에 명시한다.
3. 상용 폐쇄형 배포가 필요하면 (a) Artifex 상용 라이선스 또는 (b) 대체 PDF 엔진으로 교체하는 후속 이슈를 연다.
4. 바이너리 릴리스에는 소스 저장소 URL과 라이선스 고지를 포함한다.

## 사용자 영향

- 수정·재배포 시 AGPL / Apache-2.0 / LGPL(PySide6) 의무를 함께 확인해야 한다.
- 민감 문서를 외부 API로 보내지 않으려면 설정에서 **로컬 전용 모드** + Ollama를 사용한다.
