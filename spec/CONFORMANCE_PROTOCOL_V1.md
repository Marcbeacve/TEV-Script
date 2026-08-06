# TEV Script Conformance Protocol V1

A conforming runtime consumes:

```text
program IR
+ controlled capability configuration
+ ordered event invocations
```

and emits `TEV_SCRIPT_CONFORMANCE_RECEIPT_V1` containing:

```text
program_hash
scenario_id
final typed state
emitted events
capability trace
receipt_hash
```

The receipt must use `TEV_CANONICAL_JSON_V1` followed by exactly one LF.
Different language implementations pass only when the bytes are identical.
Input files must be parsed before execution through a strict boundary that
rejects duplicate members, floating-point JSON numbers, negative zero, unsafe
structural integers, malformed UTF-8, and malformed syntax.

The authoritative campaign contains:

- `player.basic.v1`: representative lifecycle, state mutation, effects and
  emitted-event chaining;
- `matrix.full.v1`: all V0.2 binary/unary operators, pure functions, portable
  value kinds, typed event arguments, Unicode and controlled capability values.

Python and JavaScript reproduce both receipts. A future runtime must also pass
`conformance/canonical.vectors.json`, all negative boundary tests, and both
receipts before it can be labelled conformant. C# has not yet crossed that gate.
