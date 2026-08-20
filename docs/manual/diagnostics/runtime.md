# Diagnósticos de runtime Total-Core 3.1

Esta página documenta los **28 códigos `TEVS_V31_RUNTIME_*`** emitidos por `tev_script/runtime_v5_total.py`. Se aplican a checkpoints, proof admission durante Apply, ejecución de unidades y validación del resultado de cada quantum.

## Valores y Program Counter

| Código | Significado / trigger | Corrección |
|---|---|---|
| `TEVS_V31_RUNTIME_HASH` | Se esperaba un hash hexadecimal de 64 caracteres. | Usar la identidad canónica exacta requerida. |
| `TEVS_V31_RUNTIME_PC` | Un PC no es un entero válido o no satisface la forma esperada. | Usar un índice entero válido del programa. |

## Checkpoints

| Código | Significado / trigger | Corrección |
|---|---|---|
| `TEVS_V31_RUNTIME_CHECKPOINT_PC` | El checkpoint apunta fuera de la tabla de instrucciones. | Restaurar un checkpoint ligado al programa correcto. |
| `TEVS_V31_RUNTIME_CHECKPOINT_EPOCH` | `next_epoch_index` es inválido. | Conservar el contador de epoch canónico no negativo. |
| `TEVS_V31_RUNTIME_CHECKPOINT_HALTED` | El flag `halted` es incompatible con el PC/instrucción actual. | No marcar como terminado un checkpoint que no está en `halt`. |
| `TEVS_V31_RUNTIME_CHECKPOINT_PREVIOUS` | La continuación previa no cumple el contrato del epoch. | Preservar exactamente el continuation hash anterior o `None` en epoch cero. |
| `TEVS_V31_RUNTIME_CHECKPOINT_STATE` | Field/PC/continuación no representan el mismo estado canónico. | Restaurar el checkpoint completo, no mezclar campos de ejecuciones distintas. |
| `TEVS_V31_RUNTIME_CHECKPOINT` | Valor de checkpoint de tipo/forma inválida. | Usar `TotalCoreCheckpointV1`. |
| `TEVS_V31_RUNTIME_CHECKPOINT_PROGRAM` | `program_hash` del checkpoint no coincide con el programa. | Usar un checkpoint capturado para ese Program IR exacto. |
| `TEVS_V31_RUNTIME_CHECKPOINT_HASH` | `checkpoint_hash` no coincide con el contenido. | No editar el checkpoint; regenerarlo desde el runtime. |

## Invocación de unidades V4 y puente a Field

| Código | Significado / trigger | Corrección |
|---|---|---|
| `TEVS_V31_RUNTIME_UNIT_PROFILE` | El runtime encuentra una unidad con perfil no soportado/incoherente. | Revalidar/recompilar la unidad V4 y el programa V5. |
| `TEVS_V31_RUNTIME_BRIDGE_APPLY` | La Transformation derivada que proyecta el resultado V4 al Field no puede aplicarse correctamente. | Corregir el artefacto/estado que viola el contrato del puente; no saltarse Apply. |

## Proof admission en runtime

| Código | Significado / trigger | Corrección |
|---|---|---|
| `TEVS_V31_RUNTIME_PROOF_REQUIRED` | Apply requiere una proof admission que no está disponible. | Suministrar/admitir la evidencia requerida antes de ejecutar esa transformación. |
| `TEVS_V31_RUNTIME_PROOF_STATUS` | Una admission encontrada no está en estado `VERIFIED`. | Usar sólo evidence admission verificada. |
| `TEVS_V31_RUNTIME_PROOF_AUTHORITY` | La authority de la proof admission no coincide con la authority del programa. | Verificar/admitir la prueba bajo la misma autoridad exacta. |
| `TEVS_V31_RUNTIME_PROOF_APPLY` | La proof admission no satisface el requirement que intenta resolver durante Apply. | Corregir el binding requirement→admission. |

## Construcción del resultado de quantum

| Código | Significado / trigger | Corrección |
|---|---|---|
| `TEVS_V31_RUNTIME_STATUS` | Estado distinto de `HALTED` o `SUSPENDED`. | Usar sólo estados normativos del quantum. |
| `TEVS_V31_RUNTIME_STEPS` | `steps_used` no cumple los límites/invariantes del quantum. | Conservar el contador producido por el runtime. |
| `TEVS_V31_RUNTIME_V4_STEPS` | Métrica de pasos V4 inválida. | No mezclar/recalcular manualmente métricas de la unidad hija. |
| `TEVS_V31_RUNTIME_CONTINUATION_RESULT` | La continuation es incompatible con el resultado/estado. | Preservar la continuación generada por el quantum. |
| `TEVS_V31_RUNTIME_CONTINUATION_STATE` | La continuación no liga exactamente Field/PC/epoch esperado. | No combinar continuación y estado de receipts diferentes. |
| `TEVS_V31_RUNTIME_CHECKPOINT_CONTINUATION` | El checkpoint siguiente no referencia la continuation del resultado. | Usar `next_checkpoint` generado por ese mismo quantum. |
| `TEVS_V31_RUNTIME_CHECKPOINT_STATUS` | `halted` del checkpoint siguiente no coincide con `HALTED/SUSPENDED`. | Mantener consistencia entre result status y checkpoint. |

## Ejecución

| Código | Significado / trigger | Corrección |
|---|---|---|
| `TEVS_V31_RUNTIME_HALTED` | Se intenta ejecutar un checkpoint que ya está terminado. | No reanudar `HALTED`; iniciar otra ejecución o usar el último resultado como final. |
| `TEVS_V31_RUNTIME_APPLY_OPEN` | Apply deja una obligación abierta que el quantum no puede considerar cerrada. | Resolver los requisitos/evidencia antes de continuar. |

## Validación del resultado wire

| Código | Significado / trigger | Corrección |
|---|---|---|
| `TEVS_V31_RUNTIME_RESULT` | El valor recibido no es un `TotalCoreQuantumResultV1` válido. | Usar el resultado real del runtime o su forma wire exacta. |
| `TEVS_V31_RUNTIME_RESULT_PROGRAM` | El resultado pertenece a otro `program_hash`. | Validarlo contra el programa que lo produjo. |
| `TEVS_V31_RUNTIME_RESULT_HASH` | `quantum_hash`/identidad final no coincide con el contenido. | Reejecutar/reconstruir; no parchear hashes. |

## Regla de interpretación

`SUSPENDED` no es un error. Significa que el quantum finito terminó con continuidad explícita. Un diagnóstico `TEVS_V31_RUNTIME_*`, en cambio, indica que una entrada, evidencia o relación interna no satisface el contrato del runtime.

Relacionado: [`../cli-reference/run.md`](../cli-reference/run.md), [`../library-reference/current-total-core.md`](../library-reference/current-total-core.md) y `spec/TEV_SCRIPT_V31_TOTAL_CORE.md`.
