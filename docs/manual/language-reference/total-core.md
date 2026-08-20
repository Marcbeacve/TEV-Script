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

En la implementación current, `profile effects` significa **Program IR V4 Effects R1 observation-only**. No es un alias genérico para todos los perfiles effects V2 posteriores.

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

Este input materializa la instancia de un child **Effects R1**: scenario de observaciones y estado inicial opcional. No convierte un child `command/request` R2 en una unidad Total-Core válida.

## Effects R1 frente a Effects R2

La ruta de compilación current es:

```text
compile_total_core_v31
    ↓
compile_effect_program_v2
    ↓
Program IR V4 Effects R1
```

`compile_effect_program_v2` rechaza sintaxis `command`/`request` con:

```text
TEVS_V2_EFFECT_R2_REQUIRED
```

porque esa sintaxis pertenece a `compile_effect_command_program_v2` y al contrato Effects R2 separado.

El validador de `TotalCoreUnitV1` current también exige el schema V4 Effects R1 admitido. Por tanto, **Total-Core no admite Effects R2** como child ni por la ruta de fuente ni por simple sustitución de un artefacto R2 precompilado.

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

El mapping V4 se valida mediante el validator de su profile. Los perfiles current se corresponden con los schemas admitidos para `pure`, `recursive` y **Effects R1**; el nombre `effects` no habilita R2.

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

Effects R1 child payload: unit identity + final state/hash + capability transcript + evaluation/observation information.

El payload entra al Field por derived Transformation + Apply.

No existe en este contrato current un bridge R2 `command/request` implícito.

## Physical effect boundary

V5 puede ejecutar la semántica **Effects R1 observacional** de un child admitido y ligar su transcript/estado al Field. No posee autoridad ambient para commit físico.

Los command intents de Effects R2 pertenecen actualmente a su pipeline/provider V2 separado; V5 current no los ejecuta como child. Si una integración futura los incorpora, necesitará un schema/validator/bridge V5 explícito y conformance propia.

## Compatibilidad

- V2 source sigue `2.0.0`;
- Effects R1 y R2 conservan fronteras distintas;
- V4 validators no se fusionan por nombre de perfil;
- semantic-process 3.0 sigue `3.0.0`;
- Total-Core es aditivo.

## Diagnósticos

La familia current usa `TEVS_V31_*`. Consulta `docs/manual/diagnostics/current-inventory.md`; el inventario está ligado automáticamente a los literals de las autoridades V31 declaradas.

## Autoridad técnica

- `spec/TEV_SCRIPT_V31_TOTAL_CORE.md`
- `tev_script/source_total_core_v31.py`
- `tev_script/source_effect_program_v2.py`
- `tev_script/program_ir_v5_total.py`
- `tev_script/runtime_v5_total.py`
