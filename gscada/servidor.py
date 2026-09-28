"""
Servidor web de GSCADA — API REST + WebSocket + HMI estatica.

Endpoints
---------
GET  /api/plcs                        → estado de cada PLC configurado
GET  /api/tags                        → ultimo valor de cada tag, todos
                                        los PLCs
GET  /api/alarms                      → alarmas activas + historial reciente
POST /api/alarms/{alarm_id}/ack       → reconocer una alarma
GET  /api/trends/{tag}?from=&to=      → muestras del historiador para un tag
WS   /ws                              → tags+alarmas empujadas cada ~1 s
GET  /                                → static/index.html

Las rutas, las claves del JSON y los parametros de consulta se mantienen
en ingles porque son el contrato que consumen las HMI de ``gscada/static``.
"""

import asyncio
import logging
import threading
import time
from pathlib import Path

from fastapi import (
    APIRouter,
    FastAPI,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.staticfiles import StaticFiles

from gscada.alarmas import MotorAlarmas
from gscada.configuracion import ConfiguracionSistema
from gscada.consultor import ConsultorModbus
from gscada.historiador import Historiador

registrador = logging.getLogger("GSCADA.Servidor")

router = APIRouter()
_consultor_por_plc = {}
_motor_alarmas = None
_historiador = None
_configuracion = None
_hilo_alarmas = None
_detencion_alarmas = threading.Event()

INTERVALO_EVALUACION_ALARMAS = 1.0


def construir_componentes(configuracion, historiador=None):
    """Arma (sin arrancar) los componentes de runtime de una configuracion."""
    global _configuracion, _motor_alarmas, _historiador
    _configuracion = configuracion
    _motor_alarmas = MotorAlarmas(configuracion.alarmas)
    _historiador = historiador
    if _historiador is None:
        _historiador = Historiador()
    consultores = {}
    for plc in configuracion.plcs:
        consultores[plc.nombre] = ConsultorModbus(plc)
    _consultor_por_plc.clear()
    _consultor_por_plc.update(consultores)
    return {
        "consultores": consultores,
        "motor_alarmas": _motor_alarmas,
        "historiador": _historiador,
    }


def iniciar_todo():
    for consultor in _consultor_por_plc.values():
        consultor.iniciar()
    _iniciar_bucle_alarmas()


def detener_todo():
    _detener_bucle_alarmas()
    for consultor in _consultor_por_plc.values():
        consultor.detener()


def _iniciar_bucle_alarmas():
    """Arranca el bucle de fondo que evalua alarmas y guarda historial."""
    global _hilo_alarmas
    if _hilo_alarmas is not None and _hilo_alarmas.is_alive():
        return
    _detencion_alarmas.clear()
    _hilo_alarmas = threading.Thread(
        target=_bucle_alarmas,
        daemon=True,
        name="EvaluacionAlarmas",
    )
    _hilo_alarmas.start()


def _detener_bucle_alarmas():
    _detencion_alarmas.set()
    if _hilo_alarmas is not None:
        _hilo_alarmas.join(timeout=2)


def _bucle_alarmas():
    while not _detencion_alarmas.is_set():
        try:
            _evaluar_alarmas()
        except Exception:
            registrador.exception("Fallo la evaluacion de alarmas")
        _detencion_alarmas.wait(INTERVALO_EVALUACION_ALARMAS)


def _todos_los_valores():
    """Ultimo valor por tag (de todos los PLCs), indexado por nombre."""
    salida = {}
    for consultor in _consultor_por_plc.values():
        for nombre, muestra in consultor.obtener_ultimas().items():
            salida[nombre] = muestra.valor
    return salida


def _evaluar_alarmas():
    valores = _todos_los_valores()
    _motor_alarmas.evaluar(valores)
    if _historiador is not None:
        for nombre, valor in valores.items():
            if valor is not None:
                _historiador.registrar(nombre, valor)
    return [alarma.a_diccionario() for alarma in _motor_alarmas.activas]


def _estado_plcs():
    salida = []
    for nombre, consultor in _consultor_por_plc.items():
        tags = consultor.obtener_ultimas()
        salida.append({
            "name": nombre,
            "host": consultor.configuracion.host,
            "port": consultor.configuracion.puerto,
            "online": consultor.en_linea,
            "last_error": consultor.ultimo_error,
            "tag_count": len(tags),
            "stale_count": sum(
                1 for muestra in tags.values() if muestra.obsoleta
            ),
            "tags": [muestra.a_diccionario() for muestra in tags.values()],
        })
    return salida


@router.get("/plcs")
async def obtener_plcs():
    return {"plcs": _estado_plcs()}


@router.get("/tags")
async def obtener_tags():
    salida = {}
    for nombre, consultor in _consultor_por_plc.items():
        salida[nombre] = {
            clave: muestra.a_diccionario()
            for clave, muestra in consultor.obtener_ultimas().items()
        }
    return salida


@router.get("/alarms")
async def obtener_alarmas():
    if _motor_alarmas is None:
        return {"active": [], "history": []}
    return {
        "active": [
            alarma.a_diccionario() for alarma in _motor_alarmas.activas
        ],
        "history": [
            alarma.a_diccionario() for alarma in _motor_alarmas.historial[-50:]
        ],
    }


@router.post("/alarms/{alarm_id}/ack")
async def reconocer_alarma(alarm_id: str):
    if _motor_alarmas is None:
        raise HTTPException(
            status_code=503, detail="motor de alarmas no disponible"
        )
    reconocida = _motor_alarmas.reconocer(alarm_id)
    if not reconocida:
        raise HTTPException(
            status_code=404, detail="alarma no encontrada o no activa"
        )
    return {"ok": True, "alarm_id": alarm_id}


@router.get("/trends/{tag}")
async def obtener_tendencias(tag, from_=None, to=None):
    if _historiador is None:
        return {"tag": tag, "samples": []}
    desde = from_ if from_ is not None else 0.0
    hasta = to if to is not None else float("inf")
    muestras = _historiador.consultar(tag, desde=desde, hasta=hasta)
    return {
        "tag": tag,
        "samples": [
            {"timestamp": marca, "value": valor}
            for marca, valor in muestras
        ],
    }


async def atender_websocket(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            activas = []
            if _motor_alarmas is not None:
                activas = [
                    alarma.a_diccionario()
                    for alarma in _motor_alarmas.activas
                ]
            payload = {
                "plcs": _estado_plcs(),
                "alarms": activas,
            }
            await websocket.send_json(payload)
            await asyncio.sleep(1.0)
    except WebSocketDisconnect:
        pass


def crear_aplicacion(carpeta_estatica=None):
    aplicacion = FastAPI(title="GSCADA", version="1.0")
    aplicacion.include_router(router, prefix="/api")
    aplicacion.add_api_websocket_route("/ws", atender_websocket)

    static = Path(__file__).parent / "static"
    if carpeta_estatica is not None:
        static = Path(carpeta_estatica)
    if static.is_dir():
        aplicacion.mount(
            "/",
            StaticFiles(directory=str(static), html=True),
            name="static",
        )
    return aplicacion
