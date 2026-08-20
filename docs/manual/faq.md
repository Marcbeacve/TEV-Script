# Preguntas frecuentes

## ¿TEVScript 3.1.2 es la versión del lenguaje?

No. `3.1.2` es el package current. El lenguaje current es `3.1.0` con source profile `total_core`.

## ¿Qué debo usar para un programa nuevo?

Un root `process ... version "3.1.0"` Total-Core. Las computaciones hijas `pure`, `recursive` y `effects` se escriben como source V2 `2.0.0` y se compilan a Program IR V4.

## ¿Por qué una unit 3.1 contiene source 2.0.0?

Porque 3.1 es aditivo. Reutiliza la semántica V2/V4 exacta en vez de copiarla/reinterpretarla dentro de V5.

## ¿Puedo escribir `fn` directamente en el root Total-Core?

No como declaración root current. `fn` pertenece a la source V2 de una unit. El root coordina facts, Fields, Transformations, labels y units.

## ¿`Field` es una variable mutable?

No. Es un snapshot semántico finito, canónico e inmutable. Un cambio produce otro Field mediante Transformation/Apply.

## ¿Un `field_hash` demuestra que sus hechos son verdaderos?

No. Demuestra identidad/integridad del contenido bajo el contrato. Truth/evidence authority es otra dimensión.

## ¿Qué diferencia hay entre Transformation y Apply?

Transformation describe/identifica un cambio propuesto. Apply es el juicio operacional que intenta aplicarlo a un Field bajo precondiciones/requisitos.

## ¿Los hashes `effects`/`resources` conceden permisos?

No. Son identidades de descripciones. Filesystem/red/Unity/hardware requieren capability/provider/grant explícitos.

## ¿TEVScript puede hacer I/O?

Puede modelar observations/commands/effects y conectarse a providers/adapters. El runtime portable no obtiene I/O ambiental por defecto.

## ¿Una unit `effects` escribe físicamente un archivo?

No necesariamente. Puede calcular estado/observaciones/intents. Physical commit se demuestra en la frontera provider correspondiente.

## ¿Qué es `effect_inputs`?

Evidence de instancia para units effects: scenario y opcional current state. Sus keys deben coincidir exactamente con las units `profile effects`.

## ¿Puedo inventar el `capability_table_hash` en JSON?

No. Debe proceder de la compilación/contrato de capabilities real de la unit.

## ¿TEVScript usa coma flotante?

El modelo portable usa valores exactos como `Int` y `Rat`. Un `float/double` de host es una conversión explícita de integración, no el significado original de `Rat`.

## ¿Hay loops infinitos?

El perfil portable usa loops/recursión acotados. Un proceso global abierto se representa por quanta finitos y continuations; puede vivir indefinidamente sin una operación individual infinita.

## ¿Qué significa `SUSPENDED`?

El quantum agotó su presupuesto sin alcanzar `halt`. Es un resultado normal reanudable, no una excepción.

## ¿Puedo reanudar un checkpoint `HALTED`?

No. Un checkpoint halted representa una ejecución terminada. Para ejecutar de nuevo, crea otra ejecución inicial.

## ¿La CLI pública tiene `resume`?

La CLI genérica `tev-script` current publica `run` con `--checkpoint-output`, pero no registra `resume`. La reanudación current puede hacerse por API Python; existe `resume-total` en la CLI versionada de bajo nivel, que no debe confundirse con la superficie genérica pública.

## ¿Qué es una proof admission?

Un objeto externo que liga requirement, verification receipt, verifier y authority con `status=VERIFIED`. Permite admitir un requisito de prueba; no es la prueba misma.

## ¿Puedo declarar una proof admission dentro de `.tevs`?

No para fabricar autoridad. Se suministra externamente al build/API/CLI.

## ¿Qué diferencia hay entre source semantic hash y program hash?

El primero identifica el modelo semántico de fuente. El segundo identifica el artefacto Program IR ejecutable completo, incluyendo evidence/units/admissions/bounds que correspondan.

## ¿Por qué cambia `program_hash` si sólo cambia el scenario de effects?

Porque el scenario participa en la instancia Program IR V4 del child aunque no cambie la semántica de source.

## ¿El orden de `--unit` importa?

No semánticamente: el mapping se canonicaliza. El orden de instrucciones/invocations sí puede importar.

## ¿Runtime ejecuta `.tevs` directamente?

No. Source se compila en build time. Runtime ejecuta IR canónico validado.

## ¿Python es la especificación?

No. Python es implementación/reference host. La autoridad son las specs/schemas/contratos normativos del perfil.

## ¿JavaScript y C# deben dar lo mismo?

Para el contrato portable que declaran soportar, deben pasar conformance/canonical vectors equivalentes. Un runtime independiente no puede redefinir hashes/semántica.

## ¿Puedo usar TEVScript en Unity?

Sí mediante el adapter/contrato Unity soportado. APIs de Unity siguen siendo del host y requieren fronteras explícitas; no se vuelven keywords TEVScript.

## ¿Qué hago ante un `TEVS_V31_*`?

Conserva el código exacto y busca en `docs/manual/diagnostics/current-inventory.md`. El inventario current está verificado contra las authorities del código.

## ¿Un PASS del validator documental certifica TEVScript?

No. Cierra cobertura/documentación. La certificación full sigue los comandos seleccionados por `REPOSITORY_CHANNEL.json` sobre el commit/tree exacto.

## ¿GitHub Actions certifica el repo?

No según la gobernanza actual: `github_actions=false`. La evidencia autoritativa es la campaña local definida por el repository channel.

## ¿Qué significa H_COMPLETE?

Que el manifest documental exige todas las secciones y sets de cobertura finales. No significa que los runners dinámicos de CERTIFY_FULL hayan PASS sobre ese commit.

## ¿Dónde empiezo?

1. `getting-started/`
2. `tutorial/`
3. `language-reference/`
4. HOWTO/integrations según tu proyecto.

Para mantener el runtime/compilador, añade después `internals/` y `versions/`.
