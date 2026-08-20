# Preguntas frecuentes

## ¿TEVScript 3.1.2 es la versión del lenguaje?
No. `3.1.2` es el paquete candidato; el lenguaje actual es `3.1.0` con perfil `total_core`.

## ¿Puedo ejecutar `.tevs` directamente en producción?
La fuente se compila/analiza mediante tooling. La frontera portable de runtime es el IR canónico validado.

## ¿Total-Core sustituye V2/V3/V4?
No. Los reutiliza sin reinterpretación: proceso V3 y unidades V4 construidas desde las fuentes/semánticas anteriores.

## ¿Un hash demuestra que algo es verdadero?
No. Demuestra identidad/integridad bajo un esquema. La autoridad de prueba entra mediante admisiones verificadas externas.

## ¿Declarar una capacidad concede acceso físico?
No. El proveedor/host concede la operación y su scope.

## ¿Cómo se representa una computación larga?
Como quanta finitos ligados por continuaciones y checkpoints.

## ¿Python, JavaScript y C# pueden cambiar la semántica?
No deberían. Son hosts/runtimes que deben respetar modelos canónicos y conformance; cualquier aproximación de host es una frontera explícita.

## ¿Dónde busco un error?
Por `diagnostic.code` en `diagnostics/current-inventory.md`.