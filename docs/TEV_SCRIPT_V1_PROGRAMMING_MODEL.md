# TEV Script V1 — Programming Model, Patterns and Data Structures

Status: programmer-facing architecture guide for the V1 implementation candidate.

This document answers a different question from the grammar reference:

> Given that TEV Script is not conventional OOP, how should a programmer decompose a real system?

The central rule is:

```text
model immutable information as values
model persistent identity as entities
model reactions as events/handlers
model reusable stateful reactions as behaviors
model pure transformation as functions
model host authority as capabilities
model absence/failure explicitly as Option/Result
```

---

## 1. The TEV Script unit of design

In classical OOP, programmers often begin with classes.

In TEV Script, begin with **state transitions and authority boundaries**.

A useful decomposition is:

```text
Domain values
    records + enums + Option/Result

Pure domain rules
    fn

Persistent reactive identity
    entity

Reusable state/reaction fragments
    behavior

Messages within one entity event machine
    events + emit

External observations/effects
    capabilities

Visibility and subsystem boundaries
    modules + export/import
```

This decomposition makes mutation and external authority explicit rather than hiding them behind arbitrary method calls.

---

## 2. What replaces a class?

There is no single replacement because a class normally mixes several responsibilities.

Suppose an OO class contains:

```text
identity
mutable fields
immutable data shape
methods
shared utility logic
interface calls
inheritance
```

TEV Script decomposes those responsibilities:

```text
identity            -> entity
mutable fields      -> state
immutable shape     -> record
discrete kind       -> enum
pure methods        -> fn
reactive methods    -> on event
external interface  -> capability
reuse               -> behavior + use
namespace/privacy   -> module + export
```

This separation is intentional. A single syntactic construct does not need to own every programming concern.

---

# Part I — Data structures

## 3. Primitive scalar values

Use:

```text
Bool
Int
Rat
Text
```

Use `Int` for exact counting/discrete quantities.

Use `Rat` for exact fractional quantities where floating-point drift would be semantically undesirable.

Examples:

```tevs
state population: Int = 100;
state energy: Rat = 1;
state label: Text = "zone-a";
state enabled: Bool = true;
```

---

## 4. Vector values

Use `Vec2` / `Vec3` when the domain really is a fixed-dimensional vector.

```tevs
state position: Vec2 = vec2(0, 0);
state velocity: Vec2 = vec2(0, 0);
```

Do not use `Vec2` merely as a convenient pair when the components have different meanings.

Prefer:

```tevs
record TemperatureRange {
    minimum: Rat;
    maximum: Rat;
}
```

instead of encoding a temperature range as an unexplained vector.

---

## 5. Record = immutable product type

A record is TEV Script's primary structured data value.

```tevs
record Resource {
    energy: Rat;
    mass: Rat;
    quality: Rat;
}
```

Think of a record as a mathematically named product:

```text
Resource = Rat × Rat × Rat
```

but with nominal identity.

Use records for:

- value objects;
- configuration values;
- event payloads;
- capability payloads;
- measurements;
- coordinates with domain meaning;
- aggregate results;
- snapshots that do not themselves own mutable identity.

Do not create an entity merely because a value has several fields.

---

## 6. Enum = closed finite choice

Use enums for finite domain alternatives:

```tevs
enum Activity {
    Idle;
    Feeding;
    Moving;
    Resting;
}
```

An enum is preferable to magic integers or strings because the compiler knows the complete domain.

That gives exhaustive `match`:

```tevs
match activity {
    Activity::Idle => { ... }
    Activity::Feeding => { ... }
    Activity::Moving => { ... }
    Activity::Resting => { ... }
}
```

This is the TEV-native replacement for many uses of polymorphic state classes.

---

## 7. Option<T> = explicit optionality

Use `Option<T>` instead of sentinel values.

Avoid:

```text
-1 means no target
"" means no owner
0 means measurement missing
```

Prefer:

```tevs
state target: Option<Int> = None;
```

Then force the absence case to be handled:

```tevs
match target {
    Some(id) => { ... }
    None => { ... }
}
```

This removes an entire family of implicit-state bugs.

---

## 8. Result<T,E> = explicit success/failure value

Use `Result<T,E>` when a domain operation can validly produce either success or an expected failure value.

```tevs
record Sample {
    value: Rat;
}

enum SensorError {
    Offline;
    OutOfRange;
}

state reading: Result<Sample, SensorError> = Err(SensorError::Offline);
```

In V1 user enums are payload-free, but they compose naturally with `Result`.

Do not model expected domain failure using host exceptions.

---

## 9. Entity state = bounded mutable store

Entity/behavior state is not a generic data structure. It is the program's explicitly mutable state surface.

```tevs
entity Reactor {
    state energy: Rat = 1;
    state active: Bool = false;
}
```

Use state only for information that must persist between event invocations.

If a value can be recomputed locally inside one handler, prefer `let`.

Bad decomposition:

```text
every intermediate computation becomes state
```

Better:

```tevs
on update {
    let delta = time.delta();
    let next = energy - delta;
    energy = max(next, 0);
}
```

---

## 10. What V1 intentionally does not expose as general data structures

V1 does not expose user-level general:

```text
List<T>
Array<T>
Map<K,V>
Set<T>
linked lists
trees
graphs
mutable object references
```

This is a deliberate bounded-language choice, not an implementation omission.

When the domain is a known finite shape, prefer records/enums.

When the problem fundamentally requires variable-size collections, that is a signal that either:

- the collection belongs in a host capability with a bounded typed query surface; or
- a future bounded collection feature should be specified explicitly.

Do not smuggle arbitrary collections through `Text` or host objects.

---

# Part II — Core architectural patterns

## 11. Pattern: Functional Core / Reactive Shell

### Intent

Keep domain transformation pure; confine state mutation and host effects to handlers.

### Shape

```tevs
fn nextEnergy(current: Rat, cost: Rat) -> Rat = max(current - cost, 0);

entity Organism {
    state energy: Rat = 1;

    on update(cost: Rat) {
        energy = nextEnergy(energy, cost);
    }
}
```

### Why it matters

Pure functions are easier to:

- type-check;
- constant-evaluate;
- inline deterministically;
- test;
- reason about;
- reproduce across runtimes.

Use handlers for orchestration, not for hiding every domain rule in mutation-heavy code.

---

## 12. Pattern: Capability Port

### Intent

Express external authority as a typed port instead of importing host APIs directly.

```tevs
capability environment.sampleTemperature(Vec2) -> Rat observation;
capability actuator.setValve(Rat) -> Unit effect;
```

Handler:

```tevs
on update {
    let temperature = environment.sampleTemperature(position);
    if temperature > threshold {
        call actuator.setValve(0);
    }
}
```

### Equivalent architectural idea

This corresponds to ports/adapters / hexagonal architecture, but the port is part of the language semantic contract.

The host adapter is replaceable.

### Benefit

The program cannot accidentally access:

- filesystem;
- clock;
- network;
- Unity scene;
- OS process;
- arbitrary C# object;

unless that authority is represented explicitly.

---

## 13. Pattern: Observation / Effect Separation

Capabilities distinguish:

```text
observation
 effect
```

Use observations when data enters the program:

```tevs
capability sensor.read() -> Rat observation;
```

Use effects when the program requests external mutation:

```tevs
capability motor.setPower(Rat) -> Unit effect;
```

This resembles Command/Query Separation, but the distinction is statically visible in the capability contract.

It also improves auditing: an entity's effect surface can be inspected without reading every implementation detail.

---

## 14. Pattern: Entity Aggregate

### Intent

Use one entity as the persistent identity boundary for state that must change atomically under one local event machine.

```tevs
entity StorageNode {
    state energy: Rat = 0;
    state capacity: Rat = 1;

    on deposit(amount: Rat) {
        energy = min(energy + amount, capacity);
    }
}
```

This is analogous to an aggregate root more than to an arbitrary object.

The entity owns:

- its state;
- its handlers;
- its local event chain;
- its capability requirements.

Avoid splitting one tightly coupled invariant across several entities unless a real event/coordination boundary exists.

---

## 15. Pattern: Behavior Composition

### Intent

Reuse bounded state + handler fragments without inheritance.

```tevs
behavior HasEnergy {
    state energy: Rat = 1;
}

behavior Metabolism {
    use HasEnergy;

    on update {
        energy = max(energy - 0.01, 0);
    }
}

entity Animal {
    use Metabolism;
}
```

### Why not inheritance?

Inheritance mixes:

- representation reuse;
- subtype relationships;
- virtual dispatch;
- override precedence;
- runtime identity.

Behavior composition only means deterministic compile-time composition.

Its conflicts are rejected rather than resolved by hidden precedence rules.

---

## 16. Pattern: Explicit State Machine

Use enum + state + exhaustive match for bounded state machines.

```tevs
enum Mode {
    Idle;
    Seeking;
    Consuming;
}

entity Agent {
    state mode: Mode = Mode::Idle;

    on update {
        match mode {
            Mode::Idle => {
                mode = Mode::Seeking;
            }
            Mode::Seeking => {
                mode = Mode::Consuming;
            }
            Mode::Consuming => {
                mode = Mode::Idle;
            }
        }
    }
}
```

This replaces many State-pattern class hierarchies with a closed, exhaustively checked representation.

---

## 17. Pattern: Strategy by Data + Match

Classical Strategy pattern often uses runtime polymorphism.

For a closed strategy family, TEV Script uses enum + match:

```tevs
enum MovementPolicy {
    Conservative;
    Balanced;
    Aggressive;
}

fn speedFor(policy: MovementPolicy) -> Rat =
    # V1 functions are expression-bodied; when policy-dependent computation
    # requires statement match, perform the match in the handler.
    1;
```

Handler form:

```tevs
match policy {
    MovementPolicy::Conservative => { speed = 0.5; }
    MovementPolicy::Balanced => { speed = 1; }
    MovementPolicy::Aggressive => { speed = 2; }
}
```

Use this when the strategy domain is closed and known.

Do not emulate open runtime subclass polymorphism with string ids.

---

## 18. Pattern: Value Object

Records are the natural Value Object pattern.

```tevs
record EnergyTransfer {
    amount: Rat;
    efficiency: Rat;
}
```

Benefits:

- immutable;
- typed;
- nominal;
- canonically serializable;
- structurally comparable;
- safe across runtime boundaries.

Prefer one meaningful record over several positionally related primitive parameters when the values form one domain concept.

---

## 19. Pattern: Explicit Maybe

Use `Option<T>` as the Maybe pattern.

```tevs
state foodTarget: Option<Vec2> = None;
```

Every consumer must acknowledge both presence and absence.

This is much stronger than relying on `null`, zero vectors or magic ids.

---

## 20. Pattern: Explicit Outcome

Use `Result<T,E>` instead of exception-driven expected control flow.

```tevs
enum HarvestError {
    Empty;
    Blocked;
}

state harvest: Result<Rat, HarvestError> = Err(HarvestError::Empty);
```

A caller must handle both outcomes.

---

## 21. Pattern: Event Reducer

For a state variable whose mutations should be centralized, route changes through one event.

```tevs
entity Wallet {
    state balance: Rat = 0;

    on credit(amount: Rat) {
        balance = balance + amount;
    }

    on debit(amount: Rat) {
        balance = max(balance - amount, 0);
    }
}
```

The set of handlers becomes the explicit transition algebra for the entity.

This is similar to reducer/event-sourced thinking, but TEV Script does not imply an external persistent event log unless the host provides one.

---

## 22. Pattern: Local Event Pipeline

Use `emit` to sequence bounded entity-local phases when the intermediate event is semantically meaningful.

```tevs
entity Processor {
    state value: Int = 0;

    on input(raw: Int) {
        emit validated(raw);
    }

    on validated(raw: Int) {
        value = raw;
        emit changed(value);
    }
}
```

The event chain is bounded by the runtime contract.

Do not use event chains merely to emulate unbounded loops or recursion.

---

## 23. Pattern: Module Facade

Use module privacy/export to expose a small semantic API.

```tevs
module ecosystem.energy version "1.0.0";

record InternalState {
    value: Rat;
}

export record Energy {
    value: Rat;
}

export fn normalize(value: Rat) -> Rat = min(max(value, 0), 1);
```

Importers depend only on the exported surface.

This is a TEV-native Facade/module-boundary pattern.

---

## 24. Pattern: Canonical Boundary Object

When a value crosses a capability/event/checkpoint boundary, prefer a nominal record over several loosely correlated arguments.

Instead of:

```tevs
capability sensor.submit(Rat, Rat, Text) -> Unit effect;
```

prefer:

```tevs
record Reading {
    value: Rat;
    confidence: Rat;
    source: Text;
}

capability sensor.submit(Reading) -> Unit effect;
```

This gives the boundary a stable nominal schema and clearer canonical identity.

---

## 25. Pattern: Bounded Batch

Use static `for` only when the iteration count is part of the program structure.

```tevs
for i in 0 .. 4 {
    emit pulse(i);
}
```

This represents a finite compile-time batch.

It is not the correct tool for data-dependent traversal.

---

## 26. Pattern: Deterministic Adapter

Host adapters should convert native host data into canonical TEV values at the boundary.

Conceptual host flow:

```text
Unity/C#/browser/native value
    ↓ adapter validation
TEV typed value
    ↓
capability invocation
    ↓
TEV runtime
```

Never place native object references directly into TEV state.

If a host object must be represented, represent its relevant portable data as a record or stable scalar id and keep the actual object outside the language runtime.

---

# Part III — Patterns that should NOT be ported literally from OOP

## 27. Singleton

Usually unnecessary.

If the system has one persistent logical entity, give it one explicit entity identity.

Do not create hidden global mutable state in the host and call it a TEV pattern.

---

## 28. Service Locator

Avoid it.

A Service Locator hides authority lookup.

TEV Script uses explicit capability requirements instead.

Bad conceptual architecture:

```text
handler -> global service locator -> arbitrary host service
```

Preferred:

```text
handler -> declared typed capability -> provided host adapter
```

---

## 29. Dependency Injection container

A general runtime DI container is usually unnecessary inside TEV Script.

Compile-time dependencies are modules/behaviors.

Runtime host dependencies are capabilities.

The host may use DI to construct capability providers, but that is a host implementation concern rather than language semantics.

---

## 30. Inheritance hierarchy

Do not simulate inheritance through naming conventions or manual field copying.

Use:

- behavior composition for reusable reactions/state;
- records for reusable immutable data shapes;
- enums/match for closed behavioral alternatives;
- capabilities for external abstractions.

If the design fundamentally needs open runtime subtype polymorphism, that capability is outside V1 and should not be emulated unsafely.

---

## 31. Observer pattern

Do not automatically translate every OO Observer into TEV events.

Use local events when:

- the event belongs to the entity's bounded event machine;
- ordering is deterministic;
- the chain is finite.

Use host capabilities when communication crosses the entity/runtime boundary.

Cross-entity/distributed pub-sub is not silently implied by `emit`.

---

## 32. Factory pattern

For immutable values, constructors already provide a typed factory:

```tevs
Resource(amount = 1, kind = ResourceKind::Mineral)
```

For derived construction logic, use a pure function:

```tevs
fn normalizedAmount(value: Rat) -> Rat = min(max(value, 0), 1);
```

V1 does not dynamically allocate arbitrary new entity identities from inside the language.

---

## 33. Repository pattern

Persistent external storage is host authority.

Expose a typed capability:

```tevs
capability storage.read(Text) -> Result<Resource, StorageError> observation;
capability storage.write(Text, Resource) -> Unit effect;
```

Do not hide a database connection inside language state.

---

# Part IV — System decomposition

## 34. How to identify entities

An entity is justified when a thing has:

- persistent identity;
- mutable state across events;
- a coherent transition boundary.

Ask:

```text
Would I still need to distinguish this thing from another identical-valued thing?
```

If yes, entity identity may be appropriate.

If no, a record is often better.

Example:

```text
Animal #17               entity
AnimalStats              record
Position                  record or Vec2
Species                   enum
CurrentTarget             Option<T>
SensorReadOutcome         Result<T,E>
```

---

## 35. How to identify state

State should satisfy:

```text
needed after the current handler finishes
```

If not, use a local.

This minimizes the mutable surface and makes invariants easier to audit.

---

## 36. How to identify a behavior

Create a behavior when a reusable concept carries one or both of:

- persistent state;
- event-handler fragments.

Do not create a behavior merely to hold one pure helper function; use a module-level `fn` for that.

---

## 37. How to identify a capability

Create a capability when the language needs information or authority that is not internally derivable.

Typical capability domains:

```text
input
clock
audio
animation
physics/motion
storage
network boundary
sensor
device actuator
Unity scene adapter
```

Capabilities should be narrow and domain-typed.

Bad:

```text
host.invoke(Text, Text) -> Text
```

Better:

```tevs
capability climate.sample(Vec2) -> Temperature observation;
capability climate.setVent(Rat) -> Unit effect;
```

A generic string RPC recreates reflection/dynamic dispatch through the back door.

---

## 38. How to identify a module

Use a module as a semantic ownership and visibility boundary.

Good module dimensions include:

```text
ecosystem.energy
ecosystem.resources
ecosystem.movement
game.combat
simulation.climate
```

Avoid both extremes:

```text
one giant module for the whole program
one module per trivial declaration
```

A module should own a coherent vocabulary/rule set.

---

# Part V — Larger example architecture

## 39. Resource ecosystem

Suppose a world conserves normalized energy and entities transform it.

A reasonable TEV decomposition could be:

```text
ecosystem.model
    Energy
    Resource
    ResourceKind
    Season

ecosystem.rules
    normalizeEnergy
    transferLoss

ecosystem.environment
    observation capabilities
    external effect capabilities

ecosystem.behaviors
    Metabolism
    Movement
    ResourceConsumer

root script
    World entity
    Creature entity templates at host level
```

Inside one entity:

```tevs
behavior Metabolism {
    state energy: Rat = 1;

    on update {
        let dt = time.delta();
        energy = max(energy - dt * 0.01, 0);
    }
}
```

External world sampling remains a capability:

```tevs
capability environment.resourceAt(Vec2) -> Option<Resource> observation;
```

The TEV program can reason over the returned value without owning the host's spatial index.

This keeps general collection/search structures in the host while preserving typed deterministic results inside the language.

---

# Part VI — Refactoring patterns

## 40. Extract Pure Function

Before:

```tevs
on update {
    energy = max(min(energy - cost, 1), 0);
}
```

After:

```tevs
fn boundedEnergy(current: Rat, cost: Rat) -> Rat =
    max(min(current - cost, 1), 0);

on update {
    energy = boundedEnergy(energy, cost);
}
```

Use when logic is domain computation without state/capability dependence.

---

## 41. Extract Record

Before:

```tevs
capability transfer.send(Rat, Rat, Text) -> Unit effect;
```

After:

```tevs
record Transfer {
    amount: Rat;
    efficiency: Rat;
    destination: Text;
}

capability transfer.send(Transfer) -> Unit effect;
```

Use when multiple values travel together as one domain concept.

---

## 42. Replace Sentinel with Option

Before conceptual state:

```text
target = -1
```

After:

```tevs
state target: Option<Int> = None;
```

---

## 43. Replace Error Flag with Result

Before conceptual state:

```text
value
has_error
error_code
```

After:

```tevs
state reading: Result<Reading, SensorError> = Err(SensorError::Offline);
```

This makes invalid mixed states unrepresentable.

---

## 44. Replace Inheritance with Behavior Composition

Instead of:

```text
LivingEntity
  -> MovingEntity
      -> Animal
```

model orthogonal composition:

```text
HasEnergy
Movement
Metabolism
Sensing
```

and compose only what one entity needs.

This avoids inheritance-order semantics and reduces coupling between unrelated concerns.

---

## 45. Replace Hidden Host Call with Capability

If a runtime implementation reaches directly into Unity/C#/browser state, extract that interaction into a capability contract.

The TEV program should remain runnable against a deterministic fake provider during conformance testing.

---

# Part VII — Design quality rules

## 46. Keep the state surface small

Every state variable increases the mutable invariant surface.

Prefer:

```text
state = long-lived truth
let   = transient calculation
```

---

## 47. Prefer nominal domain types over primitive bundles

If three primitives always travel together, that is often one record.

If an integer has a finite semantic domain, that is often one enum.

If a value can be absent, that is often `Option`.

If a computation has expected failure, that is often `Result`.

---

## 48. Keep capabilities narrow

A capability should describe one auditable authority.

Avoid generic escape hatches.

Narrow capabilities improve:

- static effect summaries;
- host policy;
- update ceilings;
- testing;
- portability;
- security review.

---

## 49. Prefer behavior composition over duplication

If the same state/handler fragment appears in several entities, evaluate whether it is one behavior.

But do not create deeply layered behavior DAGs merely to remove two identical lines. Composition has semantic cost and should represent a real reusable concern.

---

## 50. Do not fight boundedness

If a design requires:

```text
unbounded recursion
arbitrary graph traversal
unknown-size user collection mutation
dynamic reflection
dynamic code loading
```

then forcing it into V1 through encoding tricks degrades the model.

Either move that computation behind a narrow typed host capability or specify a future bounded language feature rigorously.

---

# Part VIII — Mapping common architecture terminology

## 51. SOLID in TEV Script

### Single Responsibility

Use modules/behaviors/entities with coherent semantic responsibility.

### Open/Closed

Prefer adding independent behaviors/modules/capabilities rather than rewriting unrelated code, but remember that V1 has closed nominal domains rather than open runtime subtype extension.

### Liskov Substitution

Traditional subtype substitution largely does not apply because V1 has no inheritance/subtyping hierarchy beyond exact numeric widening.

Do not pretend record shape equality is subtype compatibility.

### Interface Segregation

Narrow capability contracts are the closest TEV-native analogue.

### Dependency Inversion

Domain logic depends on capability contracts, not concrete host APIs.

---

## 52. DRY

Use:

```text
fn        for pure repeated computation
record    for repeated data shape
behavior  for repeated state + reaction
module    for semantic ownership/reuse
```

Do not force unrelated code through one abstraction merely because two lines look similar.

---

## 53. KISS

Prefer explicit finite code over generic dynamic mechanisms.

In TEV Script, explicitness has additional value because it improves static verification and cross-runtime determinism.

---

## 54. YAGNI

Do not add a host capability, state variable, behavior layer or new language construct until the semantic requirement exists.

Every new authority or dynamic feature enlarges the conformance surface.

---

# Part IX — Choosing IR profile deliberately

## 55. Design for IR V2 when appropriate

IR V2 remains excellent for programs whose runtime values stay primitive/vector based.

A V1 codebase can still use:

```text
modules
pure functions
behaviors
bounded for
```

and have those features disappear before runtime.

This can be desirable for very small embedded targets.

---

## 56. Use IR V3 when the domain needs algebraic values

Do not distort a domain merely to remain in IR V2.

If the natural model needs:

```text
Resource record
Season enum
Option<Target>
Result<Sample, Error>
```

use those types and target IR V3.

The runtime was designed precisely to preserve them without host-object semantics.

---

# Part X — Review checklist

## 57. Before considering a TEV subsystem well designed

Check that:

```text
persistent mutable data is state, not hidden host mutation
transient values are locals
pure logic is extracted where useful
optional values use Option
expected failures use Result
domain bundles use records
finite modes use enums
reusable stateful reactions use behaviors
host authority uses capabilities
capability ABI is narrow and typed
imports are explicit
module exports are intentional
loops are statically bounded
no recursion/dynamic reflection has been smuggled in
semantic order is explicit
cross-host values are canonical TEV values
```

The best TEV Script architecture is usually the one where a reviewer can answer three questions directly from the program:

```text
What can change?
Why can it change?
What external authority can cause or observe effects?
```

If those answers require inspecting host implementation details, the boundary is probably too implicit.
