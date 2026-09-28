"""Tests del simulador de proceso."""

import time

import pytest

from core.memoria import MemoriaPLC
from process_sim import (
    Cinta,
    Motor,
    SensorTemperatura,
    SimuladorProceso,
    Tanque,
    Valvula,
    cargar_escenario,
)


class TestTanque:
    def test_nivel_inicial_es_la_mitad(self):
        memoria = MemoriaPLC()
        tanque = Tanque(
            nombre="t1",
            capacidad_litros=1000,
            caudal_llenado_lps=5,
            caudal_drenaje_lps=2,
            registro_entrada_nivel=0,
            entrada_alarma_alta=0,
            entrada_alarma_baja=1,
            bobina_llenado=0,
        )
        tanque.actualizar(0.0, memoria)
        assert memoria.obtener_entrada(0) == 50  # 50 %

    def test_bomba_encendida_sube_el_nivel(self):
        memoria = MemoriaPLC()
        tanque = Tanque("t", 1000, 5, 2, 0, 0, 1, 0)
        # Sin bomba, solo drenaje 100 s → pierde 200 L (20 %).
        for _ in range(100):
            tanque.actualizar(1.0, memoria)
        assert memoria.obtener_entrada(0) == pytest.approx(30, abs=1)

    def test_alarmas_alta_y_baja(self):
        memoria = MemoriaPLC()
        # Llenado rapido: bomba ON a 100 lps; 10 s → 1000 L.
        tanque = Tanque("t", 1000, 100, 0, 0, 0, 1, 0)
        memoria.establecer_bobina(0, True)
        for _ in range(10):
            tanque.actualizar(1.0, memoria)
        assert memoria.obtener_entrada(0) == 100
        assert memoria.obtener_entrada_discreta(0) is True   # alarma alta
        assert memoria.obtener_entrada_discreta(1) is False  # no baja

        # Ahora drena: un tanque nuevo sin bomba y con drenaje de 100 lps.
        memoria2 = MemoriaPLC()
        tanque2 = Tanque("t2", 1000, 0, 100, 0, 0, 1, 0)
        for _ in range(10):
            tanque2.actualizar(1.0, memoria2)
        assert memoria2.obtener_entrada(0) == 0
        assert memoria2.obtener_entrada_discreta(0) is False
        assert memoria2.obtener_entrada_discreta(1) is True  # alarma baja

    def test_nivel_se_limita_a_la_capacidad(self):
        memoria = MemoriaPLC()
        tanque = Tanque("t", 100, 1000, 0, 0, 0, 1, 0)
        memoria.establecer_bobina(0, True)
        for _ in range(5):
            tanque.actualizar(1.0, memoria)
        assert memoria.obtener_entrada(0) == 100


class TestMotor:
    def test_motor_acelera_gradualmente(self):
        memoria = MemoriaPLC()
        motor = Motor("m", rpm_maximas=1000, aceleracion_rpm_s=100,
                      bobina_marcha=0, registro_entrada_rpm=0,
                      entrada_marcha=0)
        memoria.establecer_bobina(0, True)
        motor.actualizar(1.0, memoria)
        assert memoria.obtener_entrada(0) == 100  # 100 RPM/s * 1 s
        motor.actualizar(1.0, memoria)
        assert memoria.obtener_entrada(0) == 200

    def test_motor_llega_al_maximo(self):
        memoria = MemoriaPLC()
        motor = Motor("m", 500, 1000, 0, 0, 0)
        memoria.establecer_bobina(0, True)
        for _ in range(2):
            motor.actualizar(1.0, memoria)
        assert memoria.obtener_entrada(0) == 500  # limitado a rpm_maximas

    def test_motor_se_detiene_sin_bobina(self):
        memoria = MemoriaPLC()
        motor = Motor("m", 1000, 100, 0, 0, 0)
        memoria.establecer_bobina(0, True)
        for _ in range(5):
            motor.actualizar(1.0, memoria)
        memoria.establecer_bobina(0, False)
        for _ in range(20):
            motor.actualizar(1.0, memoria)
        assert memoria.obtener_entrada(0) == 0


class TestValvula:
    def test_valvula_llega_a_la_consigna(self):
        memoria = MemoriaPLC()
        valvula = Valvula("v", tiempo_recorrido_s=2.0, registro_consigna=0,
                          registro_entrada_posicion=0)
        memoria.establecer_retencion(0, 50)
        valvula.actualizar(1.0, memoria)
        # Recorrido completo en 2 s: la mitad en 1 s.
        assert memoria.obtener_entrada(0) == 50

    def test_valvula_se_limita_a_100(self):
        memoria = MemoriaPLC()
        valvula = Valvula("v", 1.0, 0, 0)
        memoria.establecer_retencion(0, 200)  # fuera de rango
        valvula.actualizar(2.0, memoria)
        assert memoria.obtener_entrada(0) == 100


class TestSensorTemperatura:
    def test_calentador_sube_la_temperatura(self):
        memoria = MemoriaPLC()
        sensor = SensorTemperatura(
            "t", temperatura_ambiente=20, tasa_calentamiento=5,
            tasa_enfriamiento=0.1, bobina_calentador=0,
            registro_entrada_temperatura=0,
        )
        memoria.establecer_bobina(0, True)
        sensor.actualizar(2.0, memoria)
        assert memoria.obtener_entrada(0) == 30  # 20 + 5*2

    def test_sin_calentador_tiende_al_ambiente(self):
        memoria = MemoriaPLC()
        sensor = SensorTemperatura(
            "t", temperatura_ambiente=20, tasa_calentamiento=5,
            tasa_enfriamiento=0.1, bobina_calentador=0,
            registro_entrada_temperatura=0,
        )
        sensor.actualizar(100.0, memoria)  # suficiente para converger
        assert memoria.obtener_entrada(0) == 20


class TestCinta:
    def test_pulso_de_objeto_con_el_motor_encendido(self):
        memoria = MemoriaPLC()
        cinta = Cinta("c", velocidad_mps=1.0, longitud_tramo_m=1.0,
                      bobina_motor=0, entrada_objeto_detectado=0)
        memoria.establecer_bobina(0, True)
        # Tras 1 s el objeto llega al sensor.
        cinta.actualizar(1.0, memoria)
        assert memoria.obtener_entrada_discreta(0) is True
        cinta.actualizar(0.1, memoria)
        assert memoria.obtener_entrada_discreta(0) is False

    def test_sin_pulso_con_el_motor_apagado(self):
        memoria = MemoriaPLC()
        cinta = Cinta("c", 1.0, 1.0, 0, 0)
        cinta.actualizar(2.0, memoria)
        assert memoria.obtener_entrada_discreta(0) is False


class TestSimuladorProceso:
    def test_el_simulador_arranca_y_se_detiene(self):
        memoria = MemoriaPLC()
        modelos = [Tanque("t", 1000, 5, 2, 0, 0, 1, 0)]
        simulador = SimuladorProceso(modelos, memoria, periodo_ms=50)
        simulador.iniciar()
        time.sleep(0.25)
        simulador.detener()
        # Tiene que haber dado varios tics.
        assert simulador.tics >= 3

    def test_los_modelos_reciben_tics(self):
        memoria = MemoriaPLC()
        simulador = SimuladorProceso(
            [Tanque("t", 1000, 0, 100, 0, 0, 1, 0)],
            memoria,
            periodo_ms=50,
        )
        simulador.iniciar()
        time.sleep(0.3)
        simulador.detener()
        # Solo drenaje 0.3 s = 30 L perdidos → el nivel baja a ~47 %.
        nivel = memoria.obtener_entrada(0)
        assert 40 <= nivel <= 50


class TestPuente:
    def test_carga_el_escenario_tanque_simple(self):
        from pathlib import Path
        carpeta = Path("process_sim/scenarios")
        simulador = cargar_escenario(
            carpeta / "tanque_simple.yaml", MemoriaPLC()
        )
        assert len(simulador.modelos) == 1
        assert simulador.modelos[0].nombre == "tanque_1"
        assert simulador.periodo_ms == 200  # por defecto

    def test_carga_escenario_con_periodo_propio(self, tmp_path):
        ruta = tmp_path / "s.yaml"
        ruta.write_text(
            "process: test\n"
            "models:\n"
            "  - type: Tank\n"
            "    name: t1\n"
            "    capacity_liters: 100\n"
            "    fill_rate_lps: 1\n"
            "    drain_rate_lps: 0\n"
            "    level_input_register: 0\n"
            "    high_alarm_input: 0\n"
            "    low_alarm_input: 1\n"
            "    fill_coil: 0\n"
        )
        simulador = cargar_escenario(str(ruta), MemoriaPLC(), periodo_ms=100)
        assert simulador.periodo_ms == 100

    def test_tipo_de_modelo_desconocido_falla(self, tmp_path):
        ruta = tmp_path / "s.yaml"
        ruta.write_text(
            "process: bad\n"
            "models:\n"
            "  - type: Alien\n"
            "    name: x\n"
        )
        with pytest.raises(ValueError, match="Tipo de modelo desconocido"):
            cargar_escenario(str(ruta), MemoriaPLC())

    def test_archivo_inexistente_falla(self):
        with pytest.raises(FileNotFoundError):
            cargar_escenario("/no/existe.yaml", MemoriaPLC())

