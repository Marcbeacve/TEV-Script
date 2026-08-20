# Embedding avanzado: `task_strategy`

`run_total_core_quantum` expone un parámetro avanzado:

```python
run_total_core_quantum(
    program,
    checkpoint,
    *,
    task_strategy=None,
)
```

Su propósito es permitir que un host cambie **cómo materializa la ejecución de grupos de tareas V4 puras** sin cambiar la semántica TEVScript, los resultados canónicos ni el accounting que el runtime valida.

Para la mayoría de integraciones debes dejar:

```python
task_strategy=None
```

`None` usa la evaluación secuencial de referencia y evita introducir una política de scheduling del host que no necesitas.

## Frontera de estabilidad

El tipo estructural que describe la operación básica vive en:

```text
tev_script.ir_v4_pure.TaskScopeExecutionStrategyV4
```

pero `TaskScopeExecutionStrategyV4` **no se exporta desde `tev_script.__all__`**. Por tanto:

- `task_strategy` sí forma parte de la firma pública actual de `run_total_core_quantum`;
- el protocolo V4 que usa internamente es una superficie avanzada/versionada del módulo `ir_v4_pure`;
- no debes presentar `TaskScopeExecutionStrategyV4` como uno de los símbolos estables importables desde `tev_script`;
- una futura evolución del scheduling V4 puede requerir revisar un adapter que dependa directamente de este protocolo.

Esta separación evita ampliar artificialmente la API root sólo porque exista un hook especializado.

## Contrato mínimo de `TASK_SCOPE` y `TASK_DAG`

El protocolo V4 define conceptualmente:

```text
run(tasks, evaluate_child)
```

con la forma:

```python
class TaskScopeExecutionStrategyV4(Protocol):
    def run(self, tasks, evaluate_child): ...
```

`tasks` es la secuencia de tareas admitida por el IR. `evaluate_child(task)` es la autoridad semántica para evaluar una tarea concreta y devuelve el `TaskChildEvaluationV4` validado por el runtime.

Una estrategia custom puede decidir cuándo invocar `evaluate_child`, incluso usar infraestructura propia del host, pero el resultado devuelto debe conservar exactamente:

```text
mismo conjunto de nombres de tarea
mismo tipo de resultado por tarea
un resultado por cada tarea requerida
accounting de evaluation_steps válido
accounting de bounded_loop_iterations válido
```

Para `TASK_DAG`, la estrategia sólo recibe la **wave actualmente ready**. No puede ejecutar por adelantado una tarea cuyas dependencias todavía no estén satisfechas.

El runtime vuelve a validar el conjunto recibido. Una estrategia que omite, duplica, renombra o fabrica resultados falla cerrado mediante los diagnósticos V4 de task strategy.

## La estrategia no es autoridad semántica

El objeto suministrado no recibe permiso para redefinir:

- el AST/IR de la tarea;
- los tipos TEV;
- el resultado canónico;
- las dependencias de `TASK_DAG`;
- las políticas `join`/cancellation fijadas por el IR;
- los límites de pasos;
- el Field V5;
- las continuations/checkpoints Total-Core.

Su papel es de **realización/scheduling**, no de semántica.

Una implementación que ejecute trabajo concurrentemente sigue obligada a devolver una observación equivalente al contrato determinista. El scheduling físico del host no puede convertirse en una nueva fuente de significado.

## Ejemplo mínimo de estrategia

Una estrategia puede reutilizar completamente la evaluación autoritativa que recibe:

```python
class HostTaskStrategy:
    def run(self, tasks, evaluate_child):
        completed = []
        for task in tasks:
            completed.append(evaluate_child(task))
        return completed
```

Este ejemplo no aporta paralelismo; sólo muestra la frontera correcta. Una implementación concurrente tendría que preservar las mismas invariantes y el mismo accounting observable.

No construyas manualmente `TaskChildEvaluationV4` cuando puedes devolver los objetos producidos por `evaluate_child`. Así evitas duplicar validación o fabricar receipts de evaluación.

## `PRIORITY_SELECT`

`PRIORITY_SELECT` tiene una semántica distinta: el orden de prioridad forma parte del contrato. Por ello el runtime no reutiliza ciegamente `run(tasks, evaluate_child)`.

Si el objeto `task_strategy` no implementa hooks de selección, el runtime usa la ruta secuencial de referencia.

Opcionalmente detecta por estructura:

```text
run_select
run_select_cooperative
```

Estos nombres no forman parte del `Protocol` mínimo y deben tratarse como extensión avanzada del runtime V4 actual.

### `run_select`

La ruta legacy recibe los candidatos indexados y una función `evaluate_candidate`. Debe devolver el conjunto **completo** de outcomes y conservar los índices canónicos `0..N-1`.

Cada outcome debe ser un `PrioritySelectCandidateOutcomeV4` coherente:

```text
index correcto
result XOR error
evaluation_steps >= 0
bounded_loop_iterations >= 0
```

La estrategia no puede hacer que un candidato de prioridad inferior gane si uno anterior es semánticamente terminal.

### `run_select_cooperative`

La ruta cooperativa recibe, además, una función de evaluación con `cancel_check` y un predicado `outcome_is_terminal`.

Puede dejar de materializar candidatos inferiores **sólo cuando el prefijo ya contiene un outcome semánticamente terminal**. El runtime exige que los outcomes devueltos formen el prefijo canónico `0..k` sin huecos.

Una cancelación puramente operacional de trabajo especulativo no puede hacerse visible como resultado semántico del programa.

## Dónde se aplica en Total-Core

`run_total_core_quantum` propaga `task_strategy` a la ejecución de unidades V4. El hook afecta a las construcciones puras que usan structured concurrency/selection; no cambia la máquina V5 de:

```text
apply
branch_fact
jump
invoke_v4
halt
```

Tampoco concede autoridad física a una unidad `effects`.

## Cuándo usarlo

Úsalo sólo si tu embedding necesita controlar la realización de tareas, por ejemplo para:

- integrar un scheduler del host;
- experimentar con ejecución concurrente conservando equivalencia semántica;
- instrumentar scheduling sin modificar el IR;
- implementar una estrategia de selección cooperativa compatible con el contrato V4.

Si sólo quieres ejecutar TEVScript correctamente, usa `task_strategy=None`.

## Fallos que una implementación custom debe probar

- falta una tarea en la respuesta;
- aparece un nombre adicional o duplicado;
- un child devuelve tipo incorrecto;
- accounting negativo o incoherente;
- una wave DAG contiene una tarea no ready;
- `run_select` devuelve menos outcomes de los requeridos;
- un outcome cambia su índice;
- un outcome contiene simultáneamente `result` y `error`;
- la ruta cooperativa corta antes de un outcome terminal;
- una cancelación operacional se filtra a la semántica.

## Autoridad técnica

- `tev_script/runtime_v5_total.py` — firma pública y propagación del hook.
- `tev_script/ir_v4_pure.py` — `TaskScopeExecutionStrategyV4`, `TaskChildEvaluationV4`, `PrioritySelectCandidateOutcomeV4` y validación de `TASK_SCOPE`, `TASK_DAG` y `PRIORITY_SELECT`.
- `spec/TEV_SCRIPT_PROGRAM_IR_V4.md` — semántica Program IR V4.
- [`current-total-core.md`](current-total-core.md) — API Python Total-Core estable exportada desde el paquete raíz.
