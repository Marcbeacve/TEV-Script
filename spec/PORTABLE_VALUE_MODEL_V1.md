# TEV Portable Value Model V1

## Semantic values

| Type | Wire representation |
|---|---|
| `Bool` | JSON boolean |
| `Int` | `{"$int":"<canonical decimal>"}` |
| `Rat` | `{"$rat":["<numerator>","<positive denominator>"]}` |
| `Text` | JSON string |
| `Vec2` | array of two `Rat` values |
| `Vec3` | array of three `Rat` values |
| `Unit` | JSON `null` |

Integer text has no plus sign, no leading zeros, and no `-0`. Rationals are
normalized by greatest common divisor and always have a positive denominator.

## Structural numbers

IR indexes, arities and budgets use bounded JSON integers. They are not gameplay
values and must remain within the limits declared by the schema. JavaScript can
therefore parse them safely as `Number`.

## Host mapping

```text
Python Int → int
JavaScript Int → BigInt
C# Int → System.Numerics.BigInteger
Rust Int → num_bigint::BigInt (or an equivalent conforming type)
```

A runtime may use another internal representation only if it reproduces the
canonical wire value exactly.
