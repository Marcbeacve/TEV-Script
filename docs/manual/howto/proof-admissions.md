# HOWTO — Suministrar una admisión de prueba

Obtén el `requirement_hash` de la transformación. Ejecuta el verificador externo autorizado y conserva su receipt/hash e identidad. Construye una `VerifiedProofAdmissionV1` ligada a la misma `authority_hash` del programa. Pásala al compilador mediante la API o `--proof-admission`.

No modifiques la Transformation para borrar sus requisitos: el runtime sólo deriva una copia local sin requisitos después de validar la admisión exacta.

Errores típicos: requisito faltante, duplicado, autoridad divergente o receipt no canónico.