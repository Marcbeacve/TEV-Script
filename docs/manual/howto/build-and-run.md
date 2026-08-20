# Cómo comprobar, compilar y ejecutar un programa Total-Core

## Objetivo

Partir de `main.tevs`, producir Program IR V5 canónico y ejecutarlo con la CLI pública actual.

## 1. Confirma la identidad instalada

```powershell
tev-script --version
tev-script describe
tev-script descriptor
```

No confundas el package (`3.1.2`) con el lenguaje (`3.1.0`). `describe` muestra los dominios de plataforma; `descriptor` muestra el contrato Total-Core current.

## 2. Crea un root mínimo

`main.tevs`:

```text
process Demo version "3.1.0";
authority aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa;
quantum_steps 8;
field actual = [];
label End = halt;
entry End;
```

La authority sintética sirve para un ejemplo puramente semántico. No la reutilices como identidad real de deployment.

## 3. Comprueba sin escribir IR

```powershell
tev-script check .\main.tevs
```

Éxito: exit code 0 y JSON con `status: "PASS"`, `language_version: "3.1.0"`, `profile: "total_core"` y hashes del programa/fuente.

Un error TEVScript se emite como diagnóstico estructurado y la ruta V31 retorna código 2.

## 4. Compila

```powershell
tev-script compile .\main.tevs -o .\program.json
```

También puede usarse `--output`. El archivo contiene Program IR V5 Total-Core canónico validado.

La escritura del artefacto usa la política atómica de la CLI V31: temporary file + fsync + replace sobre un único path.

## 5. Valida el artefacto por su ruta pública

La CLI genérica no expone un comando `validate-total`; esa es una superficie versionada interna. Para un usuario current, `compile` ya valida antes de escribir y `run` vuelve a cargar/validar el root.

No documentes un helper interno como si fuera subcomando público.

## 6. Ejecuta

```powershell
tev-script run .\program.json --epochs 1
```

Para el programa mínimo, el resultado esperado es `HALTED`.

La salida liga, entre otros datos, `program_ir_hash`, `source_semantic_hash`, epoch, continuation, `field_hash` y `checkpoint_hash`.

## 7. Guarda checkpoint si lo necesitas

```powershell
tev-script run .\program.json `
  --epochs 1 `
  --checkpoint-output .\checkpoint.json
```

Si el programa queda `SUSPENDED`, ese checkpoint permite continuar la misma cadena mediante API/runtime versionado. Si queda `HALTED`, no debe reanudarse.

## Proyecto con units

Cuando el root declara:

```text
unit Calc profile pure;
```

añade el binding:

```powershell
tev-script check .\main.tevs --unit Calc=.\calc.tevs
tev-script compile .\main.tevs --unit Calc=.\calc.tevs -o .\program.json
```

El nombre a la izquierda de `=` debe coincidir con el `unit_id` exacto.

## Proyecto effects

Añade también:

```powershell
--effect-input Sensors=.\sensors.json
```

sólo para units declaradas `profile effects`. El set debe coincidir exactamente.

## Proyecto con proof admission

```powershell
--proof-admission .\proof.json
```

puede repetirse. El archivo debe ser una `VerifiedProofAdmissionV1` canónica real.

## Qué no hacer

- no edites `program.json` y esperes que el hash siga válido;
- no uses un source child `3.1.0` donde se espera V2 `2.0.0`;
- no añadas una unit file sin declararla;
- no confundas un PASS de compilación con commit de efectos físicos;
- no ejecute `.tevs` desde runtime como sustituto del IR.

## Diagnóstico rápido

Si falla:

1. conserva el JSON diagnóstico completo;
2. busca el campo `diagnostic.code` en `docs/manual/diagnostics/`;
3. corrige fuente/input, no el hash del IR manualmente;
4. repite `check` antes de volver a `compile`.

## Autoridad

- `tev_script/cli.py`
- `tev_script/cli_v31.py`
- `docs/manual/cli-reference/`
