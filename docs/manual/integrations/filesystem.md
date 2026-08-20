# Integración filesystem

## Estado

Filesystem no es un runtime target. Es una **capability/provider boundary V2 compatible** con dos niveles que no deben confundirse:

```text
Effects R1 observation    file.read
Effects R2 command        file.replace
```

La ruta Total-Core 3.1 actual admite children `effects` **R1 de observación**. No admite Effects R2 de `command/request` como unidades hijas V5.

El perfil filesystem V2 definido por la spec contiene:

```text
observation file.read(Text) -> Text
command     file.replace(Text, Text)
```

No existe ambient `open()` portable.

## Frontera Total-Core actual: R1 sí, R2 no

`compile_total_core_v31` compila una unidad declarada:

```text
unit Fs profile effects;
```

mediante `compile_effect_program_v2`, es decir, la ruta **Effects R1 observation-only**. Si la fuente hija contiene:

```text
command file.replace(Text,Text);
request file.replace(...);
```

ese compilador falla cerrado con:

```text
TEVS_V2_EFFECT_R2_REQUIRED
```

porque esa sintaxis requiere `compile_effect_command_program_v2` y el contrato R2 separado.

La frontera no se evita precompilando el R2 por fuera: `TotalCoreUnitV1` current valida el schema V4 Effects admitido por Total-Core y no convierte automáticamente un artefacto R2 command en una unidad Effects R1.

Por tanto, en el estado actual:

```text
file.read evidence/scenario
    → puede alimentar un child Effects R1 Total-Core

file.replace command/request
    → contrato/provider V2 R2 compatible
    → NO es hoy un child Total-Core admitido por compile_total_core_v31
```

Una futura integración R2→V5 necesita una frontera/schema/validator explícitamente admitidos y su conformance; no debe inferirse por compartir la palabra `effects`.

## Root authority

El provider filesystem abre una raíz autorizada como objeto directory y conserva el handle. `authority_scope_hash` liga spelling canónico, plataforma e identidad del objeto/volume.

Reemplazar el path por otro directorio no conserva authority aunque el string sea igual.

## Admisión de paths

El argumento es relativo a la raíz. Se rechazan antes del acceso:

- absolute/UNC/rooted/drive paths;
- segmentos vacíos, `.` o `..`;
- NUL;
- trailing space/dot;
- colon/ADS;
- device names Windows `CON`, `PRN`, `AUX`, `NUL`, `COM1..9`, `LPT1..9`.

La traversal debe ser handle-relative y no-follow; no `lstat` seguido de path access vulnerable a TOCTOU.

## `file.read` — observation R1

- abre target una vez bajo root pinned;
- exige regular non-reparse file;
- lee máximo 1,048,576 bytes + un byte witness de overflow;
- overflow → `TEVS_FILE_READ_BUDGET`;
- strict UTF-8;
- evidence liga byte count + SHA-256;
- runtime posterior puede reproducir el scenario en vez de releer el host.

Esta es la parte del perfil filesystem que encaja conceptualmente con el child `effects` R1 admitido actualmente por Total-Core, siempre que se construya el scenario exacto exigido por la capability table del artefacto hijo.

## `file.replace` — command R2

El provider R2:

1. pin parent por traversal segura;
2. crea temporary regular file no-reparse;
3. escribe UTF-8 completo;
4. flush;
5. rewind/verifica bytes;
6. rename atómico handle-relative al target;
7. fsync parent donde el contrato/plataforma lo permita.

El rename es el linearization point.

Esta operación pertenece a la vía `command/request` R2. Su existencia y sus receipts **no demuestran** que el frontend/runtime Total-Core current pueda incorporar ese command como child V5.

## Symlinks/reparse attacks

Un symlink/junction/mount/reparse no puede redirigir la operación fuera de la raíz. Si la plataforma no ofrece primitivas que prueben esa propiedad, el provider falla cerrado; no cae a una implementación insegura «best effort».

## Same-content retry

Un no-op de contenido idéntico puede ser válido si el target se abre/verifica de forma segura. El receipt content-addressed permite retry sin una segunda rename física en ese caso.

## Receipt de replace

Liga:

```text
intent_hash
command_id = file.replace
authority_scope_hash
relative_path
data_sha256
byte_count
final_sha256
receipt_hash
```

El receipt demuestra la operación del provider en su linearization point; no demuestra que otro proceso no cambiara el archivo después ni concede soporte R2 al root V5.

## Failure/cleanup

Errores de path/type/reparse/root identity/primitive support/write/flush/rename/verify/budget/UTF-8/authority/hash fallan sin PASS receipt inventado.

Cleanup actúa sobre el temporary ya abierto, no hace un lookup inseguro nuevo que pueda borrar otro objeto.

## Relación con Total-Core

Una unit V2 Effects R1 puede usar observaciones filesystem como `file.read` y convertirse en child V4 de Total-Core si su evidence/scenario es válido. El root V5 sigue sin poseer filesystem ambient.

Effects R2 (`file.replace`, `request`) permanece en su ruta V2 de command planning/realization y provider físico. Total-Core current **no admite Effects R2** como child mediante `compile_total_core_v31`.

## Sobre el fixture documental 3.1

`examples/docs/v31/integrations/filesystem/` comprueba la source Total-Core current. No realiza acceso de filesystem físico, no ejecuta `file.read` real y no demuestra `file.replace` R2 dentro de V5.

## Autoridad

- `spec/TEV_SCRIPT_V2_FILESYSTEM_CAPABILITIES.md`
- `tev_script/source_effect_program_v2.py`
- `tev_script/program_ir_v5_total.py`
- `tev_script/source_total_core_v31.py`
- `schemas/tev-script-v2-filesystem-artifacts.schema.json`
- provider/validators filesystem del repositorio.
