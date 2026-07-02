#!/usr/bin/env bash
# Idempotent bootstrap for the shared _consultant venv.
# Re-runs only when requirements.lock SHA changes.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="${ROOT}/.venv"
LOCK="${ROOT}/requirements.lock"
STAMP="${VENV}/.lock.sha"
PY_BIN="${CONSULTANT_PY:-/opt/homebrew/bin/python3.12}"

mkdir -p "${ROOT}"

# Create venv if missing
if [[ ! -d "${VENV}" ]]; then
  "${PY_BIN}" -m venv "${VENV}"
fi

CURR_SHA="$(shasum -a 256 "${LOCK}" | awk '{print $1}')"
PREV_SHA=""
[[ -f "${STAMP}" ]] && PREV_SHA="$(cat "${STAMP}")"

if [[ "${CURR_SHA}" != "${PREV_SHA}" ]]; then
  "${VENV}/bin/pip" install --quiet --upgrade pip
  "${VENV}/bin/pip" install --quiet -r "${LOCK}"
  echo "${CURR_SHA}" > "${STAMP}"
fi

# Emit the activation path for callers
echo "${VENV}/bin/python3"
