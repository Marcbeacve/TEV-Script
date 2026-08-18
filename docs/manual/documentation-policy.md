# Política de documentación de TEVScript

Esta política define qué puede afirmar el manual, cómo se mantiene sincronizado con TEVScript y qué hacer cuando la documentación, la implementación y la especificación no coinciden.

## 1. La documentación explica; no legisla

La autoridad semántica pertenece, en este orden conceptual, a los contratos normativos de gramática y semántica estática, modelos de valores e IR, ABI/checkpoints, hashing canónico, schemas y contratos de conformance. Las implementaciones de Python, JavaScript, C#, Unity u otros hosts son testigos de conformidad. El manual humano está por debajo de ambos niveles.

Por tanto:

```text
especificación normativa
        ↓
implementaciones conformes
        ↓
manual humano
```

Si dos runtimes discrepan, no se elige arbitrariamente el resultado más cómodo. Se resuelve la discrepancia contra la autoridad normativa. Si este manual contradice esa autoridad, el manual contiene un defecto.

## 2. Idioma

La documentación pedagógica principal de `docs/manual/` se escribe en castellano. Los elementos que forman parte del contrato técnico conservan su grafía exacta: palabras reservadas, nombres de tipos, APIs, comandos CLI, códigos `TEVS_*`, nombres de schemas, rutas de archivos, hashes y nombres de perfiles.

Las especificaciones normativas permanecen en inglés mientras no exista una traducción gobernada de forma independiente. Una traducción explicativa nunca sustituye silenciosamente el texto normativo.

## 3. Versiones explícitas

El manual no utiliza «versión de TEVScript» como si existiera un único número universal. Debe distinguir, cuando sea relevante:

- versión del paquete;
- versión del lenguaje;
- perfil de fuente;
- versión del linked program;
- versión de Program IR;
- ABI de runtime;
- versión de checkpoint;
- versión de un adapter/provider.

La matriz `spec/TEV_SCRIPT_VERSION_MATRIX.json` es la referencia de compatibilidad entre estos dominios.

## 4. Actual frente a histórico

Una página actual debe indicar claramente el perfil al que se refiere cuando una regla no es común a todas las líneas. V1, V2 y V3 conservan valor como compatibilidad y evidencia histórica, pero no deben aparecer como si fueran el camino recomendado para un usuario nuevo de Total-Core 3.1.

No se eliminan documentos históricos sólo para simplificar la navegación. Se preservan y se contextualizan.

## 5. Ejemplos ejecutables

Un ejemplo presentado como ejecutable debe tener una única copia ejecutable canónica bajo `examples/docs/v31/`. El Markdown lo enlaza inmediatamente antes del bloque mediante:

```text
<!-- tevdoc-source: ruta/al/archivo.tevs -->
```

El bloque mostrado debe coincidir byte a byte con el archivo, salvo normalización CRLF/LF y la posible eliminación de un único salto de línea terminal.

Los ejemplos negativos añaden:

```text
<!-- tevdoc-expect-diagnostic: TEVS_CODIGO_EXACTO -->
```

y su `case.json` debe exigir el mismo diagnóstico. Si un ejemplo que debe fallar empieza a pasar, la documentación falla su validación.

## 6. Afirmaciones de estado

Un hash garantiza identidad/integridad de contenido dentro de su contrato; no demuestra que una proposición física o lógica sea verdadera. Una declaración de capability describe una frontera; no concede por sí misma autoridad de host. Una proof admission registra evidencia admitida; no fabrica la prueba que referencia.

El manual debe mantener estas distinciones explícitas.

## 7. Corrección de contradicciones

Cuando la documentación descubre una contradicción se clasifica antes de modificar nada:

```text
DOC_BUG
IMPLEMENTATION_BUG
SPEC_BUG
VERSION_GOVERNANCE_BUG
TEST_GAP
```

La secuencia de corrección es:

```text
reproducir
→ escribir una prueba que falle
→ identificar la autoridad esperada
→ aplicar el cambio mínimo
→ observar GREEN
→ validar documentación
→ ejecutar la regresión exigida por gobernanza
```

Nunca se corrige una explicación para que coincida con un comportamiento accidental del runtime si ese comportamiento contradice la especificación.

## 8. Cobertura

`docs/manual/DOCUMENTATION_COVERAGE_V1.json` será el inventario machine-readable que enlaza superficies públicas actuales con sus páginas y evidencia. Tener una entrada en esa matriz no convierte el manual en autoridad semántica; demuestra que una superficie ya autoritativa no ha quedado sin explicar.

Una superficie pública actual sin cobertura es un fallo documental. Una superficie documentada como actual que ya no existe también lo es.

## 9. Validación local

El entry point de validación es:

```text
python tools/validate_documentation_v31.py --root .
```

El validador es determinista y no necesita red. Es un gate de calidad documental, no una décima autoridad semántica añadida a los nueve gates de Platform Completion.

## 10. Criterio editorial

Una página correcta debe poder responder, según su tipo, al menos a estas preguntas: qué es el concepto, para qué sirve, cómo se usa, qué tipos/valores acepta, qué produce, qué límites tiene, cómo falla, en qué versión/perfil aplica y dónde está la autoridad técnica correspondiente.

La referencia puede ser compacta; el tutorial debe enseñar. Mezclar ambos estilos en una única página empeora las dos funciones.