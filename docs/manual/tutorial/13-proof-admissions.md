# 13 — Admisiones de prueba

Una fuente TEVScript no puede fabricar autoridad de prueba. Las `VerifiedProofAdmissionV1` llegan desde fuera, ligadas a `requirement_hash`, recibo del verificador, identidad del verificador y `authority_hash`. Sólo `status = VERIFIED` es admisible.

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

Este programa no necesita una prueba externa. Cuando una Transformation declara requisitos, Program IR valida que exista una admisión exacta y el runtime vuelve a comprobar autoridad y estado.

**Contraprueba:** Apply proof-open sin admisión exacta produce `TEVS_V31_TOTAL_PROOF_REQUIRED` antes de ejecutar o `TEVS_V31_RUNTIME_PROOF_REQUIRED` en la frontera runtime.

Autoridad: `spec/TEV_SCRIPT_V31_TOTAL_CORE.md`.