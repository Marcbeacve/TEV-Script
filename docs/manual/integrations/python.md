# Integración Python

## Semántica TEVScript
Program IR, hashes, Field/Transformation/Apply y recibos conservan su autoridad; Python es un host.

## Adaptador/proveedor
`PythonRuntimeHostV1` y las APIs actuales cargan/validan artefactos y conectan capacidades explícitas.

## Conversiones
Convierte valores Python sólo mediante el modelo portable/canónico; un `dict` arbitrario no es un IR válido.

## Capacidades
Concede únicamente contratos declarados y scoped.

## No soportado
No se asume que callbacks Python, excepciones o mutaciones de objetos sean semántica TEVScript.

<!-- tevdoc-source: examples/docs/v31/integrations/python/main.tevs -->
```tevs
process IntegrationPython version "3.1.0";
authority aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa;
quantum_steps 8;
unit Calc profile pure;
field actual = [];
label Start = invoke_v4 Calc result tev.integration.python End;
label End = halt;
entry Start;
```

Autoridad: `tev_script/python_host_v1.py`, `tev_script/source_total_core_v31.py`.