# 07 — Capacidades y efectos

Los efectos físicos no forman parte de una ejecución portable implícita. Una unidad `effects` declara qué necesita; el host/proveedor aporta entradas externas y concede capacidades. Total-Core puede ejecutar el IR V4 de efectos, pero el commit físico permanece en la frontera del proveedor.

<!-- tevdoc-source: examples/docs/v31/tutorial/07_capabilities_effects/main.tevs -->
```tevs
process Tutorial07 version "3.1.0";
authority aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa;
quantum_steps 8;
unit Calc profile pure;
field actual = [];
label Start = invoke_v4 Calc result tev.tutorial.capability End;
label End = halt;
entry Start;
```

El ejemplo base no solicita capacidades; sirve para contrastar el caso seguro sin efectos. Al añadir una unidad `effects`, `effect_inputs` debe corresponder exactamente al conjunto de unidades de ese perfil.

**Contraprueba:** omitir la entrada externa de una unidad de efectos produce `TEVS_V31_SOURCE_EFFECT_INPUT_SET` o `TEVS_V31_SOURCE_EFFECT_INPUT_REQUIRED` según la frontera alcanzada.

Autoridad: `spec/TEV_SCRIPT_V2_FILESYSTEM_CAPABILITIES.md`, `spec/TEV_SCRIPT_V31_TOTAL_CORE.md`.