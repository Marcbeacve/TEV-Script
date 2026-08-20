# Pipeline de frontend a runtime

La ruta 3.1 es `fuente Total-Core → normalización → proceso V3 + unidades V2 → IR V4 por unidad → IR V5 Total-Core → validación canónica → runtime V5`. V1/V2 conservan además su parser/linker/lowering histórico.

La normalización 3.1 no recompone la semántica de los hijos. `compile_total_core_v31` usa los compiladores publicados, conserva el hash semántico de cada hijo y construye una identidad superior. La ejecución nunca debe confiar en un artefacto sin `validate_total_core_program`.

Fronteras: fuente = intención; IR = artefacto portable; runtime = ejecución validada; provider = efecto físico.