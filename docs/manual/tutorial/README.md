# Tutorial progresivo de TEVScript 3.1

Esta ruta enseña TEVScript desde valores exactos hasta una aplicación Total-Core compuesta. El tutorial es pedagógico; la autoridad normativa sigue estando en `spec/` y la referencia de consulta en `docs/manual/language-reference/`.

## Antes de empezar

Completa primero `getting-started/first-program.md` y asegúrate de distinguir:

```text
package 3.1.2
lenguaje root 3.1.0 / total_core
fuente child V2 2.0.0
Program IR child V4
Program IR root V5
```

El tutorial mezcla esas capas deliberadamente, pero nunca cambia sus versiones para que «parezcan iguales».

## Bloque I — computación cerrada

1. [`01-values-exactness.md`](01-values-exactness.md) — `Int`, `Rat`, canonical values y frontera con float del host.
2. [`02-names-bindings-expressions.md`](02-names-bindings-expressions.md) — scopes, bindings inmutables y expresión tipada.
3. [`03-control-bounds.md`](03-control-bounds.md) — recursión contratada, loops acotados y quantum.
4. [`04-functions-types.md`](04-functions-types.md) — funciones, genéricos, tipos construidos y especialización.
5. [`05-data-models.md`](05-data-models.md) — records nominales, Option/Result y colecciones acotadas.

Al terminar este bloque deberías poder leer una unit V2 pura/recursiva y explicar por qué puede convertirse en un Program IR V4 cerrado.

## Bloque II — estado y composición

6. [`06-state-events.md`](06-state-events.md) — facts, Field y una transición `Idle → Running` ejecutable.
7. [`07-capabilities-effects.md`](07-capabilities-effects.md) — observations, state effects, scenarios y physical commit boundary.
8. [`08-modules-composition.md`](08-modules-composition.md) — dos units V4 de profiles distintos dentro de un root.
9. [`09-field-transformation-apply.md`](09-field-transformation-apply.md) — contrato Field/Transformation/Apply y `branch_fact` posterior.
10. [`10-processes-continuations.md`](10-processes-continuations.md) — ciclo real que acaba `SUSPENDED` por quantum finito.

Al terminar este bloque deberías distinguir estado child V2, Field padre V5, unit identity, bridge fact y capability/provider.

## Bloque III — Total-Core operativo

11. [`11-v4-units.md`](11-v4-units.md) — qué valida V4 y qué añade `TotalCoreUnitV1`.
12. [`12-total-core.md`](12-total-core.md) — estructura completa de Program IR V5 Total-Core.
13. [`13-proof-admissions.md`](13-proof-admissions.md) — requisitos de prueba y evidencia externa; por qué source no puede autoverificarse.
14. [`14-checkpoints-replay.md`](14-checkpoints-replay.md) — checkpoint, continuation, resume y replay.
15. [`15-complete-application.md`](15-complete-application.md) — pure + recursive + bridge facts + Transformation root + halt.

Al terminar deberías poder clasificar cada pieza de una aplicación en source, artifact, runtime evidence o host authority.

## Cómo usar los ejemplos

Cada bloque `tevs` presentado como ejecutable está ligado a un archivo real bajo `examples/docs/v31/tutorial/` con:

```text
<!-- tevdoc-source: ... -->
```

El validator compara bytes y cada directorio con `main.tevs` tiene un `case.json`. Los casos `operation: run` ejecutan quanta reales y distinguen `HALTED` de `SUSPENDED`; no se consideran correctos sólo porque la fuente compile.

## Qué no hace el tutorial

No usa hashes sintéticos como prueba real, no confunde un command intent con un commit físico y no presenta C#/Unity/WASM/WASI como runtime Total-Core cuando sus gates actuales pertenecen a perfiles compatibles anteriores.

Para firmas exactas, límites y diagnósticos ve a `language-reference/`, `library-reference/`, `cli-reference/` y `diagnostics/`.
