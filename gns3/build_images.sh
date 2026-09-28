#!/usr/bin/env bash
# Compila las imagenes Docker de GSIMPLC y GSCADA para los appliances
# de GNS3.
#
# Necesita los binarios (dist/gsimplc.bin y dist/gscada.bin) porque los
# Dockerfile los copian adentro. Si falta alguno, lo compila antes con
# build.sh / build_scada.sh.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

if [[ ! -f "dist/gsimplc.bin" ]]; then
    echo "falta dist/gsimplc.bin — lo compilo primero"
    "${SCRIPT_DIR}/build.sh"
fi
if [[ ! -f "dist/gscada.bin" ]]; then
    echo "falta dist/gscada.bin — lo compilo primero"
    "${SCRIPT_DIR}/build_scada.sh"
fi

echo "Compilando la imagen Docker: gsimplc:latest"
docker build -t gsimplc:latest -f Dockerfile.gsimplc .

echo "Compilando la imagen Docker: gscada:latest"
docker build -t gscada:latest -f Dockerfile.gscada .

echo "ok: imagenes gsimplc:latest y gscada:latest listas"
