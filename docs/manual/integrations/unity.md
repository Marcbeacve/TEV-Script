# Integración Unity

## Semántica TEVScript
El core portable sigue siendo independiente de `GameObject`, escena, frame rate o MonoBehaviour.

## Adaptador/proveedor
La capa Unity traduce eventos/estado del motor a capacidades y valores admitidos; el Core no llama directamente a la escena.

## Conversiones
Vectores, IDs y datos Unity deben convertirse explícitamente a una representación portable.

## Capacidades
Movimiento, filesystem, red o cambios de escena requieren concesión en la frontera Unity.

## No soportado
No se asume paridad por ejecutar sólo en Editor; existen gates Mono/IL2CPP/PlayMode separados.

<!-- tevdoc-source: examples/docs/v31/integrations/unity/main.tevs -->
```tevs
process IntegrationUnity version "3.1.0";
authority aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa;
quantum_steps 8;
unit Calc profile pure;
field actual = [];
label Start = invoke_v4 Calc result tev.integration.unity End;
label End = halt;
entry Start;
```

Autoridad: `adapters/unity/UNITY_ADAPTER_CONTRACT_V2.md`, `unity/Package/README.md`.