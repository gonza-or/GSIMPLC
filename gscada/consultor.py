"""
Consultor Modbus — lee periodicamente todos los tags de un PLC.

Agrupa las lecturas por area de memoria para minimizar la cantidad de
transacciones Modbus. Los tags cuya consulta falla quedan marcados como
obsoletos, para que la HMI pueda mostrar "sin comunicacion".
"""

import logging
import threading
import time

from gscada.configuracion import ConfiguracionPLC

registrador = logging.getLogger("GSCADA.Consultor")


class MuestraTag:
    """Ultimo valor conocido de un tag."""

    def __init__(self, nombre, valor, marca_tiempo, obsoleta=False):
        self.nombre = nombre
        self.valor = valor
        self.marca_tiempo = marca_tiempo
        self.obsoleta = obsoleta

    def copia(self):
        return MuestraTag(
            self.nombre, self.valor, self.marca_tiempo, self.obsoleta
        )

    def a_diccionario(self):
        # Claves del contrato HTTP que consume la HMI.
        return {
            "name": self.nombre,
            "value": self.valor,
            "timestamp": self.marca_tiempo,
            "is_stale": self.obsoleta,
        }


class ConsultorModbus:
    """Consulta los tags de un PLC cada ``intervalo_consulta_ms``."""

    def __init__(self, configuracion: ConfiguracionPLC):
        self.configuracion = configuracion
        self._cliente = None
        self._ultimas = {}
        self._cerradura = threading.Lock()
        self._evento_detencion = threading.Event()
        self._hilo = None
        self._ultimo_error = ""
        # Arranca en obsoleto: el llamador ve un estado conocido.
        self._sembrar_obsoletas()

    def _sembrar_obsoletas(self):
        ahora = time.time()
        with self._cerradura:
            for tag in self.configuracion.tags:
                self._ultimas[tag.nombre] = MuestraTag(
                    tag.nombre, None, ahora, obsoleta=True
                )

    def iniciar(self):
        if self._hilo is not None and self._hilo.is_alive():
            return
        self._evento_detencion.clear()
        self._sembrar_obsoletas()
        self._hilo = threading.Thread(
            target=self._correr,
            daemon=True,
            name=f"Consultor[{self.configuracion.nombre}]",
        )
        self._hilo.start()
        registrador.info(
            "Consultor iniciado: %s @ %s:%d (%d tags, cada %d ms)",
            self.configuracion.nombre,
            self.configuracion.host,
            self.configuracion.puerto,
            len(self.configuracion.tags),
            self.configuracion.intervalo_consulta_ms,
        )

    def detener(self):
        self._evento_detencion.set()
        if self._hilo is not None:
            self._hilo.join(timeout=2)

    def obtener_ultimas(self):
        with self._cerradura:
            return {
                nombre: muestra for nombre, muestra in self._ultimas.items()
            }

    @property
    def en_linea(self):
        """Verdadero si la ultima consulta salio bien."""
        with self._cerradura:
            for muestra in self._ultimas.values():
                if not muestra.obsoleta:
                    return True
        return False

    @property
    def ultimo_error(self):
        return self._ultimo_error

    def _conectar(self):
        if self._cliente is not None:
            return
        from pymodbus.client import ModbusTcpClient
        self._cliente = ModbusTcpClient(
            host=self.configuracion.host,
            port=self.configuracion.puerto,
            timeout=1.0,
        )

    def _agrupar_por_area(self):
        grupos = {
            "coil": [],
            "discrete_input": [],
            "holding_register": [],
            "input_register": [],
        }
        for tag in self.configuracion.tags:
            if tag.tipo in grupos:
                grupos[tag.tipo].append(tag)
        return grupos

    def _leer_area(self, area, tags):
        if not tags:
            return {}
        try:
            if area == "coil":
                respuesta = self._cliente.read_coils(
                    tags[0].direccion,
                    count=len(tags),
                    slave=self.configuracion.id_unidad,
                )
                if respuesta.isError():
                    raise IOError(respuesta)
                valores = respuesta.bits[: len(tags)]
            elif area == "discrete_input":
                respuesta = self._cliente.read_discrete_inputs(
                    tags[0].direccion,
                    count=len(tags),
                    slave=self.configuracion.id_unidad,
                )
                if respuesta.isError():
                    raise IOError(respuesta)
                valores = respuesta.bits[: len(tags)]
            elif area == "holding_register":
                respuesta = self._cliente.read_holding_registers(
                    tags[0].direccion,
                    count=len(tags),
                    slave=self.configuracion.id_unidad,
                )
                if respuesta.isError():
                    raise IOError(respuesta)
                valores = respuesta.registers[: len(tags)]
            elif area == "input_register":
                respuesta = self._cliente.read_input_registers(
                    tags[0].direccion,
                    count=len(tags),
                    slave=self.configuracion.id_unidad,
                )
                if respuesta.isError():
                    raise IOError(respuesta)
                valores = respuesta.registers[: len(tags)]
            else:
                valores = []
            return {
                tags[i].nombre: valores[i] for i in range(len(tags))
            }
        except Exception as error:
            raise IOError(f"fallo de lectura en {area}: {error}") from error

    def _consultar_una_vez(self):
        try:
            self._conectar()
            if not self._cliente.connect():
                raise IOError("connect() devolvio False")
            grupos = self._agrupar_por_area()
            frescas = {}
            for area, tags in grupos.items():
                lectura = self._leer_area(area, tags)
                for tag in tags:
                    crudo = lectura.get(tag.nombre)
                    if crudo is None:
                        frescas[tag.nombre] = MuestraTag(
                            tag.nombre, None,
                            time.time(), obsoleta=True,
                        )
                    else:
                        # Aplica la escala a los valores numericos.
                        valor = crudo
                        escala = tag.escala
                        if isinstance(crudo, (int, float)) and escala != 1.0:
                            valor = crudo * escala
                        frescas[tag.nombre] = MuestraTag(
                            tag.nombre, valor,
                            time.time(), obsoleta=False,
                        )
            with self._cerradura:
                self._ultimas = frescas
            self._ultimo_error = ""
            return True
        except Exception as error:
            self._ultimo_error = str(error)
            # Marca todos los tags como obsoletos, conservando el valor.
            ahora = time.time()
            with self._cerradura:
                for tag in self.configuracion.tags:
                    anterior = self._ultimas.get(tag.nombre)
                    valor = None
                    if anterior is not None:
                        valor = anterior.valor
                    self._ultimas[tag.nombre] = MuestraTag(
                        tag.nombre, valor, ahora, obsoleta=True
                    )
            return False

    def _correr(self):
        intervalo = self.configuracion.intervalo_consulta_ms / 1000.0
        while not self._evento_detencion.is_set():
            self._consultar_una_vez()
            self._evento_detencion.wait(intervalo)
