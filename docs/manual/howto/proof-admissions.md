# Cómo construir y suministrar una Proof Admission

## Antes de empezar

Necesitas cuatro identidades **reales** del sistema de verificación/integración:

```text
requirement_hash
verification_receipt_hash
verifier_identity_hash
authority_hash
```

Si sólo tienes textos descriptivos, todavía no tienes una admission válida.

## 1. Construye el objeto con la API

```python
from tev_script import VerifiedProofAdmissionV1

admission = VerifiedProofAdmissionV1.build(
    requirement_hash=requirement_hash,
    verification_receipt_hash=verification_receipt_hash,
    verifier_identity_hash=verifier_identity_hash,
    authority_hash=authority_hash,
)
```

`build` valida 64-hex lowercase y calcula `admission_hash` canónico.

## 2. Serializa exactamente los campos del schema

```python
payload = {
    "schema": admission.schema,
    "requirement_hash": admission.requirement_hash,
    "verification_receipt_hash": admission.verification_receipt_hash,
    "verifier_identity_hash": admission.verifier_identity_hash,
    "authority_hash": admission.authority_hash,
    "status": admission.status,
    "admission_hash": admission.admission_hash,
}
```

Guárdalo como JSON sin añadir metadata al mismo objeto. Unknown fields hacen que el validator cerrado lo rechace.

## 3. Comprueba la authority

La admission sólo es válida en un root cuyo:

```text
program.authority_hash == admission.authority_hash
```

Si necesitas usar evidencia bajo otra authority, no edites el hash; debes pasar por el proceso de verificación/admisión que corresponda a ese scope.

## 4. Suministra a la CLI

```powershell
tev-script check .\main.tevs `
  --proof-admission .\proof-a.json `
  --proof-admission .\proof-b.json
```

Y en compile:

```powershell
tev-script compile .\main.tevs `
  --proof-admission .\proof-a.json `
  -o .\program.json
```

## 5. No intentes crearla desde `.tevs`

La fuente current no tiene autoridad para declararse a sí misma verificada. Una statement inventada `proof_admission ...;` no es el mecanismo correcto.

## 6. Qué valida el build

- schema/field set exacto;
- status VERIFIED;
- hashes bien formados;
- admission_hash correcto;
- requirement único;
- admission hash único;
- authority igual al root;
- cada proof requirement usado por Apply está cubierto.

## 7. Qué valida runtime

Runtime vuelve a comprobar requirement/admission/status/authority antes de un Apply proof-open. Después liga el uso concreto mediante `proof_use_hash`.

## 8. No mutar la Transformation original

El runtime crea un derivado execution-local para ejecutar con los requisitos ya satisfechos. La Transformation canónica conserva `proof_requirement_hashes`.

## 9. Diagnósticos útiles

```text
TEVS_V31_TOTAL_PROOF_FIELDS
TEVS_V31_TOTAL_PROOF_HASH
TEVS_V31_TOTAL_PROOF_AUTHORITY
TEVS_V31_TOTAL_PROOF_REQUIRED
TEVS_V31_RUNTIME_PROOF_REQUIRED
TEVS_V31_RUNTIME_PROOF_STATUS
TEVS_V31_RUNTIME_PROOF_AUTHORITY
```

## 10. Auditoría

Conserva juntos, pero como artefactos distintos:

```text
proof requirement
verification receipt
verifier identity
admission
program root
runtime proof_use_hash/receipt
```

Eso permite reconstruir por qué una ejecución fue admitida sin convertir el programa en su propio notario.

## Referencia

- `docs/manual/language-reference/proof-admissions.md`
- `spec/TEV_SCRIPT_V31_TOTAL_CORE.md`
