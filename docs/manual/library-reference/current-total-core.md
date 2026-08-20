# API Python actual: Total-Core 3.1

Esta página documenta los **16 símbolos públicos actuales** de `tev_script` que pertenecen directamente al perfil Total-Core 3.1.

Importación típica:

```text
from tev_script import compile_total_core_v31, initial_total_core_checkpoint, run_total_core_quantum
```

La autoridad semántica sigue en `spec/TEV_SCRIPT_V31_TOTAL_CORE.md`; estas APIs son implementación pública Python.

## Flujo recomendado

```text
process_source + unit_sources/evidence
        ↓ compile_total_core_v31
TotalCoreProgramV1
        ↓ initial_total_core_checkpoint
TotalCoreCheckpointV1
        ↓ run_total_core_quantum
TotalCoreQuantumResultV1
        ↓ next_checkpoint
siguiente quantum, si status = SUSPENDED
```

---

## `compile_total_core_v31`

```text
compile_total_core_v31(
    process_source: str,
    *,
    unit_sources: Mapping[str, str],
    effect_inputs: Mapping[str, Mapping[str, Any]] | None = None,
    proof_admissions: Sequence[VerifiedProofAdmissionV1] = (),
) -> TotalCoreProgramV1
```

Compila fuente de proceso `3.1.0` a un `TotalCoreProgramV1`. `unit_sources` es obligatorio incluso si está vacío; su conjunto de claves debe coincidir exactamente con las unidades declaradas. `effect_inputs` debe corresponder exactamente a las unidades `effects`. Las proof admissions permanecen evidencia externa.

Puede lanzar `TevScriptError` con códigos `TEVS_V31_SOURCE_*` o de las capas V4/IR subyacentes cuando una unidad o evidencia es inválida.

---

## `TotalCoreProgramV1`

Dataclass inmutable que representa Program IR V5 Total-Core validado.

Campos principales:

```text
schema
language_version
profile
program_id
source_semantic_hash
initial_field
transformations
v4_units
proof_admissions
instructions
entry_pc
quantum_step_limit
authority_hash
program_hash
```

### `TotalCoreProgramV1.build(...)`

```text
TotalCoreProgramV1.build(
    *,
    program_id: str,
    source_semantic_hash: str,
    initial_field: SemanticFieldV1,
    transformations: Sequence[FieldTransformationV1],
    v4_units: Sequence[TotalCoreUnitV1],
    proof_admissions: Sequence[VerifiedProofAdmissionV1],
    instructions: Sequence[TotalCoreInstructionV1],
    entry_pc: int,
    quantum_step_limit: int,
    authority_hash: str,
) -> TotalCoreProgramV1
```

El constructor valida y canonicaliza tablas de transformaciones, unidades y proof admissions. Rechaza duplicados, targets fuera de la tabla, unidades desconocidas, proof requirements no admitidos y límites fuera de contrato.

La tabla admite como máximo `65_536` instrucciones y `quantum_step_limit` debe estar entre `1` y `1_000_000`.

---

## `TotalCoreInstructionV1`

Representa una instrucción V5 Total-Core content-addressed. Kinds admitidos:

```text
apply
branch_fact
jump
halt
invoke_v4
```

Constructores públicos de clase:

```text
TotalCoreInstructionV1.apply(transformation_hash, *, next_pc)
TotalCoreInstructionV1.branch_fact(fact_hash, *, present_pc, absent_pc)
TotalCoreInstructionV1.jump(target_pc)
TotalCoreInstructionV1.halt()
TotalCoreInstructionV1.invoke_v4(*, unit_hash, result_relation, next_pc)
```

Cada instancia incluye `instruction_hash`. Los campos que no pertenecen al kind seleccionado quedan canónicamente a `None`; no son parámetros opcionales con semántica libre.

---

## `TotalCoreUnitV1`

Envuelve una unidad Program IR V4 exacta dentro de Total-Core.

```text
TotalCoreUnitV1.build(
    unit_id: str,
    profile: str,
    program_ir_v4: Mapping[str, Any],
) -> TotalCoreUnitV1
```

Perfiles admitidos:

```text
pure
recursive
effects
```

El schema V4 incrustado debe coincidir con el perfil y su `program_ir_hash` se revalida. La unidad resultante conserva `program_ir_hash` y añade `unit_hash`.

---

## `VerifiedProofAdmissionV1`

Evidencia de prueba verificada que puede satisfacer un `proof_requirement_hash` concreto.

```text
VerifiedProofAdmissionV1.build(
    *,
    requirement_hash: str,
    verification_receipt_hash: str,
    verifier_identity_hash: str,
    authority_hash: str,
) -> VerifiedProofAdmissionV1
```

La instancia producida tiene `status = "VERIFIED"` y `admission_hash` canónico. Una proof admission no genera la prueba: registra evidencia externa ya verificada y queda ligada a requisito, verificador y autoridad.

---

## `validate_total_core_program`

```text
validate_total_core_program(value: object) -> TotalCoreProgramV1
```

Acepta una instancia o un mapping con el field set exacto del schema `TEV_SCRIPT_PROGRAM_IR_V5_TOTAL_CORE_V1`. Reconstruye la identidad canónica y rechaza:

```text
schema/perfil/versión incorrectos
tablas no canónicas
hashes manipulados
targets inválidos
unidades desconocidas
proof requirements sin admission
```

No «repara» un IR casi válido.

---

## `total_core_program_to_mapping`

```text
total_core_program_to_mapping(value: TotalCoreProgramV1) -> dict[str, Any]
```

Valida primero el programa y devuelve su representación wire completa, incluyendo `program_hash`.

Úsalo cuando necesites un objeto Python serializable pero quieras conservar la forma canónica del contrato.

---

## `canonical_total_core_program_bytes`

```text
canonical_total_core_program_bytes(
    value: TotalCoreProgramV1 | Mapping[str, Any]
) -> bytes
```

Valida el programa y devuelve JSON canónico UTF-8 **sin** convertir el objeto en una serialización específica del host. La CLI añade el salto de línea de archivo cuando persiste un artefacto.

---

## `TotalCoreCheckpointV1`

Dataclass inmutable de estado reanudable del runtime.

Campos:

```text
schema
program_hash
field
pc
next_epoch_index
previous_continuation
halted
checkpoint_hash
```

El checkpoint está ligado a un `program_hash`; no es intercambiable entre programas.

---

## `initial_total_core_checkpoint`

```text
initial_total_core_checkpoint(
    program: TotalCoreProgramV1
) -> TotalCoreCheckpointV1
```

Valida el programa y crea el checkpoint de epoch cero:

```text
field                 = program.initial_field
pc                    = program.entry_pc
next_epoch_index      = 0
previous_continuation = None
halted                = False
```

---

## `validate_total_core_checkpoint`

```text
validate_total_core_checkpoint(
    program: TotalCoreProgramV1,
    value: object,
) -> TotalCoreCheckpointV1
```

Requiere una instancia `TotalCoreCheckpointV1`, verifica que pertenezca al programa y reconstruye su hash/estado. Entre otras invariantes:

- el `pc` debe pertenecer al programa;
- el epoch cero no puede tener continuación anterior;
- un epoch reanudado debe tener la continuación precedente exacta;
- la continuación debe ligar el mismo estado;
- `halted=True` sólo puede apuntar a una instrucción `halt`.

---

## `TotalCoreQuantumResultV1`

Resultado inmutable de un quantum.

Campos principales:

```text
program_hash
epoch
status
steps_used
v4_evaluation_steps
field
pc
apply_receipt_hashes
child_receipt_hashes
result_hash
continuation
next_checkpoint
quantum_hash
```

Los estados admitidos son:

```text
HALTED
SUSPENDED
```

`SUSPENDED` no significa fallo: significa que el quantum finito terminó y dejó continuidad explícita.

---

## `run_total_core_quantum`

```text
run_total_core_quantum(
    program: TotalCoreProgramV1,
    checkpoint: TotalCoreCheckpointV1,
    *,
    task_strategy: TaskScopeExecutionStrategyV4 | None = None,
) -> TotalCoreQuantumResultV1
```

Valida programa y checkpoint y ejecuta como máximo `program.quantum_step_limit` instrucciones V5. Puede:

- aplicar una Transformation;
- ramificar por presencia de un fact;
- saltar;
- ejecutar una unidad V4;
- terminar en `halt`.

Una unidad V4 produce un receipt hijo y su resultado entra al `Field` V5 mediante una transformación puente derivada. Las métricas V4 se mantienen separadas de los pasos V5.

`task_strategy` es un hook avanzado de realización de tareas V4. Para el uso normal debe quedar en `None`, que usa la evaluación secuencial de referencia. El protocolo `TaskScopeExecutionStrategyV4` vive en `tev_script.ir_v4_pure` y no se exporta desde la API root estable `tev_script.__all__`; consulta [`advanced-embedding.md`](advanced-embedding.md) antes de proporcionar una estrategia custom.

Si el checkpoint de entrada ya está `halted`, lanza `TEVS_V31_RUNTIME_HALTED`; un proceso terminado no se «reanuda» como si fuese suspensión.

El resultado siempre contiene `next_checkpoint` ligado a la continuación del quantum.

---

## `validate_total_core_quantum_result`

```text
validate_total_core_quantum_result(
    program: TotalCoreProgramV1,
    value: object,
) -> TotalCoreQuantumResultV1
```

Verifica pertenencia al programa, reconstruye todas las invariantes del resultado y exige identidad exacta. Un `quantum_hash` o una relación checkpoint/continuation manipulada falla cerrado.

---

## `v31_descriptor`

```text
v31_descriptor() -> dict[str, Any]
```

Devuelve el descriptor Total-Core content-addressed. Expone, entre otros datos:

```text
language_version = 3.1.0
program_ir_version = 5
profiles = ["total_core"]
semantic_basis = ["Field", "Transformation", "Apply"]
proof_admission_external_only = true
physical_effect_commit_inside_runtime = false
```

Incluye `descriptor_hash`.

---

## `verify_v31_descriptor`

```text
verify_v31_descriptor(value: Mapping[str, Any]) -> bool
```

Recalcula el descriptor esperado y compara tanto contenido como `descriptor_hash`. Devuelve `False` ante ausencia/manipulación de los campos requeridos; no lanza para los casos de mismatch normales que captura su contrato.

---

## Límites y autoridad

Estas 16 APIs son la superficie Python directa de Total-Core exportada por el paquete actual. No convierten Python en autoridad semántica: un runtime alternativo conformante debe respetar los mismos contratos de Program IR, Field, checkpoints, receipts y quanta.

Para un programa de usuario normal, la CLI [`../cli-reference/README.md`](../cli-reference/README.md) ofrece una frontera más estrecha. Usa estas APIs cuando necesites embedding, construcción/validación de artefactos o control explícito de quanta desde Python. Para hooks de realización/scheduling que no amplían la API root, continúa con [`advanced-embedding.md`](advanced-embedding.md).
