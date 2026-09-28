"""Tests para el servidor Modbus TCP."""

import time
import socket

import pytest
from core.memoria import MemoriaPLC
from protocols.modbus_server import ServidorModbus


class TestServidorModbus:
    def test_creacion_servidor(self):
        memoria = MemoriaPLC()
        servidor = ServidorModbus(memoria, host="127.0.0.1", puerto=15502)
        assert servidor.puerto == 15502
        assert servidor.host == "127.0.0.1"

    def test_inicio_detencion(self):
        memoria = MemoriaPLC()
        servidor = ServidorModbus(memoria, host="127.0.0.1", puerto=15502)
        servidor.iniciar()
        time.sleep(0.5)
        assert servidor._ejecutando is True
        servidor.detener()
        time.sleep(0.3)
        assert servidor._ejecutando is False

    def test_creacion_contexto(self):
        memoria = MemoriaPLC()
        servidor = ServidorModbus(memoria, host="127.0.0.1", puerto=15503)
        servidor.iniciar()
        time.sleep(0.3)
        contexto = servidor.obtener_contexto()
        assert contexto is not None
        servidor.detener()

    def test_escrituras_modbus_actualizan_memoria_plc(self):
        memoria = MemoriaPLC()
        servidor = ServidorModbus(memoria, host="127.0.0.1", puerto=15504)
        servidor.iniciar()
        time.sleep(0.2)
        contexto = servidor.obtener_contexto()
        assert contexto is not None
        esclavo = contexto[0]
        esclavo.setValues(1, 6, [1])
        esclavo.setValues(3, 7, [321])

        time.sleep(0.2)

        assert memoria.obtener_bobina(6) is True
        assert memoria.obtener_retencion(7) == 321
        servidor.detener()

    def test_detener_libera_puerto_modbus(self):
        memoria = MemoriaPLC()
        servidor = ServidorModbus(memoria, host="127.0.0.1", puerto=15505)
        servidor.iniciar()
        time.sleep(0.2)

        with socket.create_connection(("127.0.0.1", 15505), timeout=1):
            pass

        servidor.detener()

        with pytest.raises(OSError):
            socket.create_connection(("127.0.0.1", 15505), timeout=1)
