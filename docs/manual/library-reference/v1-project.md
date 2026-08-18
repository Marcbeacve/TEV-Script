# API Python compatible: proyectos V1

Esta familia contiene **4 símbolos públicos** para manifests de proyecto V1 reproducibles.

## `ProjectSourceV1`

Dataclass inmutable:

```text
ProjectSourceV1(
    relative_path: str,
    path: Path,
    sha256: str,
    byte_count: int,
)
```

Representa una fuente ya resuelta, ligada tanto a su spelling portable relativo como a sus bytes exactos.

## `ProjectManifestV1`

Dataclass inmutable que conserva:

```text
manifest_path
base_directory
default_target
sources
normalized
canonical_json
manifest_hash
project_input_hash
```

Properties:

```text
source_paths
relative_sources
```

`input_witness()` devuelve el witness reproducible de manifest + paths + SHA-256 + tamaños, ligado por `project_input_hash`.

## `load_v1_project`

```text
load_v1_project(path: str | Path) -> ProjectManifestV1
```

Carga un manifest `TEV_SCRIPT_PROJECT_V1`, lenguaje `1.0.0`.

El manifest tiene field set cerrado:

```text
schema
language_version
default_target
sources
```

`default_target` debe ser uno de:

```text
auto
irv2
irv3
```

Límites actuales:

```text
manifest bytes ≤ 1_000_000
1 ≤ número de sources ≤ 257
```

Los source paths deben:

- ser relativos;
- usar `/`;
- no contener segmentos vacíos, `.` o `..`;
- usar segmentos portables;
- terminar en `.tevs`;
- resolver dentro del directorio de proyecto;
- no ser aliases de un mismo archivo.

El orden del array de presentación no es semántico: las fuentes se canonicalizan por path relativo.

## `verify_v1_project_inputs`

```text
verify_v1_project_inputs(
    manifest: ProjectManifestV1,
    witness: Mapping[str, object] | None = None,
) -> None
```

Vuelve a cargar el proyecto y exige que no hayan cambiado ni el manifest canónico ni los bytes de las fuentes. Si se suministra `witness`, debe coincidir canónicamente con `manifest.input_witness()`.

Fallos relevantes:

```text
TEVS_V1_PROJECT_MANIFEST_CHANGED
TEVS_V1_PROJECT_INPUT_CHANGED
TEVS_V1_PROJECT_INPUT_WITNESS
```

## Aplicabilidad

Esta API pertenece a proyectos V1 compatibles. Un proyecto Total-Core 3.1 usa bindings explícitos de la CLI/frontend actual y no necesita adoptar este manifest para ser válido.
