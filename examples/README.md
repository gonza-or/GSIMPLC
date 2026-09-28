# Ejemplos `.lad` de GSIMPLC

Acá viven los dos programas de ejemplo que vienen con GSIMPLC. Empezá
por `contador.lad` (3 rungs, comportamiento obvio) y seguí con
`semaforo.lad` (8 rungs, usa timers, contadores y comparaciones).

---

## Formato `.lad` desde cero

Un archivo `.lad` es texto plano con esta estructura:

```
# Esto es un comentario, va con # al inicio de la línea

RUNG 0 "nombre opcional del escalón"
  INSTRUCCION arg1 arg2 arg3
  OTRA_INSTRUCCION arg1
END_RUNG

RUNG 1 "otro escalón"
  XIC I:0
  BRANCH
    XIC I:1
  END_BRANCH
  OTE Q:0
END_RUNG
```

Reglas:

- **Comentarios**: cualquier línea que empiece con `#` se ignora.
- **RUNG / END_RUNG**: delimita un escalón. Entre medio van las
  instrucciones en serie (AND entre contactos).
- **BRANCH / END_BRANCH**: dentro de un RUNG, una rama paralela (OR)
  con la cadena principal. Útil para lógica "este O este otro".
- Las instrucciones se ejecutan en el orden en que aparecen.
- Las direcciones y los literales van sin comillas.

---

## Mapeo de direcciones

| Sintaxis      | Significado                                         | Tipo         |
|---------------|-----------------------------------------------------|--------------|
| `I:N`         | Entrada discreta N (botón, sensor, lectura digital) | bit (bool)   |
| `Q:N`         | Salida (bobina) N (LED, relé, actuador)             | bit (bool)   |
| `HR:N`        | Holding register N (variable entera de 16 bits)     | word (int)   |
| `IR:N`        | Input register N (lectura analógica, sensor 0-10V)   | word (int)   |
| `T:N`         | Timer N (su flag `DN` es `True` cuando terminó)     | bit          |
| `T:N.ACC`     | Acumulador del timer N (ms transcurridos)           | word (int)   |
| `T:N.PRE`     | Preset del timer N (ms objetivo)                    | word (int)   |
| `T:N.EN`      | Timer N habilitado (su entrada está activa)         | bit          |
| `T:N.TT`      | Timer N contando (entre EN y DN)                    | bit          |
| `C:N`         | Counter N (su flag `DN` es `True` cuando llegó al preset) | bit    |
| `C:N.ACC`     | Acumulador del counter N                            | word (int)   |
| `C:N.PRE`     | Preset del counter N                                | word (int)   |
| `N`           | Literal numérico (ej. `42`, `100`, `0`)             | word (int)   |

> Las direcciones distinguen mayúsculas/minúsculas solo en el prefijo
> (`I:0` ≠ `i:0`). El índice es siempre decimal.

---

## Tabla de instrucciones

### Contactos (booleanos)

| Mnemónico | Nombre                       | Sintaxis       | Pasa energía si…                           |
|-----------|------------------------------|----------------|---------------------------------------------|
| `XIC`     | Normally-Open contact        | `XIC <addr>`   | la dirección vale `True`                    |
| `XIO`     | Normally-Closed contact      | `XIO <addr>`   | la dirección vale `False`                   |

### Bobinas

| Mnemónico | Nombre                       | Sintaxis       | Efecto                                      |
|-----------|------------------------------|----------------|---------------------------------------------|
| `OTE`     | Output coil                  | `OTE <addr>`   | escribe el estado a la dirección             |
| `OTL`     | Latch (set)                  | `OTL <addr>`   | si hay energía, fuerza `True` y lo retiene  |
| `OTU`     | Unlatch (reset)              | `OTU <addr>`   | si hay energía, fuerza `False` y lo retiene |

### Timers (requieren argumento `PRE=<ms>`)

| Mnemónico | Nombre              | Sintaxis                  | Notas                                     |
|-----------|---------------------|---------------------------|-------------------------------------------|
| `TON`     | Timer ON-delay      | `TON T:N PRE=<ms>`        | empieza a contar en flanco ascendente     |
| `TOF`     | Timer OFF-delay     | `TOF T:N PRE=<ms>`        | empieza a contar en flanco descendente    |

El timer se "auto-resetea" cuando su XIC de entrada se desactiva. La
forma estándar de hacer un TON cíclico es usar un flag intermedio
(ver `semaforo.lad` para el patrón).

### Contadores (requieren argumento `PRE=<valor>`)

| Mnemónico | Nombre              | Sintaxis                  | Notas                                     |
|-----------|---------------------|---------------------------|-------------------------------------------|
| `CTU`     | Contador ascendente | `CTU C:N PRE=<valor>`     | incrementa en flanco ascendente           |
| `CTD`     | Contador descendente| `CTD C:N PRE=<valor>`     | decrementa en flanco ascendente           |

`DN` se activa cuando `ACC >= PRE`.

### Movimiento y aritmética

| Mnemónico | Nombre              | Sintaxis                    | Notas                                |
|-----------|---------------------|-----------------------------|--------------------------------------|
| `MOV`     | Copiar valor        | `MOV <src> <dst>`           | `<dst>` debe ser `HR:N` o `IR:N`     |
| `ADD`     | Sumar               | `ADD <a> <b> <dst>`         | resultado en `HR:N` o `IR:N`         |
| `SUB`     | Restar              | `SUB <a> <b> <dst>`         | `dst = a - b`                        |

### Comparación (booleanos: devuelven True/False)

| Mnemónico | Nombre          | Sintaxis          | Pasa energía si…     |
|-----------|-----------------|-------------------|----------------------|
| `EQU`     | Igual           | `EQU <a> <b>`     | `a == b`             |
| `NEQ`     | Distinto        | `NEQ <a> <b>`     | `a != b`             |
| `GRT`     | Mayor           | `GRT <a> <b>`     | `a > b`              |
| `LES`     | Menor           | `LES <a> <b>`     | `a < b`              |

Las comparaciones convierten los operandos a entero antes de comparar.
Sirven para `HR:N`, `IR:N`, `T:N.ACC`, `C:N.ACC` y literales.

### Ejemplo mínimo

```lad
# Si I:0 está activo, activar Q:0
RUNG 0 "encender Q:0 con I:0"
  XIC I:0
  OTE Q:0
END_RUNG

# Copiar el valor de HR:0 a HR:1 en cada scan
RUNG 1 "eco de HR:0"
  MOV HR:0 HR:1
END_RUNG
```

---

## Cómo cargar tu programa

Tenés dos formas:

### 1. Al iniciar (CLI)

Pasás el archivo con `--program`:

```bash
python main.py --program examples/contador.lad --cycle 100
```

Esto carga el programa en el arranque y queda corriendo indefinidamente.
La combinación con `--nic` y `--ip` lo deja corriendo dentro de GNS3:

```bash
./gsimplc.bin --nic eth0 --ip 192.168.1.10/24 --program examples/semaforo.lad
```

### 2. En caliente (panel web)

Con el PLC ya corriendo, abrí `http://localhost:8080`, andá a la
sección **Program Loader** y elegí un archivo `.lad`. El PLC lo
recompila, lo instala en el ciclo de scan al instante y empieza a
ejecutarlo sin reiniciar.

También podés apuntar a un path absoluto del server:

```bash
curl -X POST http://localhost:8080/api/program/load \
     -H 'Content-Type: application/json' \
     -d '{"path": "/opt/gsimplc/progs/mi_logica.lad"}'
```

---

## Escribí tu propia lógica paso a paso

Supongamos que querés un programa que **prenda Q:0 cuando I:0 lleve
presionado más de 3 segundos**.

1. **Identificá las entradas y salidas**: I:0 (botón) → Q:0 (LED).
2. **Buscás la instrucción que necesitás**: para "más de X segundos
   activo" usás un `TON` con preset 3000 ms.
3. **Pensás el flujo**:
   - Si I:0 está activo → arrancar el timer.
   - Si el timer llegó a `DN` → Q:0 ON.
4. **Lo escribís**:

    ```lad
    RUNG 0 "arrancar el timer cuando se presiona I:0"
      XIC I:0
      TON T:0 PRE=3000
    END_RUNG

    RUNG 1 "encender Q:0 cuando el timer llegó a DN"
      XIC T:0.DN
      OTE Q:0
    END_RUNG
    ```

5. **Lo cargás**:
   - `python main.py --program mi_programa.lad` para arrancar con él, o
   - panel web → **Program Loader** para instalarlo en caliente.
6. **Lo verificás** en el panel:
   - Sección **Inputs** → click en I:0 para simular el botón.
   - Sección **Outputs** → mirá Q:0 encenderse después de 3 s.
   - Sección **Timers** → la barra de T:0 va llenándose hasta el 100 %.

### Tips rápidos

- **El orden de las rungs importa**: si una rung escribe a `HR:0` y
  otra lo lee, poné la que escribe primero.
- **`MOV T:N.ACC HR:M`** es la forma estándar de "ver" el valor de un
  timer en el panel.
- **Para rangos con solo `GRT` y `LES`**: `[3000, 6000)` se escribe
  como `GRT HR:X 2999` + `LES HR:X 6000` (ver `semaforo.lad`).
- **`PRE` muy alto en un counter** (ej. `999999`) lo hace prácticamente
  infinito.

---

## Archivos en este directorio

- `contador.lad` — programa "Hola Mundo" (3 rungs, sin timers).
  Suma un contador HR:0 cada scan, lo resetea al llegar a 100, y
  prende Q:0 mientras está en la "mitad alta".
- `semaforo.lad` — demo visual de 8 rungs. Semá cíclico
  ROJO → VERDE → AMARILLO con timers TON, contadores CTU y
  comparaciones GRT/LES.
- `README.md` — este archivo.
