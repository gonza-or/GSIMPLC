import threading

import pytest

from core.plc import PLC
from ladder.escalon import Escalon
from ladder.instrucciones import BobinaSalida
from ladder.programa import Programa
from main import interpretar_argumentos
from process_sim.simulador import SimuladorProceso


def test_plc_se_puede_crear_fuera_del_hilo_principal():
    errores = []

    def crear_plc():
        try:
            PLC()
        except Exception as error:
            errores.append(error)

    hilo = threading.Thread(target=crear_plc)
    hilo.start()
    hilo.join()

    assert errores == []


def test_plc_ejecuta_programa_ladder_en_un_scan():
    plc = PLC()
    programa = Programa([Escalon("activar salida", [BobinaSalida("Q:0")])])

    plc.establecer_programa(programa)
    plc.ciclo._paso()

    assert plc.memoria.obtener_bobina(0) is True


def test_argumentos_aceptan_escenario_de_proceso():
    argumentos = interpretar_argumentos(
        ["--escenario", "proceso.yaml", "--ciclo-proceso", "50"]
    )

    assert argumentos.escenario == "proceso.yaml"
    assert argumentos.ciclo_proceso == 50


@pytest.mark.parametrize(
    "argumento, valor",
    [("--cycle", "0"), ("--cycle", "-1"), ("--ciclo-proceso", "0")],
)
def test_argumentos_rechazan_ciclos_no_positivos(argumento, valor):
    with pytest.raises(SystemExit):
        interpretar_argumentos([argumento, valor])


def test_plc_administra_motor_de_proceso():
    plc = PLC()
    motor_proceso = SimuladorProceso([], plc.memoria, periodo_ms=10)
    plc.agregar_componente(motor_proceso)

    plc.iniciar()
    plc.detener()

    assert motor_proceso.tics > 0
