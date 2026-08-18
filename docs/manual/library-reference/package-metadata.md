# Metadatos públicos del paquete

## `__version__`

```text
from tev_script import __version__
```

`__version__` es un alias público de `tev_script.version.PACKAGE_VERSION`.

En el candidato actual:

```text
__version__ == "3.1.2"
```

Este valor identifica el **paquete**, no el lenguaje. La versión de lenguaje Total-Core actual es `3.1.0`.

Usos apropiados:

- registrar qué distribución está cargada;
- comprobar compatibilidad explícita de una integración con una versión de paquete;
- incluir identidad de paquete en diagnósticos de host.

No lo uses para inferir automáticamente:

```text
source profile
Program IR version
runtime ABI
checkpoint version
```

Esos dominios están separados en `spec/TEV_SCRIPT_VERSION_MATRIX.json`.

Relacionado: [`../versions/version-domains.md`](../versions/version-domains.md).
