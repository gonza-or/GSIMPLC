"""
Motor de alarmas — evalua condiciones simples contra los valores de tags.

Condiciones soportadas (en texto)::

    "> 90"     mayor que
    "< 10"     menor que
    ">= 5"     mayor o igual
    "<= 5"     menor o igual
    "== 0"     igual
    "!= 1"     distinto
"""

import logging
import re
import threading
import time
import uuid

from gscada.configuracion import ConfiguracionAlarma

registrador = logging.getLogger("GSCADA.Alarmas")

# Patron de operador soportado.
_PATRON_OPERADOR = re.compile(
    r"^\s*(>=|<=|==|!=|>|<)\s*(-?\d+(?:\.\d+)?)\s*$"
)

# El historial en memoria se mantiene acotado.
_MAX_HISTORIAL = 1000

# Estados del contrato HTTP que consume la HMI.
ESTADO_ACTIVA = "ACTIVE"
ESTADO_RECONOCIDA = "ACKNOWLEDGED"
ESTADO_DESPEJADA = "CLEARED"


def _interpretar_condicion(condicion):
    coincidencia = _PATRON_OPERADOR.match(condicion)
    if not coincidencia:
        return None
    return coincidencia.group(1), float(coincidencia.group(2))


def _evaluar_valor(valor, operador, umbral):
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return False
    if operador == ">":
        return numero > umbral
    if operador == "<":
        return numero < umbral
    if operador == ">=":
        return numero >= umbral
    if operador == "<=":
        return numero <= umbral
    if operador == "==":
        return numero == umbral
    if operador == "!=":
        return numero != umbral
    return False


class AlarmaActiva:
    """Alarma disparada, con su estado y sus marcas de tiempo."""

    def __init__(self, identificador, tag, severidad, mensaje, marca_tiempo,
                 estado=ESTADO_ACTIVA, marca_reconocida=None,
                 marca_despejada=None):
        self.id = identificador
        self.tag = tag
        self.severidad = severidad
        self.mensaje = mensaje
        self.marca_tiempo = marca_tiempo
        self.estado = estado
        self.marca_reconocida = marca_reconocida
        self.marca_despejada = marca_despejada

    def a_diccionario(self):
        # Claves del contrato HTTP que consume la HMI.
        return {
            "id": self.id,
            "tag": self.tag,
            "severity": self.severidad,
            "message": self.mensaje,
            "timestamp": self.marca_tiempo,
            "state": self.estado,
            "ack_timestamp": self.marca_reconocida,
            "clear_timestamp": self.marca_despejada,
        }


class MotorAlarmas:
    """Sigue las alarmas activas y el historial de un set de condiciones."""

    def __init__(self, configuraciones: list[ConfiguracionAlarma]):
        self._configuraciones = list(configuraciones)
        self._activas = {}
        self._historial = []
        self._cerradura = threading.Lock()

    @property
    def activas(self):
        with self._cerradura:
            return [
                alarma for alarma in self._activas.values()
                if alarma.estado != ESTADO_DESPEJADA
            ]

    @property
    def historial(self):
        with self._cerradura:
            return list(self._historial)

    def _buscar_activa(self, configuracion):
        for alarma in self._activas.values():
            if (alarma.tag == configuracion.etiqueta
                    and alarma.mensaje == configuracion.mensaje
                    and alarma.severidad == configuracion.severidad):
                return alarma
        return None

    def evaluar(self, valores_tags):
        """Corre una pasada de evaluacion y devuelve las alarmas que salen."""
        ahora = time.time()
        disparando = []
        with self._cerradura:
            for configuracion in self._configuraciones:
                interpretada = _interpretar_condicion(configuracion.condicion)
                if interpretada is None:
                    registrador.warning(
                        "Condicion de alarma invalida para %s: %r",
                        configuracion.etiqueta,
                        configuracion.condicion,
                    )
                    continue
                operador, umbral = interpretada
                valor = valores_tags.get(configuracion.etiqueta)
                dispara = False
                if valor is not None:
                    dispara = _evaluar_valor(valor, operador, umbral)
                existente = self._buscar_activa(configuracion)
                if dispara:
                    if existente is None:
                        alarma = AlarmaActiva(
                            identificador=uuid.uuid4().hex[:12],
                            tag=configuracion.etiqueta,
                            severidad=configuracion.severidad,
                            mensaje=configuracion.mensaje or (
                                f"{configuracion.etiqueta} "
                                f"{configuracion.condicion}"
                            ),
                            marca_tiempo=ahora,
                        )
                        self._activas[alarma.id] = alarma
                        existente = alarma
                    disparando.append(existente)
                else:
                    if (existente is not None
                            and existente.estado != ESTADO_DESPEJADA):
                        existente.estado = ESTADO_DESPEJADA
                        existente.marca_despejada = ahora
                        self._historial.append(existente)
            self._activas = {
                llave: alarma
                for llave, alarma in self._activas.items()
                if alarma.estado != ESTADO_DESPEJADA
            }
            if len(self._historial) > _MAX_HISTORIAL:
                del self._historial[:- _MAX_HISTORIAL]
        return disparando

    def reconocer(self, identificador):
        with self._cerradura:
            for alarma in self._activas.values():
                if alarma.id == identificador:
                    alarma.estado = ESTADO_RECONOCIDA
                    alarma.marca_reconocida = time.time()
                    return True
        return False
