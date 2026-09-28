from core.memoria import MemoriaPLC
from ladder.instrucciones import Instruccion


class Escalon:

    def __init__(self, nombre, instrucciones, ramas=None):
        self.nombre = nombre
        self.instrucciones = list(instrucciones)
        self.ramas = list(ramas) if ramas else []

    def ejecutar(self, memoria: MemoriaPLC) -> bool:
        if not self.instrucciones and not self.ramas:
            return False

        resultado = self._ejecutar_serie(self.instrucciones, memoria)
        for rama in self.ramas:
            if self._ejecutar_serie(rama, memoria):
                return True
        return resultado

    @staticmethod
    def _ejecutar_serie(cadena: list, memoria: MemoriaPLC) -> bool:
        # Se ejecuta cada instruccion aunque el flujo ya este cortado, para
        # que los bloques con estado propio (TON, CTU, OTE, MOV) observen el
        # flujo que les llega en cada exploracion. Solo se propaga el valor.
        estado = True
        for instruccion in cadena:
            estado = instruccion.ejecutar(memoria, estado)
        return estado

    def __repr__(self) -> str:
        return (
            f"Escalon(nombre={self.nombre!r}, "
            f"instrucciones={len(self.instrucciones)}, "
            f"ramas={len(self.ramas)})"
        )
