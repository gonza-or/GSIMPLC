#!/bin/sh
# Control del servicio del binario GSIMPLC/GSCADA.
#
# Se instala como /usr/local/bin/gsimplc-manage (el mismo script para las
# dos imagenes; usa la variable GSIMPLC_BIN que define el Dockerfile).

BIN="/usr/local/bin/${GSIMPLC_BIN}.bin"
ARGS_FILE="/etc/gsimplc/${GSIMPLC_BIN}.args"
PID_FILE="/var/run/${GSIMPLC_BIN}.pid"
LOG_FILE="/var/log/gsimplc.log"

usage() {
    echo "usage: $0 {start|stop|status|set-args|show-logs}"
    exit 1
}

is_running() {
    [ -f "${PID_FILE}" ] && kill -0 "$(cat "${PID_FILE}")" 2>/dev/null
}

do_start() {
    if is_running; then
        echo "${GSIMPLC_BIN} ya esta corriendo (pid $(cat "${PID_FILE}"))"
        return 0
    fi
    ARGS=""
    if [ -f "${ARGS_FILE}" ]; then
        ARGS=$(cat "${ARGS_FILE}")
    fi
    nohup "${BIN}" ${ARGS} "$@" >> "${LOG_FILE}" 2>&1 &
    echo $! > "${PID_FILE}"
    echo "${GSIMPLC_BIN} arrancado (pid $(cat "${PID_FILE}"))"
}

do_stop() {
    if is_running; then
        kill "$(cat "${PID_FILE}")"
        rm -f "${PID_FILE}"
        echo "${GSIMPLC_BIN} detenido"
    else
        echo "${GSIMPLC_BIN} no esta corriendo"
    fi
}

do_status() {
    if is_running; then
        echo "${GSIMPLC_BIN} corriendo (pid $(cat "${PID_FILE}"))"
        return 0
    fi
    echo "${GSIMPLC_BIN} detenido"
    return 1
}

do_set_args() {
    printf '%s\n' "$*" > "${ARGS_FILE}"
    echo "args actualizados: $*"
}

case "${1:-}" in
    start)    shift; do_start "$@" ;;
    stop)     do_stop ;;
    status)   do_status ;;
    set-args) shift; do_set_args "$@" ;;
    show-logs) tail -f "${LOG_FILE}" ;;
    *)        usage ;;
esac
