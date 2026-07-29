# GitHub 작업 관리

저장소: https://github.com/progh2/privatedataremover

## 마일스톤

| 마일스톤 | URL |
|----------|-----|
| M0 — Repo & Docs | https://github.com/progh2/privatedataremover/milestone/1 |
| M1 — Shell UI & PDF View | https://github.com/progh2/privatedataremover/milestone/2 |
| M2 — Detect & Manual Mask | https://github.com/progh2/privatedataremover/milestone/3 |
| M3 — Pattern & Undo | https://github.com/progh2/privatedataremover/milestone/4 |
| M4 — Export | https://github.com/progh2/privatedataremover/milestone/5 |
| M5 — Release v0.1.0 | https://github.com/progh2/privatedataremover/milestone/6 |
| M6 — Excel / HWPX | https://github.com/progh2/privatedataremover/milestone/7 |

이슈 목록: https://github.com/progh2/privatedataremover/issues

## Projects 보드

GitHub Projects 생성에는 `project` / `read:project` 스코프가 필요합니다.

```bash
gh auth refresh -s project,read:project
gh project create --owner progh2 --title "Private Data Remover"
# 이슈를 보드에 추가한 뒤 레포 Settings → Projects에서 연결
```

또는 웹 UI: https://github.com/users/progh2/projects

권장 컬럼: **Backlog → Ready → In Progress → Review → Done**

## 이슈 재생성 스크립트

```bash
python scripts/create_github_issues.py
```

이미 이슈가 있으면 중복 생성되므로 일반적으로 재실행하지 마세요.

## 문서 동기화 규칙

기능·설치·사용법·로드맵이 바뀌면 **같은 PR에서** `README.md`와 `docs/PRD.md`를 함께 갱신합니다.
