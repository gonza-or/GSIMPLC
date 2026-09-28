from core.memoria import MemoriaPLC


class Programa:

    def __init__(self, escalones):
        self.escalones = list(escalones)

    def ejecutar(self, memoria: MemoriaPLC) -> list:
        resultados = []
        for escalon in self.escalones:
            resultados.append(escalon.ejecutar(memoria))
        return resultados

    @classmethod
    def cargar_desde_archivo(cls, ruta: str) -> "Programa":
        from ladder.lector import LectorLadder
        return LectorLadder().leer(ruta)

    def __repr__(self) -> str:
        return f"Programa(escalones={len(self.escalones)})"
