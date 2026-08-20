# Fronteras de proof, authority, capability y physical commit

Varias palabras de TEVScript describen «permiso/evidencia», pero no son equivalentes.

## Matriz conceptual

```text
proof requirement   qué proposición/requisito necesita evidencia
verification receipt evidencia producida por un verificador
proof admission      enlace gobernado de esa evidencia a un programa/authority
program authority    scope semántico del programa
capability contract  qué interacción externa puede pedirse/observarse
resource identity    qué recurso concreto se toca
provider grant       permiso operativo para materializar
commit receipt       qué ocurrió realmente al realizar
```

## Proof requirement

Forma parte de una Transformation. No concede nada; declara una obligación.

## Verification receipt

Proviene del proceso de verificación. Su identidad se referencia desde admission. Puede tener su propio scope/assumptions y no debe reducirse al string hash aislado.

## Proof admission

Afirma que un receipt/verifier exactos están admitidos para requirement/authority exactos. Es Program IR data externo a fuente.

## Program authority

`authority_hash` liga scope/identidad semántica. Una admission de otra authority se rechaza.

No es necesariamente un token de OS ni una ACL física.

## Capability

Describe una interfaz observable/efectiva. Ejemplo:

```text
sensor.read(Int)->Int
```

Dos invocaciones de la misma capability pueden tocar recursos concretos distintos en otros dominios; capability ID no sustituye resource identity.

## Resource

La descripción puede depender de argumentos:

```text
file.write(pathA)
file.write(pathB)
```

El analysis de aliasing/resource debe ser explícito. «Misma capability» no implica «mismo recurso» ni independencia automática.

## Grant/provider

El provider es la implementación que tiene acceso al entorno. El grant delimita qué puede hacer. Esta es la frontera donde importan permisos de SO, Unity APIs, network sandbox, etc.

## Intent frente a commit

Una semántica puede producir:

```text
intent(file.replace,...)
```

sin que el archivo haya cambiado. Después del provider pueden existir estados como applied/confirmed/unknown/partial según el contrato.

Nunca promociones intent a success físico sin evidencia.

## Observación como efecto

Leer no siempre es neutral: `queue.pop()` adquiere información y consume recurso. El modelo general permite describir dimensiones de effect/commit por dominio; no hardcodea que toda observation sea reversible/gratuita.

## Desirability no sobreescribe safety

La admisión debe separar al menos:

```text
Possible
Authorized
Safe
ResourcesAvailable
Desirable
```

Utility/desirability no puede convertir `Authorized=False` en acción admitida.

## Hashes no conceden autoridad

Un effect/resource/proof hash es identidad de contenido. No es credential secreta ni firma/autorización por sí mismo.

## Patrón de integración correcto

```text
program produce intent/requirement
        ↓
verifier/provider autorizado
        ↓
receipt/evidence
        ↓
admission/reconciliation
        ↓
next semantic state
```

Mantener estas capas desacopladas permite sustituir providers sin cambiar el significado portable.

## Errores de arquitectura a evitar

- runtime importando `os`/Unity API como bypass de capability;
- source autodeclarándose verified;
- authority hash usado como bearer token;
- resource aliasing asumido sin análisis;
- command intent marcado COMMITTED antes del provider;
- failure de provider convertido en semantic PASS.

## Autoridades

- `spec/TEV_SCRIPT_SEMANTIC_APPLY_CALCULUS_V0.md`
- `spec/TEV_SCRIPT_V2_FILESYSTEM_CAPABILITIES.md`
- `spec/TEV_SCRIPT_V31_TOTAL_CORE.md`
- adapters/providers específicos.
