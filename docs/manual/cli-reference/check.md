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

`--unit NAME=PATH` puede repetirse. Suministra la ruta de la fuente de una unidad V4 declarada en el proceso raíz. El conjunto de nombres debe coincidir exactamente con las unidades declaradas.

`--effect-input NAME=JSON` puede repetirse. Aquí `JSON` representa una **ruta a un archivo JSON**, no un objeto JSON inline. El archivo suministra evidencia/input externo para una unidad `effects`; la CLI lo carga como strict JSON antes de compilar.

`--proof-admission JSON` puede repetirse. También aquí `JSON` es una **ruta a un archivo JSON**. Cada archivo debe contener una proof admission externa validable; la fuente no puede auto-concedérsela.

Los metavars `PATH` y `JSON` describen el tipo de archivo esperado por la interfaz humana. En ambos argumentos JSON, el valor de línea de comandos sigue siendo un path del host.

## Archivos aceptados

```text
SOURCE                         ruta a fuente Total-Core 3.1 UTF-8
--unit NAME=PATH               ruta a fuente V2 de la unidad hija
--effect-input NAME=JSON       NAME=ruta a archivo strict JSON para unidad effects
--proof-admission JSON         ruta a archivo JSON de proof admission validable
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

Con una unidad `effects` cuya evidencia está en un archivo:

```text
tev-script check main.tevs \
  --unit Sensors=sensors.tevs \
  --effect-input Sensors=effects.json
```

Con una proof admission serializada:

```text
tev-script check main.tevs --proof-admission proof-a.json
```

No uses una forma inline como `--effect-input Sensors={...}`: la implementación interpreta el lado derecho como una ruta y después carga ese archivo.

## Ejemplo negativo

Una raíz que declara `unit Calc profile pure;` pero se ejecuta sin `--unit Calc=...` falla cerrado por discrepancia del conjunto de unidades. También falla suministrar una unidad extra no declarada.

Una ruta JSON inexistente, JSON no estricto o un objeto con contrato incorrecto falla en la frontera host/validator correspondiente; no se sustituye por datos ambientales.

## Versión/perfil

```text
language = 3.1.0
profile  = total_core
```

## Relacionado

- [`compile.md`](compile.md)
- [`run.md`](run.md)
- [`../getting-started/project-layout.md`](../getting-started/project-layout.md)
