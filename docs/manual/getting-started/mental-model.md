# Modelo mental de TEVScript

Piensa TEVScript como una cadena de **contratos explícitos**, no como un script al que el runtime concede poderes implícitos.

## 1. La fuente describe una computación

Una fuente `.tevs` pertenece a un perfil. En 3.1, el proceso `total_core` coordina un Field, labels, transformaciones y unidades hijas. Las unidades conservan la semántica de sus perfiles V2/V4.

## 2. Compilar fija una identidad

La compilación produce Program IR canónico. Los hashes permiten saber exactamente qué semántica/artefacto se está validando y ejecutando. Un hash no demuestra verdad física: demuestra identidad bajo su esquema.

## 3. El runtime ejecuta un artefacto validado

El runtime no debería reinterpretar fuente ni depender de detalles accidentales de Python, JavaScript, C# o Unity. Ejecuta el IR admitido y produce resultados, receipts, continuaciones y checkpoints.

## 4. `Field → Transformation → Apply`

`Field` representa hechos canónicos. `Transformation` describe un cambio con precondiciones y, si corresponde, requisitos de prueba/recursos. `Apply` intenta materializar ese cambio y produce evidencia de la transición.

## 5. Computación abierta ≠ operación infinita

`quantum_steps` acota cada quantum. Si el proceso debe continuar, genera una continuación y un checkpoint; la siguiente ejecución vuelve a validar identidad y estado.

## 6. Capacidad ≠ autoridad automática

Nombrar filesystem, red, Unity u otra operación no concede acceso. El host/provider debe exponer una capability explícita y scoped. Del mismo modo, pedir una prueba no la fabrica: una `VerifiedProofAdmissionV1` llega desde un verificador externo autorizado.

## Regla práctica

Cuando dudes dónde pertenece algo, pregunta: **¿cambia el significado portable del programa o sólo cómo el host lo materializa?** Lo primero pertenece al lenguaje/IR; lo segundo debe permanecer en el adaptador/provider.

Continúa con `../tutorial/README.md` para construir programas progresivamente y con `../language-reference/README.md` para la referencia exacta.