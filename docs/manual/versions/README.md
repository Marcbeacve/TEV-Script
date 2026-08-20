# Versiones y compatibilidad

TEVScript tiene varios dominios de versión independientes. Esta sección evita reducirlos a un único número ambiguo.

## Estado current

```text
package                 3.1.2
language                3.1.0
source profile           total_core
Program IR root          V5 total_core
runtime ABI              v5-total-v1
checkpoint               v5-total-checkpoint-v1
published package parent 3.1.1
```

## Páginas

- [`current.md`](current.md) — snapshot detallado de la plataforma current.
- [`version-domains.md`](version-domains.md) — significado de package/language/profile/IR/runtime/checkpoint.
- [`compatibility.md`](compatibility.md) — reglas de compatibilidad entre generaciones.
- [`v1.md`](v1.md) — V1 historical y APIs/artefactos que permanecen por compatibilidad.
- [`v2.md`](v2.md) — V2 compatible; fuente actual de units V4.
- [`v3.md`](v3.md) — semantic-process 3.0 compatible.
- [`v31.md`](v31.md) — Total-Core 3.1 current.
- [`deprecations.md`](deprecations.md) — qué significa deprecation y qué no está retirado.

## Regla principal

Una versión nueva del **package** no renumera automáticamente el lenguaje ni los IR existentes. Un artefacto conserva su schema/version/profile y se valida con la autoridad de su generación.

La matriz machine-readable autoritativa es `spec/TEV_SCRIPT_VERSION_MATRIX.json`.
