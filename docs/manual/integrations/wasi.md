# Integración WASI

## Semántica TEVScript
WASI no añade instrucciones TEVScript; proporciona un entorno de host para un runtime portable.

## Adaptador/proveedor
El gate WASI valida que la implementación mantenga conformance e identidad al salir del entorno nativo.

## Conversiones
Argumentos/archivos/stdio del host deben transformarse en inputs explícitos.

## Capacidades
Preopens y otras capacidades WASI se conceden fuera del lenguaje.

## No soportado
No se asume acceso al filesystem completo, sockets o variables de entorno.

<!-- tevdoc-source: examples/docs/v31/integrations/wasi/main.tevs -->
```tevs
process IntegrationWasi version "3.1.0";
authority aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa;
quantum_steps 8;
unit Calc profile pure;
field actual = [];
label Start = invoke_v4 Calc result tev.integration.wasi End;
label End = halt;
entry Start;
```

Autoridad: `runtimes/csharp/TevScript.V3WasiGate/Program.cs`.