"""Tests de los componentes de GSCADA.

Cubre configuracion, alarmas, historiador, consultor y servidor.
"""

import json
import threading
import time
import urllib.error
import urllib.request

import pytest

from gscada.alarmas import MotorAlarmas, _evaluar_valor, _interpretar_condicion
from gscada.configuracion import (
    ConfiguracionAlarma,
    ConfiguracionPLC,
    ConfiguracionSistema,
    ConfiguracionTag,
)
from gscada.consultor import ConsultorModbus
from gscada.historiador import Historiador
from gscada.servidor import (
    _estado_plcs,
    construir_componentes,
    crear_aplicacion,
)


class _AplicacionPrueba:
    """Context manager chico alrededor de uvicorn + urllib para los tests."""

    def __init__(self, aplicacion):
        import socket
        import uvicorn
        self._aplicacion = aplicacion
        self._servidor = uvicorn.Server(uvicorn.Config(
            aplicacion, host="127.0.0.1", port=0, log_level="warning"
        ))
        # Busca un puerto libre.
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as socket_libre:
            socket_libre.bind(("127.0.0.1", 0))
            self._puerto = socket_libre.getsockname()[1]
        self._servidor.config.port = self._puerto
        self._hilo = None

    def __enter__(self):
        self._hilo = threading.Thread(
            target=self._servidor.run, daemon=True
        )
        self._hilo.start()
        import socket
        for _ in range(100):
            try:
                with socket.create_connection(
                    ("127.0.0.1", self._puerto), timeout=0.1
                ):
                    break
            except OSError:
                time.sleep(0.05)
        return self

    def __exit__(self, *argumentos):
        self._servidor.should_exit = True
        if self._hilo is not None:
            self._hilo.join(timeout=3)

    @property
    def base(self):
        return f"http://127.0.0.1:{self._puerto}"

    def get(self, ruta):
        return self._solicitar("GET", ruta)

    def post(self, ruta):
        return self._solicitar("POST", ruta)

    def _solicitar(self, metodo, ruta):
        try:
            peticion = urllib.request.Request(
                self.base + ruta, method=metodo
            )
            with urllib.request.urlopen(peticion, timeout=2) as respuesta:
                return _Respuesta(respuesta.status, respuesta.read())
        except urllib.error.HTTPError as error:
            return _Respuesta(error.code, error.read() or b"")


class _Respuesta:
    def __init__(self, estado, cuerpo):
        self.status_code = estado
        self._cuerpo = cuerpo

    def json(self):
        return json.loads(self._cuerpo or b"{}")

    @property
    def text(self):
        return self._cuerpo.decode("utf-8", "replace")


class TestConfiguracion:
    def test_carga_config_minima(self, tmp_path):
        ruta = tmp_path / "c.yaml"
        ruta.write_text(
            "plcs:\n"
            "  - name: p1\n"
            "    host: 1.2.3.4\n"
            "    port: 502\n"
            "    tags:\n"
            "      - name: t1\n"
            "        address: 0\n"
            "        type: input_register\n"
        )
        configuracion = ConfiguracionSistema.cargar(str(ruta))
        assert len(configuracion.plcs) == 1
        assert configuracion.plcs[0].nombre == "p1"
        assert configuracion.plcs[0].tags[0].tipo == "input_register"

    def test_carga_config_con_alarmas(self, tmp_path):
        ruta = tmp_path / "c.yaml"
        ruta.write_text(
            "plcs:\n"
            "  - name: p1\n"
            "    host: 1.2.3.4\n"
            "    tags:\n"
            "      - name: t1\n"
            "        address: 0\n"
            "        type: input_register\n"
            "      - name: t2\n"
            "        address: 0\n"
            "        type: coil\n"
            "alarms:\n"
            "  - tag: t1\n"
            "    condition: '> 90'\n"
            "    severity: high\n"
            "    message: hi\n"
        )
        configuracion = ConfiguracionSistema.cargar(str(ruta))
        assert len(configuracion.alarmas) == 1
        assert configuracion.alarmas[0].condicion == "> 90"
        assert configuracion.alarmas[0].severidad == "high"

    def test_carga_archivo_inexistente(self):
        with pytest.raises(FileNotFoundError):
            ConfiguracionSistema.cargar("/no/existe.yaml")

    def test_tipo_de_tag_invalido_se_rechaza(self):
        with pytest.raises(Exception):
            ConfiguracionTag(nombre="x", direccion=0, tipo="invalid")


class TestAlarmas:
    def test_interpretar_condicion(self):
        assert _interpretar_condicion("> 5") == (">", 5.0)
        assert _interpretar_condicion(">= 0.5") == (">=", 0.5)
        assert _interpretar_condicion("== 0") == ("==", 0.0)
        assert _interpretar_condicion("!= 1") == ("!=", 1.0)
        assert _interpretar_condicion("  <  10  ") == ("<", 10.0)
        assert _interpretar_condicion("basura") is None

    def test_evaluar_valor(self):
        assert _evaluar_valor(95, ">", 90) is True
        assert _evaluar_valor(5, ">", 90) is False
        assert _evaluar_valor(0, "==", 0) is True
        assert _evaluar_valor(1, "==", 0) is False
        assert _evaluar_valor(10, "<", 10) is False
        assert _evaluar_valor(10, "<=", 10) is True
        assert _evaluar_valor("no_es_numero", ">", 0) is False

    def test_el_motor_dispara_una_alarma(self):
        motor = MotorAlarmas([
            ConfiguracionAlarma(
                tag="nivel", condition="> 90", severity="high", message="alto"
            )
        ])
        activas = motor.evaluar({"nivel": 95})
        assert len(activas) == 1
        assert activas[0].tag == "nivel"
        assert activas[0].estado == "ACTIVE"

    def test_la_alarma_se_despeja(self):
        motor = MotorAlarmas([
            ConfiguracionAlarma(
                tag="nivel", condition="> 90", severity="high", message="alto"
            )
        ])
        motor.evaluar({"nivel": 95})
        activas = motor.evaluar({"nivel": 50})
        assert activas == []
        assert len(motor.historial) == 1
        assert motor.historial[0].estado == "CLEARED"

    def test_reconocer_alarma(self):
        motor = MotorAlarmas([
            ConfiguracionAlarma(
                tag="nivel", condition="> 90", severity="high", message="alto"
            )
        ])
        motor.evaluar({"nivel": 95})
        alarma = motor.activas[0]
        assert motor.reconocer(alarma.id) is True
        assert motor.activas[0].estado == "ACKNOWLEDGED"
        # Reconocer un id inexistente devuelve False.
        assert motor.reconocer("nada") is False

    def test_reconocer_perdura_mientras_la_condicion_sigue(self):
        motor = MotorAlarmas([
            ConfiguracionAlarma(
                tag="nivel", condition="> 90", severity="high", message="alto"
            )
        ])
        motor.evaluar({"nivel": 95})
        alarma = motor.activas[0]
        motor.reconocer(alarma.id)
        # Una evaluacion posterior, con la condicion todavia activa, debe
        # mantener la alarma reconocida en vez de reiniciarla o perderla.
        motor.evaluar({"nivel": 95})
        assert motor.activas[0].id == alarma.id
        assert motor.activas[0].estado == "ACKNOWLEDGED"

    def test_reconocer_se_despeja_cuando_la_condicion_normaliza(self):
        motor = MotorAlarmas([
            ConfiguracionAlarma(
                tag="nivel", condition="> 90", severity="high", message="alto"
            )
        ])
        motor.evaluar({"nivel": 95})
        alarma = motor.activas[0]
        motor.reconocer(alarma.id)
        motor.evaluar({"nivel": 50})
        assert motor.activas == []
        assert motor.historial[-1].estado == "CLEARED"


class TestHistoriador:
    def test_registrar_y_consultar(self, tmp_path):
        base = tmp_path / "h.db"
        historiador = Historiador(ruta_bd=base, antiguedad_maxima_s=0)
        historiador.registrar("nivel", 50, marca_tiempo=1000.0)
        historiador.registrar("nivel", 60, marca_tiempo=1001.0)
        historiador.registrar("nivel", 70, marca_tiempo=1002.0)
        filas = historiador.consultar("nivel")
        assert len(filas) == 3
        assert filas[0] == (1000.0, 50.0)
        assert filas[-1] == (1002.0, 70.0)

    def test_consultar_con_rango_de_tiempo(self, tmp_path):
        historiador = Historiador(
            ruta_bd=tmp_path / "h.db", antiguedad_maxima_s=0
        )
        for indice, valor in enumerate([10, 20, 30, 40, 50]):
            historiador.registrar("t", valor, marca_tiempo=1000.0 + indice)
        filas = historiador.consultar("t", desde=1001.0, hasta=1003.0)
        assert len(filas) == 3
        assert filas[0][1] == 20.0
        assert filas[-1][1] == 40.0

    def test_depura_los_datos_viejos(self, tmp_path):
        historiador = Historiador(
            ruta_bd=tmp_path / "h.db", antiguedad_maxima_s=10.0
        )
        historiador.registrar("t", 1, marca_tiempo=time.time() - 100)
        historiador.registrar("t", 2, marca_tiempo=time.time())
        # Otro registro dispara la depuracion.
        historiador.registrar("t", 3, marca_tiempo=time.time())
        filas = historiador.consultar("t")
        assert all(marca > time.time() - 50 for marca, _ in filas)

    def test_ignora_valores_no_numericos(self, tmp_path):
        historiador = Historiador(
            ruta_bd=tmp_path / "h.db", antiguedad_maxima_s=0
        )
        historiador.registrar("t", "hola")
        historiador.registrar("t", None)
        assert historiador.consultar("t") == []

    def test_ultimas_muestras(self, tmp_path):
        historiador = Historiador(
            ruta_bd=tmp_path / "h.db", antiguedad_maxima_s=0
        )
        for indice in range(20):
            historiador.registrar(
                "t", indice, marca_tiempo=1000.0 + indice
            )
        filas = historiador.ultimas("t", cantidad=5)
        assert len(filas) == 5
        assert filas[0][1] == 15.0
        assert filas[-1][1] == 19.0


class TestConsultor:
    def test_siembra_los_tags_como_obsoletos(self):
        configuracion = ConfiguracionPLC(nombre="p1", host="1.2.3.4", tags=[
            ConfiguracionTag(nombre="t1", direccion=0, tipo="input_register")
        ])
        consultor = ConsultorModbus(configuracion)
        ultimas = consultor.obtener_ultimas()
        assert ultimas["t1"].obsoleta is True
        assert consultor.en_linea is False

    def test_agrupa_por_area(self):
        configuracion = ConfiguracionPLC(nombre="p", host="1.2.3.4", tags=[
            ConfiguracionTag(nombre="c1", direccion=0, tipo="coil"),
            ConfiguracionTag(nombre="c2", direccion=1, tipo="coil"),
            ConfiguracionTag(nombre="hr1", direccion=0,
                             tipo="holding_register"),
            ConfiguracionTag(nombre="di1", direccion=0,
                             tipo="discrete_input"),
            ConfiguracionTag(nombre="ir1", direccion=0,
                             tipo="input_register"),
        ])
        consultor = ConsultorModbus(configuracion)
        grupos = consultor._agrupar_por_area()
        assert len(grupos["coil"]) == 2
        assert len(grupos["holding_register"]) == 1
        assert len(grupos["discrete_input"]) == 1
        assert len(grupos["input_register"]) == 1

    def test_marca_obsoletos_si_falla_la_conexion(self):
        # Apunta a un host inalcanzable para que falle el connect.
        configuracion = ConfiguracionPLC(
            nombre="p", host="127.0.0.1", puerto=1, intervalo_consulta_ms=100,
            tags=[ConfiguracionTag(nombre="t", direccion=0,
                                   tipo="input_register")],
        )
        consultor = ConsultorModbus(configuracion)
        resultado = consultor._consultar_una_vez()
        assert resultado is False
        assert consultor.ultimo_error != ""
        assert consultor.obtener_ultimas()["t"].obsoleta is True

    def test_aplica_la_escala_a_los_tags_numericos(self):
        configuracion = ConfiguracionPLC(nombre="p", host="1.2.3.4", tags=[
            ConfiguracionTag(nombre="t", direccion=0,
                             tipo="input_register", escala=0.1)
        ])
        consultor = ConsultorModbus(configuracion)
        # Inyecta un valor falso en vez de hablar Modbus de verdad.
        consultor._conectar = lambda: None
        consultor._cliente = _ClienteFalso()
        resultado = consultor._consultar_una_vez()
        assert resultado is True
        assert consultor.obtener_ultimas()["t"].valor == 5.0  # 50 * 0.1


class _ClienteFalso:
    """Cliente Modbus falso: responde 50 en los registros de entrada."""

    def read_input_registers(self, address, count=1, slave=1):
        class _Respuesta:
            def isError(self):
                return False
            registers = [50]
        return _Respuesta()

    def connect(self):
        return True


class TestServidor:
    def _configuracion(self):
        return ConfiguracionSistema(plcs=[
            ConfiguracionPLC(nombre="p1", host="1.2.3.4", tags=[
                ConfiguracionTag(nombre="t1", direccion=0,
                                 tipo="input_register")
            ])
        ])

    def test_obtener_plcs(self):
        configuracion = self._configuracion()
        construir_componentes(configuracion)
        aplicacion = crear_aplicacion(carpeta_estatica=None)
        with _AplicacionPrueba(aplicacion) as cliente:
            respuesta = cliente.get("/api/plcs")
            assert respuesta.status_code == 200
            cuerpo = respuesta.json()
            assert len(cuerpo["plcs"]) == 1
            assert cuerpo["plcs"][0]["name"] == "p1"
            # Sembrado como obsoleto → no esta en linea.
            assert cuerpo["plcs"][0]["online"] is False

    def test_obtener_alarmas_vacio(self):
        configuracion = self._configuracion()
        construir_componentes(configuracion)
        aplicacion = crear_aplicacion(carpeta_estatica=None)
        with _AplicacionPrueba(aplicacion) as cliente:
            respuesta = cliente.get("/api/alarms")
            assert respuesta.status_code == 200
            assert respuesta.json() == {"active": [], "history": []}

    def test_obtener_tendencias(self, tmp_path):
        configuracion = self._configuracion()
        historiador = Historiador(
            ruta_bd=tmp_path / "h.db", antiguedad_maxima_s=0
        )
        historiador.registrar("t1", 42, marca_tiempo=1000.0)
        construir_componentes(configuracion, historiador=historiador)
        aplicacion = crear_aplicacion(carpeta_estatica=None)
        with _AplicacionPrueba(aplicacion) as cliente:
            respuesta = cliente.get("/api/trends/t1")
            assert respuesta.status_code == 200
            assert respuesta.json()["samples"] == [
                {"timestamp": 1000.0, "value": 42.0}
            ]

    def test_montaje_de_estaticos(self):
        construir_componentes(self._configuracion())
        aplicacion = crear_aplicacion(carpeta_estatica="gscada/static")
        with _AplicacionPrueba(aplicacion) as cliente:
            respuesta = cliente.get("/")
            assert respuesta.status_code == 200
            assert "GSCADA" in respuesta.text

    def test_payload_del_websocket(self):
        # El handler del WS arma el payload con _plc_status() y el estado
        # de las alarmas; ejercitamos los helpers directamente.
        configuracion = self._configuracion()
        construir_componentes(configuracion)
        plcs = _estado_plcs()
        assert len(plcs) == 1
        assert plcs[0]["name"] == "p1"


