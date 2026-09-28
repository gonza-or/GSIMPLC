#!/usr/bin/env python3
"""
GSCADA — punto de entrada.

Arranca los consultores Modbus configurados, el motor de alarmas, el
historiador y el servidor web. Esta pensado para correr como proceso
aparte (normalmente como nodo de GNS3), pero funciona igual de bien
suelto.
"""

import argparse
import logging
import os
import signal
import sys
import threading

import uvicorn
from fastapi.middleware.cors import CORSMiddleware

from gscada.configuracion import ConfiguracionSistema
from gscada.historiador import Historiador
from gscada.servidor import (
    construir_componentes,
    crear_aplicacion,
    detener_todo,
    iniciar_todo,
)

registrador = logging.getLogger("GSCADA")

_evento_apagado = threading.Event()


def interpretar_argumentos(argumentos=None):
    analizador = argparse.ArgumentParser(
        prog="gscada",
        description="GSCADA — cliente SCADA/HMI Modbus",
    )
    analizador.add_argument(
        "--config", default="gscada/configs/ejemplo.yaml",
        help="Ruta al YAML de configuracion del sistema",
    )
    analizador.add_argument(
        "--port", default=8080, type=int, help="Puerto del servidor web"
    )
    analizador.add_argument(
        "--host", default="0.0.0.0", help="Direccion de escucha"
    )
    analizador.add_argument(
        "--db", default="historian.db",
        help="Archivo SQLite del historiador",
    )
    analizador.add_argument(
        "--max-age-hours", default=24.0, type=float,
        help="Depura del historiador las filas mas viejas que estas horas",
    )
    analizador.add_argument("--verbose", action="store_true")
    return analizador.parse_args(argumentos)


def instalar_manejadores_senales():
    def _manejar(numero_senal, _marco):
        registrador.info(
            "Recibida la senal %s — apagando", numero_senal
        )
        _evento_apagado.set()

    for senal in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(senal, _manejar)
        except (ValueError, OSError):
            pass


def main():
    argumentos = interpretar_argumentos()
    logging.basicConfig(
        level=logging.DEBUG if argumentos.verbose else logging.INFO,
        format="[%(asctime)s] %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    instalar_manejadores_senales()

    try:
        configuracion = ConfiguracionSistema.cargar(argumentos.config)
    except Exception as error:
        registrador.error("No se puede cargar la configuracion: %s", error)
        return 1

    registrador.info(
        "GSCADA arrancando: %d PLC(s), %d tag(s), %d alarma(s)",
        len(configuracion.plcs),
        sum(len(plc.tags) for plc in configuracion.plcs),
        len(configuracion.alarmas),
    )

    historiador = Historiador(
        ruta_bd=argumentos.db,
        antiguedad_maxima_s=argumentos.max_age_hours * 3600,
    )
    construir_componentes(configuracion, historiador=historiador)
    iniciar_todo()

    carpeta_estatica = os.path.join(
        os.path.dirname(__file__), "gscada", "static"
    )
    aplicacion = crear_aplicacion(carpeta_estatica=carpeta_estatica)
    aplicacion.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    config_uvicorn = uvicorn.Config(
        aplicacion,
        host=argumentos.host,
        port=argumentos.port,
        log_level="warning",
    )
    servidor = uvicorn.Server(config_uvicorn)
    hilo = threading.Thread(
        target=servidor.run, daemon=True, name="GSCADA-Web"
    )
    hilo.start()
    registrador.info(
        "HMI de GSCADA en http://%s:%d", argumentos.host, argumentos.port
    )

    try:
        while not _evento_apagado.is_set():
            _evento_apagado.wait(timeout=1.0)
    finally:
        servidor.should_exit = True
        detener_todo()
        hilo.join(timeout=3)
        registrador.info("GSCADA detenido correctamente")
    return 0


if __name__ == "__main__":
    sys.exit(main())

