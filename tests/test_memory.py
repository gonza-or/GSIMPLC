"""Tests para MemoriaPLC."""

import threading
import pytest
from core.memoria import MemoriaPLC


class TestMemoriaPLC:
    def test_bobinas(self):
        memoria = MemoriaPLC()
        assert memoria.obtener_bobina(0) is False
        memoria.establecer_bobina(0, True)
        assert memoria.obtener_bobina(0) is True
        memoria.establecer_bobina(0, False)
        assert memoria.obtener_bobina(0) is False

    def test_entradas_discretas(self):
        memoria = MemoriaPLC()
        assert memoria.obtener_entrada_discreta(5) is False
        memoria.establecer_entrada_discreta(5, True)
        assert memoria.obtener_entrada_discreta(5) is True

    def test_registros_retencion(self):
        memoria = MemoriaPLC()
        assert memoria.obtener_retencion(0) == 0
        memoria.establecer_retencion(0, 1234)
        assert memoria.obtener_retencion(0) == 1234
        memoria.establecer_retencion(0, 70000)
        assert memoria.obtener_retencion(0) == 70000 & 0xFFFF

    def test_registros_entrada(self):
        memoria = MemoriaPLC()
        assert memoria.obtener_entrada(3) == 0
        memoria.establecer_entrada(3, 999)
        assert memoria.obtener_entrada(3) == 999

    def test_seguridad_hilos(self):
        memoria = MemoriaPLC()
        errores = []

        def escritor():
            try:
                for i in range(0, 1000, 1):
                    memoria.establecer_retencion(0, i)
            except Exception as error:
                errores.append(error)

        def lector():
            try:
                for i in range(0, 1000, 1):
                    memoria.obtener_retencion(0)
            except Exception as error:
                errores.append(error)

        hilo1 = threading.Thread(target=escritor)
        hilo2 = threading.Thread(target=lector)
        hilo1.start()
        hilo2.start()
        hilo1.join()
        hilo2.join()
        assert len(errores) == 0

    def test_estado_temporizador(self):
        memoria = MemoriaPLC()
        memoria.establecer_temporizador(0, 1000)
        assert memoria.obtener_temporizador(0).preseleccion == 1000
        memoria.actualizar_temporizador(0, True, 500, False, True)
        temporizador = memoria.obtener_temporizador(0)
        assert temporizador.habilitado is True
        assert temporizador.acumulado == 500
        assert temporizador.completado is False

    def test_estado_contador(self):
        memoria = MemoriaPLC()
        memoria.establecer_contador(0, 10)
        assert memoria.obtener_contador(0).preseleccion == 10
        memoria.actualizar_contador(0, 5, False, contando_arriba=True)
        contador = memoria.obtener_contador(0)
        assert contador.acumulado == 5
        assert contador.completado is False

    def test_estado_completo(self):
        memoria = MemoriaPLC()
        memoria.establecer_bobina(0, True)
        memoria.establecer_entrada_discreta(1, True)
        memoria.establecer_retencion(2, 100)
        estado = memoria.obtener_estado_completo()
        assert estado["bobinas"][0] is True
        assert estado["entradas_discretas"][1] is True
        assert estado["registros_retencion"][2] == 100
        assert "temporizadores" in estado
        assert "contadores" in estado
