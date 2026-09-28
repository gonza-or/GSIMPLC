#!/bin/sh
# Entrypoint del contenedor — arranca sshd, lanza el binario via
# gsimplc-manage (que escribe el pid y manda la salida a
# /var/log/gsimplc.log) y mantiene el contenedor vivo.
#
# GSIMPLC_BIN la define el Dockerfile (gsimplc o gscada).
set -e

# sshd necesita que exista este directorio.
mkdir -p /run/sshd

# Arranco sshd en segundo plano, para gestion remota.
/usr/sbin/sshd

# Lanzo el binario por el manage para que start|stop|status|set-args
# sigan funcionando en caliente.
gsimplc-manage start

# Detengo el binario cuando piden apagar el contenedor.
trap 'gsimplc-manage stop' TERM INT

# Mantengo el PID 1 esperando para que el contenedor no muera.
tail -f /dev/null &
wait $!
