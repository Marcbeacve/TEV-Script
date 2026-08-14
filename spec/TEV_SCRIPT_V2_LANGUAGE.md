# TEV Script V2 Language Specification

## 1. Status and authority

This document is the normative source-language and static-semantics authority for
TEV Script `2.0.0`. V2 is an implementation candidate. It is not stable, published,
or merge-authorized merely because an implementation or test suite exists.

The following documents jointly close V2:

- this source-language specification;
- `TEV_SCRIPT_PROGRAM_IR_V4.md` for executable portable artifacts;
- `TEV_SCRIPT_V2_FILESYSTEM_CAPABILITIES.md` for physical file authority;
- `TEV_SCRIPT_V2_FEATURE_MATRIX.json` for governed implementation and gates;
- the JSON Schemas indexed by that matrix.

When implementation behavior conflicts with these authorities, the implementation
is nonconforming. Python is a reference implementation, not language authority.

The keywords MUST, MUST NOT, SHOULD, and MAY have their usual normative meanings.

## 2. Processing model

A conforming source processor performs these phases in order:

1. admit at most 1,000,000 UTF-8 source bytes;
2. tokenize with the lexical rules below;
3. parse exactly one script or one pure module;
4. resolve the finite, explicit module set by content identity;
5. form closed nominal and constructed types;
6. resolve names, protocols, associated types, methods, and generic constraints;
7. prove purity, recursion contracts, collection bounds, task bounds, and effect
   boundaries;
8. compute the canonical source-semantic identity;
9. lower one entry profile to a self-contained Program IR V4 artifact.

No runtime may parse or compile `.tevs` source. Runtime inputs are validated Program
IR V4 only.

## 3. Lexical grammar

Source is Unicode decoded from strict UTF-8. A byte-order mark is not part of the
language. Identifiers and keywords use ASCII spelling. Whitespace separates tokens
and is otherwise nonsemantic. Line comments begin with `//` and end before the line
terminator. Block comments and nested comments are not admitted.

```ebnf
letter          = "A"…"Z" | "a"…"z" | "_" ;
digit           = "0"…"9" ;
identifier      = letter , { letter | digit } ;
qualified-name  = identifier , { "." , identifier } ;
integer         = "0" | nonzero-digit , { digit } ;
rational        = integer , "." , digit , { digit } ;
string          = '"' , { string-character | escape } , '"' ;
escape          = "\\\"" | "\\\\" | "\\n" | "\\r" | "\\t" ;
```

Numeric tokens have no sign; negation is an expression operator. Leading zeroes are
not canonical except for zero itself. Rational arithmetic remains exact. Host-native
floating-point values are not TEV values.

Structural words are recognized contextually by the productions below. They are not
a separate token class; an identifier position is rejected only where the governing
production or static rule reserves that spelling.

```text
script module import as export version
generic record protocol type impl for in fold while when max_iterations
fn recursive decreases max_depth max_steps entry
state capability observation command action
let if then else match self assert not
observe all request set map
spawn task scope return await within_steps do select first_within
true false Some None Ok Err
```

## 4. Top-level grammar

```ebnf
pure-script = "script" , identifier , "version" , '"2.0.0"' , ";" ,
              { import-declaration } ,
              { pure-declaration } , pure-entry-declaration ;

effect-script = "script" , identifier , "version" , '"2.0.0"' , ";" ,
                { effect-declaration } , effect-entry-declaration ;

module = "module" , qualified-name , "version" , '"2.0.0"' , ";" ,
         { import-declaration } , { module-declaration } ;

pure-declaration = generic-record-declaration
                 | protocol-declaration | implementation-declaration
                 | generic-implementation-declaration
                 | function-declaration | generic-function-declaration
                 | recursive-function-declaration ;

effect-declaration = state-declaration | capability-declaration
                   | command-declaration | action-declaration ;

module-declaration = [ "export" ] ,
                     ( function-declaration | generic-function-declaration ) ;

import-declaration = "import" , qualified-name , "as" , identifier , ";" ;
pure-entry-declaration = "entry" , identifier , ":" , type , "=" ,
                         expression , ";" ;
effect-entry-declaration = "entry" , identifier , "=" , identifier ,
                           "(" , [ arguments ] , ")" , ";" ;
```

A source unit contains at most 4,096 declarations. A script has exactly one entry
and is admitted by exactly one of the pure or effect profiles; declarations from the
two profiles cannot be mixed.
A module has no executable entry, state, observation lane, command, or physical
effect. Module source order and filesystem path are nonsemantic; declared module ID
and canonical source bytes establish identity.

The current pure-module profile admits only plain and generic pure functions and
requires at least one explicit `export`. `private` is therefore descriptive of every
non-exported module function rather than a source marker in this profile.

Remote module acquisition is a build-time operation only. An HTTPS locator is never
an import identity. A remote manifest binds module IDs to exact SHA-256 content and,
for the signed profile, to an externally pinned Ed25519 public-key identity. Runtime
network resolution is forbidden.

## 5. Types and values

```ebnf
type = "Bool" | "Int" | "Rat" | "Text" | "Vec2" | "Vec3"
     | identifier
     | "Option" , "<" , type , ">"
     | "Result" , "<" , type , "," , type , ">"
     | "List" , "<" , type , "," , positive-integer , ">"
     | "Array" , "<" , type , "," , positive-integer , ">"
     | "Set" , "<" , type , "," , positive-integer , ">"
     | "Map" , "<" , type , "," , type , "," , positive-integer , ">"
     | associated-type ;

associated-type = identifier , "::" , identifier ;

generic-record-declaration = "generic" , "record" , identifier ,
                             type-parameters , "{" ,
                             field , { field } , "}" ;
field              = identifier , ":" , type , ";" ;
type-parameters    = "<" , identifier , { "," , identifier } , ">" ;
```

`Bool`, `Int`, `Rat`, `Text`, `Vec2`, and `Vec3` are portable primitives. `Unit` is
capability-return-only and is not source-storable. Generic records are nominal.
`Option` and `Result` are the closed algebraic payload families. Collection capacity
or array length is part of the type identity and is an integer in `1..4096`.

Record fields and enum variants have unique local names. Canonical descriptors sort
them lexically. Type tables are closed, sorted, contain all referenced types, contain
the seven portable base descriptors, and contain no illegal value-recursive cycle.
Values nest at most 128 levels.

Lists and arrays preserve sequence order. Sets order by canonical value bytes. Maps
order by canonical key bytes. Duplicate canonical set values and duplicate canonical
map keys are invalid. No operation can grow a collection beyond its type capacity.

## 6. Pure declarations and expressions

```ebnf
function-declaration = "fn" , identifier ,
                       "(" , [ parameters ] , ")" , "->" , type ,
                       "=" , expression , ";" ;

generic-function-declaration = "generic" , "fn" , identifier ,
                       constrained-type-parameters ,
                       "(" , [ parameters ] , ")" , "->" , type ,
                       "=" , expression , ";" ;

recursive-function-declaration = "recursive" , "fn" , identifier ,
                       "(" , parameters , ")" , "->" , type ,
                       "decreases" , identifier ,
                       "max_depth" , positive-integer ,
                       [ "max_steps" , positive-integer ] ,
                       "=" , expression , ";" ;

parameters      = parameter , { "," , parameter } ;
parameter       = identifier , ":" , type ;
constrained-type-parameters = "<" , constrained-type-parameter ,
                              { "," , constrained-type-parameter } , ">" ;
constrained-type-parameter = identifier , [ ":" , protocol-refinement ,
                                            { "+" , protocol-refinement } ] ;
protocol-refinement = qualified-name , [ "<" , associated-equality ,
                                        { "," , associated-equality } , ">" ] ;
associated-equality = identifier , "=" , type ;

expression = literal | identifier | field-expression | call-expression
           | constructor-expression | collection-expression
           | unary-expression | binary-expression
           | "if" , expression , "then" , expression , "else" , expression
           | match-expression | for-expression | while-expression
           | task-expression | step-limit-expression | select-expression ;

match-expression = "match" , expression , "{" , match-arm ,
                   { match-arm } , "}" ;
match-arm = identifier , [ "(" , identifier , ")" ] , "=>" , expression , ";" ;

for-expression = "for" , identifier , [ "," , identifier ] , "in" , expression ,
                 "fold" , identifier , ":" , type , "=" , expression ,
                 "do" , expression ;
while-expression = "while" , identifier , ":" , type , "=" , expression ,
                   "when" , expression ,
                   "max_iterations" , positive-integer , "do" , expression ;

task-expression = task-scope-expression | await-all-expression | await-expression ;
task-scope-expression = "task" , "scope" , "{" , spawn-declaration ,
                        { spawn-declaration } , "return" , expression , ";" , "}" ;
spawn-declaration = "spawn" , identifier , ":" , type , "=" , expression , ";" ;
await-all-expression = "await" , "all" , "(" , task-binding ,
                       { "," , task-binding } , [ "," ] , ")" , "=>" , expression ;
task-binding = identifier , ":" , type , "=" , expression ;
await-expression = "await" , identifier ;
step-limit-expression = "within_steps" , positive-integer , "do" , expression ;
select-expression = "select" , "first_within" , "{" ,
                    step-limit-expression , ";" ,
                    { step-limit-expression , ";" } , "}" ;
```

Bindings are immutable and lexically scoped. Every name resolves uniquely. Function
arguments are evaluated left to right. Pure calls have no observation or effect
authority. Generic records and functions are introduced by the explicit `generic`
keyword and are monomorphized for a finite set of
concrete type arguments; all constraints are proven before specialization. The
specialization identity binds the template and concrete type identities.

Expression nesting is at most 128 and pure inlining depth is at most 64. Every pure
expression receives a conservative static step upper bound. Evaluation fails before
executing a step beyond its declared maximum.

### 6.1 Operators

`Int` and `Rat` arithmetic is exact. Division by zero fails closed. Boolean operators
short-circuit deterministically. Equality is defined only for the closed portable
value model. Ordering used by collections is canonical-byte ordering, not locale or
host ordering. Text operations do not depend on locale.

### 6.2 Match

A match over `Option` or `Result` must be exhaustive and have no duplicate or
unreachable arm. All arms produce the same static result type. Pattern bindings are
immutable and arm-local.

### 6.3 Bounded iteration

`for … fold` iterates a statically admitted List, Array, Set, or Map and updates an
immutable accumulator value. One binding receives each sequence/set element; Map
iteration uses two bindings for key and value. The collection type proves the maximum
iteration count.

`while … max_iterations N do …` is a bounded accumulator fold, not an unbounded
loop. `N` is in `1..4096`; the condition and body can read the current accumulator,
and the result is the accumulator after the first false condition or after exactly
`N` true iterations. A missing finite bound is not syntax.

### 6.4 Contracted recursion

Recursion exists only in a `recursive fn`. Exactly one direct `self` call is admitted
on each recursive path. The declared measure names an `Int` parameter and the self
call argument must be statically proven to decrease. Self calls in loop bodies or
conditions are forbidden. `max_depth` and `maximum_steps` are positive finite bounds.
Mutual recursion and recursion through ordinary function calls are forbidden.

## 7. Protocols, methods, and associated types

```ebnf
protocol-declaration = "protocol" , identifier , "{" ,
                       { associated-declaration } ,
                       method-signature , { associated-declaration | method-signature } ,
                       "}" ;
associated-declaration = "type" , identifier , ";" ;
method-signature = "fn" , identifier , "(" , "self" ,
                   { "," , parameter } , ")" ,
                   "->" , type , ";" ;

implementation-declaration = "impl" , type , [ ":" , identifier ] , "{" ,
                             { associated-binding | method-declaration } , "}" ;
generic-implementation-declaration = "generic" , "impl" ,
                             constrained-type-parameters , type ,
                             ":" , identifier , "{" ,
                             { associated-binding | method-declaration } , "}" ;
associated-binding = "type" , identifier , "=" , type , ";" ;
method-declaration = "fn" , identifier , "(" , "self" ,
                     { "," , parameter } , ")" , "->" , type ,
                     "=" , expression , ";" ;
```

Protocol identity is nominal. An implementation group must provide exactly the
required methods and associated types with matching signatures. For any concrete
receiver/protocol pair, coherence selects exactly one implementation; overlap or
ambiguity fails. Associated projections normalize uniquely before Program IR
lowering. Generic prerequisite constraints and associated-type equalities are part
of witness and specialization hashes.

## 8. Tasks and deterministic concurrency

Tasks express an acyclic pure dependency graph, not threads. A task can observe only
its explicit immutable inputs. Spawn order is nonsemantic. Join results are returned
in declared task order. Cancellation follows `cooperative_boundary_v1`. Priority
selection chooses the lowest declared priority and then lexical declaration order;
speculative losers cannot commit observations, state, or physical effects.

`await all` creates independent children and joins them in declared binding order.
`task scope` admits an explicit acyclic dependency graph: `await name` may reference
only a spawned binding and every binding required by `return` is evaluated under the
closed graph. `within_steps N do value` admits `N` in `1..1,000,000` and fails before
crossing that local budget. `select first_within` evaluates candidates under their
declared step bounds and chooses the earliest lexical candidate that completes within
its bound; speculative failure or cancellation cannot leak a commit.

At most 4,096 pure tasks and the statically declared pure-evaluation step budget are
admitted. Worker count and scheduling are operational only and cannot change
canonical values, hashes, or receipts.

## 9. State, observations, and effects

```ebnf
state-declaration      = "state" , identifier , ":" , type , "=" , expression , ";" ;
capability-declaration = "capability" , "observation" , qualified-name ,
                         "(" , [ type-list ] , ")" , "->" , type , ";" ;
command-declaration    = "command" , qualified-name ,
                         "(" , [ type-list ] , ")" , ";" ;
action-declaration     = "action" , identifier , "(" , [ parameters ] , ")" ,
                         "{" , { action-step } , "}" ;
action-step            = observe-step | observe-all-step | local-step | request-step
                       | set-step | assert-step ;
observe-step           = "observe" , identifier , "=" , call-expression , ";" ;
observe-all-step       = "observe" , "all" , "{" , observe-binding ,
                         { observe-binding } , "}" ;
observe-binding        = identifier , "=" , call-expression , ";" ;
local-step             = "let" , identifier , ":" , type , "=" , expression , ";" ;
request-step           = "request" , call-expression , ";" ;
set-step               = "set" , identifier , "=" , expression , ";" ;
assert-step            = "assert" , expression , ";" ;
```

State is the only persistent mutable language surface. Each state slot has a closed
storable type and canonical initial value. An action observes a provided finite
scenario transcript, evaluates deterministically, and proposes one final state.
Missing calls, extra calls, signature mismatch, or exhausted observation budget fail
closed.

Observation capabilities return recorded host facts but cannot commit effects.
Command declarations produce inert, content-addressed intents. Planning never grants
authority. A physical provider may commit only after an explicit grant binds the
exact batch hash, provider descriptor hash, authority scope hash, and allowed
contract hashes. Failed commit never finalizes proposed state.

`file.read(Text)->Text` and `file.replace(Text,Text)` use the additional mandatory
rules in `TEV_SCRIPT_V2_FILESYSTEM_CAPABILITIES.md`.

## 10. Source semantic identity

The semantic form contains only resolved, typed, bounded declarations and entry
identity. Comments, permitted whitespace, source path, declaration enumeration path,
and worker count are erased. Order is retained only where this specification makes
order semantic; all other maps and sets sort by their governed key or canonical
bytes.

Canonical JSON is UTF-8, has sorted object keys, uses no insignificant whitespace,
and escapes non-ASCII characters. SHA-256 lowercase hexadecimal hashes those exact
bytes. Self-hashing objects exclude their own hash field from the hashed body.

## 11. Diagnostics and failure

A conforming processor fails closed on malformed UTF-8, lexical or parse error,
unknown or duplicate name, incoherent protocol implementation, unresolved associated
type, type mismatch, unproven bound, budget exhaustion, malformed artifact, hash
mismatch, missing capability, undeclared physical authority, acquisition drift, or
unsupported security primitive. It does not repair, coerce, truncate, infer ambient
authority, or execute a partially admitted program.

## 12. Explicit exclusions

V2 excludes unbounded loops, uncontracted or mutual recursion, classes and
inheritance, reflection, exceptions as ordinary control flow, dynamic loading or code
generation, runtime source compilation, host-native object references, implicit
threads, nondeterministic scheduling semantics, ambient filesystem/network/process
access, package-registry resolution, semver-range import resolution, wildcard
imports, and implicit re-export.
