# Léxico, codificación y estructura de fuente

## Aplicabilidad

Esta página distingue explícitamente el root **CURRENT 3.1 Total-Core** y la fuente **INHERITED_COMPATIBILITY V2**. No deben pasarse reglas de un lexer al otro por analogía.

## Codificación

La fuente se interpreta como UTF-8 estricto en las fronteras de archivo. Un error de decodificación del root 3.1 se reporta como `TEVS_V31_SOURCE_UTF8` en la CLI versionada.

V2 fija además un máximo de 1.000.000 bytes de fuente y no considera el BOM parte del lenguaje.

## Root Total-Core 3.1

El frontend 3.1 divide la fuente en declaraciones terminadas en `;`. La división respeta strings entre comillas y arrays `[...]`, de modo que un punto y coma sólo cierra una declaración en el nivel raíz admitido.

Forma mínima:

```text
process Demo version "3.1.0";
authority <64-hex>;
quantum_steps 8;
field actual = [];
label End = halt;
entry End;
```

### Punto y coma

Toda declaración raíz debe terminar en `;`. Texto residual al final sin terminador produce `TEVS_V31_SOURCE_SEMICOLON`.

### Strings y arrays durante el split

El splitter conserva escapes dentro de strings y cuenta brackets `[`/`]`. Un `]` sin apertura produce `TEVS_V31_SOURCE_BRACKETS`; string o array sin cerrar produce `TEVS_V31_SOURCE_UNCLOSED`.

La validación semántica posterior aplica además el parser/canonical JSON estricto donde corresponda.

### Comentarios root

Una línea cuyo contenido, tras quitar whitespace inicial, comienza por `#` se ignora como comentario del proceso 3.1/V3 heredado.

```text
# comentario root
field actual = [];
```

No documentes `#` inline como si fuera comentario universal: la implementación de split sólo descarta líneas lógicamente comentadas completas.

## Identificadores root 3.1

Los IDs estables usados por process/unit/relation/labels en las fronteras 3.1 admiten la familia:

```text
[A-Za-z_][A-Za-z0-9_.:/-]*
```

No todos los subparsers históricos permiten exactamente el mismo subconjunto. Usa nombres ASCII simples cuando no necesites namespaces.

Ejemplos válidos típicos:

```text
Demo
Calc
tev.app.result
sensor/read
module:v1
```

## Header 3.1

La forma es exactamente:

```text
process <ProgramId> version "3.1.0";
```

Otro número produce `TEVS_V31_SOURCE_VERSION`; más de un header produce `TEVS_V31_SOURCE_DUPLICATE`; ausencia de header produce `TEVS_V31_SOURCE_REQUIRED`.

## Fuente V2 de unidades

V2 usa un lexer distinto y un header distinto:

```text
script Demo version "2.0.0";
```

o, para módulos:

```text
module My.Module version "2.0.0";
```

### Identificadores V2

Forma básica:

```ebnf
letter         = "A"…"Z" | "a"…"z" | "_" ;
digit          = "0"…"9" ;
identifier     = letter , { letter | digit } ;
qualified-name = identifier , { "." , identifier } ;
```

### Comentarios V2

Los comentarios de línea comienzan por `//`. El perfil no admite comentarios de bloque/nesting como sintaxis portable.

```text
// comentario V2
fn add1(x:Int)->Int=x+1;
```

### Números V2

Los tokens numéricos no llevan signo léxico; la negación es una operación de expresión. Los racionales de fuente usan forma decimal admitida y se convierten al modelo racional exacto canónico.

Los ceros iniciales no son canónicos salvo el propio `0`.

### Strings V2

Los strings usan comillas dobles y escapes portables definidos por el lenguaje, incluidos `\"`, `\\`, `\n`, `\r` y `\t`.

## Whitespace y semántica

Whitespace superficial y comentarios son no semánticos donde la especificación correspondiente así lo define. El hash semántico se deriva del modelo resuelto/canónico, no de los bytes crudos del archivo.

No generalices esto a cualquier cambio textual: renombrar una identidad estable, cambiar un literal o modificar el control sí puede cambiar la semántica.

## Errores/fallo cerrado

El frontend no intenta «arreglar» automáticamente:

- versión equivocada;
- declaración sin `;`;
- bracket desbalanceado;
- string sin cerrar;
- source child V2 presentada como `3.1.0`;
- comentario de una generación interpretado como comentario de otra;
- UTF-8 inválido.

## Autoridad técnica

- `tev_script/source_total_core_v31.py`
- `spec/TEV_SCRIPT_V3_SEMANTIC_PROCESS_SOURCE.md`
- `spec/TEV_SCRIPT_V2_LANGUAGE.md`, secciones lexical grammar y processing model.
