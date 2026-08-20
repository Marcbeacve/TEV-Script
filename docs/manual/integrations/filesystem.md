# Integración filesystem

## Estado

Filesystem no es un runtime target. Es una **capability/provider boundary V2 compatible** que puede alimentar unidades effects y physical command realization bajo un contrato seguro.

El único perfil físico V2 conforming definido por la spec es:

```text
observation file.read(Text) -> Text
command     file.replace(Text, Text)
```

No existe ambient `open()` portable.

## Root authority

El provider abre una raíz autorizada como objeto directory y conserva el handle. `authority_scope_hash` liga spelling canónico, plataforma e identidad del objeto/volume.

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

## `file.read`

- abre target una vez bajo root pinned;
- exige regular non-reparse file;
- lee máximo 1,048,576 bytes + un byte witness de overflow;
- overflow → `TEVS_FILE_READ_BUDGET`;
- strict UTF-8;
- evidence liga byte count + SHA-256;
- runtime posterior reproduce scenario, no relee el host.

## `file.replace`

El provider:

1. pin parent por traversal segura;
2. crea temporary regular file no-reparse;
3. escribe UTF-8 completo;
4. flush;
5. rewind/verifica bytes;
6. rename atómico handle-relative al target;
7. fsync parent donde el contrato/plataforma lo permita.

El rename es el linearization point.

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

El receipt demuestra la operación del provider en su linearization point; no demuestra que otro proceso no cambiara el archivo después.

## Failure/cleanup

Errores de path/type/reparse/root identity/primitive support/write/flush/rename/verify/budget/UTF-8/authority/hash fallan sin PASS receipt inventado.

Cleanup actúa sobre el temporary ya abierto, no hace un lookup inseguro nuevo que pueda borrar otro objeto.

## Relación con Total-Core

Una unit V2 effects puede usar evidence/intents filesystem y ser child V4 de Total-Core. El root V5 sigue sin poseer filesystem ambient. El provider vive fuera y su evidence/receipt debe preservarse en la cadena correspondiente.

## Sobre el fixture documental 3.1

`examples/docs/v31/integrations/filesystem/` comprueba la source Total-Core current, no realiza un acceso de filesystem físico.

## Autoridad

- `spec/TEV_SCRIPT_V2_FILESYSTEM_CAPABILITIES.md`
- `schemas/tev-script-v2-filesystem-artifacts.schema.json`
- provider/validators filesystem del repositorio.
