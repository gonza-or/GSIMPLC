#!/usr/bin/env python3
"""
GSIMPLC — punto de entrada del simulador de PLC generico.

Dos modos de operacion:

  Modo dev (sin TAP)::

      python main.py --program examples/contador.lad

  Modo GNS3 (con TAP)::

      ./gsimplc.bin --nic eth0 --ip 192.168.1.10/24 --program my.lad

La interfaz TAP se crea solo cuando se pasan ``--nic`` y ``--ip``, y se
libera siempre al final del programa.
"""

import argparse
import logging
import os
import signal
import sys
import threading

from core.plc import PLC
from panel.servidor import ServidorPanel
from protocols.modbus_server import ServidorModbus

registrador = logging.getLogger("PLC")

# Lo llena instalar_manejadores_senales cuando llega SIGINT/SIGTERM.
_evento_apagado = threading.Event()


def entero_positivo(valor):
    numero = int(valor)
    if numero <= 0:
        raise argparse.ArgumentTypeError("debe ser un entero positivo")
    return numero


def interpretar_argumentos(argumentos=None):
    analizador = argparse.ArgumentParser(
        prog="gsimplc",
        description=(
            "GSIMPLC — Simulador de PLC generico (Ladder + Modbus + HMI web)"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Ejemplos:\n"
            "  Modo dev:   python main.py --program examples/contador.lad\n"
            "  Modo GNS3:  ./gsimplc.bin --nic eth0 --ip 192.168.1.10/24\n"
            "  Ciclo:      python main.py --program examples/semaforo.lad "
            "--cycle 50\n"
        ),
    )
    analizador.add_argument(
        "--program", default="",
        help="Ruta a un archivo de programa .lad",
    )
    analizador.add_argument(
        "--escenario", default="",
        help="Ruta a un escenario YAML de proceso simulado",
    )
    analizador.add_argument(
        "--ciclo-proceso", default=200, type=entero_positivo,
        help="Periodo del proceso simulado en milisegundos (default: 200)",
    )
    analizador.add_argument(
        "--cycle", default=100, type=entero_positivo,
        help="Periodo del ciclo de exploracion en milisegundos (default: 100)",
    )
    analizador.add_argument(
        "--modbus-port", default=502, type=int,
        help="Puerto Modbus TCP (default: 502)",
    )
    analizador.add_argument(
        "--panel-port", default=8080, type=int,
        help="Puerto del panel web (default: 8080)",
    )
    analizador.add_argument(
        "--host", default="0.0.0.0",
        help="Direccion de escucha cuando no se usa TAP (default: 0.0.0.0)",
    )
    analizador.add_argument(
        "--nic", default="",
        help="Nombre de la interfaz TAP para GNS3 (ej. eth0)",
    )
    analizador.add_argument(
        "--ip", default="",
        help="IP en formato CIDR, ej. 192.168.1.10/24 (activa el modo TAP)",
    )
    analizador.add_argument(
        "--verbose", action="store_true",
        help="Activa el registro en nivel DEBUG",
    )
    return analizador.parse_args(argumentos)


def configurar_registro(verboso):
    nivel = logging.DEBUG if verboso else logging.INFO
    logging.basicConfig(
        level=nivel,
        format="[%(asctime)s] %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def cargar_programa(ruta):
    from ladder.lector import ErrorLadder, LectorLadder
    if not os.path.isfile(ruta):
        raise FileNotFoundError(f"No se encontro el programa: {ruta}")
    try:
        return LectorLadder().leer(ruta)
    except ErrorLadder as error:
        raise ValueError(f"Error de parseo en {error}") from error


def _manejar_senal(numero_senal, _marco):
    nombre = signal.Signals(numero_senal).name
    registrador.info("Recibida la senal %s — iniciando apagado", nombre)
    _evento_apagado.set()


def instalar_manejadores_senales():
    """Instala SIGINT/SIGTERM para activar la bandera de apagado."""
    for senal in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(senal, _manejar_senal)
        except (ValueError, OSError):
            # Fuera del hilo principal o senal no soportada.
            pass


def _resolver_direccion_escucha(argumentos):
    if argumentos.nic and argumentos.ip:
        direccion = argumentos.ip.split("/", 1)[0]
        registrador.info(
            "Modo GNS3 — TAP=%s IP=%s", argumentos.nic, argumentos.ip
        )
        return direccion
    registrador.info("Modo dev — escuchando en %s", argumentos.host)
    return argumentos.host


def _interpretar_cidr(ip_cidr):
    if "/" not in ip_cidr:
        raise ValueError(f"La IP debe venir en formato CIDR: {ip_cidr!r}")
    ip, prefijo = ip_cidr.split("/", 1)
    return ip, int(prefijo)


def ejecutar(argumentos):
    instalar_manejadores_senales()
    configurar_registro(argumentos.verbose)

    direccion = _resolver_direccion_escucha(argumentos)

    plc = PLC(ciclo_ms=argumentos.cycle)

    if argumentos.program:
        ruta = os.path.abspath(argumentos.program)
        try:
            programa = cargar_programa(ruta)
        except (FileNotFoundError, ValueError) as error:
            registrador.error("No se puede cargar el programa: %s", error)
            return 1
        plc.establecer_programa(programa)
        registrador.info(
            "Programa cargado: %s (%d escalones)",
            os.path.basename(ruta),
            len(programa.escalones),
        )
    else:
        registrador.warning(
            "Sin programa .lad — el ciclo de exploracion correra vacio"
        )

    if argumentos.escenario:
        from process_sim.puente import cargar_escenario

        try:
            proceso = cargar_escenario(
                argumentos.escenario,
                plc.memoria,
                periodo_ms=argumentos.ciclo_proceso,
            )
        except (FileNotFoundError, ValueError) as error:
            registrador.error(
                "No se puede cargar el escenario de proceso: %s", error
            )
            return 1
        plc.agregar_componente(proceso)

    servidor_modbus = ServidorModbus(
        plc.memoria,
        host=direccion,
        puerto=argumentos.modbus_port,
    )
    plc.agregar_componente(servidor_modbus)

    servidor_panel = ServidorPanel(
        plc.memoria,
        plc.ciclo,
        puerto=argumentos.panel_port,
        ruta_programa=argumentos.program,
    )
    plc.agregar_componente(servidor_panel)

    tap = None
    if argumentos.nic and argumentos.ip:
        from io_plc.interfaz_tap import InterfazTAP
        try:
            ip, prefijo = _interpretar_cidr(argumentos.ip)
        except ValueError as error:
            registrador.error("%s", error)
            return 1
        try:
            tap = InterfazTAP(argumentos.nic)
            tap.crear()
            tap.asignar_ip(ip, prefijo)
        except (OSError, RuntimeError) as error:
            registrador.error(
                "No se puede crear la interfaz TAP: %s", error
            )
            return 1
        plc.ciclo.establecer_tap(tap)
        registrador.info(
            "TAP activa: %s -> %s/%d", argumentos.nic, ip, prefijo
        )

    try:
        plc.iniciar()
        registrador.info(
            "GSIMPLC en ejecucion. Modbus=%s:%d  Panel=http://%s:%d  "
            "Ctrl+C para detener.",
            direccion, argumentos.modbus_port,
            direccion, argumentos.panel_port,
        )
        while not _evento_apagado.is_set():
            _evento_apagado.wait(timeout=1.0)
    finally:
        plc.detener()
        if tap is not None:
            tap.destruir()
        registrador.info("GSIMPLC detenido correctamente")

    return 0


def main():
    argumentos = interpretar_argumentos()
    try:
        return ejecutar(argumentos)
    except KeyboardInterrupt:
        registrador.info("Interrumpido por el usuario")
        return 0
    except Exception as error:
        registrador.exception("Error fatal: %s", error)
        return 1


if __name__ == "__main__":
    sys.exit(main())

