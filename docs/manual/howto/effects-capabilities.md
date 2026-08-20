# Cómo preparar una unidad effects y sus capabilities

## Objetivo

Compilar una unidad V2 effects dentro de Total-Core sin inventar observaciones, authority ni command commit.

## 1. Escribe la unidad

Ejemplo de observación:

```text
script Sensors version "2.0.0";
state last:Int=0;
capability observation sensor.read(Int)->Int;
action sample() {
    observe value=sensor.read(last);
    set last=value;
}
entry main=sample();
```

## 2. Declárala en el root

```text
unit Sensors profile effects;
```

## 3. No inventes `effect_inputs`

El artefacto effects necesita un scenario ligado a la capability table real que produce la compilación de la fuente. No copies hashes de un ejemplo.

La estructura conceptual incluye:

```json
{
  "scenario": {
    "capability_table_hash": "<hash real>",
    "capabilities": [
      {
        "capability_id": "sensor.read",
        "contract_hash": "<hash real>",
        "calls": [
          {
            "arguments": [{"$int":"0"}],
            "return": {"$int":"10"}
          }
        ]
      }
    ]
  }
}
```

## 4. Genera la skeleton desde el contrato compilado

La capa V2 contiene el helper versionado de build `effect_scenario_skeleton_v2`. No forma parte del `tev_script.__all__` current; úsalo como tooling de build V2, no como primitive Total-Core:

```python
from tev_script.source_effect_program_v2 import (
    compile_effect_program_v2,
    effect_scenario_skeleton_v2,
)

source = open("sensors.tevs", encoding="utf-8").read()
compiled = compile_effect_program_v2(source)
scenario = effect_scenario_skeleton_v2(compiled)
```

La skeleton contiene los IDs/hashes de capability correctos y `calls` vacíos. El integrador/provider autorizado rellena evidence de llamadas concretas.

## 5. Construye `sensors.json`

La CLI 3.1 espera el objeto de effect input con campo `scenario` y opcional `current_state`:

```json
{
  "scenario": { "...": "..." },
  "current_state": { "last": 0 }
}
```

No añadas campos arbitrarios: el shape es cerrado.

## 6. Compila el root

```powershell
tev-script check .\main.tevs `
  --unit Sensors=.\sensors.tevs `
  --effect-input Sensors=.\sensors.json

tev-script compile .\main.tevs `
  --unit Sensors=.\sensors.tevs `
  --effect-input Sensors=.\sensors.json `
  -o .\program.json
```

## 7. Entiende qué se ejecuta

El Program IR V4 Effects contiene una instancia ligada al scenario. Al `invoke_v4`:

- se valida el artefacto;
- se reproducen/consumen las observaciones declaradas;
- se calcula estado final/receipt;
- el receipt se proyecta al Field padre.

## 8. Commit físico separado

Para commands/actuación, el portable runtime puede producir intent. El provider externo decide commit bajo grant/policy y debe producir evidencia propia.

Nunca hagas:

```text
command intent == "el archivo ya fue escrito"
```

sin receipt de la frontera de realización.

## Repetibilidad

Misma fuente + distinto scenario puede conservar source semantic hash y cambiar Program IR hash/result. Eso es esperado: observación de ejecución no es fuente.

## Errores frecuentes

- olvidar `--effect-input`;
- dar effect input a unit pure;
- usar capability_table_hash de otra compilación;
- call con arguments diferentes a los esperados;
- return mal tipado;
- suponer que el provider existe porque la source declara la capability.

## Referencia

- `docs/manual/language-reference/state-events-effects.md`
- `spec/TEV_SCRIPT_V2_LANGUAGE.md`
- `spec/TEV_SCRIPT_V31_TOTAL_CORE.md`
