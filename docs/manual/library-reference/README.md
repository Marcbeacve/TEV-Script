# Referencia de biblioteca Python

El paquete `tev_script` exporta una superficie pública explícita mediante `tev_script.__all__`. En el candidato actual son **77 símbolos**.

No todos pertenecen a la misma generación semántica. Esta referencia los separa por familia para que una API histórica compatible no parezca parte del camino recomendado Total-Core 3.1.

## Familias

- [`current-total-core.md`](current-total-core.md) — 16 símbolos Total-Core 3.1 actuales.
- [`advanced-embedding.md`](advanced-embedding.md) — hooks avanzados de embedding, incluido `task_strategy`, sin ampliar la API root estable.
- [`python-host-v1.md`](python-host-v1.md) — 5 símbolos del host de producción Python para IR V3.
- [`ir-v3.md`](ir-v3.md) — 13 símbolos de valores, validación, runtime, checkpoint y conformance IR V3.
- [`v1-compiler.md`](v1-compiler.md) — 16 símbolos del pipeline/compiler V1 compatible.
- [`v1-project.md`](v1-project.md) — 4 símbolos de proyectos V1.
- [`lowering-receipts.md`](lowering-receipts.md) — 6 símbolos de receipts de lowering V2/V3.
- [`v02-compatibility.md`](v02-compatibility.md) — 16 símbolos de la superficie portable V0.2 preservada.
- [`package-metadata.md`](package-metadata.md) — `__version__`.

## Regla de selección

Para código nuevo que quiere Total-Core 3.1, comienza por:

```text
compile_total_core_v31
TotalCoreProgramV1
initial_total_core_checkpoint
run_total_core_quantum
```

y usa la CLI pública cuando no necesites embedding Python.

Si necesitas controlar la realización de tareas V4 desde el host, consulta [`advanced-embedding.md`](advanced-embedding.md). Es una frontera especializada: no convierte sus tipos auxiliares en símbolos estables de `tev_script.__all__`.

Las APIs V1/V0.2/IR V3 siguen siendo públicas por compatibilidad y por contratos de integración existentes; su presencia en `__all__` no significa que debas reconstruir un proyecto Total-Core moderno con ellas.

## Autoridad y compatibilidad

`tev_script.__all__` define qué nombres se exportan públicamente desde el paquete. La semántica de cada familia pertenece a sus specs/contratos correspondientes; esta referencia no redefine esa semántica.
