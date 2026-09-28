#!/usr/bin/env python3
"""
Despliega la topologia demo de GSIMPLC + GSCADA en un servidor GNS3 local.

Crea:
  - 2 plantillas Docker de GSIMPLC (imagen gsimplc:latest)
  - 1 plantilla Docker de GSCADA (imagen gscada:latest)
  - un proyecto "gsimplc-demo" con 2 nodos PLC + 1 nodo SCADA + 1 switch
  - un enlace de cada nodo contra el switch
  - una IP estatica en cada nodo (192.168.1.10 / .11 / .20) escrita en la
    configuracion de red de los archivos del proyecto

Despues arranca todos los nodos.

Requisitos:
  - Servidor GNS3 corriendo localmente (http://127.0.0.1:3080) con auth.
  - Imagenes Docker gsimplc:latest y gscada:latest ya construidas
    (correr gns3/build_images.sh primero).

Uso:
  python3 gns3/scripts/desplegar_demo.py
"""

import argparse
import json
import os
import pathlib
import sys
import urllib.error
import urllib.request

HOST_POR_DEFECTO = "127.0.0.1"
PUERTO_POR_DEFECTO = 3080
USUARIO_POR_DEFECTO = "admin"

# Plantilla del switch integrado de GNS3 (id fijo).
PLANTILLA_SWITCH = "1966b864-93e7-32d5-965f-001384eec461"


def leer_clave_servidor():
    """Lee la clave del servidor GNS3 desde su configuracion local."""
    configuracion = (
        pathlib.Path.home() / ".config" / "GNS3" / "2.2" / "gns3_server.conf"
    )
    if configuracion.is_file():
        for linea in configuracion.read_text().splitlines():
            if linea.startswith("password"):
                return linea.split("=", 1)[1].strip()
    # Alternativa: variable de entorno.
    return os.environ.get("GNS3_PASSWORD", "")


class ClienteGNS3:
    """Cliente minimo de la API REST v2 de GNS3."""

    def __init__(self, host, puerto, usuario, clave):
        self.base = f"http://{host}:{puerto}/v2"
        self.usuario = usuario
        self.clave = clave

    def solicitar(self, metodo, ruta, datos=None):
        url = self.base + ruta
        cuerpo = None
        cabeceras = {"Authorization": self._autorizacion()}
        if datos is not None:
            cuerpo = json.dumps(datos).encode("utf-8")
            cabeceras["Content-Type"] = "application/json"
        peticion = urllib.request.Request(
            url, data=cuerpo, headers=cabeceras, method=metodo
        )
        try:
            with urllib.request.urlopen(peticion, timeout=30) as respuesta:
                crudo = respuesta.read()
                return respuesta.status, (json.loads(crudo) if crudo else None)
        except urllib.error.HTTPError as error:
            crudo = error.read()
            return error.code, (json.loads(crudo) if crudo else None)

    def _autorizacion(self):
        import base64
        token = base64.b64encode(
            f"{self.usuario}:{self.clave}".encode()
        ).decode()
        return f"Basic {token}"


def _asegurar_plantilla(cliente, nombre, imagen):
    """Devuelve el id de la plantilla Docker, creandola si no existe."""
    _, plantillas = cliente.solicitar("GET", "/templates")
    if plantillas:
        for plantilla in plantillas:
            if (plantilla.get("name") == nombre
                    and plantilla.get("template_type") == "docker"):
                return plantilla["template_id"]
    codigo, creada = cliente.solicitar("POST", "/templates", {
        "name": nombre,
        "template_type": "docker",
        "compute_id": "local",
        "image": imagen,
        "adapters": 1,
        "console_type": "http",
        "console_http_port": 8080,
        "console_http_path": "/",
        "category": "guest",
        "symbol": ":/symbols/docker_guest.svg",
        "default_name_format": f"{nombre}-{{0}}",
    })
    if codigo != 201:
        print(
            f"error al crear la plantilla {nombre}: {codigo} {creada}",
            file=sys.stderr,
        )
        sys.exit(1)
    return creada["template_id"]


def _crear_nodo(cliente, proyecto_id, plantilla_id, nombre, x, y):
    codigo, nodo = cliente.solicitar(
        "POST",
        f"/projects/{proyecto_id}/templates/{plantilla_id}",
        {"x": x, "y": y, "name": nombre},
    )
    if codigo != 201:
        print(
            f"error al crear el nodo {nombre}: {codigo} {nodo}",
            file=sys.stderr,
        )
        sys.exit(1)
    return nodo["node_id"]


def _enlazar(cliente, proyecto_id, nodo_a, puerto_a, nodo_b, puerto_b):
    codigo, _ = cliente.solicitar("POST", f"/projects/{proyecto_id}/links", {
        "nodes": [
            {
                "node_id": nodo_a,
                "adapter_number": 0,
                "port_number": puerto_a,
            },
            {
                "node_id": nodo_b,
                "adapter_number": 0,
                "port_number": puerto_b,
            },
        ],
    })
    if codigo != 201:
        print(f"error al enlazar los nodos: {codigo}", file=sys.stderr)
        sys.exit(1)


def _escribir_ips_estaticas(ruta_proyecto, ips):
    carpeta_docker = pathlib.Path(ruta_proyecto) / "project-files" / "docker"
    for nodo_id, ip in ips.items():
        carpeta_red = carpeta_docker / nodo_id / "etc" / "network"
        carpeta_red.mkdir(parents=True, exist_ok=True)
        interfaces = carpeta_red / "interfaces"
        interfaces.write_text(
            "auto lo\n"
            "iface lo inet loopback\n"
            "\n"
            "auto eth0\n"
            "iface eth0 inet static\n"
            f"    address {ip}\n"
            "    netmask 255.255.255.0\n"
        )
        print(f"ip estatica {ip} -> {nodo_id}")


def main():
    analizador = argparse.ArgumentParser(
        description="Despliega la topologia demo de GSIMPLC+GSCADA"
    )
    analizador.add_argument("--host", default=HOST_POR_DEFECTO)
    analizador.add_argument("--port", default=PUERTO_POR_DEFECTO, type=int)
    analizador.add_argument("--user", default=USUARIO_POR_DEFECTO)
    analizador.add_argument(
        "--no-start", action="store_true",
        help="No arrancar los nodos",
    )
    argumentos = analizador.parse_args()

    clave = leer_clave_servidor()
    if not clave:
        print(
            "error: no se encontro la clave del servidor GNS3",
            file=sys.stderr,
        )
        return 1

    cliente = ClienteGNS3(
        argumentos.host, argumentos.port, argumentos.user, clave
    )

    plantilla_gsimplc = _asegurar_plantilla(
        cliente, "GSIMPLC", "gsimplc:latest"
    )
    plantilla_gscada = _asegurar_plantilla(
        cliente, "GSCADA", "gscada:latest"
    )
    print(
        f"plantillas: GSIMPLC={plantilla_gsimplc} GSCADA={plantilla_gscada}"
    )

    codigo, proyecto = cliente.solicitar("POST", "/projects", {
        "name": "gsimplc-demo",
        "auto_start": False,
        "auto_open": True,
        "auto_close": True,
    })
    if codigo != 201:
        print(
            f"error al crear el proyecto: {codigo} {proyecto}",
            file=sys.stderr,
        )
        sys.exit(1)
    proyecto_id = proyecto["project_id"]
    cliente.solicitar("POST", f"/projects/{proyecto_id}/open")
    print(f"proyecto: {proyecto_id}")

    # El switch es una plantilla integrada y necesita compute_id local.
    codigo, nodo_switch = cliente.solicitar(
        "POST",
        f"/projects/{proyecto_id}/templates/{PLANTILLA_SWITCH}",
        {"x": 600, "y": 300, "name": "Switch1", "compute_id": "local"},
    )
    if codigo != 201:
        print(
            f"error al crear el switch: {codigo} {nodo_switch}",
            file=sys.stderr,
        )
        sys.exit(1)
    switch_id = nodo_switch["node_id"]

    plc1_id = _crear_nodo(
        cliente, proyecto_id, plantilla_gsimplc, "PLC-Tanque", 200, 150
    )
    plc2_id = _crear_nodo(
        cliente, proyecto_id, plantilla_gsimplc, "PLC-Cinta", 200, 450
    )
    scada_id = _crear_nodo(
        cliente, proyecto_id, plantilla_gscada, "SCADA", 1000, 300
    )
    print(
        f"nodos: switch={switch_id} plc1={plc1_id} "
        f"plc2={plc2_id} scada={scada_id}"
    )

    _enlazar(cliente, proyecto_id, plc1_id, 0, switch_id, 0)
    _enlazar(cliente, proyecto_id, plc2_id, 0, switch_id, 1)
    _enlazar(cliente, proyecto_id, scada_id, 0, switch_id, 2)
    print("enlaces creados")

    _escribir_ips_estaticas(proyecto["path"], {
        plc1_id: "192.168.1.10",
        plc2_id: "192.168.1.11",
        scada_id: "192.168.1.20",
    })

    if argumentos.no_start:
        print(
            "nodos creados (sin arrancar). Arrancalos desde GNS3 o con "
            "POST /nodes/start"
        )
        return 0

    codigo, _ = cliente.solicitar(
        "POST", f"/projects/{proyecto_id}/nodes/start"
    )
    print(f"arrancar todos: {codigo}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
