"""
Interfaz TAP — wrapper de TUN/TAP de Linux para la integracion con GNS3.

Crea un dispositivo TAP sobre ``/dev/net/tun`` para colgar el PLC de una
red GNS3 como un nodo L2 real. Todos los ioctl usan la peticion canonica
``TUNSETIFF``.
"""

import fcntl
import logging
import os
import select
import struct
import subprocess

registrador = logging.getLogger("PLC.InterfazTAP")

# Constantes ioctl de TUN/TAP en Linux.
TUNSETIFF = 0x400454CA
IFF_TAP = 0x0002
IFF_NO_PI = 0x1000  # sin cabecera de informacion de paquete


class InterfazTAP:
    """
    Interfaz de red TAP de Linux.

    Uso::

        with InterfazTAP("tap0") as tap:
            tap.asignar_ip("192.168.1.10", 24)
            paquete = tap.leer_paquete(timeout=1.0)
            if paquete:
                tap.escribir_paquete(respuesta)
    """

    def __init__(self, nombre="tap0"):
        self.nombre = nombre
        self._descriptor = None

    def __enter__(self):
        self.crear()
        return self

    def __exit__(self, tipo_error, error, traza):
        self.destruir()

    def crear(self):
        """Abre ``/dev/net/tun`` y registra el dispositivo TAP."""
        if self._descriptor is not None:
            return
        self._descriptor = os.open("/dev/net/tun", os.O_RDWR)
        peticion = struct.pack(
            "16sH",
            self.nombre.encode(),
            IFF_TAP | IFF_NO_PI,
        )
        fcntl.ioctl(self._descriptor, TUNSETIFF, peticion)
        registrador.info("Interfaz TAP creada: %s", self.nombre)

    def destruir(self):
        """Cierra el descriptor y elimina el dispositivo TAP."""
        if self._descriptor is not None:
            try:
                os.close(self._descriptor)
            except OSError as error:
                registrador.warning(
                    "Error al cerrar el descriptor TAP: %s", error
                )
            self._descriptor = None
        try:
            subprocess.run(
                ["ip", "link", "delete", self.nombre],
                check=False,
                capture_output=True,
            )
            registrador.info("Interfaz TAP destruida: %s", self.nombre)
        except FileNotFoundError:
            registrador.warning(
                "El comando `ip` no esta disponible; no se borra el enlace"
            )
        except Exception as error:
            registrador.warning("Error al destruir la TAP: %s", error)

    def asignar_ip(self, ip, prefijo=24):
        """Asigna ``ip/prefijo`` a la TAP y levanta el enlace."""
        if self._descriptor is None:
            raise RuntimeError(
                "La interfaz TAP no esta creada; llamar a crear() primero"
            )
        cidr = f"{ip}/{prefijo}"
        subprocess.run(
            ["ip", "addr", "add", cidr, "dev", self.nombre],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["ip", "link", "set", self.nombre, "up"],
            check=True,
            capture_output=True,
        )
        registrador.info("IP asignada: %s en %s", cidr, self.nombre)

    def leer_paquete(self, timeout=1.0):
        """Lee una trama Ethernet o devuelve ``None`` si vence el timeout."""
        if self._descriptor is None:
            return None
        try:
            listos, _, _ = select.select([self._descriptor], [], [], timeout)
            if not listos:
                return None
            return os.read(self._descriptor, 65536)
        except OSError as error:
            registrador.debug("Error de lectura en la TAP: %s", error)
            return None

    def escribir_paquete(self, datos):
        """Escribe una trama Ethernet en el dispositivo TAP."""
        if self._descriptor is None:
            raise RuntimeError(
                "La interfaz TAP no esta creada; llamar a crear() primero"
            )
        os.write(self._descriptor, datos)
