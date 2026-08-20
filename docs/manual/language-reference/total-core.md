# Total-Core 3.1 — referencia del root actual

## Identidad

```text
language_version = 3.1.0
source_profile    = total_core
Program IR root   = TEV_SCRIPT_PROGRAM_IR_V5_TOTAL_CORE_V1
```

El package Python puede ser `3.1.2` sin cambiar estos discriminadores.

## Gramática de alto nivel

Total-Core reutiliza semantic-process y añade units/invocations. Una forma representativa es:

```text
process <ProgramId> version "3.1.0";
authority <64hex>;
quantum_steps <1..1000000>;

unit <UnitId> profile pure|recursive|effects;

fact <FactName> = <relation-id> <canonical-json-array>;
field <profile-id> = [<FactName>, ...];
transform ...;

label A = apply ...;
label B = branch_fact ...;
label C = jump ...;
label D = invoke_v4 <UnitId> result <relation-id> <NextLabel>;
label E = halt;
entry <Label>;
```

No todas las secciones son obligatorias: un proceso mínimo puede no tener units/facts/transforms.

## `unit`

Regex de fuente actual:

```text
unit <stable-id> profile pure|recursive|effects;
```

Cada declaración exige una entrada homónima en `unit_sources` durante compilación.

## `invoke_v4`

Sólo se reconoce en un body de label con forma:

```text
label <L> = invoke_v4 <UnitId> result <RelationId> <NextLabel>;
```

El compiler sustituye temporalmente esa label por halt para delegar el resto del semantic process a V3, resuelve units/labels, y después emite la instrucción `invoke_v4` V5 exacta.

## Effect inputs

Argumento externo de compilación:

```text
effect_inputs: mapping unit_id -> {
    scenario: object,
    current_state?: object
}
```

El set de keys debe coincidir exactamente con units `effects`.

## Proof admissions

Argumento externo:

```text
proof_admissions: sequence[VerifiedProofAdmissionV1]
```

La fuente no crea estos objetos.

## Program IR root fields

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

Unknown/missing root fields se rechazan al validar mapping serializado.

## Canonical table order

```text
transformations  → transformation_hash ascending
v4_units         → (unit_id, unit_hash) ascending
proof_admissions → (requirement_hash, admission_hash) ascending
instructions     → control-flow order, NO sort
```

## V5 instruction schemas

Kinds admitidos:

```text
apply
branch_fact
jump
halt
invoke_v4
```

Los campos no aplicables de cada instruction son canonicalmente `null`. Cada instruction posee `instruction_hash`.

## `apply`

Campos semánticos activos:

```text
transformation_hash
next_pc
```

## `branch_fact`

```text
fact_hash
present_pc
absent_pc
```

## `jump`

```text
target_pc
```

## `halt`

No posee target/child.

## `invoke_v4`

```text
unit_hash
result_relation
next_pc
```

## Bounds

```text
MAX_TOTAL_CORE_INSTRUCTIONS_V1 = 65_536
MAX_TOTAL_CORE_QUANTUM_STEPS_V1 = 1_000_000
```

Entry/targets deben estar dentro de la tabla.

## Child unit schema

```text
TEV_SCRIPT_PROGRAM_IR_V5_TOTAL_UNIT_V1
```

Campos:

```text
unit_id
profile
program_ir_v4
program_ir_hash
unit_hash
```

El mapping V4 se valida mediante el validator de su profile.

## Proof admission schema

```text
TEV_SCRIPT_PROGRAM_IR_V5_PROOF_ADMISSION_V1
```

Sólo `status = VERIFIED`.

## Runtime checkpoint

Schema:

```text
TEV_SCRIPT_PROGRAM_IR_V5_TOTAL_CHECKPOINT_V1
```

Liga program, Field, PC, epoch, continuation previa y halted.

## Quantum result

Schema:

```text
TEV_SCRIPT_PROGRAM_IR_V5_TOTAL_QUANTUM_RESULT_V1
```

Status actual:

```text
HALTED | SUSPENDED
```

Además liga steps, child receipts, Field, continuation y next checkpoint.

## Bridge contract

Pure/recursive child payload: unit identity + result type/encoding/hash + evaluation steps.

Effects child payload: unit identity + final state/hash + capability transcript + evaluation/observation information.

El payload entra al Field por derived Transformation + Apply.

## Physical effect boundary

V5 puede ejecutar semántica effects/command intent de un child. No posee autoridad ambient para commit físico. La realización externa permanece detrás del provider/grant existente.

## Compatibilidad

- V2 source sigue `2.0.0`;
- V4 validators no cambian;
- semantic-process 3.0 sigue `3.0.0`;
- Total-Core es aditivo.

## Diagnósticos

La familia current usa `TEVS_V31_*`. Consulta `docs/manual/diagnostics/current-inventory.md`; el inventario está ligado automáticamente a los literals de las autoridades V31.

## Autoridad técnica

- `spec/TEV_SCRIPT_V31_TOTAL_CORE.md`
- `tev_script/source_total_core_v31.py`
- `tev_script/program_ir_v5_total.py`
- `tev_script/runtime_v5_total.py`
