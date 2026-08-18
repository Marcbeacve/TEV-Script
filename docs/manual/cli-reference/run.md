# `tev-script run`

## Sinopsis

```text
tev-script run PROGRAM_IR [--checkpoint-output PATH] [--epochs N]
```

## Propósito

Ejecuta Program IR V5 Total-Core ya compilado y validado. `run` no recibe `.tevs`: la separación fuente→IR→runtime es una frontera deliberada de la plataforma.

## Argumentos

`PROGRAM_IR` es un objeto JSON canónico compatible con el runtime Total-Core actual.

## Opciones

`--checkpoint-output PATH` escribe el checkpoint canónico resultante tras la ejecución.

`--epochs N` solicita cuántos epochs ejecutar. El valor por defecto es `1`; la CLI actual admite enteros entre `1` y `1_000_000`. Cada epoch sigue ejecutando un quantum finito definido por el programa.

## stdout

En éxito de la operación de runtime emite `TEV_SCRIPT_V31_RUN_TOTAL_RESULT_V1` con campos como:

```text
status
program_ir_hash
source_semantic_hash
epochs_executed
last_epoch_index
continuation_hash
field_hash
checkpoint_hash
checkpoint_output
```

`status` describe el estado del proceso (`HALTED` o continuidad acotada según el programa), no el exit code del proceso de shell.

## stderr

Un IR/checkpoint inválido produce diagnóstico o error estructurado; un hash incompatible no se corrige heurísticamente.

## Exit codes

```text
0  la solicitud de runtime se ejecutó y produjo un resultado estructurado
2  IR/checkpoint inválido, parámetros fuera de contrato o fallo de host/IO
```

Un resultado no terminado puede seguir tener exit code `0` si el quantum/epoch se ejecutó correctamente y el estado de continuación está representado explícitamente.

## Ejemplo positivo

```text
tev-script run first-program.json
```

El primer caso documental espera `status = HALTED` en un epoch.

## Checkpoint

```text
tev-script run program.json --epochs 4 --checkpoint-output checkpoint.json
```

El checkpoint resultante está ligado a la identidad del programa y al estado canónico. No es un archivo de estado genérico intercambiable entre programas.

## Ejemplo negativo

```text
tev-script run program.json --epochs 0
```

falla porque `0` está fuera del rango admitido.

## Versión/perfil

```text
runtime ABI = v5-total-v1
profile     = total_core
```

## Relacionado

- [`compile.md`](compile.md)
- [`../versions/version-domains.md`](../versions/version-domains.md)
