# Diagnósticos

La referencia actual y autoauditable está en [`current-inventory.md`](current-inventory.md). `DIAGNOSTIC_COVERAGE_V31.json` liga cada familia a su archivo de autoridad y usa descubrimiento wildcard: un literal `TEVS_V31_*` nuevo en una autoridad cubierta no queda documentado por accidente; el validador exige que el código aparezca en el inventario.

Páginas temáticas históricas/concretas: `source.md`, `program-ir.md`, `runtime.md`, `release-tooling.md`.

Para automatización, compara `diagnostic.code`; el mensaje humano puede ganar contexto sin cambiar el código. Los ejemplos negativos bajo `examples/docs/v31/diagnostics/` fijan casos ejecutables.