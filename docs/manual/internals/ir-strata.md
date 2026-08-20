# Estratos de IR: V2, V3, V4 y V5

Los números de IR en TEVScript reflejan evolución de contratos, no una obligación de convertir todo artefacto antiguo al último número.

## Visión resumida

```text
V0.2/V1 source
   ↓ linked/lowering
Program IR V2 / V3

V2 source 2.0.0
   ↓
Program IR V4
   ├─ pure
   ├─ recursive
   └─ effects

V3 semantic process 3.0.0
   ↓
Program IR V5 Semantic Process

3.1 Total-Core
   ↓
Program IR V5 Total-Core
   └─ embeds exact Program IR V4 units
```

## Program IR V2

Pertenece a la línea linked/lowering V1. Se conserva por compatibilidad, receipts de lowering y conformance histórica.

No es la raíz current de 3.1.

## Program IR V3

Amplía el modelo portable histórico con tipos/values/runtime/checkpoint V3. `tev_script.__all__` conserva API pública de compatibilidad para value encode/decode, validator, conformance y runtime.

## Program IR V4

Es la autoridad ejecutable de children V2 actuales.

Profiles:

```text
TEV_SCRIPT_PROGRAM_IR_V4_PURE_V1
TEV_SCRIPT_PROGRAM_IR_V4_RECURSIVE_V1
TEV_SCRIPT_PROGRAM_IR_V4_EFFECTS_V1
```

Algunos subprofiles effects/commands pueden evolucionar con schema propios versionados, pero Total-Core actual exige la correspondencia admitida por su validator.

## Program IR V5 Semantic Process

Schema histórico/current-compatible de V3:

```text
TEV_SCRIPT_PROGRAM_IR_V5_SEMANTIC_PROCESS_V1
language_version = 3.0.0
profile = semantic_process
```

No puede presentarse como Total-Core sólo cambiando discriminadores.

## Program IR V5 Total-Core

Schema current:

```text
TEV_SCRIPT_PROGRAM_IR_V5_TOTAL_CORE_V1
language_version = 3.1.0
profile = total_core
```

Añade V4 units, proof admissions y `invoke_v4` sobre la base Field/Transformation/control.

## Por qué V4 vive dentro de V5

V4 ya cierra computación pure/recursive/effects. Reimplementar esas semánticas en V5 crearía duplicación y riesgo de divergencia.

V5 actúa como **orquestador semántico** y valida que cada child sea exactamente un V4 conforme.

## No hay reinterpretación

Regla aditiva:

```text
validator del artefacto original sigue siendo autoridad
```

Por ello:

- V3 IR no se valida con V5 Total validator;
- V4 child se valida primero como V4;
- V5 no reescribe operators/types internos del child.

## Version domains separados

No confundas:

```text
language_version
source_profile
program_ir version/profile
runtime ABI
checkpoint
package
```

El package 3.1.2 distribuye un lenguaje 3.1.0 con Program IR V5 root; esos números no deben sincronizarse artificialmente.

## Evolución segura

Una nueva generación debería responder antes de publicarse:

- ¿es additive o breaking?
- ¿qué validator conserva autoridad sobre predecessors?
- ¿qué schema discrimina el nuevo artefacto?
- ¿qué conversiones existen y con qué receipts?
- ¿qué runtime targets deben tener conformance?

## Debugging de schema mismatch

Si un unit profile `pure` recibe schema recursive/effects, falla en la frontera de unidad. No modifiques el discriminador JSON; recompila con el frontend/profile correcto.

## Autoridades

- `schemas/`
- `spec/TEV_SCRIPT_PROGRAM_IR_V4.md`
- `spec/TEV_SCRIPT_PROGRAM_IR_V5_SEMANTIC_PROCESS.md`
- `spec/TEV_SCRIPT_V31_TOTAL_CORE.md`
- `tev_script/program_ir_v4.py`
- `tev_script/program_ir_v5_total.py`
