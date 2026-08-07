# TEV Script Source Lexical Contract V1

This document closes the lexical authority for TEV Script `0.2.0`.

- Source bytes are UTF-8. A single leading UTF-8 BOM is accepted and discarded.
- NUL bytes are forbidden.
- Identifiers are ASCII: `[A-Za-z_][A-Za-z0-9_]*`.
- Stable capability names are dot-qualified identifiers in source. The compiled IR may use the wider stable-id alphabet defined by IR V2.
- Integer and decimal source tokens use ASCII digits only. Decimals are lowered to exact rationals; exponent notation is not source syntax.
- `#` starts a line comment outside a string.
- Strings cannot cross a physical line and support exactly `\\n`, `\\r`, `\\t`, `\\"`, and `\\\\` escapes. Other Unicode scalars are preserved literally.
- Keywords are lowercase and reserved.

A frontend must reject a non-ASCII identifier character rather than normalizing, case-folding, transliterating, or silently accepting it.
