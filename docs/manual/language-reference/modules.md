# Módulos, linking y unidades

TEVScript posee dos mecanismos que pueden parecer «módulos» pero pertenecen a capas distintas:

1. **módulos/linking V1/V2** dentro de una generación de fuente;
2. **unidades V4 en Total-Core V5** para componer artefactos computacionales cerrados.

No son alias y no deben intercambiarse en documentación o tooling.

## Módulo V2

Forma de header:

```text
module My.Module version "2.0.0";
```

Un módulo V2 no tiene entry ejecutable, estado, observation lane, command o efecto físico. La superficie de módulo pure actual admite funciones plain/generic y exige al menos un `export` explícito.

## `import`

Forma:

```text
import Qualified.Module as Alias;
```

La resolución ocurre en build/link time. El alias es de fuente; la identidad del módulo se liga al ID/contenido canónico, no a una búsqueda runtime por filename.

## `export`

Marca la superficie que el módulo hace disponible al linking. Lo no exportado permanece privado por contrato aunque no exista una keyword `private` en el perfil descrito.

## Remote acquisition

Si el build obtiene un módulo por HTTPS, el locator no se convierte en identidad semántica. El contrato remoto liga un module ID a contenido SHA-256 exacto y, en perfiles firmados, a una identidad criptográfica externa.

Runtime network resolution está prohibida para este modelo: el artefacto ejecutable debe ser cerrado.

## Linking V1

La línea V1 conserva `TEV_SCRIPT_LINKED_PROGRAM_V1` y metadata de proyecto/lowering como compatibilidad. Su función es cerrar explícitamente el conjunto de fuentes antes de generar IR.

Total-Core no reemplaza retroactivamente ese linked-program contract.

## `unit` Total-Core 3.1

Forma:

```text
unit Calc profile pure;
unit Rec profile recursive;
unit Sensors profile effects;
```

Cada declaración exige una fuente hija aportada externamente por `unit_sources`. El set suministrado debe coincidir exactamente con el declarado.

## Profiles de unidad

```text
pure
recursive
effects
```

El perfil determina qué frontend/IR V4 exacto se espera. Un nombre de unidad no decide el perfil por convención.

## `unit_id`

El ID declarado forma parte de la identidad V5 de la unidad. Debe ser estable/único en el programa.

## `unit_hash`

Se deriva del schema de unidad, `unit_id`, profile y `program_ir_hash`. Permite que `invoke_v4` apunte al artefacto exacto en vez de a una ruta de build.

## Orden canónico

Las unidades del root V5 se ordenan por:

```text
(unit_id, unit_hash)
```

Por eso el orden de inserción de `unit_sources` no es semántico.

## `invoke_v4`

Forma 3.1:

```text
label A = invoke_v4 Calc result tev.result B;
```

El compiler resuelve `Calc` al `unit_hash` exacto. `result_relation` debe ser un ID estable y B un label válido.

## Comunicación padre/hijo

La unidad no comparte variables con el root. Tras la ejecución, V5 proyecta un payload de receipt al Field con la `result_relation` declarada.

Así la frontera es explícita:

```text
V4 child artifact
   ↓ receipt
bridge fact
   ↓ Apply
V5 parent Field
```

## Módulo V2 dentro de una unidad V4

Una unidad V2 puede a su vez haberse construido desde módulos/linking. El orden conceptual es:

```text
fuentes/módulos V2
      ↓ link/compile
Program IR V4 cerrado
      ↓ embed
Total-Core unit V5
```

No existe import dinámico desde un label Total-Core.

## Errores representativos

- module/import no resuelto durante build;
- contenido remoto cuyo hash no coincide;
- runtime intentando resolver red para import;
- unidad declarada sin fuente;
- fuente extra no declarada;
- `unit_id` duplicado;
- profile/schema hijo incompatible;
- `invoke_v4` a unit desconocida.

## Autoridad técnica

- `spec/TEV_SCRIPT_V1_LINK_MODEL.md`
- `spec/TEV_SCRIPT_V2_LANGUAGE.md`
- `spec/TEV_SCRIPT_PROGRAM_IR_V4.md`
- `spec/TEV_SCRIPT_V31_TOTAL_CORE.md`
- `tev_script/source_total_core_v31.py`
