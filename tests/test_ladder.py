"""Tests del motor Ladder."""

import time

import pytest

from core.memoria import MemoriaPLC
from ladder.escalon import Escalon
from ladder.instrucciones import (
    BobinaDesenclavar,
    BobinaEnclavar,
    BobinaSalida,
    ContactoNormalAbierto,
    ContactoNormalCerrado,
    ContadorAscendente,
    Igual,
    Mayor,
    Menor,
    Mover,
    Restar,
    Sumar,
    TemporizadorConexion,
)
from ladder.lector import ErrorLadder, LectorLadder
from ladder.programa import Programa
from ladder.referencias import Referencia


class TestReferencias:
    def test_referencia_entrada_discreta(self):
        memoria = MemoriaPLC()
        memoria.establecer_entrada_discreta(3, True)
        assert Referencia.interpretar("I:3").leer(memoria) is True

    def test_referencia_bobina(self):
        memoria = MemoriaPLC()
        memoria.establecer_bobina(5, True)
        assert Referencia.interpretar("Q:5").leer(memoria) is True

    def test_referencia_registro_retencion(self):
        memoria = MemoriaPLC()
        memoria.establecer_retencion(2, 42)
        assert Referencia.interpretar("HR:2").leer(memoria) == 42

    def test_referencia_literal_entero(self):
        memoria = MemoriaPLC()
        assert Referencia.interpretar("100").leer(memoria) == 100

    def test_referencia_temporizador(self):
        memoria = MemoriaPLC()
        memoria.establecer_temporizador(7, 100)
        memoria.actualizar_temporizador(7, True, 100, True, False)
        assert Referencia.interpretar("T:7").leer(memoria) is True
        assert Referencia.interpretar("T:7.ACC").leer(memoria) == 100
        assert Referencia.interpretar("T:7.PRE").leer(memoria) == 100


class TestContactos:
    def test_contacto_normal_abierto_con_entrada_activa(self):
        memoria = MemoriaPLC()
        memoria.establecer_entrada_discreta(0, True)
        assert ContactoNormalAbierto("I:0").ejecutar(memoria, True) is True

    def test_contacto_normal_abierto_con_entrada_inactiva(self):
        memoria = MemoriaPLC()
        memoria.establecer_entrada_discreta(0, False)
        assert ContactoNormalAbierto("I:0").ejecutar(memoria, True) is False

    def test_contacto_normal_cerrado_con_entrada_inactiva(self):
        memoria = MemoriaPLC()
        memoria.establecer_entrada_discreta(0, False)
        assert ContactoNormalCerrado("I:0").ejecutar(memoria, True) is True

    def test_contacto_normal_cerrado_con_entrada_activa(self):
        memoria = MemoriaPLC()
        memoria.establecer_entrada_discreta(0, True)
        assert ContactoNormalCerrado("I:0").ejecutar(memoria, True) is False

    def test_contactos_respetan_flujo_interrumpido(self):
        memoria = MemoriaPLC()
        memoria.establecer_entrada_discreta(0, True)
        assert ContactoNormalAbierto("I:0").ejecutar(memoria, False) is False
        assert ContactoNormalCerrado("I:0").ejecutar(memoria, False) is False


class TestBobinas:
    def test_bobina_salida_escribe_bobina(self):
        memoria = MemoriaPLC()
        bobina = BobinaSalida("Q:0")
        bobina.ejecutar(memoria, True)
        assert memoria.obtener_bobina(0) is True
        bobina.ejecutar(memoria, False)
        assert memoria.obtener_bobina(0) is False

    def test_bobina_enclavada_mantiene_estado(self):
        memoria = MemoriaPLC()
        bobina = BobinaEnclavar("Q:0")
        bobina.ejecutar(memoria, True)
        assert memoria.obtener_bobina(0) is True
        bobina.ejecutar(memoria, False)
        assert memoria.obtener_bobina(0) is True

    def test_bobina_desenclavada_apaga_bobina(self):
        memoria = MemoriaPLC()
        memoria.establecer_bobina(0, True)
        BobinaDesenclavar("Q:0").ejecutar(memoria, True)
        assert memoria.obtener_bobina(0) is False


class TestTemporizadores:
    def test_temporizador_conexion_completa_despues_preseleccion(self):
        memoria = MemoriaPLC()
        ton = TemporizadorConexion("T:0", 100)
        ton.ejecutar(memoria, True)
        assert memoria.obtener_temporizador(0).habilitado is True
        time.sleep(0.15)
        resultado = ton.ejecutar(memoria, True)
        assert resultado is True
        assert memoria.obtener_temporizador(0).completado is True

    def test_temporizador_conexion_se_reinicia_sin_flujo(self):
        memoria = MemoriaPLC()
        ton = TemporizadorConexion("T:0", 100)
        ton.ejecutar(memoria, True)
        time.sleep(0.05)
        ton.ejecutar(memoria, False)
        temporizador = memoria.obtener_temporizador(0)
        assert temporizador.acumulado == 0
        assert temporizador.completado is False

    def test_temporizador_conexion_no_se_rearma_mientras_esta_activo(self):
        memoria = MemoriaPLC()
        ton = TemporizadorConexion("T:0", 200)
        ton.ejecutar(memoria, True)
        time.sleep(0.05)
        acumulado_inicial = memoria.obtener_temporizador(0).acumulado
        ton.ejecutar(memoria, True)
        acumulado_final = memoria.obtener_temporizador(0).acumulado
        assert acumulado_final >= acumulado_inicial


class TestContadores:
    def test_contador_ascendente_cuenta_por_flanco(self):
        memoria = MemoriaPLC()
        ctu = ContadorAscendente("C:0", 3)

        ctu.ejecutar(memoria, True)
        assert memoria.obtener_contador(0).acumulado == 1

        ctu.ejecutar(memoria, True)
        assert memoria.obtener_contador(0).acumulado == 1

        ctu.ejecutar(memoria, False)
        ctu.ejecutar(memoria, True)
        assert memoria.obtener_contador(0).acumulado == 2

        ctu.ejecutar(memoria, False)
        ctu.ejecutar(memoria, True)
        assert memoria.obtener_contador(0).acumulado == 3
        assert memoria.obtener_contador(0).completado is True


class TestOperacionesDatos:
    def test_mover(self):
        memoria = MemoriaPLC()
        memoria.establecer_retencion(0, 42)
        Mover("HR:0", "HR:1").ejecutar(memoria, True)
        assert memoria.obtener_retencion(1) == 42

    def test_sumar(self):
        memoria = MemoriaPLC()
        memoria.establecer_retencion(0, 10)
        memoria.establecer_retencion(1, 20)
        Sumar("HR:0", "HR:1", "HR:2").ejecutar(memoria, True)
        assert memoria.obtener_retencion(2) == 30

    def test_restar(self):
        memoria = MemoriaPLC()
        memoria.establecer_retencion(0, 50)
        memoria.establecer_retencion(1, 20)
        Restar("HR:0", "HR:1", "HR:2").ejecutar(memoria, True)
        assert memoria.obtener_retencion(2) == 30


class TestComparaciones:
    def test_igual(self):
        memoria = MemoriaPLC()
        memoria.establecer_retencion(0, 5)
        assert Igual("HR:0", "5").ejecutar(memoria, True) is True
        assert Igual("HR:0", "10").ejecutar(memoria, True) is False

    def test_mayor(self):
        memoria = MemoriaPLC()
        memoria.establecer_retencion(0, 10)
        assert Mayor("HR:0", "5").ejecutar(memoria, True) is True
        assert Mayor("HR:0", "15").ejecutar(memoria, True) is False

    def test_menor(self):
        memoria = MemoriaPLC()
        memoria.establecer_retencion(0, 5)
        assert Menor("HR:0", "10").ejecutar(memoria, True) is True


class TestEscalones:
    def test_escalon_simple(self):
        memoria = MemoriaPLC()
        memoria.establecer_entrada_discreta(0, True)
        escalon = Escalon(
            nombre="basico",
            instrucciones=[ContactoNormalAbierto("I:0"), BobinaSalida("Q:0")],
        )
        assert escalon.ejecutar(memoria) is True
        assert memoria.obtener_bobina(0) is True

    def test_escalon_con_rama_or(self):
        memoria = MemoriaPLC()
        memoria.establecer_entrada_discreta(0, False)
        memoria.establecer_entrada_discreta(1, True)
        escalon = Escalon(
            nombre="con_rama",
            instrucciones=[ContactoNormalAbierto("I:0"), BobinaSalida("Q:0")],
            ramas=[[ContactoNormalAbierto("I:1"), BobinaSalida("Q:1")]],
        )
        assert escalon.ejecutar(memoria) is True
        assert memoria.obtener_bobina(0) is False
        assert memoria.obtener_bobina(1) is True


class TestPrograma:
    def test_ejecutar_devuelve_estado_por_escalon(self):
        memoria = MemoriaPLC()
        memoria.establecer_entrada_discreta(0, True)
        programa = Programa(
            escalones=[
                Escalon("a", [ContactoNormalAbierto("I:0"), BobinaSalida("Q:0")]),
                Escalon("b", [ContactoNormalCerrado("I:0"), BobinaSalida("Q:1")]),
            ]
        )
        resultados = programa.ejecutar(memoria)
        assert resultados == [True, False]
        assert memoria.obtener_bobina(0) is True
        assert memoria.obtener_bobina(1) is False


class TestLectorLadder:
    def test_leer_escalon_simple(self, tmp_path):
        path = tmp_path / "simple.lad"
        path.write_text(
            '# simple test\n'
            'RUNG 0 "simple"\n'
            '  XIC I:0\n'
            '  OTE Q:0\n'
            'END_RUNG\n'
        )
        programa = LectorLadder().leer(str(path))
        assert len(programa.escalones) == 1
        assert programa.escalones[0].nombre == "simple"
        assert len(programa.escalones[0].instrucciones) == 2

    def test_leer_rama(self, tmp_path):
        path = tmp_path / "branch.lad"
        path.write_text(
            'RUNG 0 "or-branch"\n'
            '  XIC I:0\n'
            '  BRANCH\n'
            '    XIC I:1\n'
            '  END_BRANCH\n'
            '  OTE Q:0\n'
            'END_RUNG\n'
        )
        programa = LectorLadder().leer(str(path))
        escalon = programa.escalones[0]
        assert len(escalon.instrucciones) == 2
        assert len(escalon.ramas) == 1
        assert len(escalon.ramas[0]) == 1

    def test_leer_temporizador(self, tmp_path):
        path = tmp_path / "timer.lad"
        path.write_text(
            'RUNG 0 "timer test"\n'
            '  XIC I:0\n'
            '  TON T:0 PRE=1000\n'
            'END_RUNG\n'
        )
        programa = LectorLadder().leer(str(path))
        assert len(programa.escalones) == 1

    def test_instruccion_desconocida_lanza_error(self, tmp_path):
        path = tmp_path / "bad.lad"
        path.write_text("FOO I:0\n")
        with pytest.raises(ErrorLadder):
            LectorLadder().leer(str(path))

    def test_escalon_sin_fin_lanza_error(self, tmp_path):
        path = tmp_path / "no_end.lad"
        path.write_text('RUNG 0 "x"\n  XIC I:0\n')
        with pytest.raises(ErrorLadder):
            LectorLadder().leer(str(path))

    def test_programa_carga_desde_archivo(self, tmp_path):
        path = tmp_path / "via_class.lad"
        path.write_text(
            'RUNG 0 "x"\n'
            '  XIC I:0\n'
            '  OTE Q:0\n'
            'END_RUNG\n'
        )
        programa = Programa.cargar_desde_archivo(str(path))
        assert len(programa.escalones) == 1
