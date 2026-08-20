# 12 — Total-Core 3.1 como sistema completo

Total-Core es el perfil fuente actual de TEVScript `3.1.0`. No es simplemente «V3 con un comando más»: define cómo conviven el proceso Field/Transformation heredado, las unidades V4, proof admissions externas, el control por quanta y una identidad Program IR V5 única.

## Ejemplo ejecutable

<!-- tevdoc-source: examples/docs/v31/tutorial/12_total_core/main.tevs -->
```tevs
process Tutorial12 version "3.1.0";
authority aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa;
quantum_steps 8;
unit Calc profile pure;
field actual = [];
label Start = invoke_v4 Calc result tev.tutorial.total End;
label End = halt;
entry Start;
```

El caso documental ahora ejecuta el artefacto, no sólo lo compila, y exige `HALTED`.

## Qué produce el frontend

La raíz compilada usa exactamente:

```text
schema           = TEV_SCRIPT_PROGRAM_IR_V5_TOTAL_CORE_V1
language_version = 3.1.0
profile          = total_core
```

No debe aceptarse como equivalente un root semantic-process 3.0 ni un V4 hijo suelto.

## Campos del root V5

El contrato raíz contiene:

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

Cada campo pertenece a una responsabilidad distinta. Por ejemplo `source_semantic_hash` identifica el modelo de fuente, mientras `program_hash` cubre el cuerpo canónico completo del artefacto ejecutable.

## `source_semantic_hash`

Para Total-Core, esta identidad liga:

- el proceso semántico raíz normalizado;
- la identidad semántica de cada fuente hija;
- los perfiles/IDs de unidad;
- el mapa de `invoke_v4`.

El scenario de una unidad effects es evidencia de ejecución, no fuente, por lo que puede cambiar el Program IR concreto sin reescribir la semántica de fuente hija.

## `program_hash`

`program_hash` es SHA-256 del root canónico con el propio campo omitido. Cubre Fields, transformations, unidades V4, proof admissions, instrucciones, límites y autoridad.

Un hash correcto demuestra integridad/identidad del artefacto. No demuestra que sus facts sean empíricamente verdaderos.

## Orden canónico

No todas las tablas se ordenan igual:

```text
transformations  → transformation_hash
v4_units         → (unit_id, unit_hash)
proof_admissions → (requirement_hash, admission_hash)
instructions     → orden de control preservado
```

Ordenar las instrucciones «para ser más determinista» rompería la semántica del programa.

## Conjunto de instrucciones

Total-Core cierra su máquina V5 a cinco kinds:

```text
apply
branch_fact
jump
halt
invoke_v4
```

Cada instrucción tiene `instruction_hash`; sus campos no aplicables son `null` en la representación canónica.

## Compatibilidad aditiva

3.1 no vuelve a definir V2, V3 o V4. La regla es:

```text
V2 source         conserva 2.0.0
V4 child          conserva su schema/validator
V3 semantic proc  conserva 3.0.0
V5 Total-Core     añade composición 3.1.0
```

Esto evita que actualizar el package cambie retrospectivamente el significado de artefactos publicados.

## Límites raíz

El contrato fija:

```text
1 <= instruction_count <= 65_536
1 <= quantum_step_limit <= 1_000_000
0 <= entry_pc < instruction_count
```

El proceso global puede ser abierto, pero cada quantum es finito.

## Autoridad

`authority_hash` forma parte del programa y también debe coincidir con proof admissions. No equivale a grant de filesystem/red/dispositivo; son dominios de autoridad distintos.

## Fuente 3.1 y compatibilidad V3

El frontend 3.1 reutiliza la gramática/semántica del semantic process para facts, Fields, transformations y control, pero exige header `3.1.0` y añade declaraciones `unit`/`invoke_v4`.

No se realiza una traducción oportunista de cualquier programa 3.0 a 3.1.

## Validación antes de ejecución

El runtime llama `validate_total_core_program`. Entre otras cosas valida:

- field/transform identities;
- unidades y hashes V4;
- proof admissions;
- targets de PC;
- referencias de transformations/unidades;
- límites;
- canonical ordering;
- `program_hash`.

El runtime no utiliza «best effort» con un root malformado.

## Frontera build/runtime

```text
.tevs                  build time
  ↓ compile
Program IR V5          artefacto canónico
  ↓ validate
runtime Total-Core     production execution
```

El runtime de producción no necesita autoridad para abrir y reinterpretar `.tevs`.

## Errores representativos

- `TEVS_V31_SOURCE_VERSION`: header de fuente incorrecto;
- `TEVS_V31_SOURCE_UNIT_SET`: conjunto hijo distinto al declarado;
- `TEVS_V31_TOTAL_PROGRAM_FIELDS`: root/schema/profile malformado;
- `TEVS_V31_TOTAL_PROGRAM_HASH`: identidad alterada;
- `TEVS_V31_TOTAL_TARGET`: PC fuera de rango;
- `TEVS_V31_TOTAL_UNIT_UNKNOWN`: `invoke_v4` inválido.

Consulta la sección de diagnósticos para el inventario completo actual.

## Autoridad técnica

- `spec/TEV_SCRIPT_V31_TOTAL_CORE.md`.
- `tev_script/source_total_core_v31.py`.
- `tev_script/program_ir_v5_total.py`.
- `tev_script/runtime_v5_total.py`.
