"""
Servidor Modbus TCP — expone la memoria del PLC via Modbus TCP.
"""

import asyncio
import logging
import threading
import time

from pymodbus.server import ModbusTcpServer
from pymodbus.datastore import (
    ModbusSequentialDataBlock,
    ModbusSlaveContext,
    ModbusServerContext,
)
from pymodbus.device import ModbusDeviceIdentification

from core.memoria import MemoriaPLC

registrador = logging.getLogger("PLC.Modbus")

AREA_BOBINAS = 1
AREA_ENTRADAS_DISCRETAS = 2
AREA_RETENCION = 3
AREA_ENTRADAS = 4


class ServidorModbus:
    """Servidor Modbus TCP sincronizado con MemoriaPLC."""

    def __init__(self, memoria, host="0.0.0.0", puerto=502):
        self.memoria = memoria
        self.host = host
        self.puerto = puerto
        self._hilo = None
        self._contexto = None
        self._hilo_sincronizacion = None
        self._servidor = None
        self._bucle_eventos = None
        self._servidor_listo = threading.Event()
        self._ejecutando = False
        self._error_arranque = None
        self._bobinas_publicadas = []
        self._retencion_publicada = []
        self._ultimo_error_sincronizacion = ""

    def _construir_contexto(self):
        almacen = ModbusSlaveContext(
            di=ModbusSequentialDataBlock(1, [0] * self.memoria.tamano),
            co=ModbusSequentialDataBlock(1, [0] * self.memoria.tamano),
            hr=ModbusSequentialDataBlock(1, [0] * self.memoria.tamano),
            ir=ModbusSequentialDataBlock(1, [0] * self.memoria.tamano),
        )
        return ModbusServerContext(slaves=almacen, single=True)

    def _construir_identidad(self):
        identidad = ModbusDeviceIdentification()
        identidad.VendorName = "GSIMPLC"
        identidad.ProductCode = "GSIM-01"
        identidad.VendorUrl = "https://github.com/gsimplc/gsimplc"
        identidad.ProductName = "GSIMPLC"
        identidad.ModelName = "GSIMPLC-V1"
        identidad.MajorMinorRevision = "1.0"
        return identidad

    def _bucle_sincronizacion(self):
        while self._ejecutando:
            try:
                esclavo = self._contexto[0]
                self._aplicar_escrituras_modbus(esclavo)
                self._publicar_memoria(esclavo)
            except Exception as error:
                mensaje = str(error)
                if mensaje != self._ultimo_error_sincronizacion:
                    registrador.error(
                        "Error de sincronizacion: %s", error, exc_info=True
                    )
                    self._ultimo_error_sincronizacion = mensaje
            time.sleep(0.1)

    def _aplicar_escrituras_modbus(self, esclavo):
        cantidad = self.memoria.tamano
        bobinas_modbus = esclavo.getValues(AREA_BOBINAS, 0, cantidad)
        retencion_modbus = esclavo.getValues(AREA_RETENCION, 0, cantidad)

        if not self._bobinas_publicadas:
            self._bobinas_publicadas = list(bobinas_modbus)
        if not self._retencion_publicada:
            self._retencion_publicada = list(retencion_modbus)

        for indice in range(cantidad):
            if bobinas_modbus[indice] != self._bobinas_publicadas[indice]:
                self.memoria.establecer_bobina(indice, bool(bobinas_modbus[indice]))
            if retencion_modbus[indice] != self._retencion_publicada[indice]:
                self.memoria.establecer_retencion(indice, retencion_modbus[indice])

    def _publicar_memoria(self, esclavo):
        cantidad = self.memoria.tamano
        bobinas = []
        entradas_discretas = []
        retencion = []
        entradas = []

        for indice in range(cantidad):
            bobinas.append(int(self.memoria.obtener_bobina(indice)))
            entradas_discretas.append(
                int(self.memoria.obtener_entrada_discreta(indice))
            )
            retencion.append(self.memoria.obtener_retencion(indice))
            entradas.append(self.memoria.obtener_entrada(indice))

        esclavo.setValues(AREA_BOBINAS, 0, bobinas)
        esclavo.setValues(AREA_ENTRADAS_DISCRETAS, 0, entradas_discretas)
        esclavo.setValues(AREA_RETENCION, 0, retencion)
        esclavo.setValues(AREA_ENTRADAS, 0, entradas)
        self._bobinas_publicadas = bobinas
        self._retencion_publicada = retencion

    def iniciar(self):
        self._contexto = self._construir_contexto()
        self._ejecutando = True
        self._servidor_listo.clear()
        self._error_arranque = None
        self._hilo = threading.Thread(
            target=self._ejecutar_servidor,
            daemon=True,
            name="ModbusTCP",
        )
        self._hilo.start()
        listo = self._servidor_listo.wait(timeout=5)
        if not listo or self._error_arranque is not None:
            self._ejecutando = False
            if self._hilo is not None:
                self._hilo.join(timeout=2)
            detalle = self._error_arranque or "timeout al iniciar"
            registrador.error(
                "No se pudo iniciar el servidor Modbus TCP en %s:%d: %s",
                self.host, self.puerto, detalle,
            )
            raise RuntimeError(
                f"No se pudo iniciar el servidor Modbus TCP en {self.host}:{self.puerto}: {detalle}"
            )
        self._hilo_sincronizacion = threading.Thread(
            target=self._bucle_sincronizacion,
            daemon=True,
            name="SincronizacionModbus",
        )
        self._hilo_sincronizacion.start()
        registrador.info(
            "Servidor Modbus TCP en %s:%d", self.host, self.puerto
        )

    def detener(self):
        self._ejecutando = False
        if self._servidor is not None and self._bucle_eventos is not None:
            cierre = asyncio.run_coroutine_threadsafe(
                self._servidor.shutdown(),
                self._bucle_eventos,
            )
            try:
                cierre.result(timeout=2)
            except (TimeoutError, RuntimeError) as error:
                registrador.warning(
                    "Cierre del servidor Modbus incompleto: %s", error
                )
        if self._hilo_sincronizacion is not None:
            self._hilo_sincronizacion.join(timeout=2)
        if self._hilo is not None:
            self._hilo.join(timeout=2)

    def _ejecutar_servidor(self):
        asyncio.run(self._servir())

    async def _servir(self):
        self._bucle_eventos = asyncio.get_running_loop()
        contexto = self._contexto
        if contexto is None:
            self._servidor_listo.set()
            return
        self._servidor = ModbusTcpServer(
            context=contexto,
            identity=self._construir_identidad(),
            address=(self.host, self.puerto),
        )
        try:
            await self._servidor.listen()
            self._servidor_listo.set()
            await self._servidor.serving
        except Exception as error:
            self._error_arranque = str(error)
            self._servidor_listo.set()
        finally:
            self._servidor.close()

    def obtener_contexto(self):
        return self._contexto
