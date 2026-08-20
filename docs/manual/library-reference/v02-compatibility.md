# API Python compatible: superficie portable V0.2

Esta página documenta los **16 símbolos públicos** preservados de la línea portable V0.2. Su lenguaje es `0.2.0` y su IR es `TEV_SCRIPT_PROGRAM_IR_V2`; no deben confundirse con el lenguaje Total-Core `3.1.0` ni Program IR V5.

## Identidad

### `LANGUAGE_VERSION`

```text
LANGUAGE_VERSION == "0.2.0"
```

Constante de la línea portable V0.2.

### `IR_SCHEMA`

```text
IR_SCHEMA == "TEV_SCRIPT_PROGRAM_IR_V2"
```

Schema del Program IR V2 portable.

## Diagnósticos

### `SourceSpan`

Dataclass inmutable:

```text
SourceSpan(
    path: str,
    start_offset: int,
    end_offset: int,
    line: int,
    column: int,
)
```

`to_dict()` devuelve la representación estructurada de localización.

### `Diagnostic`

```text
Diagnostic(
    code: str,
    message: str,
    span: SourceSpan | None = None,
    hint: str = "",
)
```

`to_dict()` materializa `code`, `message`, `span` y `hint`.

### `TevScriptError`

Excepción de usuario derivada de `ValueError`. Conserva el `Diagnostic` estructurado en `error.diagnostic` y construye un mensaje humano con localización/hint cuando existen.

El código estructurado es la API estable para diagnóstico; no conviene parsear el string de excepción para recuperar campos.

## Compilación portable

### `CompilationBundle`

```text
CompilationBundle(
    ir: dict[str, Any],
    canonical_json: str,
)
```

Agrupa Program IR V2 validado y su serialización canónica.

### `compile_bytes`

```text
compile_bytes(
    path: str,
    data: bytes,
    *,
    debug_source_name: str | None = None,
    capability_catalog: Mapping[str, tuple[Signature, ...]] | None = None,
) -> CompilationBundle
```

Valida el presupuesto de fuente, decodifica/lexea/parsea y compila una única unidad V0.2. `debug_source_name` afecta la identidad/debug presentation, no cambia la semántica del programa. Un capability catalog adicional debe ser compatible con el catálogo portable base.

### `compile_path`

```text
compile_path(
    path: str | Path,
    *,
    debug_source_name: str | None = None,
    capability_catalog: Mapping[str, tuple[Signature, ...]] | None = None,
) -> CompilationBundle
```

Lee los bytes de una ruta y delega en `compile_bytes`.

### `compile_declaration`

```text
compile_declaration(
    declaration: ScriptDecl,
    *,
    debug_source_name: str | None = None,
    capability_catalog: Mapping[str, tuple[Signature, ...]] | None = None,
) -> dict[str, Any]
```

Compila un AST ya parseado. Exige `declaration.language_version == "0.2.0"`, aplica límites de entidades/states/handlers/locals/instrucciones y produce `TEV_SCRIPT_PROGRAM_IR_V2` con:

```text
semantic_hash
debug
debug_hash
boundary flags
```

El IR se revalida antes de devolverse.

## Valores exactos

### `encode_typed_value`

```text
encode_typed_value(type_name: str, value: Any) -> Any
```

Codifica los tipos portables:

```text
Bool
Int
Rat
Text
Vec2
Vec3
Unit
```

`Int` usa texto decimal canónico bajo `$int`; `Rat` usa numerador/denominador normalizados bajo `$rat`; vectores contienen componentes `Rat`. No usa float implícito para racionales.

### `decode_typed_value`

```text
decode_typed_value(type_name: str, raw: Any) -> Any
```

Decodifica y revalida la forma canónica. Rechaza, por ejemplo, `-0`, racionales no reducidos y denominador cero.

## Runtime portable

### `EmittedEvent`

```text
EmittedEvent(
    entity_id: str,
    event_id: str,
    arguments: tuple[Any, ...],
)
```

Evento producido por `ScriptRuntime`.

### `ScriptRuntime`

```text
ScriptRuntime(
    ir: Mapping[str, Any],
    capabilities: Mapping[str, Callable[..., Any]] | None = None,
)
```

Copia y valida Program IR V2 antes de crear el estado de entidades.

Métodos públicos principales:

```text
invoke(entity_id, event_id, *arguments) -> tuple[EmittedEvent, ...]
state(entity_id) -> dict[str, Any]
```

La cadena de eventos está acotada por `maximum_event_chain`; los handlers por `instruction_budget`. Una capability invocada sin binding produce `TEVS_RUNTIME_CAPABILITY_MISSING`.

La declaración semántica de una capability no crea el callable físico: el mapping del host es la frontera de autoridad efectiva.

## Conformance portable

### `run_conformance`

```text
run_conformance(
    ir: Mapping[str, Any],
    scenario: Mapping[str, Any],
) -> dict[str, Any]
```

Ejecuta un escenario con providers deterministas `constant`/`trace` y devuelve un `TEV_SCRIPT_CONFORMANCE_RECEIPT_V1` que liga:

```text
scenario_id
program_hash
final_states
emitted_events
capability_trace
receipt_hash
```

## Capability catalogs

### `parse_capability_catalog`

```text
parse_capability_catalog(
    raw: Any,
) -> dict[str, tuple[Signature, ...]]
```

Valida `TEV_SCRIPT_CAPABILITY_CATALOG_V1`. Cada entrada tiene exactamente:

```text
capability_id
parameters
return_type
kind
```

`kind` debe ser `observation` o `effect`; los parámetros no pueden usar `Unit` y están limitados a 64.

### `load_capability_catalog`

```text
load_capability_catalog(
    path: str | Path,
) -> dict[str, tuple[Signature, ...]]
```

Lee JSON estricto y delega en `parse_capability_catalog`.

Un catálogo describe contratos disponibles para compilación; no concede automáticamente esos effects al runtime.

## Aplicabilidad

Esta superficie sigue pública por compatibilidad, conformance y portabilidad. Para código nuevo:

- fuente Total-Core 3.1 → [`current-total-core.md`](current-total-core.md);
- host de IR V3 → [`python-host-v1.md`](python-host-v1.md);
- IR V3 directo → [`ir-v3.md`](ir-v3.md).
