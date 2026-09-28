"""
Historiador — almacen SQLite de solo agregado para el historial de tags.

Cada fila es ``(timestamp, tag, value)``. Las filas viejas se podan al
insertar cuando la tabla supera ``antiguedad_maxima_s`` de datos.

Las columnas de la tabla se mantienen en ingles porque son el esquema ya
existente de ``historian.db``.
"""

import logging
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path

registrador = logging.getLogger("GSCADA.Historiador")


class Historiador:
    """Historiador SQLite seguro para uso multihilo."""

    def __init__(self, ruta_bd="historian.db", antiguedad_maxima_s=86400.0):
        self.ruta_bd = Path(ruta_bd)
        self.antiguedad_maxima_s = antiguedad_maxima_s
        self._cerradura = threading.Lock()
        self._ultima_depuracion = 0.0
        self._iniciar_esquema()

    def _conectar(self):
        conexion = sqlite3.connect(
            str(self.ruta_bd), timeout=5.0, isolation_level=None
        )
        conexion.execute("PRAGMA journal_mode=WAL")
        return conexion

    def _iniciar_esquema(self):
        with self._conectar() as conexion:
            conexion.execute(
                """
                CREATE TABLE IF NOT EXISTS samples (
                    timestamp REAL NOT NULL,
                    tag TEXT NOT NULL,
                    value REAL
                )
                """
            )
            conexion.execute(
                "CREATE INDEX IF NOT EXISTS idx_tag_ts "
                "ON samples(tag, timestamp)"
            )

    @contextmanager
    def _cursor(self):
        with self._cerradura:
            conexion = self._conectar()
            try:
                yield conexion.cursor()
            finally:
                conexion.close()

    def registrar(self, tag, valor, marca_tiempo=None):
        if valor is None:
            return
        try:
            valor_numerico = float(valor)
        except (TypeError, ValueError):
            return
        marca = marca_tiempo
        if marca is None:
            marca = time.time()
        with self._cursor() as cursor:
            cursor.execute(
                "INSERT INTO samples(timestamp, tag, value) VALUES (?, ?, ?)",
                (marca, tag, valor_numerico),
            )
        self._depurar()

    def _depurar(self):
        if self.antiguedad_maxima_s <= 0:
            return
        ahora = time.time()
        if ahora - self._ultima_depuracion < self.antiguedad_maxima_s:
            return
        self._ultima_depuracion = ahora
        corte = ahora - self.antiguedad_maxima_s
        with self._cursor() as cursor:
            cursor.execute("DELETE FROM samples WHERE timestamp < ?", (corte,))

    def consultar(self, tag, desde=None, hasta=None):
        condiciones = ["tag = ?"]
        parametros = [tag]
        if desde is not None:
            condiciones.append("timestamp >= ?")
            parametros.append(desde)
        if hasta is not None:
            condiciones.append("timestamp <= ?")
            parametros.append(hasta)
        filtro = " AND ".join(condiciones)
        with self._cursor() as cursor:
            cursor.execute(
                "SELECT timestamp, value FROM samples "
                f"WHERE {filtro} ORDER BY timestamp ASC",
                parametros,
            )
            return list(cursor.fetchall())

    def ultimas(self, tag, cantidad=100):
        with self._cursor() as cursor:
            cursor.execute(
                "SELECT timestamp, value FROM samples WHERE tag = ? "
                "ORDER BY timestamp DESC LIMIT ?",
                (tag, cantidad),
            )
            filas = list(cursor.fetchall())
        filas.reverse()
        return filas
