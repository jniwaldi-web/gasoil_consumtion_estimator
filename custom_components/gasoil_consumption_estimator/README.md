# Estimador de consumo de gasoil

Integración personalizada para [Home Assistant](https://www.home-assistant.io/) que **estima el consumo de gasoil** de una caldera a partir del **consumo eléctrico** medido por cualquier sensor de energía acumulada (Shelly, Sonoff, enchufe inteligente, etc.).

La idea es sencilla: una caldera de gasoil consume electricidad (bomba, quemador, ventilador...) de forma más o menos proporcional al gasoil que quema. Si dispones de un sensor de energía en kWh y de vez en cuando anotas los litros que marca el contador del depósito, la integración aprende automáticamente cuántos **litros de gasoil equivalen a cada kWh** y estima el consumo en tiempo real.

---

## ¿Qué hace?

- Calcula el **gasoil consumido acumulado estimado** (litros).
- Calibra automáticamente el ratio `L/kWh` a partir de tus lecturas manuales.
- Si indicas la **capacidad del depósito**, calcula el **gasoil restante** y el **porcentaje**.
- Permite registrar lecturas manuales del contador, incluso **con fecha pasada** (resuelve la energía histórica desde el registro de Home Assistant).

### Entidades creadas

| Entidad | Unidad | Descripción |
|---|---|---|
| `sensor.*_gasoil_consumido_estimado` | L | Gasoil total consumido estimado |
| `sensor.*_gasoil_consumido_desde_la_ultima_lectura` | L | Consumo estimado desde la última lectura manual |
| `sensor.*_ratio_gasoil` | L/kWh | Ratio de calibración activo |
| `sensor.*_ultima_lectura_manual_de_gasoil` | L | Litros de la última lectura manual |
| `sensor.*_fecha_de_la_ultima_lectura` | fecha | Marca de tiempo de la última lectura |
| `sensor.*_energia_actual` | kWh | Valor actual del sensor de energía (transparencia) |
| `sensor.*_gasoil_restante_estimado` | L | *(solo si defines capacidad)* Litros restantes |
| `sensor.*_porcentaje_estimado_del_deposito` | % | *(solo si defines capacidad)* Porcentaje restante |

---

## Requisitos previos

Necesitas un **sensor de energía acumulada en kWh** (`state_class: total_increasing`, `device_class: energy`).

- Los dispositivos Shelly/Sonoff con medición de energía ya exponen un sensor de este tipo (p. ej. `sensor.caldera_energy`).
- Si tu enchufe solo mide **potencia instantánea (W)**, crea un sensor de energía con el ayudante **«Integración - Suma de Riemann»**:
  1. *Ajustes → Dispositivos y servicios → Ayudantes → Crear ayudante → Integración - Suma de Riemann*.
  2. Selecciona tu sensor de potencia (W).
  3. Método: *trapezoidal*; unidad de tiempo: *horas* (para obtener kWh).

---

## Instalación

### Vía HACS (repositorio personalizado)

1. En HACS → *Integraciones* → menú (⋮) → **Repositorios personalizados**.
2. Añade la URL de este repositorio y selecciona la categoría **Integración**.
3. Busca «Estimador de consumo de gasoil» e instálalo.
4. **Reinicia** Home Assistant.

### Manual

1. Copia la carpeta `gasoil_consumption_estimator/` dentro de `config/custom_components/`.
2. Reinicia Home Assistant.

---

## Configuración

1. *Ajustes → Dispositivos y servicios → Añadir integración → «Estimador de consumo de gasoil»*.
2. Rellena el formulario:
   - **Sensor de energía (kWh)**: obligatorio.
   - **Nombre de la instancia**: opcional (por defecto «Estimador gasoil»).
   - **Capacidad del depósito (L)**: opcional; habilita los sensores de restante y porcentaje.
   - **Lectura inicial del contador (L)**: opcional; primera lectura del depósito.
   - **Fecha/hora de la lectura inicial**: opcional; por defecto, ahora.
   - **Ratio inicial (L/kWh)**: opcional; por defecto `0.1`. Se usa hasta tener al menos 2 lecturas.

Puedes cambiar posteriormente el sensor, el nombre, la capacidad y el ratio inicial desde **Configurar** (options flow).

---

## Uso: registrar lecturas manuales

Cada vez que anotes lo que marca el contador de gasoil, llama al servicio
`gasoil_consumption_estimator.add_manual_reading`. Cuantas más lecturas
registres, más preciso será el ratio.

### Desde la interfaz

*Ajustes → Dispositivos y servicios → Servicios → «Añadir lectura manual de gasoil»*, rellena los litros y (opcionalmente) la fecha.

### Desde YAML (por ejemplo, en un botón o automatización)

Lectura con la hora actual:

```yaml
service: gasoil_consumption_estimator.add_manual_reading
data:
  liters: 1250.0
```

Lectura con fecha pasada (se resuelve la energía histórica automáticamente):

```yaml
service: gasoil_consumption_estimator.add_manual_reading
data:
  liters: 1180.5
  timestamp: "2026-06-01T09:00:00+02:00"
```

Con varias instancias configuradas, indica cuál:

```yaml
service: gasoil_consumption_estimator.add_manual_reading
data:
  liters: 1250.0
  config_entry_id: "1a2b3c4d..."
```

### Reiniciar la calibración

Borra todas las lecturas y vuelve al ratio inicial:

```yaml
service: gasoil_consumption_estimator.reset_calibration
```

---

## ¿Cómo funciona la calibración?

Cada lectura manual guarda una pareja `(litros_gasoil, energía_kWh)`. Con dos o
más lecturas, el ratio activo se calcula como un **promedio ponderado** sobre los
tramos consecutivos en los que tanto el gasoil como la energía crecen:

```
ratio = Σ (Δ litros_gasoil) / Σ (Δ energía_kWh)
```

La estimación en cualquier instante es:

```
gasoil_estimado = última_lectura.litros
                + (energía_actual − última_lectura.kWh) × ratio_activo
```

Y, si hay capacidad de depósito definida:

```
restante   = capacidad − gasoil_estimado
porcentaje = restante / capacidad × 100
```

Mientras no haya al menos 2 lecturas, se emplea el **ratio inicial** configurado.

### Resolución de energía histórica

Si registras una lectura con fecha pasada, la integración obtiene el valor del
sensor de energía en ese momento consultando el `recorder` de Home Assistant:
primero las **estadísticas** (`statistics_during_period`) y, si no hay datos, el
**historial de estados** (`state_changes_during_period` /
`get_last_state_changes`). Si no encuentra ningún dato para esa fecha, la llamada
falla con un error explicativo en español.

---

## Notas

- El sensor `gasoil consumido estimado` usa `state_class: total_increasing`, por
  lo que puedes usarlo en el panel de energía o en tarjetas de estadísticas.
- Si el sensor de energía queda `unavailable`, la integración mantiene la última
  estimación en lugar de caer a cero.
- El ratio y las lecturas se guardan de forma persistente (`Store` de Home
  Assistant) y sobreviven a reinicios.
- La estimación es una **aproximación**: depende de que la relación
  electricidad↔gasoil de tu caldera sea razonablemente estable.
