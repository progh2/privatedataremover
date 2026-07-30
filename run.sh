#!/usr/bin/env bash
# Private Data Remover launcher (Linux / macOS)
set -euo pipefail
cd "$(dirname "$0")"

if [[ -f .venv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
elif [[ -f venv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source venv/bin/activate
fi

if ! command -v python3 >/dev/null 2>&1 && ! command -v python >/dev/null 2>&1; then
  echo "[오류] python3 를 찾을 수 없습니다. Python 3.11+ 를 설치하세요." >&2
  exit 1
fi

PYTHON=python3
command -v python3 >/dev/null 2>&1 || PYTHON=python

if ! "$PYTHON" -c "import privatedataremover" >/dev/null 2>&1; then
  echo "패키지가 없습니다. 편집 모드로 설치합니다..."
  "$PYTHON" -m pip install -e ".[dev]"
fi

echo "Private Data Remover 실행 중..."
exec "$PYTHON" -m privatedataremover "$@"
