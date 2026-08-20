# Editor y LSP

TEVScript 3.1 incluye un servidor LSP para que el editor use **el compilador canónico Total-Core como analizador**, en lugar de mantener una gramática semántica paralela.

## Arranque

El entry point de la distribución es `tev-script-lsp`. Sin bindings de proyecto puede analizar el documento abierto. Para un proyecto Total-Core, suministra el proceso y las dependencias explícitas:

```powershell
tev-script-lsp --process .\main.tevs --unit Calc=.\calc.tevs
```

Las unidades de efectos se acompañan con `--effect-input NAME=JSON`; las admisiones externas se pasan con `--proof-admission JSON`.

## Qué hace el servidor

El protocolo anuncia `positionEncoding = utf-16`, sincronización full-text y diagnósticos. En `didOpen`, `didChange` y `didSave` recompila el proyecto usando `compile_total_core_v31`. Si el compilador emite `TevScriptError`, el LSP conserva el mismo `diagnostic.code` y lo proyecta al rango correspondiente cuando existe `SourceSpan`.

Los documentos abiertos actúan como overlays sobre los archivos del proyecto: editar una unidad en memoria no obliga al servidor a fingir que el archivo del disco ya cambió.

## Qué no hace

El LSP no concede capabilities, no ejecuta efectos físicos y no transforma un diagnóstico en warning por conveniencia del editor. Tampoco acepta bindings de unidad/efecto/prueba sin `--process`, porque entonces no existiría una raíz de proyecto inequívoca.

Autoridad: `tev_script/lsp_v31.py`, `tev_script/source_total_core_v31.py`; pruebas: `tests/test_lsp_v31.py`.