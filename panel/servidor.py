"""
Servidor web del panel — FastAPI + WebSocket para la HMI de GSIMPLC.

Corre en un hilo daemon para no bloquear nunca el ciclo de exploracion
del PLC. Pensado para entrar en un unico binario PyInstaller
(``gsimplc.bin``) sin mas recursos que ``panel/static/index.html``.
"""

import logging
import os
import threading

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from panel.api import (
    atender_websocket,
    establecer_contexto_plc,
    router as api_router,
)

registrador = logging.getLogger("PLC.Panel")


class ServidorPanel:
    """Panel web liviano para ver la I/O en vivo y subir programas."""

    def __init__(self, memoria, ciclo_exploracion, puerto=8080,
                 ruta_programa=""):
        self.memoria = memoria
        self.ciclo_exploracion = ciclo_exploracion
        self.puerto = puerto
        self.ruta_programa = ruta_programa
        self._hilo = None
        self._servidor = None

    def _crear_aplicacion(self):
        aplicacion = FastAPI(title="GSIMPLC Panel", version="1.0")
        aplicacion.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_methods=["*"],
            allow_headers=["*"],
        )
        establecer_contexto_plc(
            self.memoria,
            self.ciclo_exploracion,
            self.ruta_programa,
        )
        aplicacion.include_router(api_router, prefix="/api")
        aplicacion.add_api_websocket_route("/ws", atender_websocket)

        carpeta_estatica = os.path.join(os.path.dirname(__file__), "static")
        if os.path.isdir(carpeta_estatica):
            aplicacion.mount(
                "/",
                StaticFiles(directory=carpeta_estatica, html=True),
                name="static",
            )
        return aplicacion

    def iniciar(self):
        """Arranca el panel en un hilo daemon. No bloquea."""
        aplicacion = self._crear_aplicacion()
        config = uvicorn.Config(
            aplicacion,
            host="0.0.0.0",
            port=self.puerto,
            log_level="warning",
        )
        self._servidor = uvicorn.Server(config)
        self._hilo = threading.Thread(
            target=self._servidor.run,
            daemon=True,
            name="ServidorPanel",
        )
        self._hilo.start()
        registrador.info("Panel web en http://0.0.0.0:%d", self.puerto)

    def detener(self):
        if self._servidor is not None:
            self._servidor.should_exit = True
        if self._hilo is not None and self._hilo.is_alive():
            self._hilo.join(timeout=3)
