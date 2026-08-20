# Cómo construir un proyecto con varias unidades

## Objetivo

Componer unidades `pure`, `recursive` y, cuando exista evidencia externa, `effects` bajo un root Total-Core sin convertirlas en un único script monolítico.

## Estructura de ejemplo

```text
project/
  main.tevs
  calc.tevs
  rec.tevs
```

`main.tevs`:

```text
process Multi version "3.1.0";
authority aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa;
quantum_steps 16;
unit Calc profile pure;
unit Rec profile recursive;
field actual = [];
label Start = invoke_v4 Calc result app.calc AfterCalc;
label AfterCalc = invoke_v4 Rec result app.rec End;
label End = halt;
entry Start;
```

`calc.tevs`:

```text
script Calc version "2.0.0";
fn add1(x:Int)->Int=x+1;
entry main:Int=add1(4);
```

`rec.tevs`:

```text
script Rec version "2.0.0";
recursive fn factorial(n:Int)->Int decreases n max_depth 8 = if n==0 then 1 else n*self(n-1);
entry main:Int=factorial(5);
```

## Comprueba

```powershell
tev-script check .\main.tevs `
  --unit Calc=.\calc.tevs `
  --unit Rec=.\rec.tevs
```

## Compila

```powershell
tev-script compile .\main.tevs `
  --unit Calc=.\calc.tevs `
  --unit Rec=.\rec.tevs `
  -o .\multi.json
```

## Ejecuta

```powershell
tev-script run .\multi.json --epochs 1
```

Con el control anterior debe alcanzar `HALTED` dentro del quantum.

## El set es cerrado

La compilación compara:

```text
units declaradas en root
        ==
keys entregadas con --unit
```

Una ausente o una extra produce `TEVS_V31_SOURCE_UNIT_SET`.

## Profile exacto

No uses el mismo child bajo un profile distinto para «forzar» compilación. El frontend verifica el `function_kind`/schema que produce el child y V5 valida de nuevo el Program IR V4 correspondiente.

## Orden de bindings

Puedes invertir el orden de flags `--unit`; el mapping de build no es semántico en su orden. La tabla V5 se canonicaliza por `(unit_id, unit_hash)`.

No confundas esto con invertir las labels/invocations: el control sí es semántico.

## Result relations

Cada `invoke_v4` declara una relation para el bridge fact:

```text
app.calc
app.rec
```

Usa nombres estables y específicos del protocolo entre child/root. No uses rutas temporales como relation IDs.

## Añadir una unit effects

Si declaras:

```text
unit Sensors profile effects;
```

debes añadir ambos bindings:

```powershell
--unit Sensors=.\sensors.tevs `
--effect-input Sensors=.\sensors.json
```

No se permite un `effect-input` para Calc/Rec si no son effects.

## Reutilización

Una unidad cerrada puede ser reutilizable entre procesos si su fuente/IR/profile son compatibles. Su identidad no depende de en qué carpeta la copies, pero el root tendrá su propio `unit_hash`/program hash al integrarla según el contrato.

## Qué revisar si cambia el hash del root

- cambió la fuente hija;
- cambió profile/unit ID;
- cambió scenario de effects;
- cambió proof admission;
- cambió control/instruction order;
- cambió Field/Transformation root.

No asumas que «sólo cambié un archivo hijo» debe conservar el mismo Program IR.

## Referencia

- `docs/manual/tutorial/08-modules-composition.md`
- `docs/manual/language-reference/modules.md`
- `spec/TEV_SCRIPT_V31_TOTAL_CORE.md`
