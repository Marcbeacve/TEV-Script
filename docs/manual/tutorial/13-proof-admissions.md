# 13 — Proof admissions: evidencia externa, no sintaxis mágica

Una Transformation puede declarar requisitos de prueba, pero una fuente `.tevs` **no puede declarar que esos requisitos ya están verificados**. Esa separación es intencionada: el programa formula la necesidad; una autoridad externa aporta evidencia de verificación.

## Ejemplo ejecutable sin prueba abierta

<!-- tevdoc-source: examples/docs/v31/tutorial/13_proof_admissions/main.tevs -->
```tevs
process Tutorial13 version "3.1.0";
authority aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa;
quantum_steps 8;
unit Calc profile pure;
field actual = [];
label Start = invoke_v4 Calc result tev.tutorial.proof End;
label End = halt;
entry Start;
```

Este programa no necesita proof admission y debe ejecutar como `HALTED`. Sirve como baseline: añadir texto que pretenda fabricar una admission en fuente debe ser rechazado.

## Por qué no hay un bloque `.tevs` que cree una admission

El primer frontend semantic-process/Total-Core no admite proof-open transformations como sintaxis capaz de crear autoridad verificada. `compile_total_core_v31` recibe las admissions por un argumento externo:

```text
proof_admissions = (...)
```

Esto impide un patrón circular como:

```text
"necesito prueba P"
"declaro en el mismo programa que P está probada"
```

## Estructura de `VerifiedProofAdmissionV1`

Una admission liga exactamente:

```text
schema = TEV_SCRIPT_PROGRAM_IR_V5_PROOF_ADMISSION_V1
requirement_hash
verification_receipt_hash
verifier_identity_hash
authority_hash
status = VERIFIED
admission_hash
```

Todos los hashes de identidad son SHA-256 lowercase de 64 hex.

## `requirement_hash`

Identifica el requisito exacto que una Transformation declara. Dentro de un programa, dos admissions no pueden cubrir el mismo `requirement_hash` como si fueran dos verdades independientes ambiguas.

## `verification_receipt_hash`

Liga la evidencia/receipt producido por el proceso de verificación externo. La admission no contiene una frase humana «verificado por X» como sustituto del receipt.

## `verifier_identity_hash`

Identifica al verificador bajo el contrato de integración. No se infiere de quién ejecutó Python ni de un username ambiental.

## `authority_hash`

Debe ser exactamente el mismo que `program.authority_hash`. Una prueba válida en otra autoridad/scope no se transplanta silenciosamente.

## `status = VERIFIED`

El schema V1 de admission sólo admite el estado verificado en el artefacto admitido. Estados abiertos o ambiguos deben resolverse fuera antes de construir este objeto; no se convierten automáticamente a VERIFIED.

## `admission_hash`

Se calcula sobre todos los campos anteriores salvo él mismo. Manipular el receipt, verifier o authority cambia la identidad de admission.

## Construcción desde la API pública Python

La API root pública expone `VerifiedProofAdmissionV1`, que construye y liga una admission ya verificada:

```python
from tev_script import VerifiedProofAdmissionV1, compile_total_core_v31

admission = VerifiedProofAdmissionV1.build(
    requirement_hash=requirement_hash,
    verification_receipt_hash=receipt_hash,
    verifier_identity_hash=verifier_hash,
    authority_hash=authority_hash,
)

program = compile_total_core_v31(
    process_source,
    unit_sources=units,
    proof_admissions=(admission,),
)
```

Los cuatro hashes deben proceder de artefactos/autoridades reales del sistema integrador; no uses strings arbitrarios como evidencia.

`VerifiedProofAdmissionV1.build(...)` valida forma e identidad de los hashes y calcula `admission_hash`, pero **no ejecuta la demostración** ni verifica por sí mismo que el receipt externo represente una prueba correcta. Esa autoridad pertenece al proceso/verificador que produjo el receipt.

## Validar una admission serializada

La implementación contiene también:

```text
validate_verified_proof_admission(value)
```

en `tev_script.program_ir_v5_total`. Acepta una instancia o mapping con el field set exacto, reconstruye la admission y rechaza schema/status/hash manipulados.

Esta función **no se exporta desde `tev_script.__all__`**. Por tanto no debe describirse como uno de los símbolos de la API root estable. La CLI versionada la usa para validar JSON de proof admission antes de compilar; un embedding que la importe directamente está usando una superficie avanzada del módulo V5 y debe mantener explícita esa dependencia.

Si la admission ya forma parte de un Program IR V5 completo, la API root `validate_total_core_program(...)` vuelve a validar las admissions como parte de la identidad total del programa.

## Admission estructural al construir el programa

`TotalCoreProgramV1.build` recopila todos los `proof_requirement_hashes` de cada Transformation usada por `apply`. Si falta uno, falla con `TEVS_V31_TOTAL_PROOF_REQUIRED`.

También rechaza:

- requirement duplicado;
- admission hash duplicado;
- authority distinta;
- admission malformada/manipulada.

## Comprobación en runtime

El runtime no confía ciegamente en que el objeto llegó al root. Antes de ejecutar un Apply proof-open vuelve a seleccionar admissions por requirement y comprueba:

```text
admission existe
status == VERIFIED
authority == program.authority_hash
```

Después crea una transformación **execution-local** sin requisitos abiertos, ligada a un `proof_use_hash` que registra qué admissions se consumieron para justificar esa ejecución.

## La Transformation canónica no se muta

Esto es crucial: el runtime no borra `proof_requirement_hashes` del artefacto original. Crea una derivación local para la ejecución admitida. El programa canónico conserva la información de que la Transformation era proof-open.

## Admission no es demostración

```text
prueba/verificación externa
        ↓ produce receipt
VerifiedProofAdmission
        ↓ permite cerrar requisito en un programa concreto
Apply
```

La admission es el **enlace gobernado** a la prueba, no la prueba misma.

## Qué no puede hacerse

- fabricar una admission desde la propia fuente;
- usar una admission de otra authority;
- reutilizar un requirement con hashes inconsistentes;
- cambiar `status` después de calcular el hash;
- considerar un SHA arbitrario como receipt verificado;
- hacer que utilidad/deseabilidad sustituya el requisito de prueba.

## Diagnósticos relevantes

- `TEVS_V31_TOTAL_PROOF_REQUIRED`;
- `TEVS_V31_TOTAL_PROOF_AUTHORITY`;
- `TEVS_V31_TOTAL_PROOF_REQUIREMENT_DUPLICATE`;
- `TEVS_V31_RUNTIME_PROOF_REQUIRED`;
- `TEVS_V31_RUNTIME_PROOF_STATUS`;
- `TEVS_V31_RUNTIME_PROOF_AUTHORITY`.

## Autoridad técnica

- `spec/TEV_SCRIPT_V31_TOTAL_CORE.md`, sección Proof admissions.
- `tev_script/program_ir_v5_total.py`.
- `tev_script/runtime_v5_total.py`.
