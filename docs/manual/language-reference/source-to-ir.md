# Frontera Source → IR

TEVScript separa el tooling que entiende `.tevs` del runtime que ejecuta artefactos. Ésta es una propiedad arquitectónica y de seguridad, no sólo una optimización.

## Regla fundamental

```text
runtime de producción NO parsea/compila fuente .tevs
```

La fuente se resuelve antes de despliegue a un IR canónico validable.

## V2 → Program IR V4

Para unidades pure/recursive:

```text
source V2
  ↓ tokenize/parse
SourceProgramV2
  ↓ resolución de tipos/functions/generics/recursion
CompiledProgramV2
  ↓ export
Program IR V4 Pure | Recursive
```

Para effects:

```text
source V2 effects
  ↓ compile
CompiledEffectProgramV2
  + scenario/current_state externos
  ↓ build
Program IR V4 Effects
```

La evidencia de effects pertenece a la instancia, no a los bytes semánticos de fuente.

## V3 → Program IR V5 Semantic Process

```text
source 3.0 semantic_process
  ↓ parse + resolve names
canonical source model
  ↓ compile
TEV_SCRIPT_PROGRAM_IR_V5_SEMANTIC_PROCESS_V1
```

El source semantic hash se deriva del modelo resuelto/canónico.

## 3.1 Total-Core → Program IR V5 Total

```text
process_source 3.1
unit_sources V2
[effect_inputs]
[proof_admissions]
        ↓ compile_total_core_v31
TEV_SCRIPT_PROGRAM_IR_V5_TOTAL_CORE_V1
```

### Paso 1 — normalizar root

El frontend 3.1:

- exige header `3.1.0`;
- extrae `unit` declarations;
- detecta labels `invoke_v4`;
- traduce temporalmente esas labels a `halt` para delegar el resto al parser/compiler V3;
- conserva unit/invoke metadata por separado.

### Paso 2 — validar inputs hijos

El set de `unit_sources` debe ser exactamente el declarado. `effect_inputs` debe coincidir exactamente con units effects.

### Paso 3 — compilar cada child

Según profile:

```text
pure      → compile_program_v2 → export_program_ir_v4_pure
recursive → compile_program_v2 → export_program_ir_v4_recursive
effects   → compile_effect_program_v2 → build_effect_program_ir_v4
```

Después `TotalCoreUnitV1.build` vuelve a validar el V4 exacto.

### Paso 4 — reconstruir instrucciones

Las labels V3 ordinarias se convierten a instructions V5 equivalentes. Las labels especiales se convierten en `invoke_v4` con `unit_hash`, relation y next_pc.

### Paso 5 — source semantic identity

El hash de fuente Total-Core liga:

```text
v3_process_semantic_hash
child source semantic hashes por unit/profile
invoke_v4 mapping resuelto
```

No depende del orden del mapping host de unit_sources.

### Paso 6 — construir root canónico

`TotalCoreProgramV1.build` valida Fields, transformations, units, admissions, instructions, targets, bounds y ordering; después calcula `program_hash`.

## Source identity frente a Program IR identity

Pueden divergir legítimamente. Ejemplo effects:

```text
misma fuente + scenario A → Program IR hash A
misma fuente + scenario B → Program IR hash B
```

El `source_semantic_hash` hijo puede seguir igual porque el scenario no es fuente.

## Canonical bytes

`canonical_total_core_program_bytes` serializa el mapping validado con canonical JSON y UTF-8. El output CLI añade un newline de archivo después de esos bytes canónicos según su contrato de artefacto.

## Validación de artefacto

La CLI `validate-total`/la ruta generic correspondiente no recompila source: carga strict JSON y llama `validate_total_core_program`.

Unknown fields, orden canónico incorrecto o hash alterado fallan.

## Build authority y runtime authority

El build puede necesitar leer archivos `.tevs`, módulos, scenarios y proof admissions. El runtime necesita únicamente el artefacto cerrado y las capacidades de ejecución que su deployment permita.

Reducir autoridad del runtime es parte del diseño.

## Compatibilidad

La existencia de V5 no invalida los IR previos. Cada artifact conserva schema/version/profile y su validator específico. No se «actualiza» un IR V4 cambiando el número en JSON.

## Errores representativos

- child V2 con versión no V2;
- source root 3.1 con unit set incorrecto;
- profile hijo incompatible;
- scenario inválido;
- proof admission inválida;
- target no resuelto;
- mapping IR con fields desconocidos;
- canonical order alterado;
- program hash manipulado.

## Autoridad técnica

- `spec/TEV_SCRIPT_V2_LANGUAGE.md`
- `spec/TEV_SCRIPT_PROGRAM_IR_V4.md`
- `spec/TEV_SCRIPT_V3_SEMANTIC_PROCESS_SOURCE.md`
- `spec/TEV_SCRIPT_V31_TOTAL_CORE.md`
- `tev_script/source_total_core_v31.py`
- `tev_script/program_ir_v5_total.py`
