# Integración C#

## Estado exacto

El árbol actual contiene runtimes/gates C# conformes para contratos **anteriores/compatibles**, pero no debe describirse `TevScript.Core` como runtime Program IR V5 Total-Core.

`runtimes/csharp/TevScript.Core/README.md` declara explícitamente:

```text
implements TEV_SCRIPT_PROGRAM_IR_V2
```

Por tanto la clasificación correcta aquí es **COMPATIBILITY**, no «C# current Total-Core».

## TevScript.Core

Características de la implementación portable V0.2/IR V2:

- `netstandard2.1` library;
- sin dependencia UnityEngine;
- sin reflection/dynamic code/source interpretation como base del core;
- smoke/conformance hosts .NET;
- canonical vectors/strict JSON/negative IR/capability failure/parity gates.

## Evidencia histórica observada

La documentación de Core registra, entre otras:

```text
CSHARP_CORE_BUILD=PASS
CSHARP_GATE1_SMOKE=PASS
CSHARP_CANONICAL_VECTORS=12_PASS
CSHARP_IR_NEGATIVE_CAMPAIGN=PASS
CSHARP_PYTHON_JAVASCRIPT_BYTE_PARITY=PASS
CSHARP_CONFORMANCE_SCENARIOS=4_PASS
```

Estas evidencias pertenecen al contrato que ejecutaron. No se promueven a V5 Total-Core por herencia.

## IR V3 C#

El repositorio también contiene capas C# V3 usadas por gates como WASI (`TevScript.Core.V3`). De nuevo, IR V3 compatible y V5 Total-Core son dominios diferentes.

## Qué puede hacer hoy un integrador C#

- usar los runtimes C# para los artefactos/profiles que declaran soportar;
- usar adapters Unity construidos sobre ese Core según su contrato;
- verificar parity mediante las campañas correspondientes.

Si necesita un runtime C# V5 Total-Core, debe existir una implementación que valide/ejecute el schema V5 actual y pasar conformance específica antes de afirmar soporte. No basta adaptar el nombre de schema.

## Conversiones CLR

Los valores portables deben cruzar por el modelo de valor/canonical JSON. Tipos CLR (`double`, `Dictionary`, exceptions, reflection objects) no son semántica TEVScript por defecto.

## Capabilities

I/O/.NET APIs pertenecen al host/provider. Un runtime portable no gana `System.IO`, network o threading como semantic authority por ejecutarse en CLR.

## Threads y scheduling

La existencia de Tasks/threads CLR no redefine el modelo determinista de tasks TEVScript. Si un host paraleliza trabajo permitido, el resultado canónico no puede depender del scheduling.

## Sobre el fixture 3.1 de documentación

`examples/docs/v31/integrations/csharp/` se valida como source Total-Core por el validator documental Python. **No es evidencia de ejecución C# V5**; la evidencia C# real está en los gates del runtime C# compatible.

## Autoridad

- `runtimes/csharp/TevScript.Core/README.md`
- `RUN_TEV_SCRIPT_CSHARP_CONFORMANCE_V1.ps1`
- `spec/TEV_SCRIPT_VERSION_MATRIX.json`
