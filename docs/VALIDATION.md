# Validation

## Current certified surface

La evidencia histórica/certificada existente permanece autoritativa en sus receipts; este documento no la reescribe. Los gates de plataforma, conformance multihost, C#, WASM/WASI, schema y determinismo siguen siendo independientes del gate documental.

## Validación de documentación 3.1

Ejecución focal durante desarrollo:

```powershell
python -m pytest -q tests/test_documentation_v31.py tests/test_documentation_coverage_v31.py tests/test_documentation_source_bindings_v31.py tests/test_documentation_example_cases_v31.py tests/test_documentation_diagnostics_v31.py tests/test_documentation_public_surface_v31.py tests/test_documentation_closure_v31.py
python tools/validate_documentation_v31.py --root .
```

Regresión de identidad/plataforma exigida antes de cerrar el parche:

```powershell
python -m pytest -q tests/test_platform_version_identity.py tests/test_platform_normative_spec.py tests/test_platform_version_matrix.py tests/test_platform_tooling.py
python -m tev_script.cli platform-check --root .
```

Como el parche modifica `tests/**`, `examples/**`, `tools/**` y documentación normativa/indexada, la certificación final debe ejecutar además cualquier comando causalmente seleccionado por `REPOSITORY_CHANNEL.json`. El validador documental es un leaf gate y no rebaja los gates semánticos existentes.

No hay GitHub Action autoritativa. La evidencia de cierre debe corresponder a un commit/tree exacto y limpio. `MERGE_AUTHORITY` y `PUBLICATION_AUTHORITY` permanecen falsas hasta autorización explícita.