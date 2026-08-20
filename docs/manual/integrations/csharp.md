# Integración C#

## Semántica TEVScript
C# ejecuta el contrato portable; no redefine hashes, tipos o transición.

## Adaptador/proveedor
`TevScript.Core` contiene runtime/conformance C# y los gates comparan resultados con los artefactos canónicos.

## Conversiones
Tipos CLR deben cruzar la frontera mediante el modelo de valor TEVScript y JSON canónico.

## Capacidades
I/O y APIs .NET se conceden en el host.

## No soportado
Reflexión, threads o excepciones CLR no son automáticamente observables TEVScript.

<!-- tevdoc-source: examples/docs/v31/integrations/csharp/main.tevs -->
```tevs
process IntegrationCSharp version "3.1.0";
authority aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa;
quantum_steps 8;
unit Calc profile pure;
field actual = [];
label Start = invoke_v4 Calc result tev.integration.csharp End;
label End = halt;
entry Start;
```

Autoridad: `runtimes/csharp/TevScript.Core/README.md`.