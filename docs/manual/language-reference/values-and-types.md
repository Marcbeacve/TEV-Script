# Valores exactos y tipos

Los tipos y literales de las unidades proceden de V2 y son **INHERITED_COMPATIBILITY**. `Int` conserva semántica entera exacta; las estructuras portables se serializan mediante modelos canónicos antes de entrar en identidades o recibos.

Total-Core no introduce una sintaxis aritmética alternativa. Su `Field` contiene hechos semánticos validados; los argumentos de esos hechos deben ser representables por el modelo portable/canónico de la capa correspondiente.

La frontera importante es: valor de fuente → valor tipado → representación IR canónica. Una clase, diccionario o número del host no adquiere autoridad semántica sólo por poder convertirse a JSON.

Clasificación: literales, tipos, records/variants y colecciones de V2/V3 = **INHERITED_COMPATIBILITY**; objetos Python/JS/C# = **INTERNAL/host**, nunca sintaxis TEVScript.

Autoridad: `spec/TEV_SCRIPT_V2_LANGUAGE.md`, `spec/PORTABLE_VALUE_MODEL_V1.md`, `spec/TEV_SCRIPT_IR_V3_VALUE_MODEL.md`.