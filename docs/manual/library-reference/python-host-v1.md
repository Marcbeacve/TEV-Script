# Host de producción Python V1

Esta familia contiene 5 símbolos públicos para ejecutar **IR V3 precompilado** desde Python con una frontera de capability explícita. Es una superficie pública de integración/compatibilidad distinta del runtime Total-Core V5 actual.

La separación central es:

```text
fuente V1 --build helper--> IR V3 validado --PythonRuntimeHostV1--> ejecución
```

`PythonRuntimeHostV1` no contiene un entry point de compilación de fuente.

## `PythonCapabilityContractV1`

Dataclass inmutable y ordenable:

```text
PythonCapabilityContractV1(
    capability_id: str,
    parameters: tuple[str, ...],
    return_type: str,
    kind: str,
)
```

Describe el contrato que un artefacto IR V3 requiere del host. No concede la capability: el callable concreto se entrega al construir el host.

## `PythonProgramArtifactV1`

Vista inmutable de un Program IR V3 canónico validado.

Campos:

```text
canonical_ir_json
program_id
source_semantic_hash
ir_semantic_hash
required_capabilities
```

### `PythonProgramArtifactV1.from_ir(ir)`

```text
from_ir(ir: Mapping[str, Any]) -> PythonProgramArtifactV1
```

Valida `ir` con `validate_program_ir_v3`, lo serializa canónicamente y deriva el conjunto de capability contracts requerido.

### `PythonProgramArtifactV1.parse(text)`

Acepta únicamente JSON IR V3 canónico, permitiendo como única diferencia de archivo un LF terminal. Un objeto JSON semánticamente equivalente pero con otra presentación se rechaza con `TEVS_PYTHON_V1_ARTIFACT_CANONICAL`.

### `artifact.ir()`

Reconstruye el mapping IR a partir de la copia canónica preservada por el artefacto.

## `build_python_program_v1`

```text
build_python_program_v1(
    sources: Mapping[str, bytes],
) -> PythonProgramArtifactV1
```

Helper **de build**, no de producción: compila un mapping de fuentes V1 a IR V3 y devuelve un artefacto validado para el host Python.

## `build_python_program_v1_paths`

```text
build_python_program_v1_paths(
    paths: Sequence[str | Path],
) -> PythonProgramArtifactV1
```

Equivalente para un conjunto de rutas de fuente V1.

## `PythonRuntimeHostV1`

```text
PythonRuntimeHostV1(
    artifact: PythonProgramArtifactV1,
    capabilities: Mapping[str, Callable[..., Any]] | None = None,
    *,
    reject_unused_capabilities: bool = True,
)
```

Host de producción de menor autoridad para IR V3 precompilado.

Al construirlo:

- valida que todas las capabilities requeridas tengan binding;
- exige bindings callables;
- por defecto rechaza capabilities extra no usadas;
- crea `ScriptRuntimeV3` ligado al `source_semantic_hash` del artefacto.

Fallos relevantes:

```text
TEVS_PYTHON_V1_CAPABILITY_MISSING
TEVS_PYTHON_V1_CAPABILITY_UNUSED
TEVS_PYTHON_V1_CAPABILITY_BINDING_ID
TEVS_PYTHON_V1_CAPABILITY_BINDING_CALLABLE
```

### `artifact`

Property de sólo lectura que devuelve el `PythonProgramArtifactV1` ligado al host.

### `required_capabilities`

Property con la tupla canónica de `PythonCapabilityContractV1` requerida.

### `invoke(entity_id, event_id, *arguments)`

```text
invoke(
    entity_id: str,
    event_id: str,
    *arguments: Any,
) -> tuple[EmittedEventV3, ...]
```

Invoca un evento del runtime IR V3 y devuelve los eventos emitidos.

### `state(entity_id)` / `canonical_state(entity_id)`

Devuelven, respectivamente, la vista de estado y la representación canónica ofrecidas por `ScriptRuntimeV3`.

### Checkpoints

```text
capture_checkpoint() -> RuntimeCheckpointV2
capture_checkpoint_json() -> str
restore_checkpoint(checkpoint: RuntimeCheckpointV2 | str) -> None
```

La restauración reconstruye exactamente el runtime usando el mismo IR y capability map.

## Concurrencia

Una instancia de `PythonRuntimeHostV1` representa un dominio de ejecución serializado. `invoke`, acceso de estado y operaciones de checkpoint usan un lock no bloqueante. Acceso concurrente o reentrante falla con:

```text
TEVS_PYTHON_V1_HOST_BUSY
```

El host no introduce una semántica implícita de scheduling Python por permitir carreras.

## Aplicabilidad

Estos cinco símbolos permanecen públicos y soportados como frontera Python para IR V3/V1. Para código Total-Core 3.1 nuevo, consulta [`current-total-core.md`](current-total-core.md): es una familia semántica diferente, no una versión nueva de `PythonRuntimeHostV1`.
