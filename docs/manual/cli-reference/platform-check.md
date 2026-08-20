# `tev-script platform-check`

## Sinopsis

```text
tev-script platform-check [--root PATH]
```

## Propósito

Valida los gates fundacionales de identidad y tooling de la plataforma actual. Es una comprobación más pequeña que `RUN_TEV_SCRIPT_PLATFORM_COMPLETION.py`: no sustituye conformance completa, fuzz, reproducibilidad ni full regression.

## Argumentos

No tiene argumentos posicionales.

## Opciones

`--root PATH` selecciona la raíz a inspeccionar. Por defecto usa el directorio de trabajo actual.

## Gates actuales

El resultado incluye:

```text
VERSION_IDENTITY
NORMATIVE_SPEC
VERSION_MATRIX
TOOLING_3X
```

Estos gates comprueban que paquete/lenguaje/perfil, índice normativo, matriz de compatibilidad y rutas públicas de tooling siguen siendo coherentes.

## stdout

Emite `TEV_SCRIPT_PLATFORM_CHECK_V1` con:

```text
status
package_version
language_version
profile
gates
```

## stderr

La comprobación intenta representar los fallos de validación dentro del objeto de salida. Un error de ejecución ajeno al contrato es un fallo de herramienta/host.

## Exit codes

```text
0  todos los gates fundacionales pasan
1  al menos un gate falla
```

## Ejemplo positivo

```text
tev-script platform-check --root .
```

## Qué no demuestra

`platform-check=PASS` **no** implica por sí solo:

```text
PLATFORM_COMPLETION=PASS
STABLE_ADMISSION=PASS
PUBLICATION_AUTHORITY=true
MERGE_AUTHORITY=true
```

Es una comprobación fundacional, no el agregador final de release.

## Versión/perfil

Aplica a la plataforma candidata `3.1.2`, lenguaje `3.1.0`, perfil `total_core`.

## Relacionado

- [`conformance.md`](conformance.md)
- `RUN_TEV_SCRIPT_PLATFORM_COMPLETION.py`
- `docs/STATUS.md`
