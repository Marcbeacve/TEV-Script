# Inventario actual de diagnósticos TEVScript 3.1

Esta página cubre los códigos deliberadamente públicos de las autoridades V31. Cada fila incluye fase, disparador mínimo y corrección. Los negativos ejecutables de fuente viven en `examples/docs/v31/diagnostics/`.

## Frontend Total-Core

| Código | Fase | Disparador que falla | Corrección / regla |
|---|---|---|---|
| `TEVS_V31_SOURCE_TYPE` | fuente | `source` no es texto | entregar `str`; `source_total_core_v31._split_statements` |
| `TEVS_V31_SOURCE_BRACKETS` | fuente | `]` sin `[` | equilibrar arrays |
| `TEVS_V31_SOURCE_UNCLOSED` | fuente | string/array abierto | cerrar `"` o `]` |
| `TEVS_V31_SOURCE_SEMICOLON` | fuente | declaración final sin `;` | terminar cada declaración con `;` |
| `TEVS_V31_SOURCE_DUPLICATE` | fuente | dos headers `process` | conservar un único header |
| `TEVS_V31_SOURCE_VERSION` | fuente | `version "3.0.0"` | usar `version "3.1.0"` |
| `TEVS_V31_SOURCE_UNIT_DUPLICATE` | fuente | dos `unit Calc ...` | identificadores de unidad únicos |
| `TEVS_V31_SOURCE_LABEL_DUPLICATE` | fuente | label `invoke_v4` duplicado | labels de invocación únicos |
| `TEVS_V31_SOURCE_REQUIRED` | fuente | falta `process ...` | añadir header 3.1 |
| `TEVS_V31_SOURCE_UNITS` | binding | `unit_sources` no es mapping | pasar mapping nombre→fuente |
| `TEVS_V31_SOURCE_UNIT_SET` | binding | falta/sobra una unidad | igualar conjunto declarado/suministrado |
| `TEVS_V31_SOURCE_UNIT_TEXT` | binding | fuente hija no textual | suministrar texto V2 |
| `TEVS_V31_SOURCE_EFFECT_INPUTS` | efectos | `effect_inputs` no mapping | usar mapping por unidad effects |
| `TEVS_V31_SOURCE_EFFECT_INPUT_SET` | efectos | falta/sobra input de efecto | cubrir exactamente unidades `effects` |
| `TEVS_V31_SOURCE_EFFECT_INPUT_PROFILE` | efectos | input asignado a perfil no-effects | retirar el input o corregir perfil |
| `TEVS_V31_SOURCE_EFFECT_INPUT` | efectos | input de unidad no es objeto | usar objeto de entrada |
| `TEVS_V31_SOURCE_EFFECT_INPUT_FIELDS` | efectos | campos distintos de `scenario[,current_state]` | usar el field set admitido |
| `TEVS_V31_SOURCE_EFFECT_SCENARIO` | efectos | `scenario` no objeto | aportar escenario mapping |
| `TEVS_V31_SOURCE_EFFECT_STATE` | efectos | `current_state` no objeto/null | aportar mapping o null |
| `TEVS_V31_SOURCE_UNIT_PROFILE` | unidad | perfil declarado no coincide/soportado | usar `pure|recursive|effects` coherente |
| `TEVS_V31_SOURCE_EFFECT_INPUT_REQUIRED` | unidad | effects sin entrada externa | suministrar input exacto |
| `TEVS_V31_SOURCE_V3_INSTRUCTION` | lowering | instrucción V3 inesperada | usar base V3 admitida |
| `TEVS_V31_SOURCE_UNKNOWN_LABEL` | enlace | target label inexistente | declarar el label exacto |
| `TEVS_V31_SOURCE_UNKNOWN_UNIT` | enlace | `invoke_v4` referencia unidad ausente | declarar/suministrar unidad |
| `TEVS_V31_SOURCE_RELATION` | enlace | relación de resultado inválida | usar identificador estable |
| `TEVS_V31_SOURCE_UTF8` | CLI/fuente | bytes no UTF-8 | guardar fuente como UTF-8 válido |

## Program IR V5 Total-Core

| Código | Fase | Disparador que falla | Corrección / regla |
|---|---|---|---|
| `TEVS_V31_TOTAL_HASH` | IR | hash no 64-hex minúscula | recalcular hash canónico |
| `TEVS_V31_TOTAL_ID` | IR | identificador inestable | usar patrón estable |
| `TEVS_V31_TOTAL_PC` | IR | PC negativo/no entero | usar entero ≥0 |
| `TEVS_V31_TOTAL_MAPPING` | IR | objeto esperado no mapping | usar objeto canónico |
| `TEVS_V31_TOTAL_CANONICAL` | IR | dato no serializable canónicamente | convertir al modelo portable |
| `TEVS_V31_TOTAL_UNIT_PROFILE` | unidad | perfil no admitido | `pure|recursive|effects` |
| `TEVS_V31_TOTAL_UNIT_SCHEMA` | unidad | IR V4 no corresponde al perfil | usar esquema V4 correcto |
| `TEVS_V31_TOTAL_UNIT_HASH` | unidad | hash embebido divergente | reconstruir unidad desde IR validado |
| `TEVS_V31_TOTAL_UNIT_IDENTITY` | unidad | dataclass manipulada | reconstruir con `build` |
| `TEVS_V31_TOTAL_UNIT` | unidad | unidad no objeto | usar `TotalCoreUnitV1`/mapping válido |
| `TEVS_V31_TOTAL_UNIT_FIELDS` | unidad | field set/schema incorrecto | usar esquema exacto |
| `TEVS_V31_TOTAL_PROOF_IDENTITY` | prueba | identidad de admisión divergente | reconstruir desde hashes autoridad |
| `TEVS_V31_TOTAL_PROOF` | prueba | admisión no objeto | usar estructura admitida |
| `TEVS_V31_TOTAL_PROOF_FIELDS` | prueba | campos/status distintos | usar `VERIFIED` y field set exacto |
| `TEVS_V31_TOTAL_PROOF_HASH` | prueba | `admission_hash` incorrecto | recalcular canónicamente |
| `TEVS_V31_TOTAL_INSTRUCTION_KIND` | instrucción | kind desconocido | usar apply/branch_fact/jump/halt/invoke_v4 |
| `TEVS_V31_TOTAL_INSTRUCTION_IDENTITY` | instrucción | identidad manipulada | reconstruir instrucción |
| `TEVS_V31_TOTAL_INSTRUCTION` | instrucción | no es objeto | usar instrucción V1 válida |
| `TEVS_V31_TOTAL_INSTRUCTION_FIELDS` | instrucción | field set/schema incorrecto | usar esquema exacto |
| `TEVS_V31_TOTAL_INSTRUCTION_HASH` | instrucción | hash incorrecto | recalcular cuerpo canónico |
| `TEVS_V31_TOTAL_TRANSFORMATIONS` | programa | tabla no secuencia | suministrar secuencia |
| `TEVS_V31_TOTAL_TRANSFORMATION_DUPLICATE` | programa | hash de transformación repetido | una transformación por hash |
| `TEVS_V31_TOTAL_UNITS` | programa | unidades no secuencia | suministrar secuencia |
| `TEVS_V31_TOTAL_UNIT_ID_DUPLICATE` | programa | `unit_id` duplicado | IDs únicos |
| `TEVS_V31_TOTAL_UNIT_HASH_DUPLICATE` | programa | `unit_hash` duplicado | unidades canónicas únicas |
| `TEVS_V31_TOTAL_PROOFS` | programa | admisiones no secuencia | suministrar secuencia |
| `TEVS_V31_TOTAL_PROOF_REQUIREMENT_DUPLICATE` | programa | requisito admitido dos veces | una admisión por requirement |
| `TEVS_V31_TOTAL_PROOF_DUPLICATE` | programa | admission hash repetido | eliminar duplicado |
| `TEVS_V31_TOTAL_PROOF_AUTHORITY` | programa | autoridad de prueba distinta | ligar a `authority_hash` del programa |
| `TEVS_V31_TOTAL_INSTRUCTIONS` | programa | código no secuencia | suministrar tabla de instrucciones |
| `TEVS_V31_TOTAL_INSTRUCTION_COUNT` | programa | 0 o >65536 instrucciones | respetar cota |
| `TEVS_V31_TOTAL_ENTRY_PC` | programa | entry fuera de tabla | usar PC existente |
| `TEVS_V31_TOTAL_QUANTUM_LIMIT` | programa | quantum fuera 1..1000000 | usar cota admitida |
| `TEVS_V31_TOTAL_TARGET` | programa | target PC fuera de tabla | corregir control flow |
| `TEVS_V31_TOTAL_TRANSFORMATION_UNKNOWN` | programa | Apply apunta a hash desconocido | incluir transformación exacta |
| `TEVS_V31_TOTAL_PROOF_REQUIRED` | programa | Apply proof-open sin admisión | aportar admisión exacta |
| `TEVS_V31_TOTAL_UNIT_UNKNOWN` | programa | invoke_v4 a unidad desconocida | incluir unidad exacta |
| `TEVS_V31_TOTAL_PROGRAM_IDENTITY` | programa | objeto tipado divergente | reconstruir desde campos canónicos |
| `TEVS_V31_TOTAL_PROGRAM` | programa | no es objeto | usar mapping/objeto Total-Core |
| `TEVS_V31_TOTAL_PROGRAM_FIELDS` | programa | schema/version/profile/campos inválidos | usar esquema V5 Total exacto |
| `TEVS_V31_TOTAL_PROGRAM_ARRAY` | programa | tablas no arrays | codificar arrays JSON |
| `TEVS_V31_TOTAL_PROGRAM_HASH` | programa | `program_hash` divergente | recalcular programa |
| `TEVS_V31_TOTAL_TRANSFORMATION_ORDER` | canon | tabla de transformaciones no canónica | ordenar por hash |
| `TEVS_V31_TOTAL_UNIT_ORDER` | canon | tabla de unidades no canónica | ordenar por identidad |
| `TEVS_V31_TOTAL_PROOF_ORDER` | canon | tabla de admisiones no canónica | ordenar por requisito/admisión |

## Runtime V5 Total-Core

| Código | Fase | Disparador que falla | Corrección / regla |
|---|---|---|---|
| `TEVS_V31_RUNTIME_HASH` | runtime | hash inválido | usar 64-hex canónico |
| `TEVS_V31_RUNTIME_PC` | runtime | PC inválido | usar PC dentro del programa |
| `TEVS_V31_RUNTIME_CHECKPOINT_PC` | checkpoint | PC fuera de programa | restaurar PC válido |
| `TEVS_V31_RUNTIME_CHECKPOINT_EPOCH` | checkpoint | índice/continuación no consecutivo | ligar epoch anterior exacto |
| `TEVS_V31_RUNTIME_CHECKPOINT_HALTED` | checkpoint | flag no bool o no apunta a halt | corregir estado halted |
| `TEVS_V31_RUNTIME_CHECKPOINT_PREVIOUS` | checkpoint | continuación previa imposible | epoch0→null; replay→continuación anterior |
| `TEVS_V31_RUNTIME_CHECKPOINT_STATE` | checkpoint | Field/PC/hash de estado no coincide | usar checkpoint derivado del quantum |
| `TEVS_V31_RUNTIME_CHECKPOINT` | checkpoint | tipo incorrecto | usar `TotalCoreCheckpointV1` |
| `TEVS_V31_RUNTIME_CHECKPOINT_PROGRAM` | checkpoint | `program_hash` distinto | cargar el programa original |
| `TEVS_V31_RUNTIME_CHECKPOINT_HASH` | checkpoint | identidad manipulada | validar/reconstruir checkpoint |
| `TEVS_V31_RUNTIME_UNIT_PROFILE` | runtime | perfil V4 desconocido | usar perfil admitido |
| `TEVS_V31_RUNTIME_BRIDGE_APPLY` | puente | Apply del recibo V4 no PASS | revisar Field/precondición |
| `TEVS_V31_RUNTIME_PROOF_REQUIRED` | prueba | falta admisión exacta | suministrar admisión VERIFIED |
| `TEVS_V31_RUNTIME_PROOF_STATUS` | prueba | estado no VERIFIED | verificar antes de ejecutar |
| `TEVS_V31_RUNTIME_PROOF_AUTHORITY` | prueba | autoridad divergente | usar autoridad del programa |
| `TEVS_V31_RUNTIME_PROOF_APPLY` | prueba | Apply derivado no PASS | revisar transformación/Field |
| `TEVS_V31_RUNTIME_STATUS` | quantum | status no HALTED/SUSPENDED | usar estado admitido |
| `TEVS_V31_RUNTIME_STEPS` | quantum | pasos fuera de presupuesto | respetar quantum limit |
| `TEVS_V31_RUNTIME_V4_STEPS` | quantum | contador V4 negativo/no entero | conservar contador válido |
| `TEVS_V31_RUNTIME_CONTINUATION_RESULT` | continuación | result hash no coincide | usar continuación generada |
| `TEVS_V31_RUNTIME_CONTINUATION_STATE` | continuación | state hash no coincide | ligar Field/PC exactos |
| `TEVS_V31_RUNTIME_CHECKPOINT_CONTINUATION` | continuación | checkpoint no liga continuación | persistir `next_checkpoint` original |
| `TEVS_V31_RUNTIME_CHECKPOINT_STATUS` | checkpoint | halted no coincide con quantum | conservar status derivado |
| `TEVS_V31_RUNTIME_HALTED` | runtime | reanudar checkpoint detenido | no reanudar; iniciar otro programa |
| `TEVS_V31_RUNTIME_APPLY_OPEN` | runtime | Apply canónico no cierra PASS | corregir precondiciones |
| `TEVS_V31_RUNTIME_RESULT` | resultado | tipo de quantum incorrecto | usar `TotalCoreQuantumResultV1` |
| `TEVS_V31_RUNTIME_RESULT_PROGRAM` | resultado | programa divergente | validar contra programa original |
| `TEVS_V31_RUNTIME_RESULT_HASH` | resultado | identidad divergente | reconstruir resultado canónico |

## CLI, LSP y release

| Código | Fase | Disparador que falla | Corrección / regla |
|---|---|---|---|
| `TEVS_V31_CLI_CHECKPOINT` | CLI | JSON checkpoint no objeto/campos | usar mapping exacto |
| `TEVS_V31_CLI_UNIT_BINDING` | CLI | `--unit` no `NAME=PATH`/duplicado | corregir binding |
| `TEVS_V31_CLI_EFFECT_BINDING` | CLI | `--effect-input` inválido | usar `NAME=JSON` único |
| `TEVS_V31_CLI_EFFECT_INPUT` | CLI | JSON efecto no objeto | usar objeto |
| `TEVS_V31_CLI_PROOF_ADMISSION` | CLI | JSON admisión no objeto | usar admisión canónica |
| `TEVS_V31_CLI_PROGRAM_IR` | CLI | Program IR JSON no objeto | cargar IR V5 Total válido |
| `TEVS_V31_CLI_EPOCHS` | CLI | epochs fuera 1..1000000 | usar cota admitida |
| `TEVS_V31_LSP_PROJECT` | LSP | proyecto/overlay no analizable | corregir bindings y fuente |
| `TEVS_V31_RELEASE_LANGUAGE_VERSION` | release | lenguaje distinto de 3.1.0 | restaurar identidad |
| `TEVS_V31_RELEASE_CANDIDATE_STATUS` | release | status candidate incoherente | usar status de candidato admitido |
| `TEVS_V31_RELEASE_CANDIDATE_AUTHORITY` | release | candidate reclama stable/merge/publication | dejar autoridad falsa |
| `TEVS_V31_RELEASE_CANDIDATE_PARENT` | release | candidate declara parent estable | vaciar parent en perfil candidate |
| `TEVS_V31_RELEASE_STABLE_STATUS` | release | stable_request con status incorrecto | usar STABLE_ADMISSION_REQUESTED |
| `TEVS_V31_RELEASE_STABLE_AUTHORITY` | release | flags de autoridad incoherentes | stable true; merge/publication false |
| `TEVS_V31_RELEASE_PARENT_COMMIT` | release | parent no SHA-40 | usar commit exacto |
| `TEVS_V31_RELEASE_PARENT_RECEIPT` | release | receipt no SHA-256 | usar hash 64-hex |
| `TEVS_V31_RELEASE_PROFILE` | release | perfil desconocido | candidate o stable_request |

## Negativos ejecutables

`source-version`, `source-semicolon`, `source-required`, `source-duplicate` y `source-unit-set` son casos con `expected_diagnostic_code` exacto. Si un caso deja de fallar o cambia de código, `EXAMPLE_CASES` falla.

Autoridades: `tev_script/source_total_core_v31.py`, `tev_script/program_ir_v5_total.py`, `tev_script/runtime_v5_total.py`, `tev_script/cli_v31.py`, `tev_script/lsp_v31.py`, `tev_script/release_metadata_v31.py`.