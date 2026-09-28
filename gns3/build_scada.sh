#!/usr/bin/env bash
# Compila el binario independiente de GSCADA con PyInstaller.
#
# Deja dist/gscada.bin (ejecutable de un solo archivo) con gscada/static
# y gscada/configs adentro, para que el HMI sirva sus archivos.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

if [[ ! -f "gscada_main.py" ]]; then
    echo "error: no esta gscada_main.py. Correlo desde la raiz del proyecto." >&2
    exit 1
fi

PYTHON_BIN="${PYTHON_BIN:-}"
if [[ -z "${PYTHON_BIN}" ]]; then
    if [[ -x "./venv/bin/python" ]]; then
        PYTHON_BIN="./venv/bin/python"
    else
        PYTHON_BIN="$(command -v python3 || true)"
    fi
fi
if [[ -z "${PYTHON_BIN}" ]]; then
    echo "error: no hay python3 en el PATH" >&2
    exit 1
fi

echo "Compilando gscada.bin con ${PYTHON_BIN} ..."
"${PYTHON_BIN}" -m PyInstaller gscada.bin.spec --noconfirm --clean --distpath dist

BIN="dist/gscada.bin"
if [[ ! -x "${BIN}" ]]; then
    echo "error: el build no genero ${BIN}" >&2
    exit 1
fi

"${BIN}" --help >/dev/null
echo "ok: ${BIN} compilado y validado"
