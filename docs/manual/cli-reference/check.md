# `tev-script check`

## Sinopsis

```text
tev-script check SOURCE [--unit NAME=PATH ...] [--effect-input NAME=JSON ...] [--proof-admission JSON ...]
```

## Propósito

Comprueba un proyecto Total-Core 3.1 sin escribir Program IR. La ruta pública delega en el mismo frontend Total-Core que usa `compile`, de modo que `check` no es un parser ligero con semántica distinta.

## Argumentos

`SOURCE` es el archivo `.tevs` raíz del proceso Total-Core.

## Opciones

`--unit NAME=PATH` puede repetirse. Suministra la fuente de una unidad V4 declarada en el proceso raíz. El conjunto de nombres debe coincidir exactamente con las unidades declaradas.

`--effect-input NAME=JSON` puede repetirse. Suministra evidencia/input externo para una unidad `effects`. No convierte ese JSON en semántica de fuente.

`--proof-admission JSON` puede repetirse. Suministra una proof admission externa validable. La fuente no puede auto-concedérsela.

## Archivos aceptados

```text
SOURCE                 fuente Total-Core 3.1 UTF-8
--unit PATH            fuente V2 de la unidad hija
--effect-input JSON    objeto JSON estricto para unidad effects
--proof-admission JSON objeto de proof admission validable
```

## stdout

En éxito emite `TEV_SCRIPT_V31_CHECK_TOTAL_RESULT_V1` con campos como:

```text
status = PASS
language_version = 3.1.0
profile = total_core
program_ir_schema
program_ir_hash
source_semantic_hash
```

Aunque se construye el programa para validarlo, `check` no escribe el artefacto de Program IR.

## stderr

Un error de lenguaje se emite como `TEV_SCRIPT_V31_DIAGNOSTIC_V1` e incluye:

```text
diagnostic.code
diagnostic.message
diagnostic.span
diagnostic.hint
```

Los errores de host/IO se distinguen mediante `TEV_SCRIPT_V31_HOST_IO_ERROR_V1`.

## Exit codes

```text
0  comprobación correcta
2  diagnóstico de fuente, error de host/IO o uso inválido de argumentos
```

## Ejemplo positivo

```text
tev-script check examples/docs/v31/getting_started/01_first/main.tevs
```

Con una unidad pura:

```text
tev-script check main.tevs --unit Calc=calc.tevs
```

## Ejemplo negativo

Una raíz que declara `unit Calc profile pure;` pero se ejecuta sin `--unit Calc=...` falla cerrado por discrepancia del conjunto de unidades. También falla suministrar una unidad extra no declarada.

## Versión/perfil

```text
language = 3.1.0
profile  = total_core
```

## Relacionado

- [`compile.md`](compile.md)
- [`run.md`](run.md)
- [`../getting-started/project-layout.md`](../getting-started/project-layout.md)
