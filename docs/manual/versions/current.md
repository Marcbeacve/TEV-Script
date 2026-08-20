# Versión actual: qué significa cada número

La línea actual de desarrollo documentada aquí combina un **paquete `3.1.2`** con el **lenguaje `3.1.0`** y el perfil **`total_core`**. No es una errata: paquete y lenguaje son dominios de versión distintos.

## Identidad actual

```text
package_version                 = 3.1.2
language_version                = 3.1.0
current_profile                 = total_core
published_predecessor_package   = 3.1.1
archived_v31_package            = 3.1.0
```

El paquete `3.1.2` es una corrección posterior a la publicación de `3.1.1` y no cambia la semántica del lenguaje Total-Core `3.1.0`.

## Por qué existen `3.1.1` y `3.1.0` a la vez

`3.1.1` es el **predecesor publicado inmediato del paquete `3.1.2`**. Es la versión de paquete que precede directamente a la candidata actual.

`3.1.0`, en cambio, sigue identificando el **artefacto V31 archivado** bajo `packaging/v31/pyproject.toml` y también coincide numéricamente con la versión actual del lenguaje. Esa coincidencia no permite sustituir un dominio por otro.

La implementación protege esta distinción con dos identidades separadas:

```text
PUBLISHED_PREDECESSOR_PACKAGE_VERSION = 3.1.1
ARCHIVED_V31_PACKAGE_VERSION          = 3.1.0
```

## Herramientas actuales

El comando genérico `tev-script` está ligado a la plataforma Total-Core actual. Sus operaciones públicas actuales son:

```text
tev-script --version
tev-script describe
tev-script descriptor
tev-script check
tev-script compile
tev-script run
tev-script conformance
tev-script platform-check
```

`tev-script check`, `compile` y `run` delegan en la misma semántica Total-Core 3.1 expuesta de forma versionada por `tev-script-v31`. El comando genérico no define un segundo compilador.

El LSP genérico `tev-script-lsp` selecciona la implementación Total-Core cuando recibe lenguaje `3.1.0`. Una versión desconocida no se aproxima ni se infiere: falla cerrada.

## Fuente actual

El perfil Total-Core usa un proceso raíz de lenguaje `3.1.0` y puede declarar unidades V4 con perfiles:

```text
pure
recursive
effects
```

Las unidades V4 siguen conservando su propia identidad Program IR V4. Total-Core las incluye como artefactos hijos validados; no reinterpreta su computación como si fuera semántica V5.

## Runtime actual

El Program IR raíz actual es el perfil Total-Core de Program IR V5:

```text
schema           = TEV_SCRIPT_PROGRAM_IR_V5_TOTAL_CORE_V1
language_version = 3.1.0
profile          = total_core
```

El runtime ejecuta quanta finitos. Una computación global abierta se representa mediante continuación entre quanta, no mediante una operación individual ilimitada.

## Qué está publicado y qué está en desarrollo

La existencia del paquete candidato `3.1.2` en el árbol fuente no concede por sí sola autoridad de publicación, merge o tag. Las reglas de gobernanza del repositorio siguen siendo independientes de la semántica del lenguaje.

Este manual describe la superficie de código actual de la rama documentada. Cuando una página hable de un artefacto histórico o compatible, lo indicará explícitamente.

## Autoridades técnicas relacionadas

```text
tev_script/version.py
spec/TEV_SCRIPT_3_1_PLATFORM.md
spec/TEV_SCRIPT_VERSION_MATRIX.json
spec/TEV_SCRIPT_V31_TOTAL_CORE.md
tev_script/platform_versioning.py
tev_script/platform_tooling.py
```

Para entender por qué un único «número de versión» no es suficiente, continúa con [`version-domains.md`](version-domains.md).