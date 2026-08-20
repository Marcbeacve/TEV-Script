# Diagnósticos de fuente Total-Core 3.1

Esta página documenta los **25 códigos `TEVS_V31_SOURCE_*`** emitidos explícitamente por `tev_script/source_total_core_v31.py`.

La fase general es:

```text
process source 3.1
  ↓ normalización/parsing V31
unit/effect/proof bindings
  ↓
compilación de unidades V4
  ↓
composición Total-Core V5
```

Los ejemplos mínimos muestran la condición que activa cada guard. Algunos guards son defensivos y normalmente quedan precedidos por una validación más temprana cuando se usa la CLI pública; se indica cuando ocurre.

---

## `TEVS_V31_SOURCE_TYPE`

**Fase:** entrada API.

**Significado:** la fuente raíz entregada al frontend no es texto.

**Trigger mínimo:** llamar `compile_total_core_v31` con `process_source` que no sea `str`.

**Diagnóstico esperado:** `TEVS_V31_SOURCE_TYPE`.

**Corrección:** decodificar/leer la fuente como texto UTF-8 antes de llamar al frontend.

**Regla relacionada:** la fuente Total-Core es texto; bytes/objetos host no se reinterpretan implícitamente.

---

## `TEVS_V31_SOURCE_BRACKETS`

**Fase:** separación de declaraciones.

**Significado:** aparece `]` sin un `[` abierto correspondiente.

**Trigger mínimo:** una declaración que contenga un cierre de array sobrante, por ejemplo `field actual = ];`.

**Diagnóstico esperado:** `TEVS_V31_SOURCE_BRACKETS`.

**Corrección:** equilibrar los corchetes de la declaración.

---

## `TEVS_V31_SOURCE_UNCLOSED`

**Fase:** separación de declaraciones.

**Significado:** al finalizar la fuente queda una cadena o array abierto.

**Trigger mínimo:** `field actual = [` sin cierre, o una cadena con `"` inicial sin cierre.

**Diagnóstico esperado:** `TEVS_V31_SOURCE_UNCLOSED`.

**Corrección:** cerrar la cadena/array antes del `;` final.

---

## `TEVS_V31_SOURCE_SEMICOLON`

**Fase:** separación de declaraciones.

**Significado:** queda texto de una declaración sin terminar en `;`.

**Trigger mínimo:**

```text
entry done
```

al final del archivo.

**Diagnóstico esperado:** `TEVS_V31_SOURCE_SEMICOLON`.

**Corrección:** `entry done;`.

---

## `TEVS_V31_SOURCE_DUPLICATE`

**Fase:** cabecera V31.

**Significado:** la fuente contiene más de una cabecera `process ... version ...`.

**Trigger mínimo:** dos declaraciones `process` válidas en el mismo archivo.

**Diagnóstico esperado:** `TEVS_V31_SOURCE_DUPLICATE`.

**Corrección:** conservar una única cabecera de proceso.

---

## `TEVS_V31_SOURCE_VERSION`

**Fase:** cabecera V31.

**Significado:** la fuente raíz no declara exactamente lenguaje `3.1.0`.

**Caso negativo canónico:**

<!-- tevdoc-source: examples/docs/v31/diagnostics/source-version/main.tevs -->
<!-- tevdoc-expect-diagnostic: TEVS_V31_SOURCE_VERSION -->
```tevs
process WrongVersion version "3.0.0";
authority aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa;
quantum_steps 1;
field actual = [];
label done = halt;
entry done;
```

**Diagnóstico esperado:** `TEVS_V31_SOURCE_VERSION` con exit code `2` a través de `tev-script check`.

**Corrección:**

```text
process WrongVersion version "3.1.0";
```

Cambiar la versión no convierte automáticamente sintaxis de otra línea en 3.1; la fuente completa debe cumplir el contrato Total-Core.

---

## `TEVS_V31_SOURCE_UNIT_DUPLICATE`

**Fase:** declaraciones de unidad.

**Significado:** el mismo `unit_id` se declara dos veces.

**Trigger mínimo:**

```text
unit Calc profile pure;
unit Calc profile pure;
```

**Diagnóstico esperado:** `TEVS_V31_SOURCE_UNIT_DUPLICATE`.

**Corrección:** cada `unit_id` debe tener una única declaración.

---

## `TEVS_V31_SOURCE_LABEL_DUPLICATE`

**Fase:** reconocimiento de `invoke_v4`.

**Significado:** el frontend encuentra más de una definición de invoke para el mismo label durante la normalización V31.

**Diagnóstico esperado:** `TEVS_V31_SOURCE_LABEL_DUPLICATE`.

**Corrección:** cada label debe representar una única instrucción. La capa V3 subyacente puede rechazar también otras formas de duplicación de labels con su propio diagnóstico compatible.

**Nota:** es un guard específico del mapa de invokes V31.

---

## `TEVS_V31_SOURCE_REQUIRED`

**Fase:** cabecera V31.

**Significado:** no existe ninguna declaración `process ... version ...`.

**Trigger mínimo:** una fuente que sólo contenga `field`, `label` y `entry`.

**Diagnóstico esperado:** `TEVS_V31_SOURCE_REQUIRED`.

**Corrección:** añadir una cabecera, por ejemplo:

```text
process Demo version "3.1.0";
```

---

## `TEVS_V31_SOURCE_UNITS`

**Fase:** API de composición.

**Significado:** `unit_sources` no es un mapping.

**Trigger mínimo:** llamar la API con `unit_sources=[]`.

**Diagnóstico esperado:** `TEVS_V31_SOURCE_UNITS`.

**Corrección:** usar un mapping `unit_id -> source_text`; para un proceso sin unidades, `{}`.

---

## `TEVS_V31_SOURCE_UNIT_SET`

**Fase:** binding de unidades.

**Significado:** el conjunto de unidades suministradas no coincide exactamente con el conjunto declarado por la fuente.

**Trigger mínimo:** declarar `unit Calc profile pure;` y suministrar `{}` o suministrar además una unidad no declarada.

**Diagnóstico esperado:** `TEVS_V31_SOURCE_UNIT_SET` e información `missing=[...] extra=[...]`.

**Corrección:** suministrar una y sólo una fuente por cada `unit_id` declarado.

**CLI relacionada:** `--unit NAME=PATH`.

---

## `TEVS_V31_SOURCE_UNIT_TEXT`

**Fase:** binding de unidades.

**Significado:** el valor de una unidad en `unit_sources` no es texto.

**Trigger mínimo:** `unit_sources={"Calc": b"..."}` a través de la API.

**Diagnóstico esperado:** `TEVS_V31_SOURCE_UNIT_TEXT`.

**Corrección:** leer/decodificar la unidad y suministrar `str`.

---

## `TEVS_V31_SOURCE_EFFECT_INPUTS`

**Fase:** binding de inputs de effects.

**Significado:** `effect_inputs` no es `None` ni un mapping.

**Trigger mínimo:** `effect_inputs=[]`.

**Diagnóstico esperado:** `TEVS_V31_SOURCE_EFFECT_INPUTS`.

**Corrección:** usar `None`, `{}`, o un mapping `unit_id -> object`.

---

## `TEVS_V31_SOURCE_EFFECT_INPUT_SET`

**Fase:** binding de inputs de effects.

**Significado:** el conjunto de inputs externos no coincide exactamente con las unidades declaradas con perfil `effects`.

**Trigger mínimo:** declarar una unidad `effects` y omitir su input, o proporcionar input para una unidad `pure`.

**Diagnóstico esperado:** `TEVS_V31_SOURCE_EFFECT_INPUT_SET`.

**Corrección:** una entrada `--effect-input NAME=JSON` exactamente por cada unidad `effects` y ninguna para otros perfiles.

---

## `TEVS_V31_SOURCE_EFFECT_INPUT_PROFILE`

**Fase:** normalización defensiva de effect input.

**Significado:** un input de effect se está asociando a una unidad cuyo perfil no es `effects`.

**Diagnóstico esperado:** `TEVS_V31_SOURCE_EFFECT_INPUT_PROFILE`.

**Corrección:** asociar inputs externos sólo a unidades `effects`.

**Nota de alcanzabilidad:** el chequeo exacto de conjuntos normalmente detecta esta discrepancia antes en la ruta pública; este código conserva un guard local fail-closed.

---

## `TEVS_V31_SOURCE_EFFECT_INPUT`

**Fase:** normalización de effect input.

**Significado:** el input de una unidad `effects` no es un objeto/mapping.

**Trigger mínimo:** asociar a la unidad un array o escalar en vez de objeto.

**Diagnóstico esperado:** `TEVS_V31_SOURCE_EFFECT_INPUT`.

**Corrección:** suministrar un objeto con `scenario` y, opcionalmente, `current_state`.

---

## `TEVS_V31_SOURCE_EFFECT_INPUT_FIELDS`

**Fase:** normalización de effect input.

**Significado:** el objeto contiene un field set distinto de los dos admitidos:

```text
{scenario}
{scenario, current_state}
```

**Trigger mínimo:** añadir una clave `extra`.

**Diagnóstico esperado:** `TEVS_V31_SOURCE_EFFECT_INPUT_FIELDS`.

**Corrección:** eliminar claves no admitidas.

---

## `TEVS_V31_SOURCE_EFFECT_SCENARIO`

**Fase:** normalización de effect input.

**Significado:** `scenario` no es un objeto/mapping.

**Trigger mínimo:** `{"scenario": []}`.

**Diagnóstico esperado:** `TEVS_V31_SOURCE_EFFECT_SCENARIO`.

**Corrección:** usar el objeto de escenario exigido por el compilador de effects V2.

---

## `TEVS_V31_SOURCE_EFFECT_STATE`

**Fase:** normalización de effect input.

**Significado:** `current_state`, cuando está presente y no es `null`, no es un objeto/mapping.

**Trigger mínimo:** `{"scenario": {...}, "current_state": []}`.

**Diagnóstico esperado:** `TEVS_V31_SOURCE_EFFECT_STATE`.

**Corrección:** usar un objeto de estado o `null`.

---

## `TEVS_V31_SOURCE_UNIT_PROFILE`

**Fase:** compilación de unidad V4.

**Significado:** el perfil declarado por la raíz no coincide con el kind real de la entrada hija, o una llamada defensiva llega con un perfil no soportado.

**Trigger típico:** declarar:

```text
unit Calc profile pure;
```

pero la fuente hija compila con entrada `recursive`.

**Diagnóstico esperado:** `TEVS_V31_SOURCE_UNIT_PROFILE`.

**Corrección:** hacer coincidir la declaración `pure|recursive|effects` con el contrato real de la unidad.

---

## `TEVS_V31_SOURCE_EFFECT_INPUT_REQUIRED`

**Fase:** compilación defensiva de unidad `effects`.

**Significado:** una unidad `effects` llega a `_compile_unit` sin su evidencia externa.

**Diagnóstico esperado:** `TEVS_V31_SOURCE_EFFECT_INPUT_REQUIRED`.

**Corrección:** suministrar el input externo correspondiente.

**Nota de alcanzabilidad:** en la ruta pública, `TEVS_V31_SOURCE_EFFECT_INPUT_SET` normalmente detecta antes la ausencia; este guard protege la función de compilación local.

---

## `TEVS_V31_SOURCE_V3_INSTRUCTION`

**Fase:** adaptación V3 → Total-Core V5.

**Significado:** el proceso semántico V3 subyacente produjo un instruction kind que el adaptador Total-Core no admite en esta frontera.

**Diagnóstico esperado:** `TEVS_V31_SOURCE_V3_INSTRUCTION`.

**Corrección:** usar sólo constructos cuya instrucción V3 tenga proyección Total-Core admitida (`halt`, `jump`, `apply`, `branch_fact`, más el `invoke_v4` reconocido por V31).

**Clasificación:** guard de integración/implementación más que error sintáctico elemental.

---

## `TEVS_V31_SOURCE_UNKNOWN_LABEL`

**Fase:** resolución de `invoke_v4`.

**Significado:** el label del invoke no fue admitido por el modelo V3 o el target `next_label` no existe.

**Trigger típico:**

```text
label call = invoke_v4 Calc result tev.result Missing;
```

sin label `Missing`.

**Diagnóstico esperado:** `TEVS_V31_SOURCE_UNKNOWN_LABEL`.

**Corrección:** referenciar un label definido exactamente una vez.

---

## `TEVS_V31_SOURCE_UNKNOWN_UNIT`

**Fase:** resolución de `invoke_v4`.

**Significado:** el invoke referencia un `unit_id` que no pertenece a la tabla de unidades compiladas.

**Trigger típico:** `invoke_v4 Missing ...` sin `unit Missing profile ...;`.

**Diagnóstico esperado:** `TEVS_V31_SOURCE_UNKNOWN_UNIT`.

**Corrección:** declarar y suministrar la unidad o cambiar el invoke al `unit_id` correcto.

---

## `TEVS_V31_SOURCE_RELATION`

**Fase:** resolución de `invoke_v4`.

**Significado:** la relación donde se proyectará el resultado de la unidad no satisface el identificador estable requerido.

**Diagnóstico esperado:** `TEVS_V31_SOURCE_RELATION`.

**Corrección:** usar una relación estable como `tev.total.result`.

**Nota de alcanzabilidad:** la expresión `invoke_v4` se reconoce ya mediante una regex restrictiva; este guard conserva la validación local si cambia o se reutiliza esa frontera.

---

## Resumen por subfase

```text
entrada/separación
  TYPE BRACKETS UNCLOSED SEMICOLON

cabecera/modelo
  DUPLICATE VERSION REQUIRED

unidades
  UNIT_DUPLICATE UNITS UNIT_SET UNIT_TEXT UNIT_PROFILE

inputs effects
  EFFECT_INPUTS EFFECT_INPUT_SET EFFECT_INPUT_PROFILE
  EFFECT_INPUT EFFECT_INPUT_FIELDS EFFECT_SCENARIO EFFECT_STATE
  EFFECT_INPUT_REQUIRED

invoke/integración
  LABEL_DUPLICATE V3_INSTRUCTION UNKNOWN_LABEL UNKNOWN_UNIT RELATION
```

La siguiente capa de la referencia cubre `TEVS_V31_TOTAL_*`, que ya no son errores de parsing de fuente sino invariantes del Program IR V5 canónico.
