# API Python compatible: receipts de lowering V1

Esta familia contiene **6 símbolos públicos** que ligan un `TEV_SCRIPT_LINKED_PROGRAM_V1` con su imagen IR V2 o IR V3 validada.

Un lowering receipt es **evidencia de enlace entre artefactos**. No es un segundo `semantic_hash` ni una prueba general de corrección del lenguaje.

## IR V2 — perfil erasable

### `LoweringReceiptBundleV1`

```text
LoweringReceiptBundleV1(
    receipt: dict[str, object],
    canonical_json: str,
    receipt_hash: str,
)
```

### `build_ir_v2_lowering_receipt`

```text
build_ir_v2_lowering_receipt(
    source: LinkedProgramBundleV1,
    target: LinkedV1IrV2Bundle,
) -> LoweringReceiptBundleV1
```

Valida source y target y exige que `target.linked_semantic_hash == source.semantic_hash`.

El receipt usa:

```text
schema  = TEV_SCRIPT_LOWERING_RECEIPT_V1
profile = TEV_SCRIPT_V1_TO_IR_V2_ERASABLE_PROFILE_V1
```

y liga para source y target:

- schema/version;
- semantic hash;
- SHA-256 de los bytes JSON canónicos.

Las proof obligations registran que el boundary IR V2 era reducible y que la imagen target pasó su contrato.

### `verify_ir_v2_lowering_receipt`

```text
verify_ir_v2_lowering_receipt(
    receipt: Mapping[str, object],
    source: LinkedProgramBundleV1,
    target: LinkedV1IrV2Bundle,
) -> None
```

Recalcula el receipt esperado y exige igualdad canónica exacta. Rechaza field sets, schema/profile, hash o binding source/target manipulados.

## IR V3 — perfil completo

### `LoweringReceiptBundleV2`

```text
LoweringReceiptBundleV2(
    receipt: dict[str, object],
    canonical_json: str,
    receipt_hash: str,
)
```

### `build_ir_v3_lowering_receipt`

```text
build_ir_v3_lowering_receipt(
    source: LinkedProgramBundleV1,
    target: LinkedV1IrV3Bundle,
) -> LoweringReceiptBundleV2
```

El receipt usa:

```text
schema  = TEV_SCRIPT_LOWERING_RECEIPT_V2
profile = TEV_SCRIPT_V1_TO_IR_V3_FULL_PROFILE_V1
```

El target debe ser `TEV_SCRIPT_PROGRAM_IR_V3`, lenguaje `1.0.0`, lowering profile `TEV_SCRIPT_V1_IR_V3_PROFILE_V1`, y su `source_semantic_hash` debe ser exactamente el del linked source.

Las proof obligations incluyen preservación de tipos algebraicos, tabla de tipos cerrada y CFG validado.

### `verify_ir_v3_lowering_receipt`

```text
verify_ir_v3_lowering_receipt(
    receipt: Mapping[str, object],
    source: LinkedProgramBundleV1,
    target: LinkedV1IrV3Bundle,
) -> None
```

Revalida ambos artefactos, recalcula el receipt y exige igualdad canónica exacta.

## Qué garantiza y qué no

Un receipt válido demuestra que:

```text
este source canónico
        ↓ lowering perfil declarado
este target canónico validado
```

quedaron ligados por el contrato concreto de lowering.

No demuestra que cualquier otro runtime, fuente o target sea equivalente; tampoco autoriza una promoción de versión o un efecto físico.

## Aplicabilidad

Usa esta familia al auditar o transportar evidencia de lowering de la línea V1. Para Program IR V5 Total-Core actual, la identidad se expresa directamente por los contratos V5 y sus hashes/receipts propios.
