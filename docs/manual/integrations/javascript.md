# Integración JavaScript

## Semántica TEVScript
La implementación JS debe producir/consumir identidades canónicas equivalentes, no una semántica aproximada.

## Adaptador/proveedor
`runtime_js_v31/` implementa la ruta independiente; el adaptador web conecta I/O del navegador.

## Conversiones
`Number`, objetos y strings del host se admiten sólo donde el modelo portable lo permita; hashes y JSON canónico mandan.

## Capacidades
APIs del navegador son capacidades del host, no primitivas implícitas.

## No soportado
No se presupone acceso a Node, DOM, red o reloj si no existe adaptador/capacidad explícita.

<!-- tevdoc-source: examples/docs/v31/integrations/javascript/main.tevs -->
```tevs
process IntegrationJavaScript version "3.1.0";
authority aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa;
quantum_steps 8;
unit Calc profile pure;
field actual = [];
label Start = invoke_v4 Calc result tev.integration.javascript End;
label End = halt;
entry Start;
```

Autoridad: `runtime_js_v31/core.mjs`, `javascript/README.md`.