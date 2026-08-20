# 14 — Checkpoints, reanudación y replay

El capítulo 10 mostró por qué un proceso abierto produce `SUSPENDED`. Aquí nos centramos en el artefacto que permite continuar **el mismo proceso**, no arrancar otra ejecución parecida.

## Ejemplo ejecutable suspendible

<!-- tevdoc-source: examples/docs/v31/tutorial/14_checkpoints_replay/main.tevs -->
```tevs
process Tutorial14 version "3.1.0";
authority aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa;
quantum_steps 1;
field actual = [];
label StepA = jump StepB;
label StepB = jump StepA;
entry StepA;
```

Con presupuesto 1, el primer quantum ejecuta un salto y devuelve `SUSPENDED`. El resultado contiene `next_checkpoint` y una continuation exacta.

El `case.json` de este capítulo exige `epochs=2`. Por tanto el documentation gate no se detiene en la primera suspensión: toma `first.next_checkpoint`, ejecuta un segundo quantum y vuelve a exigir `SUSPENDED`. La continuidad entre epochs forma parte del ejemplo ejecutable.

## Checkpoint inicial

La API pública crea el primer estado con:

```python
checkpoint = initial_total_core_checkpoint(program)
```

Sus propiedades esenciales son:

```text
program_hash = programa actual
field = initial_field
pc = entry_pc
next_epoch_index = 0
previous_continuation = None
halted = False
```

## Ejecutar un quantum

```python
first = run_total_core_quantum(program, checkpoint)
```

En este ejemplo `first.status == "SUSPENDED"`. El siguiente checkpoint es:

```python
checkpoint_1 = first.next_checkpoint
```

No necesitas reconstruirlo manualmente.

## Reanudar

La misma API de runtime acepta el checkpoint sucesor:

```python
second = run_total_core_quantum(program, checkpoint_1)
```

`second` pertenece al siguiente epoch y produce otra continuation ligada a la primera. Esto es exactamente lo que ejecuta el caso documental de dos epochs.

La cadena no es una lista decorativa; cada enlace verifica identidades.

## Qué liga un checkpoint

El objeto Total-Core contiene:

```text
schema
program_hash
field
pc
next_epoch_index
previous_continuation
halted
checkpoint_hash
```

El `checkpoint_hash` cubre el cuerpo canónico del checkpoint.

## Validación al reanudar

`validate_total_core_checkpoint` reconstruye la identidad esperada y exige, entre otras condiciones:

- `program_hash` exacto;
- PC dentro de la tabla;
- epoch no negativo;
- epoch 0 sin continuation previa;
- epochs posteriores con continuation inmediatamente anterior;
- `state_hash` de continuation igual a `program_hash + field_hash + pc` canónicos;
- estado halted compatible con la instrucción actual.

## No mezclar programas

Copiar un checkpoint de programa A a programa B produce `TEVS_V31_RUNTIME_CHECKPOINT_PROGRAM`, incluso aunque ambos tengan un Field visualmente parecido y el mismo número de PC.

La identidad de computation forma parte del estado reanudable.

## Checkpoint halted

Cuando un quantum termina por `halt`, el siguiente checkpoint se marca `halted=True`. Reanudarlo produce `TEVS_V31_RUNTIME_HALTED`.

Si quieres volver a ejecutar un programa terminado, debes comenzar una nueva ejecución; no fingir que es el mismo epoch continuo.

## Replay

Replay y resume son conceptos relacionados pero diferentes:

- **resume**: continúa desde el checkpoint real de una cadena;
- **replay**: repite una computación con transcripts/evidencia registrados para comprobar identidad/resultados.

Si hubo observaciones externas, un replay reproducible necesita la misma evidencia o un transcript autorizado; no puede volver a consultar el mundo y asumir que eso es «el mismo replay».

## CLI pública actual

La CLI genérica `tev-script run` puede escribir el checkpoint sucesor:

```text
tev-script run program.json --epochs 1 --checkpoint-output checkpoint.json
```

La reanudación programática está disponible en la API Python actual mediante `run_total_core_quantum`. Existe una ruta versionada de bajo nivel `cli_v31 resume-total`, pero no se documenta como comando genérico público porque `tev_script.cli` no lo registra en su superficie actual.

Esta distinción evita documentar como pública una opción que sólo existe en tooling interno/versionado.

## Checkpoint y persistencia

Persistir un checkpoint no le concede autoridad adicional. El host es responsable de almacenamiento durable, atomicidad del archivo, acceso y recuperación; el contenido semántico sigue validándose al cargarlo.

## Cadena conceptual

```text
program + checkpoint_0
      ↓ quantum 0
result_0 + continuation_0 + checkpoint_1
      ↓ quantum 1
result_1 + continuation_1 + checkpoint_2
      ↓ ...
```

Cada tramo es finito y auditable.

## Fallos que debes probar

- hash de checkpoint alterado;
- program hash sustituido;
- continuation de otro epoch;
- state hash incoherente;
- `halted=True` en PC no-halt;
- intento de resumir halted;
- PC fuera del programa.

## Autoridad técnica

- `tev_script/runtime_v5_total.py`.
- `tev_script/omega_kernel_v1.py`.
- `spec/TEV_SCRIPT_V31_TOTAL_CORE.md`.
- `spec/TEV_SCRIPT_RUNTIME_CHECKPOINT_V2.md` para el dominio histórico de checkpoints.
