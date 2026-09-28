import threading

from core.contador import Contador
from core.temporizador import Temporizador


class MemoriaPLC:
    def __init__(self, tamano=256):
        self.tamano = tamano
        self.bobinas = []
        self.entradas_discretas = []
        self.registros_retencion = []
        self.registros_entrada = []
        self._cerradura = threading.Lock()
        self._temporizadores = {}
        self._contadores = {}

        for _ in range(tamano):
            self.bobinas.append(False)
            self.entradas_discretas.append(False)
            self.registros_retencion.append(0)
            self.registros_entrada.append(0)

    def establecer_bobina(self, direccion, valor):
        with self._cerradura:
            self.bobinas[direccion] = bool(valor)

    def obtener_bobina(self, direccion):
        with self._cerradura:
            return self.bobinas[direccion]

    def establecer_entrada_discreta(self, direccion, valor):
        with self._cerradura:
            self.entradas_discretas[direccion] = bool(valor)

    def obtener_entrada_discreta(self, direccion):
        with self._cerradura:
            return self.entradas_discretas[direccion]

    def establecer_retencion(self, direccion, valor):
        with self._cerradura:
            self.registros_retencion[direccion] = int(valor) & 0xFFFF

    def obtener_retencion(self, direccion):
        with self._cerradura:
            return self.registros_retencion[direccion]

    def establecer_entrada(self, direccion, valor):
        with self._cerradura:
            self.registros_entrada[direccion] = int(valor) & 0xFFFF

    def obtener_entrada(self, direccion):
        with self._cerradura:
            return self.registros_entrada[direccion]

    def obtener_temporizador(self, identificador):
        with self._cerradura:
            temporizador = self._temporizadores.get(identificador)
            if temporizador is None:
                return Temporizador(identificador, 0)
            return temporizador.copia()

    def establecer_temporizador(self, identificador, preseleccion):
        with self._cerradura:
            temporizador = self._temporizadores.get(identificador)
            if temporizador is None:
                self._temporizadores[identificador] = Temporizador(
                    identificador, preseleccion
                )
            else:
                temporizador.cambiar_preseleccion(preseleccion)

    def actualizar_temporizador(self, identificador, habilitado, acumulado,
                               completado, temporizando):
        with self._cerradura:
            temporizador = self._temporizadores.get(identificador)
            if temporizador is None:
                temporizador = Temporizador(identificador, 0)
                self._temporizadores[identificador] = temporizador
            temporizador.actualizar(
                habilitado, acumulado, completado, temporizando
            )

    def obtener_contador(self, identificador):
        with self._cerradura:
            contador = self._contadores.get(identificador)
            if contador is None:
                return Contador(identificador, 0)
            return contador.copia()

    def establecer_contador(self, identificador, preseleccion):
        with self._cerradura:
            contador = self._contadores.get(identificador)
            if contador is None:
                self._contadores[identificador] = Contador(
                    identificador, preseleccion
                )
            else:
                contador.cambiar_preseleccion(preseleccion)

    def actualizar_contador(self, identificador, acumulado, completado,
                            contando_arriba=False, contando_abajo=False):
        with self._cerradura:
            contador = self._contadores.get(identificador)
            if contador is None:
                contador = Contador(identificador, 0)
                self._contadores[identificador] = contador
            contador.actualizar(
                acumulado, completado, contando_arriba, contando_abajo
            )

    def obtener_estado_completo(self):
        with self._cerradura:
            temporizadores = {}
            for llave in self._temporizadores:
                temporizadores[llave] = self._temporizadores[llave].copia()

            contadores = {}
            for llave in self._contadores:
                contadores[llave] = self._contadores[llave].copia()

            return {
                "bobinas": list(self.bobinas[:16]),
                "entradas_discretas": list(self.entradas_discretas[:16]),
                "registros_retencion": list(self.registros_retencion[:16]),
                "registros_entrada": list(self.registros_entrada[:16]),
                "temporizadores": temporizadores,
                "contadores": contadores,
            }
