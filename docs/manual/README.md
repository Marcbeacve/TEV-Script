# Manual de TEVScript 3.1

Esta es la puerta de entrada a la documentación actual de TEVScript.

TEVScript es un lenguaje y una plataforma de ejecución determinista con valores exactos, fronteras explícitas de capacidad y una separación estricta entre semántica del lenguaje, artefactos compilados y efectos del host. La documentación de este directorio explica cómo aprenderlo, programarlo, integrarlo y depurarlo sin tener que reconstruir su comportamiento leyendo el compilador.

## Identidad documentada

```text
paquete actual candidato     = 3.1.2
lenguaje actual              = 3.1.0
perfil actual                = total_core
predecesor publicado inmediato = 3.1.1
paquete V31 archivado        = 3.1.0
```

Estas versiones pertenecen a dominios distintos. Que el paquete Python sea `3.1.2` no significa que la versión del lenguaje sea `3.1.2`: la semántica Total-Core actual sigue siendo `3.1.0`.

La autoridad de compatibilidad de versiones es `spec/TEV_SCRIPT_VERSION_MATRIX.json`. La integración normativa actual se define en `spec/TEV_SCRIPT_3_1_PLATFORM.md` y el perfil Total-Core en `spec/TEV_SCRIPT_V31_TOTAL_CORE.md`.

## ¿Por dónde empiezo?

Si nunca has usado TEVScript, sigue **Getting Started** y después el **Tutorial**. Si ya conoces el lenguaje y necesitas saber exactamente qué acepta una construcción, usa la **Referencia del lenguaje**. Si estás integrando TEVScript desde Python, JavaScript, C#, Unity u otro host soportado, ve a **Integraciones** y a la **Referencia de biblioteca/API**.

## Documentación por objetivo

- **Empezar:** [`getting-started/`](getting-started/)
- **Aprender progresivamente:** [`tutorial/`](tutorial/)
- **Consultar sintaxis y semántica:** [`language-reference/`](language-reference/)
- **Consultar APIs de integración:** [`library-reference/`](library-reference/)
- **Consultar la línea de comandos:** [`cli-reference/`](cli-reference/)
- **Resolver una tarea concreta:** [`howto/`](howto/)
- **Integrar con runtimes y hosts:** [`integrations/`](integrations/)
- **Entender un error `TEVS_*`:** [`diagnostics/`](diagnostics/)
- **Entender compilación, IR, runtime y receipts:** [`internals/`](internals/)
- **Entender versiones y compatibilidad:** [`versions/`](versions/)
- **Consultar términos:** [`glossary.md`](glossary.md)
- **Preguntas frecuentes:** [`faq.md`](faq.md)

Las secciones se irán cerrando contra `DOCUMENTATION_COVERAGE_V1.json`. Una ruta que todavía no tenga su contenido completo no debe interpretarse como una promesa de semántica; la especificación normativa sigue siendo la autoridad.

## Modelo mental mínimo

Un programa TEVScript no recibe autoridad física por el mero hecho de declarar una operación. El código expresa computación, estado semántico, transformaciones y requisitos. Las interacciones con el exterior atraviesan fronteras explícitas de capacidad/provider.

En Total-Core 3.1 conviven dos capas principales:

```text
Program IR V4
    computación hija cerrada
    perfiles: pure | recursive | effects

Program IR V5 Total-Core
    Field + Transformation + Apply
    control por quanta finitos
    puede invocar unidades V4 exactas
```

Un `Field` es un portador semántico finito e inmutable. Una `Transformation` describe un cambio semántico identificable. `Apply` es el juicio operacional que intenta aplicar una transformación a un Field. Estos conceptos no convierten automáticamente una afirmación en verdadera, un hash en una prueba, ni una intención de efecto en permiso físico.

## Fuente frente a runtime

Los archivos `.tevs` se analizan y compilan en tooling de construcción. El runtime de producción ejecuta artefactos/IR canónicos validados; no obtiene autoridad para reinterpretar fuente `.tevs` en producción.

El flujo conceptual es:

```text
.tevs
  ↓ parser + semántica estática
modelo semántico de fuente
  ↓ lowering/compilación
Program IR canónico
  ↓ validación
runtime acotado
  ↓
resultado / checkpoint / receipt
```

## Valores exactos

Los enteros y racionales portables se mantienen exactos mientras permanezcan dentro de la semántica que hereda el contrato de valores exactos. Una conversión a un tipo aproximado del host —por ejemplo, un `float` físico o gráfico— es una frontera explícita del host, no una redefinición silenciosa de la aritmética TEVScript.

## Errores y fallo cerrado

TEVScript favorece fronteras de fallo explícitas. Entre otros casos, un IR malformado, un hash que no coincide, una capacidad ausente, una versión no soportada o una prueba requerida pero no admitida no se convierten silenciosamente en éxito.

Los diagnósticos estructurados de usuario se documentarán por su código `TEVS_*`, con ejemplo que falla, causa y corrección.

## Documentación ejecutable

Los ejemplos que se presenten como ejecutables no son fragmentos decorativos. Cada bloque ejecutable se enlaza a un archivo canónico mediante una directiva como:

```text
<!-- tevdoc-source: examples/docs/v31/tutorial/01_exact/main.tevs -->
```

El validador `tools/validate_documentation_v31.py` comprobará que el bloque y el archivo siguen siendo equivalentes y que los casos positivos/negativos producen el resultado documentado.

## Qué documento tiene autoridad

Este manual está diseñado para ser comprensible y completo, pero **no es una segunda especificación del lenguaje**. Si una explicación humana y una especificación normativa discrepan, la discrepancia es un defecto que debe corregirse; el manual no puede redefinir la semántica por sí mismo.

Consulta [`documentation-policy.md`](documentation-policy.md) para la jerarquía completa de autoridad y las reglas de mantenimiento.