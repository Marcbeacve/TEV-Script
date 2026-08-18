# API Python compatible: Program IR V3

Esta página es la referencia canónica de los **13 símbolos públicos** relacionados con valores, validación, runtime, checkpoint y conformance de Program IR V3.

IR V3 es una superficie compatible importante y sigue siendo la frontera del `PythonRuntimeHostV1`; no es el Program IR actual de Total-Core, que es V5.

## Modelo de tipos y valores

### `TypeDescriptorV3`

Dataclass inmutable que describe un tipo V3. Campos:

```text
type_id
kind
fields
variants
argument
ok_type
err_type
```

Kinds cubiertos por la tabla actual:

```text
primitive
unit
record
enum
option
result
```

`field_type(name)` devuelve el tipo de un campo de record o `None` si no existe.

### `RecordValueV3`

```text
RecordValueV3(
    type_id: str,
    fields: tuple[tuple[str, Any], ...],
)
```

Representa un valor record ya decodificado. `field(name)` devuelve el valor exacto del campo o lanza `KeyError`.

### `VariantValueV3`

```text
VariantValueV3(
    type_id: str,
    variant: str,
    payload: Any = <missing>,
)
```

Representa enums, `Option` y `Result`. `has_payload` distingue canónicamente variantes con y sin payload.

### `TypeTableV3`

Tabla inmutable de `TypeDescriptorV3` con un límite `maximum_value_nesting`.

Métodos públicos:

```text
get(type_id) -> TypeDescriptorV3 | None
require(type_id, *, context="type") -> TypeDescriptorV3
is_storable(type_id) -> bool
variant_payload_type(type_id, variant) -> str | None
```

`require` falla con `TEVS_IR_V3_TYPE_UNKNOWN` cuando el tipo no existe. `Unit` no es storable como valor de estado.

### `build_type_table_v3`

```text
build_type_table_v3(ir: Mapping[str, Any]) -> TypeTableV3
```

Construye y valida la tabla de tipos del IR. Requiere los descriptores portables base, orden canónico, referencias cerradas, límites de nesting y records acíclicos.

### `decode_v3_value`

```text
decode_v3_value(
    type_id: str,
    raw: Any,
    table: TypeTableV3,
    *,
    context: str = "value",
    depth: int = 1,
) -> Any
```

Convierte la representación wire canónica en valores Python exactos/estructurados. Mantiene el límite de nesting y rechaza `Unit` como valor runtime.

### `encode_v3_value`

```text
encode_v3_value(
    type_id: str,
    value: Any,
    table: TypeTableV3,
    *,
    context: str = "value",
    depth: int = 1,
) -> Any
```

Realiza la conversión inversa. Para records y variantes exige instancias `RecordValueV3`/`VariantValueV3` del tipo exacto; no convierte arbitrariamente objetos Python parecidos.

## Validación de programa

### `validate_program_ir_v3`

```text
validate_program_ir_v3(
    ir: Any,
    *,
    expected_source_semantic_hash: str | None = None,
) -> TypeTableV3
```

Valida el Program IR V3 completo y devuelve su tabla de tipos. Entre sus invariantes:

- schema `TEV_SCRIPT_PROGRAM_IR_V3`;
- versión de lenguaje IR V3 `1.0.0`;
- combinación exacta `source_schema/lowering_profile`;
- `source_semantic_hash` opcionalmente ligado a una fuente esperada;
- boundary flags como `dynamic_code`, `reflection`, `unbounded_loops`, `implicit_physical_effects` y `runtime_source_compilation` deben permanecer `false`;
- entidades, states, capabilities, eventos, handlers y tablas deben tener forma y orden canónicos;
- `semantic_hash` y `debug_hash` se recalculan.

El validador es fail-closed: no normaliza un IR malformado para hacerlo pasar.

## Runtime IR V3

### `EmittedEventV3`

```text
EmittedEventV3(
    entity_id: str,
    event_id: str,
    argument_types: tuple[str, ...],
    arguments: tuple[Any, ...],
)
```

`canonical_arguments(table)` codifica los argumentos con el modelo de valores V3.

### `ScriptRuntimeV3`

```text
ScriptRuntimeV3(
    ir: Mapping[str, Any],
    capabilities: Mapping[str, Callable[..., Any]] | None = None,
    *,
    expected_source_semantic_hash: str | None = None,
)
```

Copia y valida el IR antes de construir el estado runtime. Los capability IDs suministrados deben ser identificadores estables canónicos.

Propiedades:

```text
source_semantic_hash
semantic_hash
```

Métodos principales:

```text
invoke(entity_id, event_id, *arguments) -> tuple[EmittedEventV3, ...]
state(entity_id) -> dict[str, Any]
canonical_state(entity_id) -> dict[str, Any]
```

`invoke` procesa una cadena de eventos acotada por `boundary.maximum_event_chain`; superar el límite produce `TEVS_IR_V3_EVENT_BUDGET`. Una capability requerida pero no enlazada produce `TEVS_IR_V3_CAPABILITY_MISSING`.

El runtime ejecuta instrucciones con un `instruction_budget` por handler; sobrepasarlo falla con `TEVS_IR_V3_INSTRUCTION_BUDGET`.

## Checkpoint V2 sobre IR V3

### `RuntimeCheckpointV2`

Dataclass inmutable con:

```text
program_id
ir_schema
semantic_hash
source_schema
source_semantic_hash
entities
```

Constructores/operaciones:

```text
RuntimeCheckpointV2.capture(runtime: ScriptRuntimeV3) -> RuntimeCheckpointV2
RuntimeCheckpointV2.parse(text: str) -> RuntimeCheckpointV2
checkpoint.to_object() -> dict[str, object]
checkpoint.to_canonical_json() -> str
checkpoint.checkpoint_hash -> str
checkpoint.restore_exact(ir, capabilities=None) -> ScriptRuntimeV3
```

`parse` exige JSON canónico **exacto**, no sólo JSON equivalente. `restore_exact` liga program id, IR schema, semantic hash, source schema, source semantic hash, conjunto de entidades, conjunto/tipos de states y sus valores. Una diferencia falla cerrado.

## Conformance IR V3

### `IrV3ConformanceReceiptBundle`

Dataclass inmutable:

```text
receipt: dict[str, object]
canonical_json: str
receipt_hash: str
```

Agrupa el receipt de una campaña, su serialización canónica y su hash.

### `run_ir_v3_conformance`

```text
run_ir_v3_conformance(
    ir: Mapping[str, Any],
    scenario: Mapping[str, Any],
) -> IrV3ConformanceReceiptBundle
```

Valida IR y escenario, ejecuta los pasos contra un host de capabilities **scriptado** y exige consumo exacto de las llamadas previstas. El receipt liga:

```text
scenario_hash
program_semantic_hash
source_semantic_hash
initial_state_hash
steps
capability_calls
final_state
final_state_hash
receipt_hash
```

La conformance no acepta llamadas extra ni deja llamadas scriptadas sin consumir. También compara argumentos y retornos mediante valores canónicos V3.

## Selección de esta familia

Usa estas APIs cuando:

- consumes o validas IR V3 existente;
- integras `PythonRuntimeHostV1`;
- necesitas checkpoints V2 de IR V3;
- ejecutas conformance de esa línea compatible.

Para código Total-Core V5 nuevo, consulta [`current-total-core.md`](current-total-core.md).
