#!/usr/bin/env bash
# Compila el binario independiente de GSIMPLC con PyInstaller.
#
# Deja dist/gsimplc.bin (ejecutable de un solo archivo) con panel/static
# y examples adentro, para que el panel web ande solo.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

if [[ ! -f "main.py" ]]; then
    echo "error: no esta main.py. Correlo desde la raiz del proyecto." >&2
    exit 1
fi
if [[ ! -d "panel/static" ]]; then
    echo "error: falta panel/static (lo necesita el panel web)." >&2
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

echo "Compilando gsimplc.bin con ${PYTHON_BIN} ..."
"${PYTHON_BIN}" -m PyInstaller gsimplc.bin.spec --noconfirm --clean --distpath dist

BIN="dist/gsimplc.bin"
if [[ ! -x "${BIN}" ]]; then
    echo "error: el build no genero ${BIN}" >&2
    exit 1
fi

"${BIN}" --help >/dev/null
echo "ok: ${BIN} compilado y validado"
