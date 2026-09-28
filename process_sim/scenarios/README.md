# Escenarios de Process Sim

Un escenario es un archivo YAML que describe qué procesos físicos se
simulan y cómo se mapean a la memoria del PLC. Se carga con:

```python
from process_sim import cargar_escenario
simulador = cargar_escenario("process_sim/scenarios/tanque_simple.yaml",
                             memoria)
simulador.iniciar()
```

> Las claves del YAML (`type`, `name`, `capacity_liters`, ...) siguen en
> inglés: son el contrato del archivo y `process_sim/puente.py` las traduce
> a los parámetros en español de cada modelo.

## Modelos disponibles

| Tipo         | Qué simula                                       | Direcciones típicas                        |
|--------------|--------------------------------------------------|--------------------------------------------|
| `Tank`       | Tanque de líquido con bomba y drenaje constante  | `IR:N` (nivel %), `I:N` (alarmas), `Q:N` (bomba) |
| `Motor`      | Motor con aceleración / desaceleración gradual   | `IR:N` (RPM), `I:N` (running), `Q:N` (start)    |
| `Valve`      | Válvula proporcional con travel time             | `HR:N` (setpoint), `IR:N` (posición)              |
| `TempSensor` | Temperatura con inercia térmica                  | `IR:N` (°C), `Q:N` (calentador)                   |
| `Conveyor`   | Cinta transportadora con sensor de objeto         | `I:N` (objeto), `Q:N` (motor)                     |

## Archivos

- `tanque_simple.yaml` — un solo tanque (1000 L, bomba 5 lps, drenaje 2 lps).
  Es el "Hola Mundo" del Process Sim. Combinado con
  `examples/demo_tanque.lad` se obtiene un lazo de control cerrado
  completo.
