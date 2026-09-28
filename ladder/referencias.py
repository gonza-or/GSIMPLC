from abc import ABC, abstractmethod

AREAS_PALABRA = ("HR", "IR")


class Referencia(ABC):

    def __init__(self, expresion):
        self.expresion = expresion

    @abstractmethod
    def leer(self, memoria) -> int:
        pass

    def escribir(self, memoria, valor) -> None:
        raise ValueError(f"Direccion invalida: {self.expresion!r}")

    @staticmethod
    def interpretar(expresion):
        texto = expresion.strip()

        entero = _interpretar_entero(texto)
        if entero is not None:
            return ReferenciaLiteral(texto, entero)

        mayusculas = texto.upper()
        if mayusculas.startswith("T:"):
            return _crear_referencia_temporizador(texto)
        if mayusculas.startswith("C:"):
            return _crear_referencia_contador(texto)

        prefijo, indice = _separar_prefijo(texto)
        if prefijo in AREAS_PALABRA:
            return ReferenciaPalabra(texto, prefijo, indice)
        return ReferenciaBit(texto, prefijo, indice)

    @staticmethod
    def interpretar_destino(expresion):
        registro = Referencia.interpretar(expresion)
        if isinstance(registro, ReferenciaLiteral):
            raise ValueError(f"Direccion invalida: {expresion!r}")
        return registro

    @staticmethod
    def indice_de(expresion):
        _, indice = _separar_prefijo(expresion.strip())
        return indice

    def es_palabra(self) -> bool:
        return False


class ReferenciaLiteral(Referencia):

    def __init__(self, expresion, valor):
        Referencia.__init__(self, expresion)
        self.valor = valor

    def leer(self, memoria) -> int:
        return self.valor


class ReferenciaBit(Referencia):

    def __init__(self, expresion, prefijo, indice):
        Referencia.__init__(self, expresion)
        self.prefijo = prefijo
        self.indice = indice

    def leer(self, memoria) -> int:
        if self.prefijo == "I":
            return memoria.obtener_entrada_discreta(self.indice)
        if self.prefijo == "Q":
            return memoria.obtener_bobina(self.indice)
        raise ValueError(f"Area de bit desconocida: {self.prefijo}")

    def escribir(self, memoria, valor) -> None:
        if self.prefijo == "Q":
            memoria.establecer_bobina(self.indice, valor)
        elif self.prefijo == "I":
            memoria.establecer_entrada_discreta(self.indice, valor)
        else:
            raise ValueError(
                f"No se puede escribir en el area de bit: {self.prefijo}"
            )


class ReferenciaPalabra(Referencia):

    def __init__(self, expresion, prefijo, indice):
        Referencia.__init__(self, expresion)
        self.prefijo = prefijo
        self.indice = indice

    def es_palabra(self) -> bool:
        return True

    def leer(self, memoria) -> int:
        if self.prefijo == "HR":
            return memoria.obtener_retencion(self.indice)
        if self.prefijo == "IR":
            return memoria.obtener_entrada(self.indice)
        raise ValueError(f"Area de palabra desconocida: {self.prefijo}")

    def escribir(self, memoria, valor) -> None:
        if self.prefijo == "HR":
            memoria.establecer_retencion(self.indice, valor)
        elif self.prefijo == "IR":
            memoria.establecer_entrada(self.indice, valor)
        else:
            raise ValueError(
                f"No se puede escribir en el area de palabra: {self.prefijo}"
            )


class ReferenciaTemporizador(Referencia):

    def __init__(self, expresion, indice, campo):
        Referencia.__init__(self, expresion)
        self.indice = indice
        self.campo = campo

    def leer(self, memoria) -> int:
        temporizador = memoria.obtener_temporizador(self.indice)
        if self.campo == "PRE":
            return temporizador.preseleccion
        if self.campo == "ACC":
            return temporizador.acumulado
        if self.campo == "EN":
            return temporizador.habilitado
        if self.campo == "DN":
            return temporizador.completado
        if self.campo == "TT":
            return temporizador.temporizando
        return 0

    def escribir(self, memoria, valor) -> None:
        raise ValueError(
            f"No se puede escribir en el campo de temporizador: "
            f"{self.expresion!r}"
        )


class ReferenciaContador(Referencia):

    def __init__(self, expresion, indice, campo):
        Referencia.__init__(self, expresion)
        self.indice = indice
        self.campo = campo

    def leer(self, memoria) -> int:
        contador = memoria.obtener_contador(self.indice)
        if self.campo == "PRE":
            return contador.preseleccion
        if self.campo == "ACC":
            return contador.acumulado
        if self.campo == "DN":
            return contador.completado
        if self.campo == "CU":
            return contador.contando_arriba
        if self.campo == "CD":
            return contador.contando_abajo
        return 0

    def escribir(self, memoria, valor) -> None:
        raise ValueError(
            f"No se puede escribir en el campo de contador: "
            f"{self.expresion!r}"
        )


def _interpretar_entero(texto):
    try:
        return int(texto)
    except ValueError:
        return None


def _separar_prefijo(texto):
    if ":" not in texto:
        raise ValueError(f"Direccion invalida: {texto!r}")
    prefijo, indice = texto.split(":", 1)
    return prefijo.upper(), int(indice)


def _separar_indice_y_campo(texto, campo_por_defecto):
    resto = texto[2:]
    if "." in resto:
        indice, campo = resto.split(".", 1)
    else:
        indice, campo = resto, campo_por_defecto
    return int(indice), campo.upper()


def _crear_referencia_temporizador(texto):
    indice, campo = _separar_indice_y_campo(texto, "DN")
    return ReferenciaTemporizador(texto, indice, campo)


def _crear_referencia_contador(texto):
    indice, campo = _separar_indice_y_campo(texto, "DN")
    return ReferenciaContador(texto, indice, campo)
