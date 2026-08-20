# Pipeline: de fuente a runtime

## Vista general current

```text
main.tevs 3.1 Total-Core
        │
        ├── parser/normalizador 3.1
        │      ├─ delega semantic-process → V3 frontend
        │      └─ extrae unit/invoke_v4
        │
        ├── unit source V2 ──→ compiler V2 ──→ Program IR V4
        │       pure | recursive | effects
        │
        └── compile_total_core_v31
                  ↓
       TotalCoreProgramV1 / Program IR V5
                  ↓
       validate_total_core_program
                  ↓
       runtime_v5_total
                  ↓
       quantum receipt + Field + continuation + checkpoint
```

## 1. Entrada de fuente

La CLI pública `tev-script check/compile` delega en `tev_script.cli_v31`, que lee UTF-8 y reúne:

```text
process source
unit_sources
optional effect_inputs
optional proof_admissions
```

La CLI no concede semantic authority por la ruta de archivo: los paths son inputs de build.

## 2. Normalización Total-Core

`source_total_core_v31.py` realiza una capa delgada:

1. separa statements `;` respetando strings/arrays;
2. valida header 3.1;
3. extrae declarations `unit`;
4. detecta labels cuyo body es `invoke_v4`;
5. sustituye temporalmente esos bodies por `halt` para que el frontend V3 valide/resuelva el semantic-process restante;
6. reconstruye después las instrucciones especiales.

Este patrón evita un segundo parser completo de facts/transforms/control.

## 3. Semantic process V3

`parse_semantic_process_v3` y `compile_semantic_process_v3` poseen la autoridad sobre:

```text
facts
initial Field
transformations
apply / branch_fact / jump / halt
entry
quantum bound
authority
```

El resultado incluye source semantic identity y estructuras canónicas reutilizadas por V5.

## 4. Compilación de children V2

Cada unit se procesa por su profile.

### Pure

```text
compile_program_v2
→ export_program_ir_v4_pure
→ validate Program IR V4 Pure
```

### Recursive

```text
compile_program_v2
→ verifica entry.function_kind == recursive
→ export_program_ir_v4_recursive
→ validator V4 Recursive
```

### Effects

```text
compile_effect_program_v2
+ scenario/current_state
→ build_effect_program_ir_v4
→ validator V4 Effects
```

El frontend 3.1 no replica tipos, genéricos, recursion evaluator o effects evaluator.

## 5. `TotalCoreUnitV1`

El mapping V4 se desacopla a canonical JSON y se valida con el validator de profile. La unidad liga `unit_id`, profile, `program_ir_hash` y `unit_hash`.

## 6. Reconstrucción de control V5

Las instrucciones semantic-process ordinarias se convierten 1:1 al tipo V5. Los placeholders de `invoke_v4` se reemplazan por:

```text
unit_hash
result_relation
next_pc
```

Todos los labels ya fueron resueltos a PCs.

## 7. Source semantic hash 3.1

No es hash bruto del archivo. Liga:

```text
v3_process_semantic_hash
child source semantic hashes
unit IDs/profiles
invoke_v4 mapping
```

`effect_inputs` pertenecen a la instancia IR y no alteran el semantic hash de source child.

## 8. `TotalCoreProgramV1.build`

Es la frontera de admisión estructural del root. Valida:

- program/source/authority IDs;
- Field/Transformations;
- V4 units;
- proof admissions;
- instruction kinds/fields;
- targets;
- referencias de transformation/unit;
- requirements de proof;
- bounds;
- canonical table order.

Sólo después calcula `program_hash`.

## 9. Serialización

`canonical_total_core_program_bytes` serializa el mapping validado como canonical JSON UTF-8. La CLI escribe esos bytes + newline mediante replace atómico de un path.

## 10. Carga en runtime

Runtime no recibe `.tevs`. Se carga strict JSON, se reconstruye/valida el root y sólo entonces se crea checkpoint inicial o se valida uno existente.

## 11. Quantum runtime

`run_total_core_quantum`:

1. valida program/checkpoint;
2. crea identity de epoch;
3. ejecuta hasta `quantum_step_limit`;
4. delega V4 children a sus runtimes;
5. aplica transformations/bridges;
6. acumula receipts/observations/effects/resources;
7. produce continuation;
8. produce next checkpoint;
9. devuelve quantum result.

## 12. Frontera externa

Ningún paso anterior equivale por sí mismo a commit físico. Providers/adapters quedan fuera del runtime portable y deben consumir intents/evidence bajo grants explícitos.

## Pipelines históricos

V0.2/V1 conservan `compiler.py`, `pipeline_v1.py`, linked program, IR V2/V3 y lowering receipts. V2/V4 y V3/V5 son capas posteriores compatibles. No deben borrarse del mapa sólo porque Total-Core sea current.

## Regla de depuración

Si el fallo aparece:

```text
antes de semantic hash → frontend/source
al validar IR          → schema/canonical/identity
al ejecutar child      → runtime V4 del profile
al ejecutar root       → runtime V5
al tocar mundo         → provider/adapter
```

Empieza en esa capa; no parches una capa vecina para ocultar el síntoma.
