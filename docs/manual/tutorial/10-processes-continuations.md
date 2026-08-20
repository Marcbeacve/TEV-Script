# 10 — Procesos, quanta, checkpoints y continuaciones

Un proceso que conceptualmente vive durante horas o años no obliga a que una llamada al runtime sea infinita. Total-Core representa la computación abierta como una cadena de **quanta finitos** ligados por checkpoints y continuations.

Este capítulo usa deliberadamente un proceso que nunca alcanza `halt` dentro de su grafo de control. El runtime debe suspenderlo limpiamente al agotar el quantum.

## Ejemplo ejecutable: ciclo acotado

<!-- tevdoc-source: examples/docs/v31/tutorial/10_processes_continuations/main.tevs -->
```tevs
process Tutorial10 version "3.1.0";
authority aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa;
quantum_steps 2;
field actual = [];
label LoopA = jump LoopB;
label LoopB = jump LoopA;
entry LoopA;
```

El caso documental ejecuta **un quantum** y exige:

```text
status = SUSPENDED
```

No se acepta «el test se quedó colgado» como implementación de procesos abiertos.

## Quantum

`quantum_steps 2` fija el máximo de instrucciones V5 que puede consumir un quantum. En el ejemplo:

```text
LoopA → LoopB   paso 1
LoopB → LoopA   paso 2
```

Se agota el presupuesto y el resultado es `SUSPENDED` con `pc` de continuación en el estado alcanzado.

## `SUSPENDED` no es error

La suspensión es un resultado operacional normal. Significa: «este tramo finito terminó y la computación tiene continuación válida».

Es diferente de:

- `HALTED`: el programa alcanzó una instrucción halt;
- fallo de validación: el artefacto/estado era inválido;
- excepción del host: problema fuera del contrato portable.

## Checkpoint

El checkpoint Total-Core liga como mínimo:

```text
program_hash
Field actual
pc
next_epoch_index
previous_continuation
halted
checkpoint_hash
```

El primer checkpoint usa `next_epoch_index = 0` y no tiene continuación previa.

## Epoch

Cada quantum posee una identidad de epoch ligada a:

- índice de epoch;
- `program_hash`/computation identity;
- hash del estado de entrada;
- `authority_hash`;
- continuación anterior cuando existe.

Así dos ejecuciones que llegan casualmente al mismo número de PC pero pertenecen a programas o cadenas diferentes no se confunden.

## Continuation receipt

Al finalizar el quantum, el runtime produce una continuation que liga el resultado y el estado alcanzado. El siguiente checkpoint incorpora esa continuación como `previous_continuation`.

La cadena conceptual es:

```text
Checkpoint 0
   ↓ quantum / epoch 0
Continuation 0
   ↓
Checkpoint 1
   ↓ quantum / epoch 1
Continuation 1
   ↓
Checkpoint 2
   ...
```

## Integridad al reanudar

No basta con construir un objeto parecido a un checkpoint. La validación comprueba, entre otras cosas:

- mismo `program_hash`;
- PC dentro del programa;
- índice de epoch coherente;
- continuation inmediatamente anterior;
- `state_hash` de la continuation igual al estado del checkpoint;
- `checkpoint_hash` exacto.

## Estado halted

Si un checkpoint está marcado `halted=True`, su PC debe señalar una instrucción `halt`, y ese checkpoint no puede reanudarse. Reejecutar un programa terminado no es lo mismo que continuar el mismo proceso.

## Recursos por quantum

El receipt registra consumo relevante, incluido número de instrucciones V5 y pasos de evaluación V4 de unidades hijas. El límite V5 no borra el coste hijo: ambos se contabilizan en dominios distintos.

## Observaciones y efectos

La continuation también liga hashes de observaciones/efectos relevantes. Esto evita que una reanudación desconecte silenciosamente la historia causal/observacional que produjo el estado.

## Proceso abierto no es divergencia oculta

La arquitectura permite representar servicios, agentes o simulaciones persistentes sin introducir una instrucción «ejecuta para siempre». Cada tramo es finito, medible y puede producir evidencia.

Esto permite al host decidir explícitamente cuándo ejecutar el siguiente quantum, aplicar políticas de recursos o persistir el checkpoint.

## Replay

Una cadena de checkpoints/receipts permite comparar ejecuciones y reconstruir qué identidad de programa/estado produjo cada epoch. Replay no significa ignorar evidencia externa: cuando existen observaciones, deben reutilizarse o verificarse bajo su contrato.

## Fallos esperables

- `quantum_steps` fuera de rango;
- PC fuera de la tabla;
- checkpoint de otro programa;
- epoch que no sigue al anterior;
- continuation cuyo `state_hash` no coincide;
- checkpoint halted apuntando a una instrucción no-halt;
- intento de reanudar un checkpoint halted;
- manipulación del hash del checkpoint/continuation.

## Regla práctica

Diseña procesos largos como una sucesión explícita de estados reanudables. Si una operación individual necesita tiempo ilimitado para ser correcta, todavía no está dentro del modelo acotado de Total-Core.

## Autoridad técnica

- `spec/TEV_SCRIPT_V31_TOTAL_CORE.md`, límites y open computation.
- `tev_script/runtime_v5_total.py`.
- `tev_script/omega_kernel_v1.py` para identidades/continuations.
- `spec/TEV_SCRIPT_RUNTIME_CHECKPOINT_V2.md` para continuidad histórica de checkpoint concepts.
