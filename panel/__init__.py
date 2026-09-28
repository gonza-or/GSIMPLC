"""Panel web — servidor FastAPI, API REST + WebSocket y HMI estatica."""

from panel.api import (
    establecer_contexto_plc,
    serializar_estado,
    serializar_info,
)
from panel.servidor import ServidorPanel

__all__ = [
    "ServidorPanel",
    "establecer_contexto_plc",
    "serializar_estado",
    "serializar_info",
]

