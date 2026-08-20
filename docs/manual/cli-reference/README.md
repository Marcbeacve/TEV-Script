# Referencia de la CLI actual

Esta sección documenta la superficie genérica `tev-script` del paquete candidato `3.1.2`, lenguaje `3.1.0`, perfil `total_core`.

La CLI actual contiene exactamente estos comandos públicos:

```text
describe
descriptor
check
compile
run
conformance
platform-check
```

y la opción raíz TEV declarada explícitamente:

```text
--version
```

`argparse` añade además su ayuda estándar `-h` / `--help` al parser raíz y a los subcomandos. Esa ayuda generada es pública para el usuario, pero no forma parte del inventario de opciones TEV declaradas que `DOCUMENTATION_COVERAGE_V1.json` deriva de llamadas explícitas `add_argument`.

Las líneas históricas `tev-script-v1`, `tev-script-v2`, `tev-script-v3` y el entry point explícito `tev-script-v31` son superficies versionadas/compatibles; no se mezclan con el camino recomendado de un usuario nuevo.

## Índice

- [`version.md`](version.md) — `tev-script --version`
- [`describe.md`](describe.md) — identidad de paquete/lenguaje/perfil y fronteras
- [`descriptor.md`](descriptor.md) — descriptor Total-Core 3.1
- [`check.md`](check.md) — comprobar fuente sin escribir IR
- [`compile.md`](compile.md) — compilar fuente a Program IR V5
- [`run.md`](run.md) — ejecutar Program IR V5
- [`conformance.md`](conformance.md) — conformance de plataforma
- [`platform-check.md`](platform-check.md) — gates fundacionales de plataforma

## Contrato común de salida

Las operaciones normales producen JSON estructurado y determinista. Los diagnósticos Total-Core de usuario usan el schema `TEV_SCRIPT_V31_DIAGNOSTIC_V1` y escriben el objeto diagnóstico en `stderr`. Los fallos de host/IO se distinguen de esos diagnósticos.

No uses el formato visual de espacios como API: consume los campos del JSON.

## Autoridad

La definición de argumentos está en `tev_script/cli.py`. `check`, `compile` y `run` delegan a la implementación Total-Core de `tev_script/cli_v31.py`; esa delegación no crea una segunda semántica.
