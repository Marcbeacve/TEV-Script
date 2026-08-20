# Arquitectura de validación

La validación documental es un **leaf gate**: comprueba que manual, ejemplos e inventarios describen la superficie real. No sustituye los nueve gates semánticos/plataforma ni otorga merge/publication authority.

`tools/validate_documentation_v31.py` verifica identidad de versión, estructura del manual, manifiesto, paths finales, bindings de fuente, casos ejecutables, diagnósticos, CLI/API pública e historia. `platform-check` y las campañas de conformance validan capas distintas.

El cierre sólo es reproducible sobre un commit/tree exacto. Un PASS documental sobre working tree distinto no certifica el candidato.