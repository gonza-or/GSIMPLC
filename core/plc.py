
import logging
import time

from core.memoria import MemoriaPLC
from core.scan_cycle import CicloExploracion

registrador = logging.getLogger("PLC")


class PLC:

    def __init__(self, ciclo_ms=100):
        self.memoria = MemoriaPLC()
        self.ciclo = CicloExploracion(self.memoria, ciclo_ms)
        self._componentes = []

    def establecer_programa(self, programa):
        self.ciclo.establecer_programa(programa)

    def agregar_componente(self, componente):
        self._componentes.append(componente)

    def iniciar(self):
        registrador.info("══ Iniciando GSIMPLC ══")
        for componente in self._componentes:
            componente.iniciar()
        time.sleep(0.3)
        self.ciclo.iniciar()
        registrador.info(
            "PLC en ejecucion. Ctrl+C para detener."
        )

    def detener(self):
        registrador.info("Deteniendo PLC...")
        self.ciclo.detener()
        for componente in reversed(self._componentes):
            if hasattr(componente, "detener"):
                componente.detener()
        registrador.info("PLC detenido.")
