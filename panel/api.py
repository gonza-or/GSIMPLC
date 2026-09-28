"""
API del panel — endpoints REST y WebSocket que expone el panel GSIMPLC.

La superficie HTTP es deliberadamente chica y usa nombres de campo en
ingles (``addr``, ``value``, ``path``) porque es el contrato que ya
consumen las HMI de ``panel/static``; la traduccion desde la API en
espanol de ``MemoriaPLC`` ocurre en :func:`serializar_estado` y en los
modelos Pydantic de mas abajo.
"""

import asyncio
import logging
import os
import time

from fastapi import (
    APIRouter,
    File,
    HTTPException,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from pydantic import BaseModel, Field

registrador = logging.getLogger("PLC.Panel.API")

router = APIRouter()

# Los inyecta :func:`establecer_contexto_plc` cuando arranca el servidor.
_memoria = None
_ciclo_exploracion = None
_ruta_programa = ""
_tiempo_inicio = 0.0


def establecer_contexto_plc(memoria, ciclo_exploracion, ruta_programa=""):
    """Lo llama el servidor una sola vez, antes de empezar a servir."""
    global _memoria, _ciclo_exploracion, _ruta_programa, _tiempo_inicio
    _memoria = memoria
    _ciclo_exploracion = ciclo_exploracion
    _ruta_programa = ruta_programa
    _tiempo_inicio = time.monotonic()


class EntradaDiscreta(BaseModel):
    addr: int = Field(..., ge=0, description="Direccion de I/O discreta")
    value: bool


class EntradaRetencion(BaseModel):
    addr: int = Field(..., ge=0, description="Direccion de registro")
    value: int = Field(..., ge=0, le=0xFFFF)


class SolicitudCargaPrograma(BaseModel):
    path: str = Field(..., description="Ruta absoluta a un .lad del servidor")


def serializar_estado():
    crudo = _memoria.obtener_estado_completo()

    temporizadores = {}
    for llave, temporizador in crudo.get("temporizadores", {}).items():
        temporizadores[str(llave)] = temporizador.a_diccionario()

    contadores = {}
    for llave, contador in crudo.get("contadores", {}).items():
        contadores[str(llave)] = contador.a_diccionario()

    return {
        "inputs": list(crudo.get("entradas_discretas", [])),
        "coils": list(crudo.get("bobinas", [])),
        "holding": list(crudo.get("registros_retencion", [])),
        "input_reg": list(crudo.get("registros_entrada", [])),
        "timers": temporizadores,
        "counters": contadores,
    }


def serializar_info():
    """Arma el diccionario de info que usan /api/info y el payload del WS."""
    if _tiempo_inicio:
        tiempo_activo = time.monotonic() - _tiempo_inicio
    else:
        tiempo_activo = 0.0

    if _ciclo_exploracion is not None:
        ciclos = _ciclo_exploracion.conteo_ciclos
        ciclo_ms = _ciclo_exploracion.ciclo_ms
    else:
        ciclos = 0
        ciclo_ms = 0

    ciclos_por_segundo = 0.0
    if tiempo_activo > 0:
        ciclos_por_segundo = round(ciclos / tiempo_activo, 1)
    programa = "none"
    if _ruta_programa:
        programa = os.path.basename(_ruta_programa)

    return {
        "program": programa,
        "cycle_ms": ciclo_ms,
        "cycles_total": ciclos,
        "uptime_seconds": round(tiempo_activo, 1),
        "cycles_per_second": ciclos_por_segundo,
    }


@router.get("/state")
async def obtener_estado():
    if _memoria is None:
        raise HTTPException(status_code=503, detail="PLC no inicializado")
    return serializar_estado()


@router.get("/info")
async def obtener_info():
    return serializar_info()


@router.post("/io/discrete")
async def escribir_entrada_discreta(entrada: EntradaDiscreta):
    if _memoria is None:
        raise HTTPException(status_code=503, detail="PLC no inicializado")
    _memoria.establecer_entrada_discreta(entrada.addr, entrada.value)
    return {"ok": True, "addr": entrada.addr, "value": entrada.value}


@router.post("/io/holding")
async def escribir_retencion(entrada: EntradaRetencion):
    if _memoria is None:
        raise HTTPException(status_code=503, detail="PLC no inicializado")
    _memoria.establecer_retencion(entrada.addr, entrada.value)
    return {"ok": True, "addr": entrada.addr, "value": entrada.value}


def _cargar_programa_desde_ruta(ruta):
    """Lee un .lad e instala su logica en el ciclo de exploracion."""
    if _memoria is None or _ciclo_exploracion is None:
        raise HTTPException(status_code=503, detail="PLC no inicializado")
    if not ruta:
        raise HTTPException(status_code=422, detail="path es obligatorio")
    if not os.path.isfile(ruta):
        raise HTTPException(
            status_code=404, detail=f"archivo no encontrado: {ruta}"
        )
    try:
        from ladder.lector import LectorLadder
        programa = LectorLadder().leer(ruta)
    except Exception as error:
        raise HTTPException(
            status_code=400, detail=f"error de parseo: {error}"
        ) from error

    global _ruta_programa
    _ruta_programa = ruta
    _ciclo_exploracion.establecer_programa(programa)
    registrador.info(
        "Programa cargado: %s (%d escalones)", ruta, len(programa.escalones)
    )
    return {
        "ok": True,
        "program": os.path.basename(ruta),
        "rungs": len(programa.escalones),
    }


def _cargar_programa_desde_bytes(contenido, nombre_archivo):
    """Guarda el archivo subido y lo carga desde la ruta guardada."""
    carpeta = "/tmp/gsimplc_uploads"
    os.makedirs(carpeta, exist_ok=True)
    nombre_seguro = os.path.basename(nombre_archivo) or "program.lad"
    ruta_guardada = os.path.join(carpeta, nombre_seguro)
    with open(ruta_guardada, "wb") as archivo:
        archivo.write(contenido)
    return _cargar_programa_desde_ruta(ruta_guardada)


@router.post("/program/load")
async def cargar_programa(solicitud: SolicitudCargaPrograma):
    """Carga un .lad referenciado por el ``path`` absoluto del servidor."""
    return _cargar_programa_desde_ruta(solicitud.path)


@router.post("/program/upload")
async def subir_programa(file: UploadFile = File(...)):
    """Recibe un .lad desde el navegador y lo instala."""
    contenido = await file.read()
    return _cargar_programa_desde_bytes(
        contenido, file.filename or "program.lad"
    )


async def atender_websocket(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            if _memoria is not None:
                payload = serializar_estado()
                payload["info"] = serializar_info()
                await websocket.send_json(payload)
            await asyncio.sleep(0.2)
    except WebSocketDisconnect:
        pass
