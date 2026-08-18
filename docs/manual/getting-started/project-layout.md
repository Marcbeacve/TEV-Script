# Estructura de un proyecto

Un proyecto Total-Core puede ser un único archivo o una raíz V5 que invoque unidades V4 explícitamente enlazadas.

## Caso mínimo

El primer ejemplo sólo necesita:

```text
project/
└── main.tevs
```

La fuente declara su `Field`, control de flujo y límites. Si no declara unidades V4, no debes suministrar mappings `--unit` adicionales: el frontend valida que el conjunto declarado y el suministrado coincidan exactamente.

## Proyecto con una unidad V4

Una composición típica puede tener:

```text
project/
├── main.tevs
└── calc.tevs
```

`main.tevs` declara una unidad, por ejemplo:

```text
unit Calc profile pure;
```

La CLI recibe la fuente concreta mediante un mapping explícito:

```text
tev-script check project/main.tevs --unit Calc=project/calc.tevs
```

El nombre de la izquierda debe coincidir con el `unit_id` declarado. No se infieren archivos por nombre ni por proximidad en el directorio.

## Perfiles de unidad V4

Total-Core 3.1 admite unidades hijas declaradas como:

```text
pure
recursive
effects
```

Una unidad declarada `pure` debe compilar realmente como una entrada pura; una discrepancia de perfil falla en compilación. El programa V5 conserva la identidad exacta del IR V4 hijo en lugar de reinterpretarlo como si fuese otra semántica.

## Effects: código y evidencia externa permanecen separados

Una unidad `effects` necesita su fuente y, cuando el contrato lo exige, un input externo explícito:

```text
project/
├── main.tevs
├── sensor.tevs
└── sensor-input.json
```

La invocación se expresa como:

```text
tev-script check project/main.tevs \
  --unit Effects=project/sensor.tevs \
  --effect-input Effects=project/sensor-input.json
```

El JSON externo no se convierte en semántica de fuente. Dos inputs físicos distintos pueden conservar la misma identidad semántica de fuente y producir artefactos/runtime outcomes distintos.

## Proof admissions

Cuando un programa necesita evidencia de prueba admitida, ésta cruza otra frontera explícita:

```text
--proof-admission proof-admission.json
```

La fuente no puede fabricarse a sí misma una proof admission válida. El runtime/compilador valida la evidencia suministrada contra su contrato.

## Regla mental

```text
main.tevs
  │
  ├── declara unidades V4 ──→ --unit NAME=PATH
  ├── necesita evidencia de effects ──→ --effect-input NAME=JSON
  └── necesita proof admission ──→ --proof-admission JSON
```

La ausencia o el exceso de bindings no se corrige por heurística: falla cerrado.

## Siguiente paso

Consulta [`cli-workflow.md`](cli-workflow.md) para ver cuándo usar `check`, `compile` y `run`.
