"""
Modelos fisicos del simulador de proceso.

Cada modelo lee de una porcion de la memoria del PLC (bobinas y
registros de retencion — lo que decide el programa Ladder) y escribe en
otra porcion (entradas discretas y registros de entrada — lo que el PLC
"percibe" del proceso). Los modelos avanzan al ritmo del simulador y
exponen un unico metodo :meth:`actualizar` que ejecuta un paso.
"""

from abc import ABC, abstractmethod


class ModeloFisico(ABC):
    """Clase base de todo elemento simulado del proceso."""

    def __init__(self, nombre):
        self.nombre = nombre

    @abstractmethod
    def actualizar(self, dt, memoria):
        """Avanza el modelo ``dt`` segundos leyendo y escribiendo memoria."""


class Tanque(ModeloFisico):
    """Tanque de liquido con una bomba de llenado y un drenaje constante.

    Entradas (se leen de ``memoria``)::

        bobina_llenado              Q:N        contactor de la bomba
    Salidas (se escriben en ``memoria``)::

        registro_entrada_nivel      IR:N       nivel en % de la capacidad
        entrada_alarma_alta         I:N        1 cuando el nivel >= 90 %
        entrada_alarma_baja         I:N        1 cuando el nivel <= 10 %
    """

    def __init__(self, nombre, capacidad_litros, caudal_llenado_lps,
                 caudal_drenaje_lps, registro_entrada_nivel,
                 entrada_alarma_alta, entrada_alarma_baja, bobina_llenado):
        ModeloFisico.__init__(self, nombre)
        self.capacidad_litros = capacidad_litros
        self.caudal_llenado_lps = caudal_llenado_lps
        self.caudal_drenaje_lps = caudal_drenaje_lps
        self.registro_entrada_nivel = registro_entrada_nivel
        self.entrada_alarma_alta = entrada_alarma_alta
        self.entrada_alarma_baja = entrada_alarma_baja
        self.bobina_llenado = bobina_llenado
        # Arranca a medio llenar: se ve reaccionar de inmediato.
        self._nivel_litros = capacidad_litros * 0.5

    def actualizar(self, dt, memoria):
        bomba_encendida = bool(memoria.obtener_bobina(self.bobina_llenado))
        caudal_neto = 0.0
        if bomba_encendida:
            caudal_neto = self.caudal_llenado_lps
        caudal_neto = caudal_neto - self.caudal_drenaje_lps
        self._nivel_litros = self._nivel_litros + caudal_neto * dt
        if self._nivel_litros < 0.0:
            self._nivel_litros = 0.0
        if self._nivel_litros > self.capacidad_litros:
            self._nivel_litros = self.capacidad_litros

        porcentaje = (self._nivel_litros / self.capacidad_litros) * 100.0
        memoria.establecer_entrada(
            self.registro_entrada_nivel, int(porcentaje)
        )
        memoria.establecer_entrada_discreta(
            self.entrada_alarma_alta, porcentaje >= 90.0
        )
        memoria.establecer_entrada_discreta(
            self.entrada_alarma_baja, porcentaje <= 10.0
        )


class Motor(ModeloFisico):
    """Motor de induccion con arranque y frenado graduales.

    Entradas (se leen de ``memoria``)::

        bobina_marcha               Q:N        contactor marcha/paro
    Salidas (se escriben en ``memoria``)::

        registro_entrada_rpm        IR:N       velocidad actual (RPM)
        entrada_marcha              I:N        1 al superar el 5 % de
                                               rpm_maximas
    """

    def __init__(self, nombre, rpm_maximas, aceleracion_rpm_s,
                 bobina_marcha, registro_entrada_rpm, entrada_marcha):
        ModeloFisico.__init__(self, nombre)
        self.rpm_maximas = rpm_maximas
        self.aceleracion_rpm_s = aceleracion_rpm_s
        self.bobina_marcha = bobina_marcha
        self.registro_entrada_rpm = registro_entrada_rpm
        self.entrada_marcha = entrada_marcha
        self._rpm = 0.0

    def actualizar(self, dt, memoria):
        objetivo = 0.0
        if bool(memoria.obtener_bobina(self.bobina_marcha)):
            objetivo = self.rpm_maximas
        variacion = self.aceleracion_rpm_s * dt
        if self._rpm < objetivo:
            self._rpm = min(objetivo, self._rpm + variacion)
        elif self._rpm > objetivo:
            self._rpm = max(objetivo, self._rpm - variacion)

        memoria.establecer_entrada(self.registro_entrada_rpm, int(self._rpm))
        memoria.establecer_entrada_discreta(
            self.entrada_marcha, self._rpm >= self.rpm_maximas * 0.05
        )


class Valvula(ModeloFisico):
    """Valvula proporcional que se desplaza linealmente a una consigna.

    Entradas (se leen de ``memoria``)::

        registro_consigna           HR:N       posicion objetivo, 0..100
    Salidas (se escriben en ``memoria``)::

        registro_entrada_posicion   IR:N       posicion actual, 0..100
    """

    def __init__(self, nombre, tiempo_recorrido_s, registro_consigna,
                 registro_entrada_posicion):
        ModeloFisico.__init__(self, nombre)
        self.tiempo_recorrido_s = tiempo_recorrido_s
        self.registro_consigna = registro_consigna
        self.registro_entrada_posicion = registro_entrada_posicion
        self._posicion = 0.0

    def actualizar(self, dt, memoria):
        consigna = float(memoria.obtener_retencion(self.registro_consigna))
        consigna = max(0.0, min(100.0, consigna))
        # El recorrido completo insume ``tiempo_recorrido_s`` segundos.
        paso_maximo = (100.0 * dt) / self.tiempo_recorrido_s
        if self._posicion < consigna:
            self._posicion = min(consigna, self._posicion + paso_maximo)
        elif self._posicion > consigna:
            self._posicion = max(consigna, self._posicion - paso_maximo)
        memoria.establecer_entrada(
            self.registro_entrada_posicion, int(self._posicion)
        )


class SensorTemperatura(ModeloFisico):
    """Temperatura con inercia termica.

    Con el calentador encendido la temperatura sube a
    ``tasa_calentamiento`` grados por segundo; apagado, tiende a
    ``temperatura_ambiente`` a ``tasa_enfriamiento``.

    Entradas (se leen de ``memoria``)::

        bobina_calentador           Q:N        contactor del calentador
    Salidas (se escriben en ``memoria``)::

        registro_entrada_temperatura IR:N      temperatura en grados
    """

    def __init__(self, nombre, temperatura_ambiente, tasa_calentamiento,
                 tasa_enfriamiento, bobina_calentador,
                 registro_entrada_temperatura):
        ModeloFisico.__init__(self, nombre)
        self.temperatura_ambiente = temperatura_ambiente
        self.tasa_calentamiento = tasa_calentamiento
        self.tasa_enfriamiento = tasa_enfriamiento
        self.bobina_calentador = bobina_calentador
        self.registro_entrada_temperatura = registro_entrada_temperatura
        self._temperatura = temperatura_ambiente

    def actualizar(self, dt, memoria):
        if bool(memoria.obtener_bobina(self.bobina_calentador)):
            self._temperatura = (
                self._temperatura + self.tasa_calentamiento * dt
            )
        else:
            diferencia = self.temperatura_ambiente - self._temperatura
            self._temperatura = (
                self._temperatura + diferencia * self.tasa_enfriamiento * dt
            )
        memoria.establecer_entrada(
            self.registro_entrada_temperatura, int(self._temperatura)
        )


class Cinta(ModeloFisico):
    """Cinta transportadora que genera un pulso de "objeto detectado".

    Un objeto virtual recorre la cinta a ``velocidad_mps`` y acciona un
    sensor al final de un tramo de longitud fija. Los objetos solo se
    mueven (y aparecen) mientras la bobina del motor esta encendida.

    Entradas (se leen de ``memoria``)::

        bobina_motor                Q:N        motor de la cinta
    Salidas (se escriben en ``memoria``)::

        entrada_objeto_detectado    I:N        pulso al pasar un objeto
    """

    def __init__(self, nombre, velocidad_mps, longitud_tramo_m,
                 bobina_motor, entrada_objeto_detectado):
        ModeloFisico.__init__(self, nombre)
        self.velocidad_mps = velocidad_mps
        self.longitud_tramo_m = longitud_tramo_m
        self.bobina_motor = bobina_motor
        self.entrada_objeto_detectado = entrada_objeto_detectado
        # Distancia que ya recorrio el proximo objeto virtual.
        self._distancia = 0.0

    def actualizar(self, dt, memoria):
        if not bool(memoria.obtener_bobina(self.bobina_motor)):
            memoria.establecer_entrada_discreta(
                self.entrada_objeto_detectado, False
            )
            return
        self._distancia = self._distancia + self.velocidad_mps * dt
        if self._distancia >= self.longitud_tramo_m:
            self._distancia = self._distancia - self.longitud_tramo_m
            memoria.establecer_entrada_discreta(
                self.entrada_objeto_detectado, True
            )
        else:
            memoria.establecer_entrada_discreta(
                self.entrada_objeto_detectado, False
            )
