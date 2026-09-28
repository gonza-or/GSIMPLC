from core.memoria import MemoriaPLC
from core.scan_cycle import CicloExploracion
from panel.servidor import ServidorPanel


def test_panel_expone_websocket_en_ruta_publica():
    memoria = MemoriaPLC()
    ciclo = CicloExploracion(memoria)
    aplicacion = ServidorPanel(memoria, ciclo)._crear_aplicacion()
    rutas = {getattr(ruta, "path", "") for ruta in aplicacion.routes}

    assert "/ws" in rutas
    assert "/api/ws" not in rutas
