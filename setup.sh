#!/usr/bin/env bash
# GSIMPLC — setup + build script.
#
# Deja el proyecto listo para:
#   1. Modo dev:    python main.py / python gscada_main.py
#   2. Modo GNS3:   import gns3/gsimplc.gns3a y gns3/gscada.gns3a
#
# Uso:
#   ./setup.sh              # install + build (ambos binarios)
#   ./setup.sh --no-build   # solo instala deps y corre tests
#   ./setup.sh --tests      # corre pytest y sale (no compila)
#   ./setup.sh --clean      # borra build/ y dist/ antes de empezar
#
# Requisitos: Python 3.10+, pip, ~600 MB libres para el build.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

RUN_BUILD=1
RUN_TESTS=0
CLEAN=0
for arg in "$@"; do
    case "${arg}" in
        --no-build)  RUN_BUILD=0 ;;
        --tests)     RUN_TESTS=1; RUN_BUILD=0 ;;
        --clean)     CLEAN=1 ;;
        -h|--help)
            sed -n '2,18p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
            exit 0
            ;;
        *) echo "Argumento desconocido: ${arg}"; exit 1 ;;
    esac
done

if [[ -t 1 ]]; then
    C_BOLD="\033[1m"; C_DIM="\033[2m"; C_GREEN="\033[32m"
    C_YELLOW="\033[33m"; C_RED="\033[31m"; C_RST="\033[0m"
else
    C_BOLD=""; C_DIM=""; C_GREEN=""; C_YELLOW=""; C_RED=""; C_RST=""
fi

step() { printf "\n${C_BOLD}══ %s ══${C_RST}\n" "$*"; }
ok()   { printf "${C_GREEN}✓${C_RST} %s\n" "$*"; }
warn() { printf "${C_YELLOW}!${C_RST} %s\n" "$*"; }
fail() { printf "${C_RED}✗${C_RST} %s\n" "$*"; exit 1; }

step "Chequeos basicos"

if [[ ! -f "main.py" ]] || [[ ! -f "gscada_main.py" ]]; then
    fail "No esta main.py / gscada_main.py. Correlo desde la raiz del proyecto."
fi

PYTHON_BIN="$(command -v python3.10 || command -v python3.11 || command -v python3.12 || command -v python3 || true)"
if [[ -z "${PYTHON_BIN}" ]]; then
    fail "No hay python3 en el PATH"
fi
PY_VERSION="$(${PYTHON_BIN} -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
ok "Python ${PY_VERSION} en ${PYTHON_BIN}"

if [[ "$(printf '%s\n' "3.10" "${PY_VERSION}" | sort -V | head -1)" != "3.10" ]]; then
    fail "Hace falta Python 3.10+, hay ${PY_VERSION}"
fi

# Busca un pip que sirva. Si hay venv activo lo usa, si no prueba con venv/ del proyecto.
PIP_BIN=""
if [[ -n "${VIRTUAL_ENV:-}" ]] && [[ -x "${VIRTUAL_ENV}/bin/pip" ]]; then
    PIP_BIN="${VIRTUAL_ENV}/bin/pip"
elif [[ -x "./venv/bin/pip" ]]; then
    PIP_BIN="./venv/bin/pip"
    PYTHON_BIN="./venv/bin/python"
    PY_VERSION="$(${PYTHON_BIN} -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
    ok "usando el venv existente: ${PYTHON_BIN}"
fi
if [[ -z "${PIP_BIN}" ]]; then
    PIP_BIN="$(command -v pip3 || command -v pip || true)"
fi
if [[ -z "${PIP_BIN}" ]]; then
    fail "no se encontro pip"
fi
ok "pip: ${PIP_BIN}"

for required in panel/static gscada/static process_sim/scenarios examples; do
    if [[ ! -d "${required}" ]]; then
        fail "falta un directorio requerido: ${required}"
    fi
done
ok "directorios de recursos presentes"

if [[ "${CLEAN}" -eq 1 ]]; then
    step "Limpiando restos del build anterior"
    rm -rf build/ dist/gsimplc.bin dist/gscada.bin dist/gsimplc/ dist/gscada/
    mkdir -p dist
    ok "limpio"
fi

step "Instalando dependencias"

# Si pip del sistema rechaza la instalacion (PEP 668), crea un venv local.
ensure_pip_install() {
    local target="$1"
    if ${PIP_BIN} install ${target} --quiet 2>/dev/null; then
        return 0
    fi
    warn "pip del sistema rechazo la instalacion (seguro PEP 668). Creando ./venv …"
    ${PYTHON_BIN} -m venv venv
    PYTHON_BIN="./venv/bin/python"
    PIP_BIN="./venv/bin/pip"
    ok "venv listo: ${PYTHON_BIN}"
    ${PIP_BIN} install --upgrade pip wheel --quiet
    ${PIP_BIN} install ${target} --quiet
}

ensure_pip_install "-r requirements.txt"
ok "dependencias instaladas (requirements.txt)"

step "Corriendo los tests"
${PYTHON_BIN} -m pytest tests/ -q
TEST_RC=$?
if [[ ${TEST_RC} -ne 0 ]]; then
    fail "fallaron los tests (rc=${TEST_RC})"
fi
ok "todos los tests pasaron"

if [[ "${RUN_TESTS}" -eq 1 ]]; then
    exit 0
fi

if [[ "${RUN_BUILD}" -eq 0 ]]; then
    step "Sin build (--no-build)"
else
    # Si se creo un venv, lo pongo primero en el PATH para que los
    # sub-scripts del build lo encuentren.
    if [[ -x "./venv/bin/pip" ]]; then
        export PATH="$(pwd)/venv/bin:${PATH}"
        ok "PATH con ./venv/bin incluido (para los sub-scripts de build)"
    fi

    step "Compilando gsimplc.bin"
    if gns3/build.sh; then
        ok "gsimplc.bin listo"
    else
        fail "fallo el build de gsimplc"
    fi

    step "Compilando gscada.bin"
    if gns3/build_scada.sh; then
        ok "gscada.bin listo"
    else
        fail "fallo el build de gscada"
    fi

    step "Compilando las imagenes Docker de GNS3"
    if command -v docker >/dev/null 2>&1; then
        if gns3/build_images.sh; then
            ok "imagenes listas: gsimplc:latest gscada:latest"
        else
            warn "fallo el build de las imagenes (ver arriba). Los binarios de dist/ igual sirven."
        fi
    else
        warn "no hay docker, salteo las imagenes. Los binarios quedan en dist/."
    fi
fi

step "Setup terminado"

cat <<EOF

${C_BOLD}Estado${C_RST}
  Python:        ${PY_VERSION}
  Pip:           ${PIP_BIN}
  Tests:         todos pasaron
EOF

if [[ "${RUN_BUILD}" -eq 1 ]] && [[ -f "dist/gsimplc.bin" ]]; then
    PLC_SIZE="$(du -h dist/gsimplc.bin | awk '{print $1}')"
    SCADA_SIZE="$(du -h dist/gscada.bin | awk '{print $1}')"
    cat <<EOF
  gsimplc.bin:   ${PLC_SIZE}   (dist/gsimplc.bin)
  gscada.bin:    ${SCADA_SIZE}   (dist/gscada.bin)
EOF
fi

cat <<EOF

${C_BOLD}Siguientes pasos${C_RST}

  ${C_DIM}# Modo dev (sin GNS3)${C_RST}
  python3 main.py --program examples/demo_tanque.lad --cycle 100
  ${C_DIM}# en otra terminal:${C_RST}
  python3 gscada_main.py --config gscada/configs/demo.yaml --port 8080

  ${C_DIM}# Modo GNS3 (requiere las imágenes Docker)${C_RST}
  1. Abrí GNS3
  2. File → Import Appliance → gns3/gsimplc.gns3a
  3. File → Import Appliance → gns3/gscada.gns3a
  4. Arrastrá los nodos al canvas (ver gns3/escenario_demo/README.md)

  ${C_DIM}Panel web del PLC${C_RST}    http://localhost:8080
  ${C_DIM}HMI de GSCADA${C_RST}        http://localhost:8080  (puerto del GSCADA)
  ${C_DIM}Modbus TCP${C_RST}           puerto 502
EOF
