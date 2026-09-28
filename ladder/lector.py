import re
from pathlib import Path

from ladder.escalon import Escalon
from ladder.instrucciones import (
    BobinaDesenclavar,
    BobinaEnclavar,
    BobinaSalida,
    ContactoNormalAbierto,
    ContactoNormalCerrado,
    ContadorAscendente,
    ContadorDescendente,
    Distinto,
    Igual,
    Instruccion,
    Mayor,
    Menor,
    Mover,
    Restar,
    Sumar,
    TemporizadorConexion,
    TemporizadorDesconexion,
)
from ladder.programa import Programa

_ENCABEZADO_ESCALON = re.compile(
    r'^\s*(?:RUNG|ESCALON)\s+(\d+)(?:\s+"([^"]*)")?\s*$',
    re.IGNORECASE,
)

_FIN_ESCALON = re.compile(r"^\s*(?:END_RUNG|FIN_ESCALON)\s*$", re.IGNORECASE)
_RAMA = re.compile(r"^\s*(?:BRANCH|RAMA)\s*$", re.IGNORECASE)
_FIN_RAMA = re.compile(r"^\s*(?:END_BRANCH|FIN_RAMA)\s*$", re.IGNORECASE)


class ErrorLadder(Exception):

    def __init__(self, numero_linea, mensaje):
        self.numero_linea = numero_linea
        self.mensaje = mensaje
        super().__init__(f"Linea {numero_linea}: {mensaje}")


class LectorLadder:

    def __init__(self):
        self._lineas = []
        self._total = 0
        self._indice = 0

    def leer(self, ruta) -> Programa:
        camino = Path(ruta)
        if not camino.is_file():
            raise ErrorLadder(0, f"No se encontro el archivo: {ruta}")

        self._lineas = _lineas_utiles(
            camino.read_text(encoding="utf-8").splitlines()
        )
        self._total = len(self._lineas)
        self._indice = 0

        escalones = []
        while self._indice < self._total:
            numero, texto = self._lineas[self._indice]
            self._indice = self._indice + 1
            encabezado = _ENCABEZADO_ESCALON.match(texto)
            if not encabezado:
                raise ErrorLadder(
                    numero, f"Sentencia inesperada: {texto!r}"
                )
            nombre = encabezado.group(2) or ""
            escalones.append(self._leer_escalon(nombre, numero))

        return Programa(escalones)

    def _leer_escalon(self, nombre, numero_inicial) -> "Escalon":
        principales = []
        ramas = []
        rama_actual = None

        while self._indice < self._total:
            numero, texto = self._lineas[self._indice]
            self._indice = self._indice + 1

            if _FIN_ESCALON.match(texto):
                return Escalon(nombre, principales, ramas)

            if _RAMA.match(texto):
                if rama_actual is not None:
                    raise ErrorLadder(
                        numero, "No se admiten ramas anidadas"
                    )
                rama_actual = []
                continue

            if _FIN_RAMA.match(texto):
                if rama_actual is None:
                    raise ErrorLadder(
                        numero, "FIN_RAMA sin RAMA"
                    )
                ramas.append(rama_actual)
                rama_actual = None
                continue

            instruccion = self._leer_instruccion(texto, numero)
            if rama_actual is not None:
                rama_actual.append(instruccion)
            else:
                principales.append(instruccion)

        raise ErrorLadder(
            numero_inicial, "No se encontro FIN_ESCALON antes del final"
        )

    def _leer_instruccion(self, texto, numero) -> Instruccion:
        partes = texto.split()
        codigo = partes[0].upper()
        argumentos = partes[1:]

        if codigo == "XIC":
            _verificar_aridad(argumentos, 1, numero, "XIC")
            return ContactoNormalAbierto(argumentos[0])
        if codigo == "XIO":
            _verificar_aridad(argumentos, 1, numero, "XIO")
            return ContactoNormalCerrado(argumentos[0])
        if codigo == "OTE":
            _verificar_aridad(argumentos, 1, numero, "OTE")
            return BobinaSalida(argumentos[0])
        if codigo == "OTL":
            _verificar_aridad(argumentos, 1, numero, "OTL")
            return BobinaEnclavar(argumentos[0])
        if codigo == "OTU":
            _verificar_aridad(argumentos, 1, numero, "OTU")
            return BobinaDesenclavar(argumentos[0])

        if codigo == "TON":
            _verificar_aridad(argumentos, 2, numero, "TON T:N PRE=ms")
            return TemporizadorConexion(
                argumentos[0], _leer_preseleccion(argumentos, "PRE", numero)
            )
        if codigo == "TOF":
            _verificar_aridad(argumentos, 2, numero, "TOF T:N PRE=ms")
            return TemporizadorDesconexion(
                argumentos[0], _leer_preseleccion(argumentos, "PRE", numero)
            )
        if codigo == "CTU":
            _verificar_aridad(argumentos, 2, numero, "CTU C:N PRE=valor")
            return ContadorAscendente(
                argumentos[0], _leer_preseleccion(argumentos, "PRE", numero)
            )
        if codigo == "CTD":
            _verificar_aridad(argumentos, 2, numero, "CTD C:N PRE=valor")
            return ContadorDescendente(
                argumentos[0], _leer_preseleccion(argumentos, "PRE", numero)
            )

        if codigo == "MOV":
            _verificar_aridad(argumentos, 2, numero, "MOV ORI DST")
            return Mover(argumentos[0], argumentos[1])
        if codigo == "ADD":
            _verificar_aridad(argumentos, 3, numero, "ADD A B DST")
            return Sumar(argumentos[0], argumentos[1], argumentos[2])
        if codigo == "SUB":
            _verificar_aridad(argumentos, 3, numero, "SUB A B DST")
            return Restar(argumentos[0], argumentos[1], argumentos[2])

        if codigo == "EQU":
            _verificar_aridad(argumentos, 2, numero, "EQU A B")
            return Igual(argumentos[0], argumentos[1])
        if codigo == "NEQ":
            _verificar_aridad(argumentos, 2, numero, "NEQ A B")
            return Distinto(argumentos[0], argumentos[1])
        if codigo == "GRT":
            _verificar_aridad(argumentos, 2, numero, "GRT A B")
            return Mayor(argumentos[0], argumentos[1])
        if codigo == "LES":
            _verificar_aridad(argumentos, 2, numero, "LES A B")
            return Menor(argumentos[0], argumentos[1])

        raise ErrorLadder(numero, f"Instruccion desconocida: {codigo}")


def _lineas_utiles(lineas):
    utiles = []
    for indice, linea_cruda in enumerate(lineas, start=1):
        texto = linea_cruda.split("#", 1)[0].strip()
        if not texto:
            continue
        utiles.append((indice, texto))
    return utiles


def _verificar_aridad(argumentos, esperados, numero, firma):
    if len(argumentos) != esperados:
        raise ErrorLadder(
            numero, f"{firma} requiere {esperados} argumentos"
        )


def _leer_preseleccion(argumentos, nombre, numero):
    prefijo = f"{nombre}="
    for argumento in argumentos:
        if argumento.upper().startswith(prefijo):
            try:
                return int(argumento[len(prefijo):])
            except ValueError as error:
                raise ErrorLadder(
                    numero, f"Valor invalido para {nombre}= ({argumento!r})"
                ) from error
    raise ErrorLadder(numero, f"Falta el argumento obligatorio {nombre}=")
