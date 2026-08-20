# Integración JavaScript

## Estado

JavaScript es el **runtime independiente requerido** por el descriptor Total-Core current. La implementación vive en `runtime_js_v31/` y reproduce el contrato V5 sin delegar la semántica a Python.

## Componentes

```text
runtime_js_v31/core.mjs
    canonical Field/Transformation/Program/Checkpoint validation

runtime_js_v31/v4_governed.mjs
    ejecución de children V4 pure/recursive/effects bajo contrato

runtime_js_v31/runtime_v5_total.mjs
    quantum loop Total-Core y CLI stdin/stdout de runtime
```

## Ejemplo source 3.1

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

La compilación de source current sigue siendo una fase de build; el runtime JS consume Program IR/checkpoint.

## Validación independiente

`validateProgram` comprueba field set cerrado, schema/version/profile, hashes, ordering, proof authority, instructions/targets y program hash. No considera válido un JSON sólo porque Python lo haya producido.

## Field/Transformation

`core.mjs` implementa `validateFact`, `fieldValue`, `validateField`, `transformationValue`, `applyTransformation` y proof-admitted Apply con canonical hashes compartidos.

Esto permite detectar deriva de semántica entre runtimes, no sólo comparar output final.

## Runtime request

`runtime_v5_total.mjs` lee por stdin un strict JSON con:

```json
{
  "program": {"...":"Program IR V5"},
  "checkpoint": {"...":"checkpoint V5"}
}
```

valida ambos y escribe el quantum result como canonical JSON + LF.

## Quantum loop

Implementa exactamente:

```text
apply
branch_fact
jump
invoke_v4
halt
```

con `SUSPENDED` al agotar el quantum, continuation/checkpoint y accounting de V5/V4 steps.

## Bridge V4→V5

Tras un child receipt, JS construye el mismo fact/Transformation puente que el runtime Python y exige Apply PASS. Pure/recursive y effects tienen payloads diferenciados.

## Proof admissions

El runtime JS valida admission hash/authority y genera el mismo `proofUseHash` conceptual antes de crear la transformation local proof-admitted.

## Canonical JSON

Usa `javascript/src/canonical.mjs` y strict JSON. No dependas de `JSON.stringify` genérico como definición del formato canónico salvo a través del helper gobernado.

## Números JavaScript

Los enteros estructurales de control se restringen a `Number.isSafeInteger` donde el contrato usa números JSON. Los valores TEV exactos V4 mantienen sus encodings canónicos; no se deben convertir silenciosamente a `Number` aproximado.

## Node frente a navegador

El entrypoint `runtime_v5_total.mjs` usa `process.stdin/stdout`, por lo que es un host Node. Que `core.mjs` sea ECMAScript modular no constituye evidencia de un runtime Total-Core Browser-WASM certificado.

## Errores

Los errores JS current usan códigos propios `TEVS_V31_*` de la implementación independiente (por ejemplo field/program/checkpoint/proof), útiles para conformance. No tienen que ser texto idéntico a Python si el contrato sólo fija semántica, pero no pueden aceptar estados que Python/normativa rechazan.

## Autoridad

- `runtime_js_v31/core.mjs`
- `runtime_js_v31/runtime_v5_total.mjs`
- `runtime_js_v31/v4_governed.mjs`
- `javascript/src/canonical.mjs`
- `spec/TEV_SCRIPT_V31_TOTAL_CORE.md`
