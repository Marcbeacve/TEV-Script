# Glosario de TEVScript

Este glosario define el vocabulario que el manual usa de forma consistente. Cuando un término posee un contrato normativo más preciso, se indica la familia de autoridad correspondiente.

## Apply

Juicio operacional que intenta aplicar una `Transformation` a un `Field`. No es una tercera familia semántica independiente: la base semántica se expresa como `Field + Transformation`, y `Apply` describe la operación entre ambas.

Una aplicación estructuralmente válida puede producir un estado que todavía requiera prueba o autoridad adicional. «Aplicable» no significa automáticamente «verificado» ni «físicamente cometido».

## Archivo `.tevs`

Fuente TEVScript. Se analiza y compila mediante tooling de construcción. El runtime de producción opera sobre IR/artefactos canónicos validados y no recibe autoridad para reinterpretar `.tevs` en producción.

## Authority / autoridad

Permiso explícito para realizar una operación gobernada. Debe distinguirse de una mera descripción de efecto, de una capability declarada o de un hash de contenido.

## Bounded / acotado

Propiedad por la cual una operación individual tiene límites finitos verificables. Total-Core representa computación global abierta mediante una secuencia de quanta finitos enlazados por continuación, no mediante una operación individual ilimitada.

## Canonical JSON

Perfil de serialización JSON que fija una representación determinista de objetos semánticos/receipts donde el contrato lo exige. La misma estructura semántica canónica debe producir los mismos bytes.

## Capability

Puerto tipado que hace explícita una interacción con el host. Declarar una capability describe qué frontera puede necesitar el programa; no concede automáticamente el permiso físico para ejecutarla.

## Checkpoint

Objeto canónico que captura el estado necesario para continuar una ejecución bajo un contrato concreto. Un checkpoint liga identidades de programa/IR/estado y no debe interpretarse como una migración universal entre versiones incompatibles.

## Conformance

Demostración de que una implementación reproduce el contrato portable/normativo para el perfil que declara soportar. Una implementación no se vuelve autoridad semántica por pasar conformance; pasa a ser un testigo conforme.

## Continuation / continuación

Identidad/estado que permite enlazar un quantum finito con el siguiente. Sirve para representar procesos abiertos sin introducir una operación individual no acotada.

## Determinismo

Propiedad según la cual las mismas entradas explícitas, artefactos validados y autoridad observacional relevante producen el mismo resultado semántico canónico dentro del perfil portable. No significa que el mundo externo sea determinista.

## Diagnostic / diagnóstico

Error estructurado que identifica una condición de fuente, compilación, validación o runtime. Los diagnósticos públicos TEVScript usan códigos estables de familias como `TEVS_V31_*`.

## Effect / efecto

Descripción de una interacción que puede afectar o depender del exterior. Un efecto declarado no equivale a autoridad concedida. El commit físico permanece detrás de la frontera del provider/grant correspondiente.

## Exact value / valor exacto

Valor cuya semántica no depende de aproximación de coma flotante. Los enteros y racionales portables que heredan el contrato de exactitud permanecen exactos hasta una conversión explícita en la frontera del host.

## Fail-closed / fallo cerrado

Política por la que una ausencia o inconsistencia no se convierte silenciosamente en éxito. Ejemplos: versión no soportada, hash incorrecto, capacidad ausente, IR malformado o evidencia de prueba requerida que no está admitida.

## Field

Portador semántico finito, inmutable y content-addressed formado por hechos canónicos. Puede representar estado, evidencia, objetivos, propuestas u otras estructuras finitas denotables.

Un hash de Field demuestra identidad del contenido bajo el contrato; no demuestra que todos sus hechos sean verdaderos en el mundo físico.

## Field fact

Hecho canónico dentro de un Field, identificado por una relación estable y argumentos canónicos. Su identidad forma parte de la identidad del Field.

## Hash canónico

Hash calculado sobre la representación canónica especificada de un objeto. Se usa para integridad e identidad de contenido. No es, por sí mismo, una prueba lógica ni empírica.

## Host

Entorno externo que integra o ejecuta un runtime: Python, JavaScript, C#, Unity, WASI, navegador, sistema de archivos, etc. Las propiedades particulares del host no redefinen automáticamente la semántica TEVScript.

## IR / Intermediate Representation

Representación intermedia validada que separa la semántica compilada del runtime de producción. TEVScript conserva varias generaciones, incluyendo IR V2, V3, V4 y V5 con perfiles distintos.

## `invoke_v4`

Instrucción Total-Core V5 que invoca una unidad V4 exacta ya incluida y validada. El runtime usa el contrato V4 correspondiente y proyecta el resultado de forma gobernada al Field; V5 no reinterpreta la computación interna de la unidad.

## Language version

Versión del contrato del lenguaje fuente. Actualmente `3.1.0`. No debe confundirse con el package version Python `3.1.2`.

## Package version

Versión de la distribución instalable. Puede avanzar por correcciones de tooling, packaging o documentación sin cambiar la semántica del lenguaje.

## Profile / perfil

Discriminador semántico dentro de un dominio de versión. Ejemplos actuales: `total_core`, `semantic_process`, `pure`, `recursive`, `effects`.

## Program IR V4

Familia de IR utilizada por unidades computacionales cerradas. Total-Core admite unidades V4 `pure`, `recursive` y `effects` como hijos validados.

## Program IR V5 Total-Core

IR raíz actual del perfil Total-Core. Integra la base semántica Field/Transformation con control finito y unidades V4 content-addressed, proof admissions y límites de quantum.

## Proof admission

Evidencia externa admitida que satisface un requisito de prueba concreto bajo identidades verificables. La admission no genera la prueba; registra que una verificación externa autorizada ha sido admitida.

## Provider

Implementación de host que materializa una capability o frontera externa. Su comportamiento físico/operacional debe permanecer separado del significado portable del programa.

## Quantum

Tramo finito de ejecución limitado por el contrato del perfil. Una ejecución abierta se compone de múltiples quanta y continuaciones.

## Receipt

Objeto estructurado que registra el resultado y las identidades relevantes de una operación de validación, ejecución, transformación o certificación. Cuando es content-addressed, su hash permite detectar alteraciones del contenido cubierto.

## Runtime

Implementación que valida/ejecuta el IR soportado. El runtime no es la autoridad semántica y no debe reinterpretar fuente `.tevs` en producción.

## Semantic identity / identidad semántica

Identidad derivada del contenido/contrato semántico canónico pertinente. Debe distinguirse de ruta de archivo, orden accidental de enumeración, backend concreto o ubicación física cuando esos elementos son no semánticos.

## Source profile

Perfil de lenguaje fuente que determina qué frontend/contrato se aplica. En la matriz actual `3.1.0 + total_core` es la ruta current.

## Total-Core

Perfil actual de TEVScript 3.1 que compone procesos V5 Field/Transformation/Apply con unidades computacionales V4 exactas, proof admissions externas y ejecución por quanta finitos.

## Transformation

Propuesta de relación/cambio semántico identificable sobre Fields. Puede exigir precondiciones, pruebas, recursos o autoridad adicional. Su identidad es independiente del backend físico que eventualmente materialice un efecto.

## V31 archivado

Artefacto de packaging `3.1.0` preservado bajo `packaging/v31/`. No es el predecesor de paquete inmediato de `3.1.2`; ese papel corresponde a `3.1.1`.

## Version matrix

`spec/TEV_SCRIPT_VERSION_MATRIX.json`: autoridad machine-readable que separa y relaciona dominios de lenguaje, perfil de fuente, linked program, Program IR, runtime ABI, checkpoint y package.