import time
from abc import ABC, abstractmethod

from ladder.referencias import Referencia


class Instruccion(ABC):

    @abstractmethod
    def ejecutar(self, memoria, estado) -> bool:
        pass


class ContactoNormalAbierto(Instruccion):

    def __init__(self, direccion):
        self.referencia = Referencia.interpretar(direccion)

    def ejecutar(self, memoria, estado) -> bool:
        if not estado:
            return False
        return bool(self.referencia.leer(memoria))


class ContactoNormalCerrado(Instruccion):

    def __init__(self, direccion):
        self.referencia = Referencia.interpretar(direccion)

    def ejecutar(self, memoria, estado) -> bool:
        if not estado:
            return False
        return not bool(self.referencia.leer(memoria))


class BobinaSalida(Instruccion):

    def __init__(self, direccion):
        self.destino = Referencia.interpretar_destino(direccion)

    def ejecutar(self, memoria, estado) -> bool:
        self.destino.escribir(memoria, int(estado))
        return estado


class BobinaEnclavar(Instruccion):

    def __init__(self, direccion):
        self.destino = Referencia.interpretar_destino(direccion)

    def ejecutar(self, memoria, estado) -> bool:
        if estado:
            self.destino.escribir(memoria, 1)
        return estado


class BobinaDesenclavar(Instruccion):

    def __init__(self, direccion):
        self.destino = Referencia.interpretar_destino(direccion)

    def ejecutar(self, memoria, estado) -> bool:
        if estado:
            self.destino.escribir(memoria, 0)
        return estado


class InstruccionTemporizador(Instruccion, ABC):

    def __init__(self, direccion_temporizador, preseleccion_ms):
        self.id_temporizador = Referencia.indice_de(direccion_temporizador)
        self.preseleccion_ms = int(preseleccion_ms)
        self._inicio = None
        self._habilitado_antes = False

    def _tiempo_transcurrido_ms(self) -> int:
        if self._inicio is None:
            return 0
        return int((time.monotonic() - self._inicio) * 1000)


class TemporizadorConexion(InstruccionTemporizador):

    def ejecutar(self, memoria, estado) -> bool:
        memoria.establecer_temporizador(
            self.id_temporizador, self.preseleccion_ms
        )

        if not estado:
            self._inicio = None
            self._habilitado_antes = False
            memoria.actualizar_temporizador(
                self.id_temporizador, False, 0, False, False
            )
            return False

        if not self._habilitado_antes:
            self._inicio = time.monotonic()
            memoria.actualizar_temporizador(
                self.id_temporizador, True, 0, False, True
            )
            self._habilitado_antes = True

        transcurrido_ms = self._tiempo_transcurrido_ms()
        if transcurrido_ms >= self.preseleccion_ms:
            memoria.actualizar_temporizador(
                self.id_temporizador, True, self.preseleccion_ms, True, False
            )
            return True

        memoria.actualizar_temporizador(
            self.id_temporizador, True, transcurrido_ms, False, True
        )
        return False


class TemporizadorDesconexion(InstruccionTemporizador):

    def ejecutar(self, memoria, estado) -> bool:
        memoria.establecer_temporizador(
            self.id_temporizador, self.preseleccion_ms
        )

        if estado:
            self._inicio = None
            self._habilitado_antes = True
            memoria.actualizar_temporizador(
                self.id_temporizador, True, 0, True, False
            )
            return True

        if self._habilitado_antes:
            self._inicio = time.monotonic()
            self._habilitado_antes = False

        if self._inicio is None:
            memoria.actualizar_temporizador(
                self.id_temporizador, False, 0, False, False
            )
            return False

        transcurrido_ms = self._tiempo_transcurrido_ms()
        if transcurrido_ms >= self.preseleccion_ms:
            self._inicio = None
            memoria.actualizar_temporizador(
                self.id_temporizador, False, self.preseleccion_ms, False, False
            )
            return False

        memoria.actualizar_temporizador(
            self.id_temporizador, True, transcurrido_ms, True, True
        )
        return True


class InstruccionContador(Instruccion, ABC):

    def __init__(self, direccion_contador, preseleccion):
        self.id_contador = Referencia.indice_de(direccion_contador)
        self.preseleccion = int(preseleccion)
        self._habilitado_antes = False


class ContadorAscendente(InstruccionContador):

    def ejecutar(self, memoria, estado) -> bool:
        memoria.establecer_contador(self.id_contador, self.preseleccion)
        contador = memoria.obtener_contador(self.id_contador)

        if estado and not self._habilitado_antes:
            contador.incrementar()

        contador.evaluar_completado()
        memoria.actualizar_contador(
            self.id_contador, contador.acumulado, contador.completado,
            bool(estado), False
        )
        self._habilitado_antes = bool(estado)
        return contador.completado


class ContadorDescendente(InstruccionContador):

    def ejecutar(self, memoria, estado) -> bool:
        memoria.establecer_contador(self.id_contador, self.preseleccion)
        contador = memoria.obtener_contador(self.id_contador)

        if estado and not self._habilitado_antes:
            contador.decrementar()

        contador.evaluar_completado()
        memoria.actualizar_contador(
            self.id_contador, contador.acumulado, contador.completado,
            False, bool(estado)
        )
        self._habilitado_antes = bool(estado)
        return contador.completado


class Mover(Instruccion):

    def __init__(self, origen, destino):
        self.origen = Referencia.interpretar(origen)
        self.destino = Referencia.interpretar_destino(destino)

    def ejecutar(self, memoria, estado) -> bool:
        if not estado:
            return False
        self.destino.escribir(memoria, int(self.origen.leer(memoria)))
        return True


class InstruccionAritmetica(Instruccion, ABC):

    def __init__(self, a, b, destino):
        self.a = Referencia.interpretar(a)
        self.b = Referencia.interpretar(b)
        self.destino = Referencia.interpretar_destino(destino)

    def ejecutar(self, memoria, estado) -> bool:
        if not estado:
            return False
        resultado = self.calcular(
            int(self.a.leer(memoria)), int(self.b.leer(memoria))
        )
        if self.destino.es_palabra():
            self.destino.escribir(memoria, resultado)
        return True

    @abstractmethod
    def calcular(self, valor_a, valor_b) -> int:
        pass


class Sumar(InstruccionAritmetica):

    def calcular(self, valor_a, valor_b) -> int:
        return valor_a + valor_b


class Restar(InstruccionAritmetica):

    def calcular(self, valor_a, valor_b) -> int:
        return valor_a - valor_b


class Comparacion(Instruccion, ABC):

    def __init__(self, a, b):
        self.a = Referencia.interpretar(a)
        self.b = Referencia.interpretar(b)

    def ejecutar(self, memoria, estado) -> bool:
        if not estado:
            return False
        return self.comparar(
            int(self.a.leer(memoria)), int(self.b.leer(memoria))
        )

    @abstractmethod
    def comparar(self, valor_a, valor_b) -> bool:
        pass


class Igual(Comparacion):

    def comparar(self, valor_a, valor_b) -> bool:
        return valor_a == valor_b


class Distinto(Comparacion):

    def comparar(self, valor_a, valor_b) -> bool:
        return valor_a != valor_b


class Mayor(Comparacion):

    def comparar(self, valor_a, valor_b) -> bool:
        return valor_a > valor_b


class Menor(Comparacion):

    def comparar(self, valor_a, valor_b) -> bool:
        return valor_a < valor_b
