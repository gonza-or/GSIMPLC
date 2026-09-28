"""
Puente entre los escenarios YAML y el simulador de proceso.

Cada escenario declara una lista de modelos con su mapa de memoria; este
modulo instancia la clase que corresponde a cada ``type`` y devuelve un
simulador listo para arrancar.

Las claves del YAML (``name``, ``capacity_liters``, ...) son el contrato
externo que ya usan los escenarios de ``process_sim/scenarios``: aca se
traducen a los parametros en espanol de cada modelo.
"""

import logging
from pathlib import Path

import yaml

from process_sim.modelos import (
    Cinta,
    Motor,
    SensorTemperatura,
    Tanque,
    Valvula,
)
from process_sim.simulador import SimuladorProceso

registrador = logging.getLogger("PLC.SimuladorProceso.Puente")

REGISTRO_MODELOS = {
    "Tank": Tanque,
    "Motor": Motor,
    "Valve": Valvula,
    "TempSensor": SensorTemperatura,
    "Conveyor": Cinta,
}

# Claves del YAML -> parametros de los constructores en espanol.
TRADUCCION_CLAVES = {
    "name": "nombre",
    "capacity_liters": "capacidad_litros",
    "fill_rate_lps": "caudal_llenado_lps",
    "drain_rate_lps": "caudal_drenaje_lps",
    "level_input_register": "registro_entrada_nivel",
    "high_alarm_input": "entrada_alarma_alta",
    "low_alarm_input": "entrada_alarma_baja",
    "fill_coil": "bobina_llenado",
    "max_rpm": "rpm_maximas",
    "accel_rpm_s": "aceleracion_rpm_s",
    "running_coil": "bobina_marcha",
    "rpm_input_register": "registro_entrada_rpm",
    "running_input": "entrada_marcha",
    "travel_time_s": "tiempo_recorrido_s",
    "setpoint_register": "registro_consigna",
    "position_input_register": "registro_entrada_posicion",
    "ambient_temp": "temperatura_ambiente",
    "heating_rate": "tasa_calentamiento",
    "cooling_rate": "tasa_enfriamiento",
    "heater_coil": "bobina_calentador",
    "temp_input_register": "registro_entrada_temperatura",
    "speed_mps": "velocidad_mps",
    "segment_length_m": "longitud_tramo_m",
    "motor_coil": "bobina_motor",
    "object_detected_input": "entrada_objeto_detectado",
}


def _traducir_especificacion(especificacion):
    """Traduce las claves del YAML a los parametros en espanol."""
    parametros = {}
    for clave, valor in especificacion.items():
        if clave == "type":
            continue
        nombre = TRADUCCION_CLAVES.get(clave)
        if nombre is None:
            raise ValueError(f"Clave de modelo desconocida: {clave!r}")
        parametros[nombre] = valor
    if "nombre" not in parametros:
        parametros["nombre"] = especificacion.get("type")
    return parametros


def _construir_modelo(especificacion):
    """Instancia un modelo a partir de su especificacion YAML."""
    tipo = especificacion.get("type")
    if tipo not in REGISTRO_MODELOS:
        raise ValueError(f"Tipo de modelo desconocido: {tipo!r}")
    clase = REGISTRO_MODELOS[tipo]
    return clase(**_traducir_especificacion(especificacion))


def cargar_escenario(ruta, memoria, periodo_ms=200):
    """Carga un escenario YAML y devuelve el simulador ya configurado."""
    ruta_escenario = Path(ruta)
    if not ruta_escenario.is_file():
        raise FileNotFoundError(f"Escenario no encontrado: {ruta}")

    with ruta_escenario.open("r", encoding="utf-8") as archivo:
        datos = yaml.safe_load(archivo) or {}

    nombre_proceso = datos.get("process", ruta_escenario.stem)
    especificaciones = datos.get("models", [])
    if not isinstance(especificaciones, list):
        raise ValueError(f"Escenario {ruta}: 'models' debe ser una lista")

    modelos = []
    for especificacion in especificaciones:
        if not isinstance(especificacion, dict):
            raise ValueError(
                f"Escenario {ruta}: cada modelo debe ser un mapeo"
            )
        try:
            modelos.append(_construir_modelo(especificacion))
        except ValueError as error:
            raise ValueError(f"Escenario {ruta}: {error}") from error
        except TypeError as error:
            raise ValueError(
                f"Escenario {ruta}: especificacion invalida para "
                f"{especificacion.get('name', '?')}: {error}"
            ) from error

    registrador.info(
        "Escenario cargado: %s — %d modelo(s): %s",
        nombre_proceso,
        len(modelos),
        [modelo.nombre for modelo in modelos],
    )
    return SimuladorProceso(modelos, memoria, periodo_ms=periodo_ms)
