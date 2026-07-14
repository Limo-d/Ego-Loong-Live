#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"
PYTHON="${ROOT}/.venv/bin/python"
[[ -x "${PYTHON}" ]] || { echo "Missing .venv. Run ./scripts/install.sh first." >&2; exit 1; }
exec "${PYTHON}" -m backend.main --mock "$@"

