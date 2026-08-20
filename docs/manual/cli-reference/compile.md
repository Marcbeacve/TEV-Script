# `tev-script compile`

## Sinopsis

```text
tev-script compile SOURCE [--unit NAME=PATH ...] [--effect-input NAME=JSON ...] [--proof-admission JSON ...] --output PROGRAM_IR
```

También puedes usar `-o` como alias de `--output`.

## Propósito

Compila una raíz Total-Core 3.1 a Program IR V5 canónico. Usa la misma validación de proyecto que `check`, pero además persiste el artefacto resultante mediante reemplazo atómico de una única ruta.

## Argumentos

`SOURCE` es la ruta de la fuente `.tevs` raíz.

## Opciones

`--unit NAME=PATH`, `--effect-input NAME=JSON` y `--proof-admission JSON` tienen el mismo contrato de rutas que en [`check.md`](check.md): `PATH` apunta a una fuente hija y cada metavar `JSON` representa una ruta a un archivo JSON que la CLI carga/valida; no es JSON inline.

`--output PROGRAM_IR` / `-o PROGRAM_IR` es obligatorio y selecciona la ruta del artefacto de salida.

## Archivos aceptados

La entrada de proyecto sigue el mismo contrato de `check`. La salida es Program IR V5 Total-Core canónico serializado como JSON.

Ejemplo con evidencia `effects` persistida en archivo:

```text
tev-script compile main.tevs \
  --unit Sensors=sensors.tevs \
  --effect-input Sensors=effects.json \
  --proof-admission proof-a.json \
  -o program.json
```

## stdout

En éxito emite `TEV_SCRIPT_V31_COMPILE_TOTAL_RESULT_V1` con campos como:

```text
status = PASS
language_version = 3.1.0
profile = total_core
program_ir_schema
program_ir_hash
source_semantic_hash
output
artifact_commit
```

`artifact_commit` identifica la política de escritura atómica usada por esta superficie.

## stderr

Los diagnósticos de fuente usan `TEV_SCRIPT_V31_DIAGNOSTIC_V1`. Los fallos de host/IO se mantienen separados.

## Exit codes

```text
0  compilación y escritura correctas
2  diagnóstico, fallo de host/IO o argumentos inválidos
```

## Ejemplo positivo

```text
tev-script compile examples/docs/v31/getting_started/01_first/main.tevs --output first-program.json
```

Con una unidad V4:

```text
tev-script compile main.tevs --unit Calc=calc.tevs -o program.json
```

## Ejemplo negativo

Si `SOURCE` declara una unidad `effects` y falta su `--effect-input` obligatorio, la compilación falla. El compilador no inventa ni reutiliza evidencia ambiental implícita.

Pasar `--effect-input Sensors={...}` tampoco introduce JSON inline: esa cadena se interpreta como una ruta de archivo y fallará si no existe un archivo con ese nombre.

## Identidad canónica

El artefacto generado incluye su identidad de programa y el `source_semantic_hash`. Un runtime posterior valida el IR recibido; no confía sólo en el nombre del archivo.

## Versión/perfil

```text
language = 3.1.0
profile  = total_core
Program IR = 5
```

## Relacionado

- [`check.md`](check.md)
- [`run.md`](run.md)
