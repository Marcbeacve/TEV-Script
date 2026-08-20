# Internals de TEVScript

Esta sección explica cómo está ensamblada la plataforma y dónde vive cada autoridad técnica. Está dirigida a mantenedores, autores de runtimes/adapters y personas que necesiten depurar una discrepancia entre source, IR, runtime y receipts.

No convierte detalles internos en sintaxis pública.

## Mapa

- [`pipeline.md`](pipeline.md) — source → modelos semánticos → IR → runtime.
- [`semantic-identity.md`](semantic-identity.md) — qué hash identifica qué objeto y qué cambios deben conservarlo/alterarlo.
- [`ir-strata.md`](ir-strata.md) — V2/V3/V4/V5 y por qué no son una única versión lineal.
- [`runtime-boundaries.md`](runtime-boundaries.md) — responsabilidades del runtime y del host/provider.
- [`proof-capability-boundaries.md`](proof-capability-boundaries.md) — proof, authority, capability, resource y physical commit.
- [`validation-architecture.md`](validation-architecture.md) — conformance, platform gates, docs gates y certificación.

## Principio de mantenimiento

Antes de cambiar un comportamiento, identifica su dueño:

```text
source grammar/static semantics  → spec + frontend
canonical value/IR               → schema/spec + validator
execution                         → runtime del perfil
physical effect                   → adapter/provider
release identity                  → version matrix/platform metadata
```

Duplicar una regla en una capa vecina sin necesidad crea dos autoridades y deriva futura.
