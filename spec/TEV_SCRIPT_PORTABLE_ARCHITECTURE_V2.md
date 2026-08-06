# TEV Script Portable Architecture V2

## Decision

The language authority is not Python, C#, JavaScript, Unity, or C--.
The authority is the following closed set:

```text
source grammar
+ static semantics
+ TEV_SCRIPT_PROGRAM_IR_V2
+ portable value model
+ runtime ABI
+ canonical hashing rules
+ conformance scenarios and receipts
```

Every implementation is replaceable and must reproduce the same conformance
receipts byte-for-byte.

## Architecture

```text
                         TEV Script source (.tevs)
                                  |
                        reference frontend/compiler
                                  |
                     TEV_SCRIPT_PROGRAM_IR_V2
                                  |
              +-------------------+--------------------+
              |                   |                    |
       Python runtime      JavaScript runtime      C# runtime
       reference/test      Node/browser/edge       .NET/Unity/etc.
              |                   |                    |
              +-------------------+--------------------+
                                  |
                         host capability ABI
                                  |
          +-----------------------+------------------------+
          |                       |                        |
       Unity/C--            browser/canvas             server/CLI
```

The Player or production host consumes compiled IR. It never needs Python or
source parsing.

## Why C# is not the base

C# is the primary runtime for Unity, but making it the semantic root would force
other hosts to imitate .NET-specific behaviour. JavaScript has `BigInt`, Rust
has ownership and enum-based values, Python has arbitrary integers, and C# has
`BigInteger`. The wire contract therefore uses tagged semantic values and does
not rely on a host's native JSON number model.

## Why JavaScript required IR V2

Standard `JSON.parse` converts JSON numbers to IEEE-754 `Number`. Arbitrary
integers would lose information. V2 separates:

```text
bounded structural integers:
  instruction indexes, budgets, arities → JSON integer

semantic integers:
  {"$int":"123456789012345678901234567890"}

semantic rationals:
  {"$rat":["1","10"]}
```

This permits exact semantic values in JavaScript, but program and scenario files
still pass through the TEV strict JSON loader. Plain `JSON.parse` is not the
authoritative input boundary because it silently accepts duplicate keys and
coerces unsafe structural integers.

## Capability namespaces

Portable capabilities do not name engines:

```text
input.move2d
motion.move2d
animation.play
time.delta
debug.log
```

Adapters map them to host APIs:

```text
Unity:
  motion.move2d  → Transform/Rigidbody/CharacterController
  animation.play → Animator

Web:
  motion.move2d  → canvas/entity position
  animation.play → sprite state or Web Animations API

MonoGame:
  motion.move2d  → game state position
```

Host-specific capabilities remain possible under explicit namespaces such as
`unity.physics2d.raycast`, but they are not part of the portable standard
library.

## Reactive versus governed execution

TEV Script has two lowering lanes:

```text
frequent reactive behaviour
  state, input, movement, animation, UI
  → TEV_SCRIPT_PROGRAM_IR_V2

causally governed behaviour
  authority, permit, expectation, verification, replay
  → TEV_CAUSAL_MODULE_IR_V1

multi-entity workflows
  dependencies and effect sets
  → TEV_GENERAL_PROGRAM_IR_V1
```

This avoids treating every frame as a causal decision while preserving the
existing TEV authorities where they are meaningful.

## Runtime boundaries

V0.2 is synchronous and bounded:

- no runtime source compilation;
- no reflection;
- no dynamic code;
- no unbounded loops or recursion;
- finite instruction budget per handler;
- finite event-chain budget;
- every physical effect crosses a named capability;
- missing capabilities fail closed;
- semantic IR hash is checked before execution.

Async capabilities require a future ABI version and cannot be introduced by
silently returning promises/tasks.

## Current implementation status

```text
Python compiler:                 implemented
Python reference runtime:        implemented
JavaScript runtime:              implemented
Python↔JavaScript byte parity:   PASS
JavaScript arbitrary Int:        PASS
Canonical JSON vectors:          PASS
Strict JSON input boundary:      PASS
JSON schemas:                    PASS
Conformance scenarios:           4 PASS
C# portable runtime:             CONFORMANT observed Windows/.NET 10, 4 receipts byte-identical
Unity adapter:                   contracted, not certified
Causal/general lowering:         future tranche
```
