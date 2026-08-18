# API Python compatible: pipeline/compiler V1

Esta página documenta los **16 exports públicos** del pipeline V1. Son APIs de compatibilidad para lenguaje/linked-program `1.0.0`; no son el frontend Total-Core 3.1 actual.

El pipeline común es:

```text
SourceInputV1...
   ↓ link_v1_sources
LinkPlanV1
   ↓ static semantics
StaticSemanticsV1
   ↓ emit linked program
TEV_SCRIPT_LINKED_PROGRAM_V1
   ↓ lowering boundary
IR V2 si es erasable, o IR V3 para el perfil completo
```

## Bundles

### `V1AnalysisBundle`

```text
V1AnalysisBundle(
    plan,
    semantics,
    linked_program,
    ir_v2_boundary,
)
```

Agrupa el plan de linking, semántica estática, linked program canónico y análisis de si la semántica puede bajar losslessly al perfil IR V2.

### `V1IrV2CompilationBundle`

```text
V1IrV2CompilationBundle(
    analysis: V1AnalysisBundle,
    target: LinkedV1IrV2Bundle,
)
```

Resultado de lowering explícito a Program IR V2.

### `V1IrV3CompilationBundle`

```text
V1IrV3CompilationBundle(
    analysis: V1AnalysisBundle,
    target: LinkedV1IrV3Bundle,
)
```

Resultado de lowering explícito a Program IR V3.

### `V1AutoCompilationBundle`

```text
V1AutoCompilationBundle(
    analysis: V1AnalysisBundle,
    target_ir: str,
    target: LinkedV1IrV2Bundle | LinkedV1IrV3Bundle,
)
```

El selector `auto` usa IR V2 sólo cuando `analysis.ir_v2_boundary.lowerable` es verdadero; en caso contrario elige IR V3. No intenta forzar el perfil reducido perdiendo semántica.

## Análisis: tres formas de entrada

### `analyze_v1_sources`

```text
analyze_v1_sources(
    sources: Iterable[SourceInputV1],
) -> V1AnalysisBundle
```

Ruta fundamental del análisis.

### `analyze_v1_mapping`

```text
analyze_v1_mapping(
    sources: Mapping[str, bytes],
) -> V1AnalysisBundle
```

Adapta un mapping `path -> bytes` a `SourceInputV1`.

### `analyze_v1_paths`

```text
analyze_v1_paths(
    paths: Iterable[str | Path],
) -> V1AnalysisBundle
```

Lee las rutas como bytes y usa su spelling POSIX como identidad de source input.

## Lowering explícito a IR V2

### `compile_v1_sources_to_ir_v2`

```text
compile_v1_sources_to_ir_v2(
    sources: Iterable[SourceInputV1],
) -> V1IrV2CompilationBundle
```

### `compile_v1_mapping_to_ir_v2`

```text
compile_v1_mapping_to_ir_v2(
    sources: Mapping[str, bytes],
) -> V1IrV2CompilationBundle
```

### `compile_v1_paths_to_ir_v2`

```text
compile_v1_paths_to_ir_v2(
    paths: Iterable[str | Path],
) -> V1IrV2CompilationBundle
```

Estas tres rutas solicitan explícitamente el perfil V2 erasable. Si el linked program usa semántica que no puede representarse losslessly allí, el lowering correspondiente falla en lugar de degradarla silenciosamente.

## Lowering explícito a IR V3

### `compile_v1_sources_to_ir_v3`

```text
compile_v1_sources_to_ir_v3(
    sources: Iterable[SourceInputV1],
) -> V1IrV3CompilationBundle
```

### `compile_v1_mapping_to_ir_v3`

```text
compile_v1_mapping_to_ir_v3(
    sources: Mapping[str, bytes],
) -> V1IrV3CompilationBundle
```

### `compile_v1_paths_to_ir_v3`

```text
compile_v1_paths_to_ir_v3(
    paths: Iterable[str | Path],
) -> V1IrV3CompilationBundle
```

IR V3 conserva la superficie algebraica/runtime V1 más completa y embebe el `source_semantic_hash` del linked program.

## Selección automática

### `compile_v1_sources_auto`

```text
compile_v1_sources_auto(
    sources: Iterable[SourceInputV1],
) -> V1AutoCompilationBundle
```

### `compile_v1_mapping_auto`

```text
compile_v1_mapping_auto(
    sources: Mapping[str, bytes],
) -> V1AutoCompilationBundle
```

### `compile_v1_paths_auto`

```text
compile_v1_paths_auto(
    paths: Iterable[str | Path],
) -> V1AutoCompilationBundle
```

La decisión es determinista:

```text
ir_v2_boundary.lowerable = true  → TEV_SCRIPT_PROGRAM_IR_V2
ir_v2_boundary.lowerable = false → TEV_SCRIPT_PROGRAM_IR_V3
```

No es una heurística de rendimiento ni una inferencia del host; es una propiedad del lowering boundary analizado.

## Aplicabilidad

Usa esta familia para mantener o integrar código V1 que necesita linked programs, lowering V2/V3 o selección automática. Para fuente Total-Core 3.1 usa [`current-total-core.md`](current-total-core.md).
