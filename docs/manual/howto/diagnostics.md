# HOWTO — Diagnosticar un fallo

1. Lee `diagnostic.code`; es más estable que el texto humano.
2. Identifica la fase por el prefijo (`SOURCE`, `TOTAL`, `RUNTIME`, `CLI`, `LSP`, `RELEASE`).
3. Reproduce con la entrada mínima.
4. Corrige la autoridad que corresponde: fuente, IR, checkpoint, binding de CLI o metadato.
5. Vuelve a ejecutar el mismo caso y confirma que no aparece otro código oculto por el primero.

No captures `TevScriptError` para convertirlo en PASS. En integraciones, conserva el código estructurado al cruzar la frontera host.

Referencia: `diagnostics/current-inventory.md`.