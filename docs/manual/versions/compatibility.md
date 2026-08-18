# Compatibilidad entre líneas de TEVScript

TEVScript conserva varias generaciones de lenguaje, IR y runtime. «Compatible» no significa «idéntico» ni autoriza a un runtime a reinterpretar un artefacto de otra línea. La compatibilidad válida siempre se expresa mediante una ruta concreta de versión, perfil, schema y entrypoint.

## Estado de las líneas de lenguaje

La matriz actual clasifica las líneas principales así:

```text
3.1.0  current      total_core
3.0.0  compatible   semantic_process
2.0.0  compatible   general_v2
1.0.0  historical   bounded_v1
```

`current` indica la superficie recomendada actual. `compatible` significa que el repositorio conserva una ruta explícita de compatibilidad. `historical` significa que la identidad se preserva como parte de la evolución y evidencia del proyecto, pero no constituye la ruta genérica actual.

## 3.1 Total-Core

Total-Core integra el proceso semántico V5 con unidades computacionales V4 cerradas. El programa raíz usa lenguaje `3.1.0`, perfil `total_core` y Program IR V5 Total-Core.

Las unidades hijas pueden usar Program IR V4 con perfiles:

```text
pure
recursive
effects
```

La unidad se valida con su propio contrato V4 y conserva su `program_ir_hash`. V5 la referencia por identidad; no vuelve a interpretar su computación.

## 3.0 semantic_process

La línea `3.0.0` introdujo el proceso semántico basado en `Field + Transformation` con `Apply` como juicio operacional. Sus artefactos Program IR V5 `semantic_process` siguen siendo compatibles, pero no deben aceptarse como si fueran artefactos `total_core`.

La distinción se reconoce por schema, versión y perfil, no sólo porque ambas líneas utilicen Program IR V5.

## 2.0 general_v2

V2 aporta computación general acotada y Program IR V4. Total-Core reutiliza unidades V4 como hijos cerrados. Esa reutilización es aditiva: no convierte un programa V2 en fuente Total-Core ni cambia retroactivamente su semántica.

## 1.0 bounded_v1

V1 conserva una superficie histórica explícitamente versionada. Incluye módulos/enlace, funciones puras, records, enums, `Option`, `Result`, `match`, `for` acotado, behaviors y capabilities tipadas, junto con lowering a IR V2/V3 según el perfil.

Los comandos V1 permanecen versionados para compatibilidad. No deben confundirse con el comando genérico `tev-script`, que actualmente está ligado a Total-Core 3.1.

## Compatibilidad de CLI

La regla es deliberadamente simple:

```text
tev-script       → superficie genérica actual 3.1 Total-Core
tev-script-v31   → entrypoint versionado Total-Core
tev-script-v3    → compatibilidad 3.0
tev-script-v2    → compatibilidad 2.0
tev-script-v1    → compatibilidad/histórico V1
```

Los entrypoints versionados no implican que todas las líneas compartan sintaxis o runtime.

## Compatibilidad de IR

Un runtime sólo acepta los schemas/perfiles para los que posee una ruta explícita. Por ejemplo:

```text
TEV_SCRIPT_PROGRAM_IR_V5_TOTAL_CORE_V1
    ≠
TEV_SCRIPT_PROGRAM_IR_V5_SEMANTIC_PROCESS_V1
```

Aunque ambos sean IR V5, su discriminador de perfil y su contrato raíz son distintos.

## Compatibilidad de valores

Las líneas que heredan el contrato portable de valores exactos deben preservar enteros/racionales exactos y serialización canónica. Una implementación host puede convertir un valor al exterior, pero esa conversión debe permanecer en una frontera explícita y no redefinir el valor portable.

## Checkpoints

Los checkpoints no son objetos de migración universal. Un checkpoint liga estado a identidades concretas de programa/IR y a su propio schema. Restaurar sobre un objetivo incompatible debe fallar cerrada.

## Efectos y capabilities

La compatibilidad de una declaración de efecto no concede autoridad en el host. Incluso si un runtime entiende el tipo de efecto, la ejecución física depende de grants/providers explícitos compatibles con ese despliegue.

## Cómo comprobar una ruta

Consulta `spec/TEV_SCRIPT_VERSION_MATRIX.json`. Una fila válida aporta, según el dominio, versión, perfil, estado, autoridad y a veces entrypoint. Si una combinación no tiene una fila resoluble exacta, no debe inferirse.

La implementación de referencia aplica esta política de forma fail-closed mediante `tev_script.platform_compatibility.resolve_runtime_route`.

## Regla práctica

Cuando leas una página antigua, identifica primero su versión/perfil. Cuando escribas código nuevo para la plataforma actual, usa la documentación `docs/manual/` y la superficie Total-Core 3.1 salvo que necesites deliberadamente una ruta de compatibilidad.