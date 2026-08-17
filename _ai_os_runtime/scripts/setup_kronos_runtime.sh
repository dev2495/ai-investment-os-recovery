#!/usr/bin/env bash
set -euo pipefail

export PATH="/opt/homebrew/bin:/opt/homebrew/opt/postgresql@16/bin:${PATH}"

RUNTIME_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
KRONOS_HOME="${AI_OS_KRONOS_HOME:-/Volumes/Devarsh SSD/AI OS Data/models/kronos-runtime}"
PYTHON_BOOTSTRAP="${AI_OS_KRONOS_BOOTSTRAP_PYTHON:-/opt/homebrew/bin/python3.13}"
SOURCE_DIR="${AI_OS_KRONOS_REPO:-${KRONOS_HOME}/source/Kronos}"
VENV_DIR="${KRONOS_HOME}/venv"
CACHE_DIR="${KRONOS_HOME}/huggingface"
PIP_CACHE_DIR="${KRONOS_HOME}/pip-cache"
TMP_DIR="${KRONOS_HOME}/tmp"
XDG_CACHE_DIR="${KRONOS_HOME}/xdg-cache"
REVISION="67b630e67f6a18c9e9be918d9b4337c960db1e9a"

if [[ ! -d "/Volumes/Devarsh SSD" ]]; then
  echo "External SSD is not mounted at /Volumes/Devarsh SSD." >&2
  exit 1
fi
if [[ ! -x "${PYTHON_BOOTSTRAP}" ]]; then
  echo "Python 3.13 is required at ${PYTHON_BOOTSTRAP}." >&2
  exit 1
fi

mkdir -p "${KRONOS_HOME}/source" "${CACHE_DIR}/hub" "${CACHE_DIR}/xet" "${PIP_CACHE_DIR}" "${TMP_DIR}" "${XDG_CACHE_DIR}"
export PIP_CACHE_DIR TMPDIR="${TMP_DIR}"
export AI_OS_KRONOS_HOME="${KRONOS_HOME}"
export AI_OS_KRONOS_REPO="${SOURCE_DIR}"
export AI_OS_KRONOS_CACHE="${CACHE_DIR}"
export AI_OS_KRONOS_PYTHON="${VENV_DIR}/bin/python"
export HF_HOME="${CACHE_DIR}"
export HF_HUB_CACHE="${CACHE_DIR}/hub"
export HF_XET_CACHE="${CACHE_DIR}/xet"
export XDG_CACHE_HOME="${XDG_CACHE_DIR}"

if [[ ! -d "${SOURCE_DIR}/.git" ]]; then
  git clone --filter=blob:none https://github.com/shiyu-coder/Kronos.git "${SOURCE_DIR}"
fi

if [[ -n "$(git -C "${SOURCE_DIR}" status --porcelain -- model)" ]]; then
  echo "Kronos model source has local changes; refusing to replace them." >&2
  exit 1
fi
git -C "${SOURCE_DIR}" fetch origin "${REVISION}"
git -C "${SOURCE_DIR}" checkout --detach "${REVISION}"
actual_revision="$(git -C "${SOURCE_DIR}" rev-parse HEAD)"
if [[ "${actual_revision}" != "${REVISION}" ]]; then
  echo "Kronos source revision verification failed." >&2
  exit 1
fi

if [[ ! -x "${VENV_DIR}/bin/python" ]]; then
  "${PYTHON_BOOTSTRAP}" -m venv "${VENV_DIR}"
fi

"${VENV_DIR}/bin/python" -m pip install --upgrade pip
"${VENV_DIR}/bin/python" -m pip install --only-binary=:all: \
  "torch==2.13.0" \
  "numpy==2.3.5" \
  "pandas==2.2.3" \
  "einops==0.8.1" \
  "huggingface_hub==0.33.1" \
  "tqdm==4.67.1" \
  "safetensors==0.6.2"

"${VENV_DIR}/bin/python" "${RUNTIME_ROOT}/scripts/kronos_inference_worker.py" --prepare
"${VENV_DIR}/bin/python" -m pip freeze > "${KRONOS_HOME}/requirements.lock.txt"
git -C "${SOURCE_DIR}" show -s --format='%H %cI %s' HEAD > "${KRONOS_HOME}/source-revision.txt"

"${PYTHON_BOOTSTRAP}" "${RUNTIME_ROOT}/scripts/run_kronos_forecast.py" \
  --readiness --activate-tool

du -sh "${KRONOS_HOME}"
