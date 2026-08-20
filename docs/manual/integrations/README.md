# Integraciones y hosts

Esta sección separa **soporte del lenguaje current** de **compatibilidad de runtimes/adapters históricos**. Que exista código C#/Unity/WASM/WASI en el repositorio no implica automáticamente que ese host ejecute Program IR V5 Total-Core.

## Matriz actual

| Integración | Contrato demostrado en el árbol actual | Relación con Total-Core 3.1 |
|---|---|---|
| Python | API/reference runtime V5 Total-Core + host V1 compatible para IR V3 | **CURRENT** para Total-Core mediante API Python |
| JavaScript | runtime independiente `runtime_js_v31` para V5 Total-Core + V4 governed children | **CURRENT / independent required target** |
| C# | `TevScript.Core` V0.2/IR V2 y otras capas de compatibilidad; conformance histórica | **COMPATIBILITY**, no afirmar runtime V5 Total-Core C# actual |
| Unity | adapter C# portable V2/Core con gates Editor/Mono/IL2CPP | **COMPATIBILITY host**, no runtime V5 Total-Core certificado |
| Browser-WASM | Gate 6B sobre C# `TevScript.Core` portable | **COMPATIBILITY gate**, no V5 Total-Core browser certificado |
| WASI | Gate C# de **IR V3** con checkpoint/restart | **COMPATIBILITY gate**, no V5 Total-Core WASI certificado |
| Filesystem | capability profile V2 `file.read` / `file.replace` + provider seguro | **COMPATIBLE child/provider boundary**, no runtime target por sí solo |

La autoridad de runtime targets current del descriptor 3.1 enumera `python_reference` y `javascript_independent_required`.

## Sobre `examples/docs/v31/integrations/`

Esos casos son **fixtures semánticos/documentales 3.1** que el validator compila con el frontend current. No son por sí solos evidencia de que el host cuyo nombre aparece en la carpeta haya ejecutado V5. La evidencia host real está en los gates/receipts específicos citados por cada página.

## Regla de integración

Una integración correcta mantiene:

```text
semántica TEVScript portable
        ↓ artefacto/receipt
adapter del host
        ↓ conversiones/capabilities explícitas
provider físico
```

No permitas que tipos, scheduling, excepciones o I/O del host redefinan hashes/semántica portable.
