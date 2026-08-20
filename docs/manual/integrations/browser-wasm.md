# Integración Browser-WASM

## Semántica TEVScript
WASM es un destino de ejecución; la semántica sigue definida por el IR y el protocolo de conformance.

## Adaptador/proveedor
El gate Browser-WASM conecta módulo, JavaScript de arranque y runtime C# compilado.

## Conversiones
Los datos cruzan la frontera por esquemas serializados/canónicos, no por memoria compartida asumida.

## Capacidades
DOM, fetch, almacenamiento y reloj sólo existen si el host los expone.

## No soportado
No se presupone filesystem POSIX ni APIs de escritorio.

<!-- tevdoc-source: examples/docs/v31/integrations/browser-wasm/main.tevs -->
```tevs
process IntegrationBrowserWasm version "3.1.0";
authority aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa;
quantum_steps 8;
unit Calc profile pure;
field actual = [];
label Start = invoke_v4 Calc result tev.integration.browser_wasm End;
label End = halt;
entry Start;
```

Autoridad: `runtimes/csharp/TevScript.BrowserWasmGate/Program.cs`.