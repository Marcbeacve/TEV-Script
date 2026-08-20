# `tev-script descriptor`

## Sinopsis

```text
tev-script descriptor
```

## Propósito

Emite el descriptor estructurado del perfil Total-Core 3.1 actual. A diferencia de `describe`, que resume la plataforma pública, `descriptor` expone metadatos del lenguaje/runtime Total-Core como versión de lenguaje, perfiles, base semántica y fronteras de proof/effects.

## Argumentos y opciones

No acepta argumentos ni opciones propias.

## Entrada aceptada

No consume fuente ni artefactos.

## stdout

Escribe el objeto devuelto por `v31_descriptor()`. Entre los campos relevantes están:

```text
schema
language_id
language_version
profiles
program_ir_version
semantic_basis
open_computation
proof_admission_external_only
physical_effect_commit_inside_runtime
runtime_targets
```

El descriptor está content-addressed mediante `descriptor_hash`; ese hash protege identidad del descriptor, no demuestra por sí mismo que una afirmación externa sea verdadera.

## stderr

Un fallo de validación de metadatos de release es un error de plataforma, no un diagnóstico de fuente de usuario.

## Exit codes

```text
0  descriptor emitido correctamente
```

## Ejemplo positivo

```text
tev-script descriptor
```

El perfil actual debe incluir `total_core` y `language_version` debe ser `3.1.0`.

## Versión/perfil

```text
language = 3.1.0
profile  = total_core
Program IR current = 5
```

## Relacionado

- [`describe.md`](describe.md)
- [`../versions/current.md`](../versions/current.md)
- `spec/TEV_SCRIPT_V31_TOTAL_CORE.md`
