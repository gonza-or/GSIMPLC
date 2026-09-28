"""
Configuracion de GSCADA — modelos Pydantic + carga desde YAML.

Un sistema GSCADA se describe como uno o mas PLCs, cada uno con su lista
de tags y (opcionalmente) una o mas condiciones de alarma que se evaluan
en cada consulta.

Las claves del YAML (``name``, ``address``, ``poll_interval_ms``, ...)
son el contrato que ya usan los archivos de ``gscada/configs``; los
atributos en Python van en espanol y se enlazan con ``alias``.
"""

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

TipoTag = Literal[
    "coil",
    "discrete_input",
    "holding_register",
    "input_register",
]
Severidad = Literal["info", "low", "medium", "high", "critical"]


class ConfiguracionTag(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    nombre: str = Field(..., alias="name")
    direccion: int = Field(..., ge=0, alias="address")
    tipo: TipoTag = Field(..., alias="type")
    unidad: str = Field("", alias="unit")
    escala: float = Field(1.0, alias="scale")


class ConfiguracionPLC(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    nombre: str = Field(..., alias="name")
    host: str = Field(...)
    puerto: int = Field(502, alias="port")
    id_unidad: int = Field(1, alias="unit_id")
    intervalo_consulta_ms: int = Field(1000, alias="poll_interval_ms")
    tags: list[ConfiguracionTag] = Field(default_factory=list)


class ConfiguracionAlarma(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    etiqueta: str = Field(..., alias="tag")
    condicion: str = Field(..., alias="condition")   # "> 90", "< 10", ...
    severidad: Severidad = Field("low", alias="severity")
    mensaje: str = Field("", alias="message")


class ConfiguracionSistema(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    plcs: list[ConfiguracionPLC] = Field(default_factory=list)
    alarmas: list[ConfiguracionAlarma] = Field(
        default_factory=list, alias="alarms"
    )

    @classmethod
    def cargar(cls, ruta):
        archivo = Path(ruta)
        if not archivo.is_file():
            raise FileNotFoundError(
                f"Configuracion GSCADA no encontrada: {ruta}"
            )
        with archivo.open("r", encoding="utf-8") as manejador:
            crudo = yaml.safe_load(manejador) or {}
        return cls.model_validate(crudo)
