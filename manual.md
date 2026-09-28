# GSIMPLC + GSCADA en GNS3 — Manual de uso

Guía práctica para montar el laboratorio completo en GNS3: dos nodos
GSIMPLC (simuladores PLC con Ladder + Modbus TCP) y un nodo GSCADA
(SCADA/HMI que los monitorea por Modbus).

---

## 1. Qué se validó y qué no

Lo que **sí está verificado** en este entorno (GNS3 2.2.58, Docker):

- Los binarios standalone se compilan desde los specs y arrancan
  (`dist/gsimplc.bin`, `dist/gscada.bin`).
- Las imágenes Docker `gsimplc:latest` y `gscada:latest` se construyen y
  ejecutan; cada una levanta su HMI en `:8080`.
- **La topología completa ya fue montada y verificada en GNS3** con la API
  REST: 2 nodos GSIMPLC + 1 switch + 1 nodo GSCADA, arrancados y con
  conectividad Modbus real entre GSCADA y ambos PLCs.
  Resultado real: `PLC Tanque online=True` (`Bomba Llenado: true`,
  `Nivel Tanque: 0`), `PLC Cinta online=True`, sin tags `stale`.
- Los appliances `.gns3a` usan el formato `docker` que GNS3 2.2.x importa
  (registro v3 con bloque `docker` directo, `console_type: http`).

Lo que **tenés que tener en cuenta**:

- **IPs estáticas**: GNS3 no asigna DHCP automáticamente a los nodos
  Docker; hay que fijar IP estática en el `interfaces` de cada nodo
  (sección 6). En este entorno ya quedaron fijadas
  `192.168.1.10` / `192.168.1.11` / `192.168.1.20`.
- **`ifupdown` es obligatorio en las imágenes**: GNS3 inyecta un
  `init.sh` que hace `ifup -a -f`. Por eso los `Dockerfile.*` ya instalan
  `ifupdown` + `isc-dhcp-client`. Sin eso, los nodos no levantan IP.
- La importación del `.gns3a` desde la GUI no se puede probar headless;
  pero los templates equivalentes se crearon vía API (`POST /v2/templates`)
  y funcionan.

---

## 2. Pre-requisitos

- **Docker** funcionando: `docker info` sin errores.
- **GNS3** (GUI + servidor local) apuntando a la misma máquina que aloja
  las imágenes Docker.
- Python 3.10+ (solo si querés reconstruir binarios con `setup.sh`).

---

## 3. Construir binarios e imágenes

Desde la raíz del proyecto:

```bash
./setup.sh              # instala deps, corre los tests, compila los .bin
gns3/build_images.sh    # construye gsimplc:latest y gscada:latest
```

Si ya tenés los binarios y solo cambiaron los scripts:

```bash
gns3/build_images.sh
```

Verificá que las imágenes existen:

```bash
docker images | grep -E 'gsimplc|gscada'
```

---

## 4. Importar los appliances en GNS3

1. Abrí GNS3.
2. `File` → `Import Appliance`.
3. Elegí `gns3/gsimplc.gns3a`. Aceptá los defaults.
4. Repetí con `gns3/gscada.gns3a`.

Ambos aparecen como templates en la barra lateral, categoría `Guest`,
con símbolo de *docker guest*. Cada uno expone 1 adaptador `eth0`.

> Si GNS3 no reconoce la categoría o el símbolo, no es bloqueante: el
> template igual se crea con `docker` como tipo de nodo.

---

## 5. Armar la topología

Topología de referencia:

```
  GSIMPLC #1 ──┐
   (tanque)    │
  GSIMPLC #2 ──┤── [Switch] ── GSCADA
   (cinta)     │               (HMI)
```

Pasos:

1. Arrastrá **2 × GSIMPLC** y **1 × GSCADA** al canvas.
2. Arrastrá un **Ethernet switch** y conectá los tres nodos a él.
3. Arrancá los tres nodos (`Start all nodes`).

Cada nodo levanta sshd (usuario `gns3` / clave `gns3`) y su binario con
los argumentos por defecto que ya vienen en la imagen.

---

## 6. Configurar las IPs (paso crítico)

GNS3 **no asigna DHCP** a los nodos Docker automáticamente. El `interfaces`
que GNS3 genera para cada nodo viene con DHCP comentado, así que los nodos
arrancan **sin IP** a menos que fijes una estática. Hay que hacerlo sobre el
archivo de red que GNS3 monta en cada contenedor.

### Dónde está el archivo de red

Para cada nodo Docker, GNS3 crea un `project-files/docker/<node_id>/etc/network/interfaces`
dentro del directorio del proyecto. Ese archivo se monta con *bind* en
`/etc/network/interfaces` del contenedor.

### Opción A — Fijar IP estática en el working_dir (recomendada)

Con el nodo **detenido**, escribí el `interfaces` del nodo:

```bash
PROJECT_DIR="/home/gonor/GNS3/projects/<project_id>/project-files/docker"
NODE_ID="<node_id>"

cat > "$PROJECT_DIR/$NODE_ID/etc/network/interfaces" <<EOF
auto lo
iface lo inet loopback

auto eth0
iface eth0 inet static
    address 192.168.1.10
    netmask 255.255.255.0
EOF
```

Luego arrancá el nodo. El `init.sh` de GNS3 corre `ifup -a -f` y aplica
la IP. IPs de referencia:

| Nodo       | IP deseada     |
|------------|----------------|
| GSIMPLC #1 | `192.168.1.10` |
| GSIMPLC #2 | `192.168.1.11` |
| GSCADA     | `192.168.1.20` |

Con esto, `demo.yaml` funciona tal cual (apunta a `192.168.1.10/11`).

### Opción B — Editar el config de GSCADA con las IPs reales

Si preferís otras IPs, editá `gscada/configs/demo.yaml` cambiando `host:`
y recargá el config en caliente por SSH:

```bash
# dentro del nodo GSCADA (vía SSH gns3@<ip> o "Auxiliary console")
gsimplc-manage set-args --config /ruta/a/demo.yaml --port 8080
gsimplc-manage stop
gsimplc-manage start
```

---

## 7. Montar la topología por API (reproducible)

Todo lo de las secciones 4–6 también se puede automatizar contra la API REST
de GNS3 (puerto `3080` local, auth `admin` + la password de
`~/.config/GNS3/2.2/gns3_server.conf`). Es lo que se usó para dejar el
entorno ya armado y verificado.

Flujo resumido:

1. `POST /v2/templates` — crear templates `docker` con `image` = `gsimplc:latest` / `gscada:latest`, `adapters: 1`, `console_type: http`, `console_http_port: 8080`.
2. `POST /v2/projects` — crear el proyecto; `POST /v2/projects/{id}/open`.
3. `POST /v2/projects/{id}/templates/{tpl}` — crear nodos (switch + 2 PLC + 1 SCADA). El switch (builtin) necesita `"compute_id": "local"`.
4. `POST /v2/projects/{id}/links` — conectar cada nodo al switch (`nodes: [{node_id, adapter_number, port_number}]`).
5. Fijar IP estática en `project-files/docker/<node_id>/etc/network/interfaces` (sección 6, Opción A).
6. `POST /v2/projects/{id}/nodes/start` — arrancar todo.

El script completo está en `gns3/scripts/desplegar_demo.py` (se crea al ejecutar
la build; si no existe, seguí los pasos manuales de las secciones 4–6).

---

## 8. Gestión por SSH (dentro de cada nodo)

Cada imagen incluye el comando `gsimplc-manage`:

```bash
gsimplc-manage status      # RUNNING / STOPPED + PID
gsimplc-manage start       # arranca el binario
gsimplc-manage stop        # lo detiene
gsimplc-manage set-args --program /opt/gsimplc/examples/semaforo.lad --cycle 100
gsimplc-manage show-logs   # tail -f del log
```

Los argumentos por defecto están en `/etc/gsimplc/gsimplc.args`
(PLC) y `/etc/gsimplc/gscada.args` (SCADA). El PLC arranca por defecto con
`demo_tanque.lad`; el SCADA con `demo.yaml`.

---

## 9. Verificar el funcionamiento

**Panel del PLC** (`http://192.168.1.10:8080` o `http://<ip-plc>:8080`):

- Botones I0–I15 (entradas), LEDs Q0–Q15 (salidas), registros HR, timers.
- En `demo_tanque.lad`, la bomba Q0 debería encenderse/apagarse según los
  niveles.

**HMI de GSCADA** (`http://192.168.1.20:8080` o `http://<ip-scada>:8080`):

- `/api/plcs` debe mostrar los PLCs con `"online": true`.
- Si aparece `"online": false` con `"connect() returned False"`, el
  problema es de red/IP (revisá la sección 6) o que el PLC aún no levantó
  Modbus en `:502`.

**Modbus directo** (desde tu host, si tenés `pymodbus` o `mbpoll`):

```bash
# leer Q0..Q7
mbpoll 192.168.1.10 -p 502 -t 0 -r 1 -c 8
```

---

## 10. Guion de demo (5 minutos)

1. Mostrar la topología en GNS3 (2 PLCs + switch + SCADA).
2. Abrir el panel de GSIMPLC #1 y ver el tanque controlado por Ladder
   (bomba Q0 ciclando según nivel alto/bajo).
3. Abrir el HMI de GSCADA: ambos PLCs `ONLINE` con tags en vivo.
4. Forzar una alarma (togglar una entrada o subir el nivel) y verla
   activarse en GSCADA.
5. Reconocer la alarma (`Acknowledge`) y abrir **Tendencias** para ver el
   histórico del tag.

---

## 11. Solución de problemas

| Síntoma | Causa probable | Solución |
|---------|----------------|----------|
| GSCADA muestra `offline` / `connect() returned False` | IPs de los `.yaml` no coinciden con las reales | Sección 6 |
| Nodos Docker arrancan **sin IP** | `ifupdown` no instalado en la imagen o `interfaces` sin IP estática | Reconstruí imágenes (`gns3/build_images.sh`) y fijá IP (sección 6) |
| El panel no abre con click derecho → Console | `console_type` mal | Ya está en `http`; reimportá el appliance |
| `docker build` falla por `gns3/scripts/*` | Árbol incompleto | Ejecutá `gns3/build_images.sh` desde la raíz |
| Nodo arranca pero el puerto 8080 no responde | Proceso viejo ocupando el puerto | `gsimplc-manage stop` y `start` |
| "No settings found in the appliance file" | `.gns3a` de formato antiguo | Asegurate de importar los `gns3/*.gns3a` de este repo |
| `ifup: not found` al querer levantar red | Imagen vieja sin `ifupdown` | Reconstruí y **recreá** los nodos (no sirve reiniciar) |

---

## Nota sobre el proyecto exportable

El `.gns3project` es un ZIP que genera GNS3 desde la GUI
(`File → Export portable project`). No se versiona a mano porque su
estructura cambia entre versiones de GNS3; armá la topología siguiendo
este manual y exportala si querés compartirla.
