# Fronteras de prueba y capacidad

Una transformación puede declarar `proof_requirement_hashes`; la autoridad para satisfacerlos llega como `VerifiedProofAdmissionV1` externa. Fuente e IR no deben inventar receipts del verificador.

Las capacidades funcionan de forma análoga: el programa declara/necesita una operación, pero el host decide si existe un proveedor autorizado y su scope. Filesystem, red, reloj, Unity y otras APIs no son poderes implícitos.

Prueba y capacidad son fronteras distintas: una prueba puede autorizar una condición semántica sin conceder I/O; una capacidad puede permitir I/O sin demostrar una proposición.