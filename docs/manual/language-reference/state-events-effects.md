# Estado, eventos, capacidades y efectos

Las declaraciones de estado, eventos, capacidades, observaciones y acciones proceden de V1/V2 y son **INHERITED_COMPATIBILITY**. Su efecto observable debe pasar por el modelo de capacidades y por un proveedor del host.

En Total-Core, el estado superior es un `SemanticFieldV1`. Una unidad `effects` se compila con un `effect_input` externo exacto. La lista de inputs debe coincidir con las unidades declaradas `effects`; el frontend rechaza entradas faltantes, sobrantes, mal tipadas o de perfil incorrecto.

El runtime V5 puede consumir el recibo de una unidad de efectos y proyectarlo al Field. El commit físico real sigue fuera del runtime portable: conceder filesystem, red, reloj o APIs de Unity es responsabilidad del adaptador/proveedor.

Autoridad: `spec/TEV_SCRIPT_V2_FILESYSTEM_CAPABILITIES.md`, `spec/TEV_SCRIPT_V31_TOTAL_CORE.md`.