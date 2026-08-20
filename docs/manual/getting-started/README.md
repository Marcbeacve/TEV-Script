# Getting Started

Esta ruta lleva desde cero hasta ejecutar y entender un proyecto Total-Core 3.1 por la superficie pública actual `tev-script`.

Orden recomendado:

1. [`installation.md`](installation.md) — qué instalar y qué versión estás usando.
2. [`first-program.md`](first-program.md) — comprobar, compilar y ejecutar el programa Total-Core mínimo.
3. [`project-layout.md`](project-layout.md) — cuándo un proyecto necesita unidades V4 y entradas externas.
4. [`cli-workflow.md`](cli-workflow.md) — flujo normal `check → compile → run` y qué frontera valida cada paso.

## Identidad de esta ruta

```text
package candidate = 3.1.2
language          = 3.1.0
profile           = total_core
public CLI        = tev-script
```

El paquete publicado inmediato es `3.1.1`. La rama de documentación está construida sobre el candidato `3.1.2`, que mantiene la semántica de lenguaje `3.1.0`.

## Qué no necesitas saber todavía

No necesitas empezar por Program IR, receipts, proof admission, WASM, adapters, Ω continuations ni por las líneas históricas V1/V2/V3. Esos conceptos aparecen cuando resuelven un problema concreto.

Sí conviene conservar desde el principio tres distinciones:

- **fuente** no es **IR de runtime**;
- declarar una **capability** no concede **autoridad física**;
- la versión del **paquete** no es la versión del **lenguaje**.
