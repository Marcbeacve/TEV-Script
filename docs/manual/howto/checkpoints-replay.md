# Cómo trabajar con checkpoints y replay

## Objetivo

Ejecutar un proceso por quanta, conservar su estado reanudable y distinguir **resume** de **replay**.

## 1. Diseña un proceso suspendible

Ejemplo:

```text
process Loop version "3.1.0";
authority aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa;
quantum_steps 1;
field actual = [];
label A = jump B;
label B = jump A;
entry A;
```

Cada quantum ejecuta un salto y devuelve `SUSPENDED`.

## 2. Compila

```powershell
tev-script compile .\loop.tevs -o .\loop.json
```

## 3. Guarda el checkpoint desde CLI

```powershell
tev-script run .\loop.json `
  --epochs 1 `
  --checkpoint-output .\checkpoint-1.json
```

La CLI pública puede materializar el checkpoint sucesor.

## 4. Reanuda desde Python API

La API pública opera con objetos validados en memoria:

```python
from tev_script import (
    initial_total_core_checkpoint,
    run_total_core_quantum,
)

checkpoint = initial_total_core_checkpoint(program)
first = run_total_core_quantum(program, checkpoint)
assert first.status == "SUSPENDED"

second = run_total_core_quantum(program, first.next_checkpoint)
```

`second` pertenece al siguiente epoch y queda ligado a `first.continuation`.

## 5. Persistencia JSON

La CLI versionada posee loader/serializer de checkpoints para su comando interno `resume-total`, pero la CLI genérica current no publica `resume` como subcomando. Si necesitas persistencia/reload desde una integración pública, usa el adapter/API de tu deployment y valida el objeto contra `validate_total_core_checkpoint` antes de ejecutarlo.

No presentes `cli_v31 resume-total` como si fuera parte de `tev-script` público.

## 6. No construyas un checkpoint a mano para saltarte estado

Debe ligar:

```text
program_hash
field
pc
next_epoch_index
previous_continuation
halted
checkpoint_hash
```

Cambiar PC/Field/epoch obliga a otra identidad; no basta recalcular un JSON casual.

## 7. Resume ≠ replay

**Resume** continúa una cadena real desde el estado producido.

**Replay** repite una ejecución usando los mismos artefactos y, cuando hubo observaciones, transcripts/evidence fijados. Su objetivo es comprobar reproducibilidad/identidad, no avanzar el proceso original.

## 8. Observaciones durante replay

Si una unidad effects consultó un sensor, volver a leer el sensor hoy no es replay de ayer. Debes utilizar el scenario/transcript registrado o un mecanismo de verificación explícito.

## 9. Checkpoint halted

Si el resultado fue `HALTED`, `next_checkpoint.halted` es true y no puede reanudarse. Iniciar otra ejecución requiere un checkpoint inicial nuevo.

## 10. Errores frecuentes

```text
TEVS_V31_RUNTIME_CHECKPOINT_PROGRAM
  checkpoint de otro root

TEVS_V31_RUNTIME_CHECKPOINT_EPOCH
  cadena de epoch inválida

TEVS_V31_RUNTIME_CHECKPOINT_STATE
  continuation y Field/PC no coinciden

TEVS_V31_RUNTIME_HALTED
  intento de continuar un programa terminado
```

## 11. Persistencia durable

El contenido de checkpoint es semántico, pero escribirlo a disco es operación del host. Si necesitas garantía de atomicidad/durabilidad, úsala en el adapter de almacenamiento; no la infieras del checkpoint hash.

## Referencia

- `docs/manual/tutorial/10-processes-continuations.md`
- `docs/manual/tutorial/14-checkpoints-replay.md`
- `tev_script/runtime_v5_total.py`
