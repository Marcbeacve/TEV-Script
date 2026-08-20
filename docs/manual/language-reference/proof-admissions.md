# Admisiones de prueba

`VerifiedProofAdmissionV1` es **CURRENT** como frontera API/IR, pero no existe una declaración de fuente que permita fabricarla. La admisión contiene `requirement_hash`, `verification_receipt_hash`, `verifier_identity_hash`, `authority_hash`, estado `VERIFIED` y `admission_hash`.

Una admisión sólo autoriza el requisito exacto al que está ligada. Program IR rechaza duplicados, autoridad divergente y Apply proof-open sin admisión. El runtime repite las comprobaciones relevantes antes de materializar la transformación derivada de ejecución.

Por diseño, el compilador recibe `proof_admissions` desde el host. Esto separa «el programa pide una prueba» de «un verificador externo certificó la prueba».

Autoridad: `tev_script/program_ir_v5_total.py`, `tev_script/runtime_v5_total.py`, `spec/TEV_SCRIPT_V31_TOTAL_CORE.md`.