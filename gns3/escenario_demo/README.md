# Escenario demo — GSIMPLC + GSCADA en GNS3

Topología de referencia para demostrar todo el stack funcionando junto:

```
                    ┌──────────────┐
  192.168.1.10 ─────┤  GSIMPLC #1  │  (tanque)
                    │  demo_tanque │
                    └──────┬───────┘
                           │
                    ┌──────┴───────┐
  192.168.1.11 ─────┤  GSIMPLC #2  │  (cinta)
                    │  demo_cinta  │
                    └──────┬───────┘
                           │
                     [ Switch ]
                           │
                    ┌──────┴───────┐
                    │  GSCADA      │  (HMI / SCADA)
                    │ 192.168.1.20 │
                    └──────────────┘
```

- **GSIMPLC #1** — `192.168.1.10`, programa `demo_tanque.lad`, Modbus :502, panel :8080
- **GSIMPLC #2** — `192.168.1.11`, programa `demo_cinta.lad`, Modbus :502, panel :8080
- **GSCADA** — `192.168.1.20`, configura `gscada/configs/demo.yaml`, HMI :8080

## Pre-requisitos

1. Docker instalado y funcionando (`docker info` sin errores).
2. GNS3 instalado, con el servidor local apuntando a la misma máquina que
   aloja las imágenes Docker.

## Paso a paso

### 1. Construir binarios e imágenes

```bash
cd gsimplc
./setup.sh          # deps + tests + gsimplc.bin + gscada.bin
gns3/build_images.sh
```

Esto deja disponibles las imágenes `gsimplc:latest` y `gscada:latest`.

### 2. Importar los appliances en GNS3

1. Abrí GNS3 → `File` → `Import Appliance`.
2. Elegí `gns3/gsimplc.gns3a` y luego `gns3/gscada.gns3a`.
3. Aceptá los valores por defecto en cada resumen.

### 3. Armar la topología

1. Arrastrá **2 nodos GSIMPLC** y **1 nodo GSCADA** al canvas.
2. Arrastrá un **switch** (Ethernet switch) y conectá los tres nodos a él.
3. Click derecho sobre cada nodo → `Configure`:

| Nodo        | Acción |
|-------------|--------|
| GSIMPLC #1  | `set-args --program /opt/gsimplc/examples/demo_tanque.lad` |
| GSIMPLC #2  | `set-args --program /opt/gsimplc/examples/demo_cinta.lad` |
| GSCADA      | `set-args --config /opt/gsimplc/gscada/configs/demo.yaml --port 8080` |

> Las IPs las asigna GNS3 automáticamente a través de DHCP de Docker; para
> que `demo.yaml` apunte a los PLC correctos, ajustá `host:` en
> `gscada/configs/demo.yaml` a las IPs reales asignadas (o fijá IPs
> estáticas en la config de red del nodo en GNS3).

### 4. Arrancar

Click en `Start` sobre los tres nodos (o `Start all nodes`). Cada nodo:

- Levanta sshd (usuario `gns3` / `gns3`) para gestión.
- Arranca su binario con los args configurados.
- Expone su HMI en `http://<ip>:8080`.

## Guion de demo (5 minutos)

1. **Mostrar la topología** en GNS3: 2 PLCs + switch + SCADA.
2. **Abrir el panel de GSIMPLC #1** (`http://192.168.1.10:8080`): ver el
   tanque controlado por `demo_tanque.lad`, con la bomba Q0 encendiéndose
   y apagándose según los niveles alto/bajo.
3. **Abrir el HMI de GSCADA** (`http://192.168.1.20:8080`): ambos PLCs
   aparecen `ONLINE` con sus tags en vivo (nivel, bomba, rpm, contador).
4. **Forzar una alarma**: desde el panel web del PLC, togglear una entrada
   o subir el nivel para disparar "Nivel crítico"; ver la alarma activarse
   en el HMI de GSCADA.
5. **Reconocer la alarma** (`Acknowledge`) y abrir **Tendencias** para
   mostrar la evolución histórica del tag en el gráfico.

## Nota sobre el proyecto exportable

El formato `.gns3project` es un ZIP que GNS3 genera desde la GUI
(`File → Export portable project`). Para compartir este escenario, armá la
topología siguiendo los pasos anteriores y exportala; no se versiona a mano
porque su estructura interna cambia entre versiones de GNS3.
