# GSIMPLC

**GSIMPLC** es una plataforma genérica de simulación de PLCs en Python.
Se integra como nodo nativo en GNS3 (con IP propia y Modbus TCP),
ejecuta programas Ladder que el usuario carga en formato `.lad`, expone
un panel web de I/O en tiempo real, y se distribuye como un único
binario autocontenido (`gsimplc.bin`) listo para dropear en una
topología. No está atada a ningún proceso industrial: la lógica
(una bomba, un semáforo, una línea de producción) la definís vos
escribiendo un `.lad`.

---

## Instalación (3 pasos)

```bash
# 1. Clonar
git clone https://github.com/gsimplc/gsimplc.git
cd gsimplc

# 2. Instalar dependencias (Python 3.10+)
pip install -r requirements.txt

# 3. Ejecutar en modo desarrollo
python main.py --program examples/contador.lad
```

Eso es todo en modo dev. Para GNS3, ver la sección
[Importar en GNS3](#importar-en-gns3).

---

## Panel web

Con el PLC corriendo, abrí en el navegador:

```
http://localhost:8080            # en modo dev
http://192.168.1.10:8080         # en modo GNS3 (la IP del nodo)
```

El HMI te muestra (todo en tiempo real, push por WebSocket cada 200 ms):

- **Inputs I0–I15** — 16 botones toggle para simular entradas digitales
- **Outputs Q0–Q15** — 16 LEDs de solo lectura
- **Holding Registers HR0–HR7** — words editables (16 bits)
- **Timers T0–T3** — barra de progreso ACC/PRE + flag `[DN]`
- **Info** — programa activo, ciclo en ms, ciclos totales, uptime, ciclos/s
- **Program Loader** — botón para subir un `.lad` en caliente (sin reiniciar)

---

## Importar en GNS3

> Si querés usar GSIMPLC como un nodo "real" dentro de un laboratorio
> virtual con routers, switches, otros PLCs, etc., seguí estos pasos.

### 1. Construir binarios e imágenes

```bash
./setup.sh          # deps + tests + gsimplc.bin + gscada.bin
gns3/build_images.sh
```

Los scripts de build:

- instalan las dependencias
- corren PyInstaller (`.spec` one-file) y meten `panel/static/`,
  `examples/` y `gscada/static/` adentro según corresponda
- producen `dist/gsimplc.bin` y `dist/gscada.bin`
- construyen las imágenes Docker `gsimplc:latest` y `gscada:latest`
  que usan los appliances GNS3

### 2. Importar el appliance

Abrí GNS3 → `File` → `Import Appliance` → elegí `gns3/gsimplc.gns3a`
(y, para el SCADA, `gns3/gscada.gns3a`).

> `gsimplc.gns3a` seleccionado.*

GNS3 valida el manifiesto y registra un appliance Docker con
1 interfaz ethernet (`eth0`). Aceptá los defaults.

> 1 interfaz ethernet (`eth0`), imagen `gsimplc:latest`.*

### 3. Dropear en el canvas

Una vez importado, el template aparece en la barra lateral bajo
`Guest`. Arrastralo al canvas como cualquier router.

> ya arrastrado al canvas.*

### 4. Cablear y configurar

Conectá su `eth0` a un switch o a otro nodo. Los argumentos por
defecto viven en `/etc/gsimplc/gsimplc.args` dentro de la imagen; para
cambiarlos usá el comando de gestión por SSH (`gns3` / `gns3`):

```bash
# dentro del nodo (o vía docker exec)
gsimplc-manage set-args --program /opt/gsimplc/examples/semaforo.lad --cycle 100
gsimplc-manage start
```

| Campo         | Ejemplo                                          |
|---------------|--------------------------------------------------|
| Programa      | `--program /opt/gsimplc/examples/semaforo.lad`   |
| Ciclo         | `--cycle 100`                                    |
| Puerto panel  | `--panel-port 8080`                              |
| Puerto Modbus | `--modbus-port 502`                              |

El árbol completo del escenario con 2 PLCs + 1 SCADA está documentado
en [gns3/escenario_demo/README.md](gns3/escenario_demo/README.md).

### 5. Arrancar y verificar

Click en `Start`. El nodo debería:

- Arrancar sshd para gestión remota.
- Arrancar Modbus TCP en `:502`.
- Arrancar el panel web en `:8080`.
- Empezar a ejecutar el scan cycle.

Desde otra máquina apuntá:

- `http://192.168.1.10:8080` → panel HMI
- `nmap -p 502 192.168.1.10` → Modbus TCP
- `modbus 192.168.1.10 -p 502 -t 0x01 -r 1 -c 8` (con `pymodbus` o
  similar) para leer Q0..Q7

> con Q:0 prendido y HR:0 mostrando un valor numérico.*

---

## Casos de uso

- **Laboratorios de seguridad OT/ICS** — montá una topología con un
  PLC, un HMI, un atacante Kali y un IDS; practicás
  Modbus fingerprinting, ladder logic tampering, replay de paquetes,
  sin necesitar hardware físico.
- **Formación en automatización** — los alumnos escriben lógica
  Ladder, la cargan, ven el resultado en el panel, y la iteración
  es instantánea. No hay PLC de $3000 que quemar.
- **Testing de SCADAs / HMIs** — los vendors pueden validar sus
  dashboards contra un PLC con comportamiento configurable antes
  de recibir el hardware del cliente.
- **CTFs de ciberseguridad industrial** — GSIMPLC corre standalone
  con un challenge (`contador.lad` con lógica escondida,
  credenciales en la memoria accesible por Modbus, etc.).
- **Prototipado rápido de lógica de control** — antes de gastar
  tiempo programando un Allen-Bradley o un Siemens, prototipás la
  lógica en `.lad` y la simulás a 100 ms de ciclo.

---

## Arquitectura

```
gsimplc/
├── core/                    # Fase 1 — Núcleo PLC
│   ├── memoria.py           # MemoriaPLC — 4 áreas de registros
│   │                        # (bobinas, entradas, HR, IR) + timers/counters
│   ├── scan_cycle.py        # Hilo de scan: lee entradas → ejecuta Ladder
│   │                        # → escribe salidas, en loop
│   └── plc.py               # Orquestador: memoria + scan + ciclo de vida
│
├── ladder/                  # Fase 2 — Motor Ladder
│   ├── instrucciones.py     # XIC, XIO, OTE, OTL, OTU, TON, TOF, CTU,
│   │                        # CTD, MOV, ADD, SUB, EQU, NEQ, GRT, LES
│   ├── escalon.py           # Escalón con soporte de ramas OR
│   ├── programa.py          # Programa = lista de escalones
│   ├── lector.py            # Lector de .lad → Programa
│   └── referencias.py       # Direcciones I/Q/HR/IR/T/C
│
├── protocols/               # Modbus TCP (server)
│
├── panel/                   # Fase 3 — HMI web del PLC
│   ├── api.py               # API REST + WebSocket
│   ├── servidor.py          # ServidorPanel (uvicorn en un hilo)
│   └── static/              # index.html
│
├── process_sim/             # Fase 6 — Simulador de procesos físicos
│   ├── modelos.py           # Tanque, Motor, Valvula, SensorTemperatura, Cinta
│   ├── simulador.py         # SimuladorProceso (loop en thread)
│   ├── puente.py            # cargar_escenario() para YAML
│   └── scenarios/           # tanque_simple.yaml, demo_tanque.yaml, demo_cinta.yaml
│
├── gscada/                  # Fase 7 — Cliente SCADA/HMI (independiente)
│   ├── configuracion.py     # Modelos Pydantic + cargador YAML
│   ├── consultor.py         # ConsultorModbus (master, consultas por área)
│   ├── alarmas.py           # Motor de alarmas con condiciones
│   ├── historiador.py       # SQLite con auto-purge
│   ├── servidor.py          # FastAPI + WebSocket
│   ├── static/              # index.html, trends.html, mimic.html
│   └── configs/             # ejemplo.yaml, demo.yaml
│
├── io_plc/                  # Integración de red
│   └── interfaz_tap.py      # InterfazTAP — TUN/TAP Linux para GNS3
│
├── gns3/                    # Empaquetado como appliances
│   ├── gsimplc.gns3a
│   ├── gscada.gns3a
│   ├── build.sh             # PyInstaller --onefile (gsimplc)
│   ├── build_scada.sh       # PyInstaller --onefile (gscada)
│   ├── scripts/             # entrypoint, manage.sh, desplegar_demo.py
│   └── escenario_demo/      # README con guion de demo de 5 min
│
├── examples/                # Programas Ladder
│   ├── contador.lad         # "Hola mundo"
│   ├── semaforo.lad         # Demo visual
│   ├── demo_tanque.lad      # Control de nivel con histéresis
│   └── demo_cinta.lad       # Cinta con conteo de objetos
│
├── tests/                   # Suite pytest
├── main.py                  # Entry point GSIMPLC
├── gscada_main.py           # Entry point GSCADA
└── README.md
```

Flujo en runtime:

```
                              ┌──────────────┐
   --program foo.lad ──────▶ │ LectorLadder │ ─┐
                              └──────────────┘  │
                                                ▼
   --nic eth0 --ip 1.2.3.4/24 ─▶ ┌────────────────┐  ┌────────────┐
                                  │ InterfazTAP    │  │            │
   ┌──────────┐  read I/Q  ┌────▶ │  → /dev/net/tun│  │ MemoriaPLC │ ◀── Modbus TCP :502
   │  Devices │ ──────────▶ │      └────────────────┘  │            │ ◀── Panel web  :8080
   │  (GNS3)  │             │ scan_cycle                └────────────┘
   └──────────┘  write Q   │    │
              ◀──────────────│    │ programa.ejecutar(memoria)
                              └────┘
```

---

## CLI de referencia

```text
usage: gsimplc [-h] [--program PROGRAM] [--escenario ESCENARIO]
               [--ciclo-proceso CICLO_PROCESO] [--cycle CYCLE]
               [--modbus-port MODBUS_PORT] [--panel-port PANEL_PORT]
               [--host HOST] [--nic NIC] [--ip IP] [--verbose]

  --program       Ruta a un archivo de programa .lad
  --escenario     Ruta a un escenario YAML de proceso simulado
  --ciclo-proceso Periodo del proceso simulado en ms (default: 200)
  --cycle         Periodo del ciclo de exploracion en ms (default: 100)
  --modbus-port   Puerto Modbus TCP (default: 502)
  --panel-port    Puerto del panel web (default: 8080)
  --host          Direccion de escucha cuando no se usa TAP (default: 0.0.0.0)
  --nic           Nombre de la interfaz TAP para GNS3 (ej. eth0)
  --ip            IP en formato CIDR, ej. 192.168.1.10/24
  --verbose       Activa el registro en nivel DEBUG
```

Con `--nic + --ip`: crea TAP y binda a esa IP (modo GNS3).
Sin TAP: binda a `--host` (default `0.0.0.0`).

---

## Tests

```bash
pytest tests/ -v
```

La suite cubre:

- **Ladder**: referencias, contactos, bobinas, temporizadores,
  contadores, operaciones, comparaciones, escalones y lectura de archivos.
- **Memoria PLC**: áreas de registros, seguridad de hilos y estado completo.
- **Modbus**: creación, sincronización, escritura remota y apagado del puerto.
- **Proceso simulado**: modelos físicos, motor y carga de escenarios YAML.
- **GSCADA**: configuración, alarmas, persistencia, polling, API y WebSocket.

---

## Licencia

MIT.
