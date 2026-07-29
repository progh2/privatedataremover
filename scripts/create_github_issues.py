#!/usr/bin/env python3
"""Create GitHub issues for privatedataremover. Requires: gh auth."""

from __future__ import annotations

import json
import subprocess
import sys

REPO = "progh2/privatedataremover"

M0 = "M0 — Repo & Docs"
M1 = "M1 — Shell UI & PDF View"
M2 = "M2 — Detect & Manual Mask"
M3 = "M3 — Pattern & Undo"
M4 = "M4 — Export"
M5 = "M5 — Release v0.1.0"
M6 = "M6 — Excel / HWPX"

ISSUES: list[dict] = [
    {
        "title": "README / PRD / 라이선스 초안 추가",
        "milestone": M0,
        "labels": ["docs"],
        "body": """## Summary
README, docs/PRD.md, LICENSE, THIRD_PARTY_NOTICES, CONTRIBUTING 초안을 레포에 추가합니다.

## Acceptance criteria
- [x] README에 설치·사용·로드맵 포함
- [x] PRD v1.4 반영 (OCR, PySide, 저장 A/B, 수동·패턴, 유형, Excel/HWPX)
- [x] Apache-2.0 LICENSE 및 서드파티 고지

## PRD refs
문서 전반

## Notes
초기 커밋에서 대부분 완료. 추적·마감용.
""",
    },
    {
        "title": "Python 프로젝트 골격 및 DocumentAdapter 스텁",
        "milestone": M0,
        "labels": ["docs"],
        "body": """## Summary
src 레이아웃, pyproject.toml, PDF/XLSX/HWPX adapter 스텁, 최소 UI 엔트리포인트.

## Acceptance criteria
- [x] pip install -e . 가능한 pyproject
- [x] DocumentAdapter + Pdf/Xlsx/Hwpx 스텁
- [x] python -m privatedataremover 엔트리
- [x] 기본 pytest

## PRD refs
F-EXT-01
""",
    },
    {
        "title": "GitHub Project·라벨·마일스톤 세팅",
        "milestone": M0,
        "labels": ["docs"],
        "body": """## Summary
라벨, 마일스톤 M0–M6, 이슈 백로그, Project 보드를 구성합니다.

## Acceptance criteria
- [ ] 라벨 생성
- [ ] 마일스톤 M0–M6
- [ ] 백로그 이슈 생성
- [ ] GitHub Project 보드 연결
""",
    },
    {
        "title": "PyMuPDF AGPL 라이선스 영향 검토 및 결정",
        "milestone": M0,
        "labels": ["docs", "export"],
        "body": """## Summary
PyMuPDF AGPL이 배포·라이선스에 미치는 영향을 문서화하고 방향을 정합니다.

## Acceptance criteria
- [ ] THIRD_PARTY_NOTICES에 결론 반영
- [ ] README 고지 (필요 시)
- [ ] 대체 엔진 필요 시 후속 이슈

## PRD refs
§7, 리스크
""",
    },
    {
        "title": "PySide6 메인 윈도우·메뉴·설정 골격",
        "milestone": M1,
        "labels": ["ui"],
        "body": """## Summary
메인 윈도우, 파일/편집/보기/설정 메뉴, 상태바 골격.

## Acceptance criteria
- [ ] QMainWindow + 메뉴바
- [ ] 설정 다이얼로그 골격
- [ ] 한국어 UI 기본 문자열

## PRD refs
F-CF-05, UX §5
""",
    },
    {
        "title": "PDF 열기·페이지 네비게이션·미리보기",
        "milestone": M1,
        "labels": ["ui", "pdf"],
        "body": """## Summary
PdfAdapter로 PDF를 열고 페이지를 탐색·미리보기합니다.

## Acceptance criteria
- [ ] 파일 열기 / 드래그앤드롭
- [ ] 페이지 이동·줌
- [ ] 원본 파일 비수정

## PRD refs
F-IO-01, F-IO-02, F-IO-03
""",
    },
    {
        "title": "LLM 설정 UI (Ollama / OpenAI / Claude) + 연결 테스트",
        "milestone": M1,
        "labels": ["ui", "llm"],
        "body": """## Summary
프로바이더·엔드포인트·모델·API 키 설정과 연결 테스트.

## Acceptance criteria
- [ ] 세 프로바이더 선택
- [ ] 키 마스킹·로컬 저장
- [ ] 연결 테스트 피드백

## PRD refs
F-CF-01, F-CF-02, F-CF-03
""",
    },
    {
        "title": "로컬 전용 모드 플래그 (외부 API 차단)",
        "milestone": M1,
        "labels": ["llm"],
        "body": """## Summary
로컬 전용 모드에서 외부 API를 막고 Ollama만 허용합니다.

## Acceptance criteria
- [ ] 설정 토글
- [ ] 외부 호출 시 명확한 오류

## PRD refs
F-CF-04, F-SEC-02
""",
    },
    {
        "title": "텍스트 추출 + Tesseract OCR 연동",
        "milestone": M2,
        "labels": ["ocr", "pdf"],
        "body": """## Summary
네이티브 텍스트 추출과 필요 시 OCR, bbox 좌표 정렬.

## Acceptance criteria
- [ ] 텍스트 페이지 추출
- [ ] OCR (kor+eng), 경로 설정, 미설치 안내
- [ ] bbox 정렬

## PRD refs
F-OCR-01–05
""",
    },
    {
        "title": "규칙 기반 PII 탐지 + 유형 분류",
        "milestone": M2,
        "labels": ["pii"],
        "body": """## Summary
규칙으로 한국형 PII 후보를 탐지하고 유형을 부여합니다.

## Acceptance criteria
- [ ] 전화·이메일·주민번호 등 기본 규칙
- [ ] 유형 enum 매핑
- [ ] 설정에서 유형 on/off

## PRD refs
F-AI-02, F-AI-05, F-TYP-01
""",
    },
    {
        "title": "LLM adapter (Ollama/OpenAI/Anthropic) + 구조화 결과",
        "milestone": M2,
        "labels": ["pii", "llm"],
        "body": """## Summary
통일 LLM 인터페이스로 PII 구조화 결과를 받습니다.

## Acceptance criteria
- [ ] 세 adapter
- [ ] 페이지/청크 단위 호출
- [ ] PDF 바이너리 미전송

## PRD refs
F-AI-01, F-SEC-03
""",
    },
    {
        "title": "탐지 목록 UI (유형·필터·상태) + 오버레이",
        "milestone": M2,
        "labels": ["ui", "pii"],
        "body": """## Summary
우측 목록에 유형·스니펫·출처·상태 표시 및 PDF 하이라이트.

## Acceptance criteria
- [ ] 유형 라벨·필터
- [ ] 색+텍스트
- [ ] 오버레이 동기화

## PRD refs
F-TYP-01–05, F-AI-03–04
""",
    },
    {
        "title": "수동 마스킹 그리기·편집·삭제",
        "milestone": M2,
        "labels": ["ui", "mask"],
        "body": """## Summary
드래그 박스 추가, 이동·리사이즈·삭제, 유형 지정.

## Acceptance criteria
- [ ] 그리기/편집/Delete/Esc
- [ ] 줌 시 좌표 정확
- [ ] 유형 지정 가능

## PRD refs
F-MAN-01–05, F-TYP-06
""",
    },
    {
        "title": "항목·유형 단위 확정 / 무시 / 마스킹 취소",
        "milestone": M2,
        "labels": ["mask", "pii"],
        "body": """## Summary
항목 또는 유형 단위로 마스킹 확정·무시·취소.

## Acceptance criteria
- [ ] 항목 취소
- [ ] 유형 전체 / 현재 페이지 유형 취소
- [ ] 취소 후 재자동적용 방지

## PRD refs
F-CX-01–04, F-UN-01–02
""",
    },
    {
        "title": "페이지 유사도·반복 그룹 탐지",
        "milestone": M3,
        "labels": ["pattern", "pdf"],
        "body": """## Summary
레이아웃/텍스트 유사도로 반복 페이지 그룹 제안.

## Acceptance criteria
- [ ] 그룹 제안 UI
- [ ] 예외 페이지 표시

## PRD refs
F-LRN-02, F-LRN-05
""",
    },
    {
        "title": "수동/확정 마스킹 시드 → 패턴 제안·미리보기·일괄 적용",
        "milestone": M3,
        "labels": ["pattern", "mask"],
        "body": """## Summary
사용자 마스킹을 시드로 유사 페이지 적용 제안, 미리보기 후 승인 시 반영.

## Acceptance criteria
- [ ] 시드 지정
- [ ] 절대/비율 좌표 옵션
- [ ] 미리보기 → 승인 → 일괄 적용

## PRD refs
F-LRN-01–04
""",
    },
    {
        "title": "패턴 단위 롤백 + 전역 Undo/Redo",
        "milestone": M3,
        "labels": ["mask"],
        "body": """## Summary
패턴 일괄 적용 롤백과 편집 Undo/Redo.

## Acceptance criteria
- [ ] 패턴 롤백
- [ ] Undo/Redo
- [ ] 페이지 전체 지우기

## PRD refs
F-UN-03–05
""",
    },
    {
        "title": "무시 영역·유형 세션 규칙",
        "milestone": M3,
        "labels": ["pii", "mask"],
        "body": """## Summary
문서 세션에서 무시 영역/유형을 저장해 재제안을 막습니다.

## Acceptance criteria
- [ ] 영역 무시
- [ ] 유형 무시 (세션)
- [ ] 재스캔 시 존중

## PRD refs
F-CX-05
""",
    },
    {
        "title": "안전 저장: 선택 텍스트 삭제 + 검정 박스",
        "milestone": M4,
        "labels": ["export", "pdf"],
        "body": """## Summary
확정 마스크에 대해 텍스트 제거 + 검정 박스 PDF 사본 저장.

## Acceptance criteria
- [ ] 확정 PII 텍스트 미추출
- [ ] 검정 박스 표시
- [ ] 원본 불변

## PRD refs
F-EX-01, F-IO-03
""",
    },
    {
        "title": "페이지 이미지화 후 PDF로 저장 (DPI 옵션)",
        "milestone": M4,
        "labels": ["export", "pdf"],
        "body": """## Summary
마스킹이 구워진 페이지 래스터로 새 PDF 생성 (별도 메뉴).

## Acceptance criteria
- [ ] 메뉴: 페이지 이미지화 후 PDF로 저장
- [ ] DPI 옵션
- [ ] 원문 텍스트 미추출

## PRD refs
F-EX-02, F-EX-03
""",
    },
    {
        "title": "저장 전 잔존 텍스트 검증·경고",
        "milestone": M4,
        "labels": ["export"],
        "body": """## Summary
저장 직전 확정 PII 잔존 여부를 검사하고 경고합니다.

## Acceptance criteria
- [ ] 안전 저장 검증
- [ ] 실패 시 경고 / 이미지화 폴백 안내

## PRD refs
F-EX-04, F-EX-05
""",
    },
    {
        "title": "임시 파일 정리·원본 비수정 보장",
        "milestone": M4,
        "labels": ["export"],
        "body": """## Summary
임시 파일 정리 및 원본 비수정 테스트.

## Acceptance criteria
- [ ] 종료/저장 후 임시 파일 삭제
- [ ] 원본 hash 불변 테스트

## PRD refs
F-EX-06, F-IO-03
""",
    },
    {
        "title": "pytest (core) + 샘플 PDF fixture",
        "milestone": M5,
        "labels": ["docs"],
        "body": """## Summary
탐지·마스킹·export용 샘플 PDF와 테스트 보강.

## Acceptance criteria
- [ ] fixture PDF
- [ ] export 잔존 텍스트 테스트
""",
    },
    {
        "title": "PyInstaller(또는 동등) Win/Mac/Linux 빌드",
        "milestone": M5,
        "labels": ["docs"],
        "body": """## Summary
OS별 실행 파일 빌드 스크립트·문서.

## Acceptance criteria
- [ ] 빌드 문서
- [ ] 최소 1개 OS 스모크 성공
""",
    },
    {
        "title": "사용 가이드 스크린샷·CONTRIBUTING 보강",
        "milestone": M5,
        "labels": ["docs", "good first issue"],
        "body": """## Summary
README 스크린샷/사용 흐름 보강, CONTRIBUTING 다듬기.

## Acceptance criteria
- [ ] README 사용 절 갱신
- [ ] PRD와 불일치 없음
""",
    },
    {
        "title": "v0.1.0 릴리스",
        "milestone": M5,
        "labels": ["docs"],
        "body": """## Summary
태그, GitHub Release, 변경 로그 게시.

## Acceptance criteria
- [ ] version bump
- [ ] Release notes
- [ ] M0–M5 핵심 완료 또는 defer 명시
""",
    },
    {
        "title": "DocumentAdapter 계약 문서화·PDF 리팩터 검증",
        "milestone": M6,
        "labels": ["docs", "ext-xlsx", "ext-hwpx"],
        "body": """## Summary
Adapter 계약 문서화 및 PDF 구현 검증.

## Acceptance criteria
- [ ] adapters 문서
- [ ] PDF 계약 테스트 통과

## PRD refs
F-EXT-01, F-EXT-04
""",
    },
    {
        "title": "Excel adapter: 셀 PII, 숨김 시트/행열 탐지 UI",
        "milestone": M6,
        "labels": ["ext-xlsx", "pii"],
        "body": """## Summary
xlsx 셀·숨겨진 시트·숨김 행/열 탐지 및 검토 UI.

## Acceptance criteria
- [ ] 숨김 시트 목록
- [ ] 셀 PII 후보
- [ ] 검토 목록 통합

## PRD refs
F-EXT-02
""",
    },
    {
        "title": "Excel export (치환·삭제)",
        "milestone": M6,
        "labels": ["ext-xlsx", "export"],
        "body": """## Summary
확정 마스크에 따라 셀 삭제/치환 xlsx 사본 저장.

## Acceptance criteria
- [ ] 사본 저장
- [ ] 숨김 시트 처리 옵션

## PRD refs
F-EXT-05
""",
    },
    {
        "title": "HWPX 조사·spike (파서·라이선스)",
        "milestone": M6,
        "labels": ["ext-hwpx", "docs"],
        "body": """## Summary
HWPX 구조·파서·라이선스 spike 및 MVP 범위 제안.

## Acceptance criteria
- [ ] spike 문서
- [ ] 후속 이슈 분해

## PRD refs
F-EXT-03
""",
    },
    {
        "title": "HWPX adapter MVP",
        "milestone": M6,
        "labels": ["ext-hwpx"],
        "body": """## Summary
spike 결과에 따른 본문 추출·기본 마스킹·export MVP.

## Acceptance criteria
- [ ] open/extract 기본
- [ ] 단순 마스킹 export
- [ ] README/PRD 갱신

## PRD refs
F-EXT-03

Depends on HWPX spike
""",
    },
]


def create_issue(item: dict) -> None:
    cmd = [
        "gh",
        "issue",
        "create",
        "--repo",
        REPO,
        "--title",
        item["title"],
        "--body",
        item["body"],
        "--milestone",
        str(item["milestone"]),
    ]
    for label in item["labels"]:
        cmd.extend(["--label", label])
    print("Creating:", item["title"], file=sys.stderr)
    subprocess.run(cmd, check=True)


def main() -> int:
    for item in ISSUES:
        create_issue(item)
    subprocess.run(["gh", "issue", "list", "--repo", REPO, "--limit", "50"], check=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
