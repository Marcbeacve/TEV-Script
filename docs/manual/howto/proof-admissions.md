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

`VerifiedProofAdmissionV1.build` valida que los cuatro hashes sean lowercase 64-hex, fija `status="VERIFIED"` y calcula `admission_hash` canónico.

No verifica la demostración externa. Que `verification_receipt_hash` corresponda realmente a una verificación válida es responsabilidad del verificador/proceso de admisión que produjo esa evidencia.

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

Guárdalo como JSON sin añadir metadata al mismo objeto. Unknown fields hacen que el validador cerrado de la admission lo rechace.

La CLI versionada valida este wire con `validate_verified_proof_admission` antes de compilar. Esa función vive en `tev_script.program_ir_v5_total` y no forma parte de `tev_script.__all__`; para embedding root estable, construye la admission con `VerifiedProofAdmissionV1` o valida el Program IR completo con `validate_total_core_program`.

## 3. Comprueba la authority

La admission sólo es válida en un root cuyo:

```text
program.authority_hash == admission.authority_hash
```

`VerifiedProofAdmissionV1.build` no puede comprobar esta igualdad por sí solo porque no recibe el programa. La comprobación pertenece a la construcción/validación del Program IR y vuelve a comprobarse en runtime.

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

## 6. Qué valida `VerifiedProofAdmissionV1.build`

- los cuatro hashes de entrada son lowercase 64-hex;
- el schema resultante es el de Proof Admission V1;
- `status` queda fijado a `VERIFIED`;
- `admission_hash` se calcula sobre el cuerpo canónico exacto.

No valida:

- que el receipt externo sea una demostración correcta;
- que el verifier sea confiable para tu política;
- que exista ya un programa con la misma authority;
- que el requirement sea usado por una Transformation concreta.

Esas propiedades requieren autoridades/artefactos externos o el Program IR que va a consumir la admission.

## 7. Qué valida la construcción/validación del programa

`TotalCoreProgramV1.build` y `validate_total_core_program` cierran la admission en el contexto del root. Entre otras cosas comprueban:

- admission bien formada y hash correcto;
- requirement único;
- admission hash único;
- authority igual al root;
- cada proof requirement usado por `apply` está cubierto;
- no existen admissions ambiguas para el mismo requisito.

## 8. Qué valida runtime

Runtime vuelve a comprobar requirement/admission/status/authority antes de un Apply proof-open. Después liga el uso concreto mediante `proof_use_hash`.

## 9. No mutar la Transformation original

El runtime crea un derivado execution-local para ejecutar con los requisitos ya satisfechos. La Transformation canónica conserva `proof_requirement_hashes`.

## 10. Diagnósticos útiles

```text
TEVS_V31_TOTAL_PROOF_FIELDS
TEVS_V31_TOTAL_PROOF_HASH
TEVS_V31_TOTAL_PROOF_AUTHORITY
TEVS_V31_TOTAL_PROOF_REQUIRED
TEVS_V31_RUNTIME_PROOF_REQUIRED
TEVS_V31_RUNTIME_PROOF_STATUS
TEVS_V31_RUNTIME_PROOF_AUTHORITY
```

## 11. Auditoría

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
- `docs/manual/tutorial/13-proof-admissions.md`
- `spec/TEV_SCRIPT_V31_TOTAL_CORE.md`
