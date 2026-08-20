# Proof admissions

## Clasificación

**CURRENT en Program IR/API**, pero **no es sintaxis de fuente que pueda fabricar verificación**.

Una proof admission es evidencia externa admitida para cerrar un `proof_requirement_hash` exacto de una Transformation.

## Schema

```text
TEV_SCRIPT_PROGRAM_IR_V5_PROOF_ADMISSION_V1
```

Campos cerrados:

```text
schema
requirement_hash
verification_receipt_hash
verifier_identity_hash
authority_hash
status
admission_hash
```

`status` debe ser exactamente `VERIFIED`.

## Hashes

Todos los campos de identidad hash son strings lowercase de 64 hex. `admission_hash` se calcula sobre el cuerpo con todos los campos anteriores excepto él mismo.

## `requirement_hash`

Identifica el requisito semántico exacto. Dentro de un programa es único entre admissions.

## `verification_receipt_hash`

Referencia el receipt producido por el proceso/verificador externo. La admission no sustituye el contenido/evidencia del receipt.

## `verifier_identity_hash`

Liga la identidad del verificador bajo el deployment/contrato correspondiente.

## `authority_hash`

Debe coincidir exactamente con `program.authority_hash`.

## `admission_hash`

Content-addresses la admission. Alterar verifier/receipt/authority/requisito invalida identidad.

## Construcción API

La clase pública root:

```text
VerifiedProofAdmissionV1
```

proporciona `build(...)`.

Mappings serializados se validan con `validate_verified_proof_admission` en `tev_script.program_ir_v5_total` y a través de las rutas de compilación/CLI que consumen admissions. Ese validador standalone **no se exporta desde `tev_script.__all__`**; es una superficie avanzada del módulo V5, no un símbolo adicional de la API root.

`VerifiedProofAdmissionV1.build` liga hashes y calcula la identidad de admission; no sustituye la verificación externa que produjo `verification_receipt_hash`.

## Entrada CLI

Los comandos de proyecto current aceptan:

```text
--proof-admission PATH.json
```

Puede repetirse. Cada archivo debe contener un objeto JSON exacto de admission; unknown/missing fields o hash inválido se rechazan.

## Compilación del root

Cuando una instruction `apply` referencia una Transformation con `proof_requirement_hashes`, `TotalCoreProgramV1.build` exige que todos estén presentes en el set de admissions.

Missing requirement:

```text
TEVS_V31_TOTAL_PROOF_REQUIRED
```

## Unicidad

Se rechazan:

- requirement duplicado;
- admission_hash duplicado;
- authority diferente.

## Runtime

Antes del Apply proof-open, el runtime vuelve a buscar admissions exactas y exige:

```text
exists
status == VERIFIED
authority == program.authority_hash
```

Crea un `proof_use_hash` que liga programa, authority, transformation, requirements y admissions seleccionadas.

## Execution-local derivative

El runtime crea una Transformation local con los mismos cambios/effects/resources pero sin requirements abiertos, únicamente para realizar ese Apply ya admitido.

La Transformation canónica original no se muta. Esto preserva auditabilidad: el artefacto sigue declarando que necesitaba prueba.

## No equivalencias falsas

```text
hash presente           ≠ prueba válida
status escrito a mano   ≠ verificación
admission               ≠ receipt de prueba
receipt                 ≠ verdad universal
```

Cada objeto tiene una función distinta.

## Fuente

La fuente Total-Core no incluye una declaración `proof_admission` que otorgue autoridad. Intentar introducirla como si fuera una keyword soportada no crea una admission válida.

## Fallos representativos

- `TEVS_V31_TOTAL_PROOF_FIELDS`
- `TEVS_V31_TOTAL_PROOF_HASH`
- `TEVS_V31_TOTAL_PROOF_REQUIREMENT_DUPLICATE`
- `TEVS_V31_TOTAL_PROOF_DUPLICATE`
- `TEVS_V31_TOTAL_PROOF_AUTHORITY`
- `TEVS_V31_TOTAL_PROOF_REQUIRED`
- `TEVS_V31_RUNTIME_PROOF_REQUIRED`
- `TEVS_V31_RUNTIME_PROOF_STATUS`
- `TEVS_V31_RUNTIME_PROOF_AUTHORITY`

## Autoridad técnica

- `spec/TEV_SCRIPT_V31_TOTAL_CORE.md`
- `tev_script/program_ir_v5_total.py`
- `tev_script/runtime_v5_total.py`
- `tev_script/cli_v31.py`
