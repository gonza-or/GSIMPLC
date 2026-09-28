"""
Simulador de proceso — ejecuta cada :class:`ModeloFisico` en un hilo
propio, a un ritmo fijo, avanzando el tiempo y escribiendo de vuelta en
la memoria del PLC.
"""

import logging
import threading
import time

registrador = logging.getLogger("PLC.SimuladorProceso")


class SimuladorProceso:
    """Mueve una lista de modelos fisicos cada ``periodo_ms``."""

    def __init__(self, modelos, memoria, periodo_ms=200):
        self.modelos = list(modelos)
        self.memoria = memoria
        self.periodo_ms = periodo_ms
        self._hilo = None
        self._evento_detencion = threading.Event()
        self._tics = 0

    @property
    def tics(self):
        return self._tics

    def iniciar(self):
        if self._hilo is not None and self._hilo.is_alive():
            return
        self._evento_detencion.clear()
        self._hilo = threading.Thread(
            target=self._correr,
            daemon=True,
            name="SimuladorProceso",
        )
        self._hilo.start()
        registrador.info(
            "Simulador de proceso iniciado: %d modelo(s), periodo=%d ms",
            len(self.modelos), self.periodo_ms,
        )

    def detener(self):
        self._evento_detencion.set()
        if self._hilo is not None:
            self._hilo.join(timeout=2)
        registrador.info(
            "Simulador de proceso detenido tras %d tics", self._tics
        )

    def _correr(self):
        periodo_s = self.periodo_ms / 1000.0
        while not self._evento_detencion.is_set():
            t0 = time.monotonic()
            try:
                for modelo in self.modelos:
                    modelo.actualizar(periodo_s, self.memoria)
            except Exception as error:
                registrador.error("Error en el ciclo del proceso: %s", error)
            self._tics = self._tics + 1
            transcurrido = time.monotonic() - t0
            espera = max(0.0, periodo_s - transcurrido)
            # Despierta antes si llega una orden de detencion.
            self._evento_detencion.wait(espera)
