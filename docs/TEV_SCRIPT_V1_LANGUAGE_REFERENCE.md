# TEV Script V1 — Language Reference

Status: **V1 implementation candidate; stable release not yet admitted**.

This document is the programmer-facing reference for TEV Script V1. Normative disputes are resolved by the V1 lexical profile, EBNF, semantic contract, link model, budgets, linked-program schema and IR V3 specifications. This guide explains how those pieces fit together in actual programs.

---

## 1. What TEV Script is

TEV Script is a bounded, statically typed, deterministic reactive language.

Its core abstraction is not a class hierarchy and not a general-purpose process. A TEV Script program describes:

```text
state
+ typed events
+ deterministic handlers
+ pure computation
+ explicit host capabilities
+ finite composition
```

The language deliberately separates **semantic computation** from **physical authority**.

A handler may compute arbitrary values inside the bounded V1 domain, but interaction with the external host occurs only through declared capabilities.

The implementation language is not part of TEV Script semantics. Python, JavaScript, C#, Browser-WASM and WASI are interchangeable runtime/compiler hosts only when they reproduce the same canonical semantics.

---

## 2. Compilation model

The V1 pipeline is:

```text
one script root + zero or more modules
    ↓
UTF-8 decoding / lexical analysis
    ↓
V1 AST
    ↓
deterministic import linking
    ↓
name resolution
    ↓
nominal and constructed type analysis
    ↓
purity / effect / event analysis
    ↓
constant evaluation
    ↓
behavior expansion
    ↓
TEV_SCRIPT_LINKED_PROGRAM_V1
    ├── erasable runtime surface ──→ TEV_SCRIPT_PROGRAM_IR_V2
    └── full V1 algebraic surface ─→ TEV_SCRIPT_PROGRAM_IR_V3
```

`TEV_SCRIPT_LINKED_PROGRAM_V1` is the canonical source-semantic boundary. Runtime backends consume linked semantics; they do not perform independent source lookup rules.

This distinction is important:

- **source syntax** determines what the programmer can express;
- **linked semantics** determines what the program means;
- **IR** determines how that meaning is represented for execution.

---

## 3. Source files

A V1 source file is exactly one of two forms.

### 3.1 Script root

A program has exactly one root script:

```tevs
script Ecosystem version "1.0.0";

entity World {
    on start {
        log "started";
    }
}
```

The root owns:

- the program id;
- root imports;
- root declarations;
- entities.

A V1 script must contain at least one entity.

### 3.2 Module

Modules contain reusable declarations but no entities:

```tevs
module ecosystem.energy version "1.0.0";

export record EnergyPacket {
    amount: Rat;
}

export fn clamp01(value: Rat) -> Rat = min(max(value, 0), 1);
```

Module identity is declared in source. It is **not derived from the filesystem path**.

Moving `energy.tevs` to another directory cannot change the semantic identity of `ecosystem.energy`.

---

## 4. Imports

Imports are explicit:

```tevs
import ecosystem.energy;
import ecosystem.motion;
```

The language does not perform:

- network package resolution;
- registry lookup;
- wildcard imports;
- path searching;
- environment-variable lookup;
- implicit re-export;
- semver-range dependency selection.

The build invocation supplies a finite set of source units. The deterministic linker resolves module ids only inside that set.

### 4.1 Direct visibility

A unit sees:

1. its own declarations;
2. exported declarations of modules it imports directly.

A transitive dependency is not implicitly visible.

If `A` imports `B` and `B` imports `C`, `A` must still explicitly import `C` before using declarations from `C`.

### 4.2 Ambiguous imports

If two directly imported modules export the same visible leaf name and an unqualified reference could mean either, compilation fails.

Resolution never depends on import discovery order or filesystem enumeration order.

---

## 5. Export and privacy

Module declarations are private by default:

```tevs
module game.damage version "1.0.0";

record InternalAccumulator {
    value: Int;
}

export record Damage {
    amount: Int;
}
```

`InternalAccumulator` is visible only inside `game.damage`.

`Damage` may be referenced by a direct importer.

The root script does not define a package export surface in V1.0, so `export` is a module-level concept.

---

## 6. Identifiers and names

Identifiers use ASCII only:

```text
[A-Za-z_][A-Za-z0-9_]*
```

They are case-sensitive.

Qualified names use `.`:

```text
ecosystem.energy
world.temperature
motion.move2d
```

Enum variants use `::`:

```text
Season::Winter
```

The distinction is semantic:

- `.` traverses qualified names / record fields;
- `::` selects a nominal enum variant.

---

## 7. Primitive types

V1 retains the portable primitive type set:

```text
Bool
Int
Rat
Text
Vec2
Vec3
Unit
```

### 7.1 Bool

```tevs
true
false
```

### 7.2 Int

`Int` is exact integer arithmetic. It is not host `int32`, JavaScript `Number` or platform machine width.

```tevs
state count: Int = 0;
```

### 7.3 Rat

`Rat` is exact rational arithmetic.

A decimal source literal denotes an exact base-10 rational:

```tevs
state rate: Rat = 0.1;
```

This means exactly `1/10`, not an IEEE-754 approximation.

`Int` widens implicitly to `Rat` where required. `Rat` never narrows implicitly to `Int`.

### 7.4 Text

Strings are immutable Unicode text values:

```tevs
state label: Text = "reactor";
```

The supported source escapes are exactly:

```text
\n
\r
\t
\"
\\
```

### 7.5 Vec2 / Vec3

Vectors are portable exact-rational vectors.

Use the pure constructors:

```tevs
vec2(1, 0)
vec3(0, 1.5, -2)
```

### 7.6 Unit

`Unit` means a capability returns no language value.

It is **not** a storable value.

Valid:

```tevs
capability audio.play(Text) -> Unit effect;
```

Invalid conceptual uses include:

```text
state x: Unit
record R { x: Unit; }
Option<Unit>
Result<Int, Unit>
fn f() -> Unit = ...
```

---

## 8. Records

Records are immutable nominal value types.

```tevs
record ResourcePacket {
    energy: Rat;
    mass: Rat;
    source: Text;
}
```

Construction uses named arguments:

```tevs
ResourcePacket(
    energy = 0.25,
    mass = 4,
    source = "vent"
)
```

All fields are mandatory.

The constructor form is deliberately distinct from positional function calls.

### 8.1 Nominal typing

These are different types even though their fields match:

```tevs
record Position { x: Rat; y: Rat; }
record Velocity { x: Rat; y: Rat; }
```

A `Position` is not assignable to `Velocity`.

### 8.2 Field access

```tevs
let amount = packet.energy;
```

Field access is statically resolved. There is no dictionary fallback or reflection.

### 8.3 Record equality

Values of the same nominal record type compare structurally by canonical field values.

Different nominal record types cannot be compared as though they were the same record.

### 8.4 Recursive records

Recursive value graphs are forbidden in V1.0:

```tevs
# invalid semantic shape
record Node {
    next: Option<Node>;
}
```

The record dependency graph must be acyclic.

This preserves finite value structure and bounded static analysis.

---

## 9. Enums

Enums define closed nominal sets of payload-free variants:

```tevs
enum Season {
    Spring;
    Summer;
    Autumn;
    Winter;
}
```

Values use `::`:

```tevs
state season: Season = Season::Spring;
```

Variants have no implicit integer representation.

This is intentionally invalid as a semantic assumption:

```text
Spring == 0
Summer == 1
```

Variant declaration order is not arithmetic data.

---

## 10. Option<T>

`Option<T>` represents presence or absence without host `null` semantics.

Constructors:

```tevs
Some(value)
None
```

Example:

```tevs
state target: Option<Int> = None;
```

A bare `None` needs contextual type information because `None` alone does not determine `T`.

---

## 11. Result<T,E>

`Result<T,E>` represents explicit success/error data without exceptions as language control flow.

Constructors:

```tevs
Ok(value)
Err(error)
```

Example:

```tevs
state lastRead: Result<Rat, Text> = Err("not sampled");
```

`Result` is a normal immutable language value. A host exception is not silently converted into `Err` unless a host adapter explicitly defines such a policy outside the language core.

---

## 12. State

State is mutable entity-owned storage:

```tevs
entity Reactor {
    state active: Bool = false;
    state energy: Rat = 0;
}
```

State initializers must be compile-time constant expressions.

State cannot depend on:

- an observation capability;
- current time;
- input;
- entity runtime state;
- environment data.

Valid:

```tevs
state origin: Vec2 = vec2(0, 0);
state packet: ResourcePacket = ResourcePacket(energy = 1, mass = 2, source = "seed");
```

Invalid conceptually:

```tevs
state dt: Rat = time.delta();
```

The constant checker rejects capability use structurally, even if an expression branch appears dead.

---

## 13. Local bindings

Use `let` for immutable lexical bindings:

```tevs
let next = count + 1;
let speed: Rat = 1;
```

A `let` may have an explicit type or infer it from the expression.

Locals cannot be reassigned.

Assignment syntax targets entity state only:

```tevs
count = next;
```

V1 also forbids shadowing an enclosing local, parameter or state name. This makes lowering and code review less capture-sensitive.

---

## 14. Events and handlers

Handlers react to typed local events:

```tevs
entity Counter {
    state count: Int = 0;

    on add(amount: Int) {
        count = count + amount;
    }
}
```

Events are not threads and do not imply concurrency.

Handlers execute deterministically within the bounded event-chain model.

### 14.1 Emit

```tevs
emit changed(count);
```

All emit sites and handler fragments for one event must agree on one parameter signature after composition.

### 14.2 Return

```tevs
return;
```

`return;` terminates the current entity handler sequence.

Behavior handler fragments cannot use `return;`, because one behavior is not allowed to suppress later composed fragments accidentally.

---

## 15. If

```tevs
if energy > 0.5 {
    active = true;
} else {
    active = false;
}
```

The condition must be `Bool`.

Boolean short-circuiting is semantic:

```tevs
false and probe.read()
true or probe.read()
```

The right side must not execute in those examples.

This remains true after lowering. TEV Script does not allow a backend to replace short-circuit semantics with an eager host operator.

---

## 16. Bounded for

V1 provides only statically bounded integer ranges:

```tevs
for i in 0 .. 4 {
    log "step";
}
```

The range is half-open:

```text
0, 1, 2, 3
```

Both bounds are signed integer literals.

The upper bound must be greater than or equal to the lower bound.

There is no:

```text
while
unbounded for
general collection iterator
break
continue
```

A backend may unroll `for` only after validating the loop and expansion budgets.

---

## 17. Match

`match` is exhaustive and statement-level in V1.0.

### 17.1 Enum

```tevs
match season {
    Season::Spring => { log "spring"; }
    Season::Summer => { log "summer"; }
    Season::Autumn => { log "autumn"; }
    Season::Winter => { log "winter"; }
}
```

Every variant must appear exactly once.

There is no wildcard/default arm.

### 17.2 Option

```tevs
match target {
    Some(value) => {
        selected = value;
    }
    None => {
        selected = -1;
    }
}
```

### 17.3 Result

```tevs
match lastRead {
    Ok(value) => {
        measurement = value;
    }
    Err(message) => {
        log message;
    }
}
```

Pattern bindings are immutable and arm-local.

---

## 18. Pure functions

User functions are pure expression functions:

```tevs
fn clamp01(value: Rat) -> Rat = min(max(value, 0), 1);
```

Every parameter and return type is explicit.

Pure functions may call:

- pure built-ins;
- visible pure user functions.

They may not:

- read entity state;
- call observation capabilities;
- call effect capabilities;
- emit events;
- mutate state.

The user-function call graph must be acyclic.

Recursion is not permitted in V1.0.

### 18.1 Call-by-value

Function arguments are evaluated exactly once before substitution/inlining.

If a later language revision permits effectful expressions in a context, a backend still cannot duplicate an argument merely because it inlined a function.

---

## 19. Portable pure built-ins

The current portable pure base contains:

```text
vec2(Rat, Rat) -> Vec2
vec3(Rat, Rat, Rat) -> Vec3
min(Int, Int) -> Int
min(Rat, Rat) -> Rat
max(Int, Int) -> Int
max(Rat, Rat) -> Rat
```

Exact overload selection is static.

---

## 20. Capabilities

Capabilities are typed host ports.

Example declarations:

```tevs
capability world.temperature(Vec2) -> Rat observation;
capability inventory.deposit(ResourcePacket) -> Unit effect;
```

Two kinds exist:

```text
observation
 effect
```

An observation returns host/environment data.

An effect requests host-side mutation/action.

### 20.1 Observation expression

A value-returning observation may be consumed in a handler expression:

```tevs
let dt = time.delta();
```

It is forbidden inside a pure user function.

### 20.2 Effect statement

A Unit-returning capability is invoked with `call`:

```tevs
call inventory.deposit(packet);
```

### 20.3 Authority is explicit

Declaring or using a capability does not grant host authority.

The compiled entity exposes its complete capability requirement set. The host separately decides whether that exact capability ABI is available.

For governed hot update V3, the capability ceiling compares the full signature:

```text
capability id
parameter types
return type
kind
```

Keeping the same id while changing the ABI is not treated as the same authority.

---

## 21. Portable base capabilities

The base portable catalog currently contains:

```text
debug.log(Text) -> Unit effect
input.move2d() -> Vec2 observation
time.delta() -> Rat observation
motion.move2d(Vec2) -> Unit effect
animation.play(Text) -> Unit effect
```

TEV Script V1 also permits typed custom capability declarations.

---

## 22. Behaviors

A behavior is a compile-time composition unit.

It is **not**:

- a class;
- a base class;
- an interface object;
- a runtime trait object;
- virtual dispatch.

Example:

```tevs
behavior Alive {
    state alive: Bool = true;
}

behavior Movement {
    use Alive;
    state speed: Rat = 1;

    on update {
        move vec2(speed, 0);
    }
}

entity Creature {
    use Movement;

    on update {
        animate "Walk";
    }
}
```

### 22.1 Expansion order

Composition is dependency-first and preserves explicit `use` order.

If an entity uses behavior `A` and then `B`, and both contribute to `update`, execution order is semantically significant:

```text
A dependency fragments
A local fragment
B dependency fragments
B local fragment
entity-local fragment
```

The exact flattening algorithm rejects cycles, repeated/diamond inclusion and conflicting state/event signatures rather than silently choosing one interpretation.

### 22.2 State visibility

A behavior may see state provided by its own dependencies.

It does not gain access to state that exists only in a sibling behavior.

An entity-local handler sees the full state closure after its behaviors are composed.

---

## 23. Expression precedence

From lowest to highest precedence:

```text
or
and
== !=
< <= > >=
+ -
* /
unary not / unary -
postfix call / field access
primary
```

Use parentheses when the semantic grouping should be visually explicit.

---

## 24. Arithmetic and comparison

### 24.1 Arithmetic

`+`, `-`, `*`, `/` use exact TEV numeric/vector rules.

`Int / Int` is not silently converted through host floating-point arithmetic.

Backends must follow the typed IR signature selected by the compiler.

Division by zero is a deterministic runtime failure.

### 24.2 Equality

Equality is defined for compatible values, including algebraic V1 values.

Records require equal nominal type before structural field comparison.

Enums require the same nominal enum type.

`Option` and `Result` compare their canonical constructors/payloads recursively.

### 24.3 Ordering

Ordering comparisons are numeric in V1.0.

Enums, records, `Option`, `Result` and `Text` do not acquire host-specific ordering implicitly.

---

## 25. Namespaces

The linker maintains distinct semantic namespaces for:

```text
types
pure functions
behaviors
capabilities
entities
```

A name collision in one namespace does not automatically mean a collision in another.

User declarations cannot silently replace predeclared portable symbols in the same semantic namespace.

---

## 26. Longest-symbol-prefix rule

Dotted expression names are resolved by the longest valid semantic symbol prefix; remaining segments are record fields.

Conceptually, if:

```text
model.current.position.x
```

resolves `model.current` as the visible symbol, then `.position.x` must type-check as record fields.

There is no reflection or dynamic property lookup fallback.

---

## 27. Constant expressions

A state initializer may contain deterministic pure constant computation:

- literals;
- exact arithmetic;
- vectors;
- records;
- enums;
- `Some` / `None`;
- `Ok` / `Err`;
- pure built-ins;
- acyclic user pure functions whose arguments are constant.

Constant evaluation has an explicit step budget.

A compiler must fail when the budget is exceeded rather than continue indefinitely.

---

## 28. Resource boundedness

V1 is designed so all mandatory source analysis is finitely bounded.

Normative examples include:

```text
source unit bytes                         1,000,000
reachable source closure bytes           16,000,000
reachable modules                        256
imports/source                            256
entities                                 128
record fields                            256
enum variants                            256
function/event/capability parameters      64
call arguments                            64
block nesting                             64
expression nesting                       128
type nesting                             128
match arms                               256
static for iterations                    1,024
nested static loops                        8
pure function call-graph depth             64
```

The authoritative complete table is `spec/TEV_SCRIPT_V1_BUDGETS.md`.

Budget failure is a compile/link error. No budget is implemented by silently truncating the program.

---

## 29. Determinism guarantees

For the same semantic source set, changing only the following must not change the linked semantic hash:

- source file paths;
- input file enumeration order;
- path separators;
- process locale;
- timezone;
- dictionary/hash-map iteration order;
- source file timestamps.

Explicit semantic order still matters:

- statement order;
- behavior `use` order;
- function argument order;
- record constructor expression evaluation order;
- event emission order.

---

## 30. Canonical linked program

The linker/static analyzer emits:

```text
TEV_SCRIPT_LINKED_PROGRAM_V1
```

This is more than serialized AST.

It normalizes semantic identity by:

- replacing source-path identity with declared semantic ids;
- resolving imports and visibility;
- resolving nominal type ids;
- alpha-renaming non-semantic parameter/local/binding names;
- normalizing constant state initializers to semantic values;
- preserving meaningful execution order;
- sorting semantic sets where declaration order has no meaning.

Consequently two sources can differ textually and still have the same linked semantic identity when their meaning is the same.

---

## 31. IR V2 versus IR V3

### 31.1 IR V2-compatible V1 programs

A V1 program may lower to certified IR V2 when every V1-only abstraction can disappear before runtime.

Examples:

- modules/imports;
- export visibility;
- pure user functions after validated inlining;
- behavior composition after deterministic expansion;
- bounded `for` after unrolling;
- custom capabilities using only V0.2 portable value types.

### 31.2 IR V3-required programs

General runtime use of these requires IR V3:

```text
records
enums
Option<T>
Result<T,E>
runtime field access
runtime algebraic match
algebraic capability arguments/returns
algebraic event payloads
```

The compiler must never encode such values through ad-hoc JSON strings or opaque host objects merely to force them through IR V2.

---

## 32. IR V3 execution model

IR V3 retains the bounded acyclic execution model.

It adds a closed type table and algebraic value instructions while preserving:

- immutable stack values;
- typed state;
- typed locals;
- typed event parameters;
- typed capabilities;
- forward-only control flow;
- definite local initialization;
- bounded event chains;
- no reflection;
- no runtime code generation;
- no host-native references.

This is deliberately not a heap/object VM.

---

## 33. Runtime checkpointing

Runtime Checkpoint V2 can persist exact V3 state.

A checkpoint binds:

```text
program id
IR schema
IR semantic hash
source schema
source semantic hash
entity ids
state names
state types
canonical state values
```

Restore is exact-target only.

A checkpoint is not a generic migration format between arbitrary programs.

Live compatible migration is handled by the transactional update layer, where compatibility is checked separately before commit.

---

## 34. Signed updates

The V3 update model uses a distinct V2 package contract.

A signed transition binds:

```text
channel
program
epoch / sequence
source IR hash (from)
target IR hash
target source-semantic hash
target canonical IR bytes
signature authority
```

The transition therefore means:

```text
A --authorized package--> B
```

not:

```text
anything --package--> B
```

Runtime migration is prepared in isolation, then atomically committed. Durable-store failure triggers runtime rollback.

---

## 35. What TEV Script V1 intentionally does not contain

V1.0 deliberately excludes:

```text
unbounded loops
recursion
async/await
threads
implicit concurrency
classes and inheritance
reflection
runtime code generation
runtime source compilation
user-defined generics
general map/dictionary values
payload-carrying user enum variants
exceptions as language control flow
host-native object references
implicit networking
package-registry/network import resolution
wildcard imports
implicit re-export
```

These are not “forgotten syntax”. Each would enlarge the semantic/proof surface and requires an explicit later language revision.

---

## 36. A complete multi-file example

### `model.tevs`

```tevs
module ecosystem.model version "1.0.0";

export enum ResourceKind {
    Mineral;
    Organic;
}

export record Resource {
    amount: Rat;
    kind: ResourceKind;
}

export fn normalized(amount: Rat) -> Rat = min(max(amount, 0), 1);
```

### `storage.tevs`

```tevs
module ecosystem.storage version "1.0.0";

import ecosystem.model;

export capability storage.deposit(ecosystem.model.Resource) -> Unit effect;
```

### `main.tevs`

```tevs
script Ecosystem version "1.0.0";

import ecosystem.model;
import ecosystem.storage;

behavior EnergyConsumer {
    state energy: Rat = 1;

    on update {
        if energy > 0 {
            energy = max(energy - 0.01, 0);
        }
    }
}

entity Harvester {
    use EnergyConsumer;

    state selected: Option<ecosystem.model.Resource> = None;

    on harvest(amount: Rat) {
        let resource = ecosystem.model.Resource(
            amount = ecosystem.model.normalized(amount),
            kind = ecosystem.model.ResourceKind::Mineral
        );

        selected = Some(resource);

        match selected {
            Some(value) => {
                call storage.deposit(value);
            }
            None => {
                log "nothing selected";
            }
        }
    }
}
```

This program exercises:

- modules/imports;
- exported nominal data types;
- a pure function;
- a custom algebraic capability;
- behavior composition;
- entity state;
- `Option`;
- record construction;
- enum construction;
- exhaustive match;
- explicit effect authority.

Because an algebraic `Resource` crosses a capability boundary and is stored inside `Option<Resource>`, this program requires IR V3 rather than the erasable IR V2 profile.

---

## 37. Design mental model

When designing a TEV Script subsystem, use this order:

```text
1. What persistent entity state exists?
2. What events may change that state?
3. Which computation can remain pure?
4. Which reusable behavior fragments compose into the entity?
5. Which external observations/effects require capabilities?
6. Which values deserve nominal records/enums instead of loose primitives?
7. What failure/absence states should be explicit Option/Result values?
8. What static bounds prove the computation is finite?
```

This leads naturally to code where authority, mutation, failure and composition are visible in the language rather than hidden in host conventions.

---

## 38. Relation to object-oriented programming

TEV Script does not reproduce traditional OOP one-for-one.

A useful correspondence is:

```text
OO concept                  TEV Script concept
-------------------------------------------------------------
object identity             entity identity
fields                      entity/behavior state
immutable value object      record
enum / closed state         enum
nullable value              Option<T>
explicit success/failure    Result<T,E>
method reacting to input    event handler
pure utility method         fn
interface to environment    capability
mixin/trait-like reuse      behavior + use
composition                 behavior dependency graph
encapsulation               module privacy/export
constructor defaults        constant state initializers
runtime polymorphism        intentionally absent in V1
inheritance                 intentionally absent in V1
```

The TEV model favors explicit composition, typed authority and deterministic event/state transitions instead of hidden mutable object graphs.

---

## 39. Error handling philosophy

TEV Script separates three categories.

### Expected domain alternatives

Model them as data:

```tevs
Option<T>
Result<T,E>
enum
```

### Invalid program

Reject statically:

```text
unknown name
ambiguous import
wrong type
non-exhaustive match
recursive function graph
behavior cycle
state conflict
capability ABI conflict
budget overflow
```

### Host/runtime failure

Fail closed with a deterministic runtime/host diagnostic. Do not reinterpret it as ordinary language control flow.

---

## 40. Portability rule

Never write TEV Script assuming implementation quirks such as:

```text
Python unlimited int behavior as authority
JavaScript Number rounding
C# dictionary enumeration order
.NET object identity
filesystem module order
locale-dependent text casing
platform-specific path rules
```

Portable semantics are those defined by TEV Script specifications and canonical artifacts.

---

## 41. Certification status versus language semantics

A source feature can be fully specified and implemented while the repository still reports:

```text
CERTIFY_FULL=NO
LANGUAGE_STABLE=NO
```

That means the exact current Git commit has not yet passed the complete mandatory multi-host admission campaign.

It does **not** mean the language feature is unspecified.

Conversely, a passing ancestor does not certify a modified descendant.

See `docs/V1_CERTIFICATION_PROTOCOL.md` for the exact admission sequence.
