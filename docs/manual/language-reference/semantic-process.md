# Semantic Process: facts, Fields, transformations y labels

## Aplicabilidad

La gramática semantic-process nació como perfil V3 `3.0.0` y se conserva como **INHERITED_COMPATIBILITY**. El frontend Total-Core 3.1 reutiliza esta base con header 3.1 y añade `unit`/`invoke_v4`.

## Forma V3 normativa

```text
process <ProgramId> version "3.0.0";
authority <sha256-hex>;
quantum_steps <1..1000000>;

fact <FactName> = <relation-id> <strict-canonical-json-array>;
...
field <profile-id> = [<FactName>, ...];

transform <TransformId> effects <sha256-hex> resources <sha256-hex>
          [profile <result-profile-id>]
          remove [<FactName>, ...] add [<FactName>, ...];
...

label <Label> = apply <TransformId> <NextLabel>;
label <Label> = branch_fact <FactName> <PresentLabel> <AbsentLabel>;
label <Label> = jump <TargetLabel>;
label <Label> = halt;
...
entry <Label>;
```

En Total-Core cambia el header a `3.1.0` y se admiten las extensiones current.

## `process`

Identifica el programa y fija la versión de lenguaje del frontend. Debe ser único.

## `authority`

Hash 64-hex que liga la autoridad semántica del programa. Se incorpora a identidad y proof-admission checks. No es grant del sistema operativo.

## `quantum_steps`

Cota finita obligatoria para la ejecución del root. V3/3.1 permite ciclos de labels porque cada epoch se corta por esta cota.

## `fact`

Forma:

```text
fact Ready = machine.ready ["M1",1];
```

Los argumentos son un array strict-canonical-JSON. Duplicate object keys, floats estructurales no admitidos, constantes no estándar o enteros estructurales no canónicos fallan antes del semantic hash.

El nombre `Ready` es una binding de fuente; relación+argumentos forman el contenido del fact.

## `field`

Forma:

```text
field actual = [Ready, Other];
```

- profile ID explícito;
- facts declarados;
- sin duplicados;
- orden superficial no usado como autoridad cuando el modelo lo canonicaliza.

## `transform`

Forma:

```text
transform Start effects <64hex> resources <64hex>
    remove [Idle] add [Running];
```

Puede añadir:

```text
profile <result-profile-id>
```

para cambiar el profile del Field resultante. Si se omite, el profile se conserva.

Los conjuntos remove/add deben ser facts declarados, únicos y sin overlap prohibido.

## `effects` y `resources`

Son hashes explícitos vinculados a la Transformation. No otorgan permisos físicos ni demuestran disponibilidad de recursos.

## `label ... apply`

```text
label A = apply T B;
```

Resuelve T y B antes de IR. La Transformation compilada queda ligada al Field esperado y el runtime ejecuta Apply.

## `label ... branch_fact`

```text
label A = branch_fact Fact Present Absent;
```

Consulta presencia del fact exacto en el Field actual.

## `label ... jump`

Salto simbólico resuelto a PC.

## `label ... halt`

Termina la ejecución en ese punto y produce estado halted en la frontera runtime.

## `entry`

Selecciona un label declarado. El compiler resuelve simbólicamente y emite `entry_pc`.

## Orden de declaraciones

V3 define facts/transforms/labels por nombre y canonicaliza el modelo fuente. El orden de declaraciones independiente es no semántico. Los labels se resuelven y el compiler emite un orden canónico por nombre lexical.

Esto no significa que el **orden de instrucciones ya emitidas** sea reordenable: en IR, el control por PC sí es semántico.

## `source_semantic_hash`

Cubre el modelo fuente resuelto:

```text
program_id
facts ordenados
field
transformations ordenadas
labels ordenados
entry
quantum_steps
authority_hash
```

No cubre path/whitespace original como sustituto de semántica.

## Proof-open source

El primer semantic-process source profile no permite fabricar proof-open transformations/admissions desde fuente. Esa evidencia se maneja en capas posteriores/externas.

## Extensiones Total-Core 3.1

Añade:

```text
unit <UnitId> profile pure|recursive|effects;
label <Label> = invoke_v4 <UnitId> result <relation-id> <NextLabel>;
```

El resto de la base se delega al parser/compiler semantic-process existente.

## Errores representativos

- header/version incorrecto;
- fact/transform/label duplicado;
- fact no declarado en Field/transform;
- overlap add/remove inválido;
- strict JSON no canónico;
- label/transform target desconocido;
- quantum bound inválido.

## Autoridad técnica

- `spec/TEV_SCRIPT_V3_SEMANTIC_PROCESS_SOURCE.md`
- `tev_script/source_semantic_process_v3.py`
- `tev_script/source_total_core_v31.py`
