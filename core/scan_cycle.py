"""
Ciclo de Exploracion — ejecuta la logica del PLC a intervalos regulares.
"""

import logging
import threading
import time

from core.memoria import MemoriaPLC

registrador = logging.getLogger("PLC.CicloExploracion")


class CicloExploracion:

    def __init__(self, memoria, ciclo_ms=100, tap=None):
        self.memoria = memoria
        self.ciclo_ms = ciclo_ms
        self._ejecutando = False
        self._hilo = None
        self._programa = None
        self._conteo_ciclos = 0
        self._tap = tap

    @property
    def conteo_ciclos(self):
        return self._conteo_ciclos

    def establecer_programa(self, programa):
        self._programa = programa

    def iniciar(self):
        self._ejecutando = True
        self._hilo = threading.Thread(
            target=self._correr,
            daemon=True,
            name="CicloExploracion"
        )
        self._hilo.start()
        registrador.info(
            "Ciclo de exploracion iniciado — periodo: %d ms",
            self.ciclo_ms
        )

    def detener(self):
        self._ejecutando = False
        if self._hilo is not None:
            self._hilo.join(timeout=2)
        registrador.info(
            "Ciclo de exploracion detenido. Ciclos ejecutados: %d",
            self._conteo_ciclos
        )

    def _correr(self):
        intervalo = self.ciclo_ms / 1000.0
        while self._ejecutando:
            t0 = time.monotonic()
            try:
                self._paso()
            except Exception as error:
                registrador.error(
                    "Error en ciclo de exploracion: %s",
                    error
                )
            tiempo_transcurrido = time.monotonic() - t0
            tiempo_espera = max(0.0, intervalo - tiempo_transcurrido)
            time.sleep(tiempo_espera)

    def _paso(self):
        self._conteo_ciclos = self._conteo_ciclos + 1
        self._leer_entradas()
        if self._programa is not None:
            self._programa.ejecutar(self.memoria)
        self._escribir_salidas()

    def _leer_entradas(self):
        if self._tap is not None:
            paquete = self._tap.leer_paquete(timeout=0.001)
            if paquete is not None and len(paquete) >= 2:
                byte_0 = paquete[0]
                for bit in range(8):
                    self.memoria.establecer_entrada_discreta(
                        bit, (byte_0 >> bit) & 0x01
                    )

    def _escribir_salidas(self):
        if self._tap is not None:
            byte_bobinas = 0
            for i in range(8):
                if self.memoria.obtener_bobina(i):
                    byte_bobinas = byte_bobinas | (1 << i)
            self._tap.escribir_paquete(bytes([byte_bobinas]))
