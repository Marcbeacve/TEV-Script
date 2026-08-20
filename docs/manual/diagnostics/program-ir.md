# Diagnósticos de Program IR V5 Total-Core

Esta página documenta los **45 códigos `TEVS_V31_TOTAL_*`** emitidos por `tev_script/program_ir_v5_total.py`. Son invariantes de construcción/validación del artefacto canónico; no son errores de parsing de `.tevs`.

## Valores escalares y canonicalidad

| Código | Significado / trigger | Corrección |
|---|---|---|
| `TEVS_V31_TOTAL_HASH` | Se esperaba un SHA-256 hexadecimal de 64 caracteres y se recibió otro valor. | Proporcionar el hash exacto exigido por el contrato; no rellenar ni truncar. |
| `TEVS_V31_TOTAL_ID` | Un identificador estable no satisface el formato permitido. | Usar un id no vacío y canónico admitido por Total-Core. |
| `TEVS_V31_TOTAL_PC` | Un program counter/target no es un entero válido. | Usar un índice entero dentro de la tabla de instrucciones. |
| `TEVS_V31_TOTAL_MAPPING` | Se esperaba un objeto/mapping wire y llegó otro tipo. | Entregar un objeto JSON/Python mapping con field set exacto. |
| `TEVS_V31_TOTAL_CANONICAL` | Una secuencia que debe estar ordenada/deduplicada no es canónica. | Ordenar según la clave normativa y eliminar duplicados; no depender del orden del host. |

## Unidades V4 embebidas

| Código | Significado / trigger | Corrección |
|---|---|---|
| `TEVS_V31_TOTAL_UNIT_PROFILE` | El perfil de unidad no es `pure`, `recursive` o `effects`, o no coincide con el IR V4. | Declarar el perfil real de la unidad. |
| `TEVS_V31_TOTAL_UNIT_SCHEMA` | El schema V4 incrustado no corresponde al perfil declarado. | Compilar la unidad al schema V4 correcto. |
| `TEVS_V31_TOTAL_UNIT_HASH` | El `program_ir_hash` embebido no coincide con el IR V4 real. | Recalcular/recompilar el artefacto hijo; no editar hashes. |
| `TEVS_V31_TOTAL_UNIT_IDENTITY` | La identidad derivada de una unidad no coincide con sus campos canónicos. | Reconstruir mediante `TotalCoreUnitV1.build`. |
| `TEVS_V31_TOTAL_UNIT` | El valor de unidad no es una instancia/mapping válido. | Usar `TotalCoreUnitV1` o su forma wire exacta. |
| `TEVS_V31_TOTAL_UNIT_FIELDS` | Field set de una unidad wire incompleto o con campos extra. | Ajustar al schema exacto. |

## Proof admissions

| Código | Significado / trigger | Corrección |
|---|---|---|
| `TEVS_V31_TOTAL_PROOF_IDENTITY` | Los campos de una admission no reproducen su identidad canónica. | Reconstruir la admission desde requisito, receipt, verifier y authority exactos. |
| `TEVS_V31_TOTAL_PROOF` | El valor de proof admission tiene forma/tipo inválido. | Usar `VerifiedProofAdmissionV1`. |
| `TEVS_V31_TOTAL_PROOF_FIELDS` | Field set wire de proof admission incorrecto. | Eliminar campos extra y añadir los obligatorios. |
| `TEVS_V31_TOTAL_PROOF_HASH` | `admission_hash` no coincide con el contenido. | No editar el hash; regenerar la admission canónica. |

## Instrucciones V5

| Código | Significado / trigger | Corrección |
|---|---|---|
| `TEVS_V31_TOTAL_INSTRUCTION_KIND` | Kind distinto de `apply`, `branch_fact`, `jump`, `halt` o `invoke_v4`. | Usar uno de los kinds normativos. |
| `TEVS_V31_TOTAL_INSTRUCTION_IDENTITY` | Campos incompatibles con el kind o identidad no canónica. | Construir mediante los classmethods de `TotalCoreInstructionV1`. |
| `TEVS_V31_TOTAL_INSTRUCTION` | Valor de instrucción no válido. | Usar instancia/mapping wire exacto. |
| `TEVS_V31_TOTAL_INSTRUCTION_FIELDS` | Field set wire de instrucción incorrecto. | Ajustarlo al schema V5 exacto. |
| `TEVS_V31_TOTAL_INSTRUCTION_HASH` | `instruction_hash` no coincide. | Reconstruir la instrucción; no parchear el hash. |

## Tablas y construcción de programa

| Código | Significado / trigger | Corrección |
|---|---|---|
| `TEVS_V31_TOTAL_TRANSFORMATIONS` | Tabla de Transformations inválida. | Suministrar una secuencia válida de `FieldTransformationV1`. |
| `TEVS_V31_TOTAL_TRANSFORMATION_DUPLICATE` | Dos transformations comparten la misma identidad/hash. | Mantener una sola entrada por Transformation canónica. |
| `TEVS_V31_TOTAL_UNITS` | Tabla de unidades inválida. | Suministrar una secuencia de unidades V4 validadas. |
| `TEVS_V31_TOTAL_UNIT_ID_DUPLICATE` | Se repite `unit_id`. | Cada id lógico debe ser único. |
| `TEVS_V31_TOTAL_UNIT_HASH_DUPLICATE` | Dos filas reutilizan el mismo `unit_hash`. | No duplicar la misma unidad canónica bajo entradas distintas. |
| `TEVS_V31_TOTAL_PROOFS` | Tabla de admissions inválida. | Suministrar admissions validadas. |
| `TEVS_V31_TOTAL_PROOF_REQUIREMENT_DUPLICATE` | Más de una admission pretende satisfacer el mismo requirement. | Una admission canónica por requirement. |
| `TEVS_V31_TOTAL_PROOF_DUPLICATE` | Se duplica la misma admission/hash. | Eliminar duplicados. |
| `TEVS_V31_TOTAL_PROOF_AUTHORITY` | La authority de la proof admission no coincide con la del programa. | Admitir evidencia bajo la misma autoridad exacta. |
| `TEVS_V31_TOTAL_INSTRUCTIONS` | Tabla de instrucciones inválida/no secuencial. | Proporcionar una secuencia válida. |
| `TEVS_V31_TOTAL_INSTRUCTION_COUNT` | Tabla vacía o superior al límite de 65 536. | Mantener `1..65536` instrucciones. |
| `TEVS_V31_TOTAL_ENTRY_PC` | `entry_pc` está fuera de la tabla. | Apuntar a una instrucción existente. |
| `TEVS_V31_TOTAL_QUANTUM_LIMIT` | `quantum_step_limit` fuera del contrato. | Usar un entero `1..1_000_000`. |
| `TEVS_V31_TOTAL_TARGET` | Un salto/branch/next_pc apunta fuera de la tabla. | Corregir el target a un PC existente. |
| `TEVS_V31_TOTAL_TRANSFORMATION_UNKNOWN` | `apply` referencia una Transformation no incluida. | Añadir la Transformation exacta o corregir el hash referenciado. |
| `TEVS_V31_TOTAL_PROOF_REQUIRED` | Una Transformation exige proof requirements sin admission correspondiente. | Suministrar admissions verificadas para todos los requirements. |
| `TEVS_V31_TOTAL_UNIT_UNKNOWN` | `invoke_v4` referencia un `unit_hash` no incluido. | Incluir la unidad exacta o corregir la referencia. |

## Programa wire y hashes finales

| Código | Significado / trigger | Corrección |
|---|---|---|
| `TEVS_V31_TOTAL_PROGRAM_IDENTITY` | Los componentes del programa no reproducen su identidad canónica. | Reconstruir el programa mediante `TotalCoreProgramV1.build`. |
| `TEVS_V31_TOTAL_PROGRAM` | El objeto recibido no representa Program IR V5 Total-Core. | Entregar una instancia/mapping del schema correcto. |
| `TEVS_V31_TOTAL_PROGRAM_FIELDS` | Field set del programa wire incorrecto. | Usar exactamente los campos normativos. |
| `TEVS_V31_TOTAL_PROGRAM_ARRAY` | Una tabla wire que debe ser array/list tiene otro tipo. | Serializarla como array JSON. |
| `TEVS_V31_TOTAL_PROGRAM_HASH` | `program_hash` no coincide con el contenido canónico. | Recompilar/reconstruir; un hash manipulado es terminal para esa validación. |
| `TEVS_V31_TOTAL_TRANSFORMATION_ORDER` | Tabla de transformations fuera del orden canónico. | Ordenar por identidad/hash según el constructor. |
| `TEVS_V31_TOTAL_UNIT_ORDER` | Tabla de unidades fuera del orden canónico. | Canonicalizar la tabla antes de serializar. |
| `TEVS_V31_TOTAL_PROOF_ORDER` | Tabla de admissions fuera del orden canónico. | Canonicalizar por requirement/admission identity. |

## Regla de uso

Estos errores significan que el **artefacto V5** no satisface su contrato. La respuesta correcta no es relajar el runtime para aceptar una forma aproximada, sino volver a la fuente/construcción que produjo el IR y regenerar un objeto canónico.

Relacionado: [`../library-reference/current-total-core.md`](../library-reference/current-total-core.md) y `spec/TEV_SCRIPT_V31_TOTAL_CORE.md`.
