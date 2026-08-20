# Documentación de TEVScript

## Manual actual

La entrada principal para programadores es:

**[`manual/README.md`](manual/README.md)**

Cubre TEVScript `3.1.0 / total_core` distribuido actualmente por el package candidato `3.1.2`, y separa de forma explícita las superficies current de las de compatibilidad V0.2/V1/V2/V3.

Ruta recomendada:

1. [`manual/getting-started/`](manual/getting-started/)
2. [`manual/tutorial/`](manual/tutorial/)
3. [`manual/language-reference/`](manual/language-reference/)
4. [`manual/library-reference/`](manual/library-reference/) o [`manual/cli-reference/`](manual/cli-reference/) según integración
5. [`manual/howto/`](manual/howto/)
6. [`manual/integrations/`](manual/integrations/) para la matriz de hosts current/compatibility
7. [`manual/diagnostics/`](manual/diagnostics/) para `TEVS_*`
8. [`manual/internals/`](manual/internals/) y [`manual/versions/`](manual/versions/) para mantenimiento

## Autoridad normativa

El manual explica pero no redefine el lenguaje. Las autoridades actuales viven en `../spec/`, especialmente:

- `TEV_SCRIPT_3_1_PLATFORM.md`
- `TEV_SCRIPT_3_1_NORMATIVE_INDEX.json`
- `TEV_SCRIPT_V31_TOTAL_CORE.md`
- `TEV_SCRIPT_VERSION_MATRIX.json`

## Validación

[`VALIDATION.md`](VALIDATION.md) conserva la evidencia histórica y los comandos que deben ejecutarse para el candidato actual. La documentación executable se comprueba con `../tools/validate_documentation_v31.py` y con la suite focal descrita allí.

`H_COMPLETE` en el manifest documental no sustituye `CERTIFY_FULL`: la certificación dinámica sigue requiriendo el commit/tree exacto y los runners seleccionados por `../REPOSITORY_CHANNEL.json`.

## Historial

Los demás documentos de `docs/` preservan especificaciones, handoffs, status y evidencia histórica. No deben reinterpretarse como la ruta pedagógica current si contradicen una autoridad 3.1 más nueva; consulta siempre `manual/versions/` y la matriz normativa para distinguir dominios de versión.
