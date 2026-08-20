# 01 — Valores exactos y determinismo

TEVScript no trata los números portables como una aproximación del tipo numérico del host. La idea de partida es más estricta: **el valor semántico pertenece al lenguaje y su representación canónica pertenece al contrato**, mientras que Python, JavaScript, C# o Unity son implementaciones que deben respetarlo.

En el perfil de computación V2 que Total-Core 3.1 puede incorporar como unidad V4, los tipos numéricos principales son `Int` y `Rat`. `Int` representa enteros exactos. `Rat` representa racionales exactos. Una conversión posterior a `float`, `double` o `float32` es una operación del host y puede perder información.

## Primer ejemplo ejecutable

El proceso raíz 3.1 invoca una unidad V4 pura. La unidad del capítulo suma enteros; el punto importante es que el `5` obtenido no depende del formato IEEE-754 del host.

<!-- tevdoc-source: examples/docs/v31/tutorial/01_values_exactness/main.tevs -->
```tevs
process Tutorial01 version "3.1.0";
authority aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa;
quantum_steps 8;
unit Calc profile pure;
field actual = [];
label Start = invoke_v4 Calc result tev.tutorial.value End;
label End = halt;
entry Start;
```

<!-- tevdoc-source: examples/docs/v31/tutorial/01_values_exactness/calc.tevs -->
```tevs
script Calc version "2.0.0";
fn add1(x:Int)->Int=x+1;
entry main:Int=add1(4);
```

El flujo real es:

```text
fuente V2 de Calc
  → análisis estático
  → Program IR V4 Pure
  → validación de su program_ir_hash
  → invoke_v4 desde Total-Core
  → resultado tipado/canónico
  → bridge fact inmutable en el Field padre
```

Total-Core no vuelve a interpretar la expresión `x+1`: conserva el artefacto V4 y usa su runtime correspondiente.

## `Int`: entero semántico, no entero de máquina

El significado de `Int` no es «el entero que resulte conveniente en esta CPU». El valor se codifica de forma canónica en el IR/receipt. Por ejemplo, en la representación portable un entero se expresa conceptualmente como:

```text
{"$int":"5"}
```

El texto decimal forma parte de la codificación exacta. Esto evita que dos hosts discrepen por anchura nativa, endianness o serialización local.

## `Rat`: racional exacto

V2 y Program IR V4 admiten aritmética racional exacta. La semántica relevante es la fracción matemática, no la expansión binaria aproximada. A nivel de IR, `3/2` se representa como una razón canónica equivalente a:

```text
{"$rat":["3","2"]}
```

La especificación admite ensanchamiento numérico controlado —por ejemplo, combinar `Int` con `Rat` cuando el operador lo permite— sin convertir silenciosamente el cálculo a coma flotante.

## Qué ocurre con la división

La división exacta conserva el resultado racional cuando procede. Una división por cero **falla cerrada**; no produce `Infinity`, `NaN` ni un valor especial dependiente del host.

Esto es una diferencia importante frente a muchos entornos numéricos generales: los estados numéricos que no pertenecen al modelo portable no aparecen por accidente.

## Exactitud no significa verdad física

Que `3/2` sea representado exactamente no demuestra que una medida experimental sea exactamente `1.5`. TEVScript separa dos cuestiones:

```text
exactitud de representación     ≠     certeza de la observación
```

Un sensor puede proporcionar evidencia aproximada o incierta. Si esa evidencia se incorpora al sistema, su procedencia y contrato deben permanecer explícitos.

## Frontera con el host

Un host puede necesitar finalmente un `float` para dibujar, simular o llamar una API. Esa conversión debe considerarse una frontera explícita:

```text
Rat exacto TEVScript
   ↓ conversión deliberada del adaptador
float/double del host
```

A partir de la conversión, la aproximación pertenece al host; no debe retroproyectarse como si hubiera sido la semántica original del programa.

## Identidad y determinismo

Los valores participan en estructuras canónicas y hashes. Por eso dos implementaciones conformes que ejecuten el mismo artefacto, con las mismas entradas explícitas y autoridad observacional, deben producir el mismo valor canónico y las mismas identidades cubiertas por el contrato.

No se promete que el mundo externo sea determinista. Se promete que **la computación portable no añade nondeterminismo oculto**.

## Errores que debes esperar

- tipo declarado incompatible con el valor calculado;
- operación no definida para los tipos de operandos;
- división por cero;
- valor fuera del modelo/capacidad de una colección;
- IR con representación numérica no canónica;
- conversión de host presentada incorrectamente como semántica del lenguaje.

## Regla práctica

Mientras permanezcas dentro de `Int`, `Rat` y las operaciones portables, razona matemáticamente. Cuando atravieses a un tipo numérico del host, documenta esa conversión como una frontera.

## Autoridad técnica

- `spec/TEV_SCRIPT_V2_LANGUAGE.md`: tipos y semántica de fuente V2.
- `spec/TEV_SCRIPT_PROGRAM_IR_V4.md`: artefactos V4 y evaluación portable.
- `spec/PORTABLE_VALUE_MODEL_V1.md`: modelo portable/canónico de valores.
- `spec/TEV_SCRIPT_V31_TOTAL_CORE.md`: incorporación exacta de unidades V4 en Total-Core.
