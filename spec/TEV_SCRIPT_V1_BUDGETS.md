# TEV Script V1 normative resource budgets

Status: **normative V1 candidate**. These budgets make parsing, linking, static analysis, expansion and lowering finitely bounded before V1 promotion.

| Budget | Limit |
|---|---:|
| bytes per source unit | 1,000,000 |
| total bytes in reachable source closure | 16,000,000 |
| reachable modules | 256 |
| imports per source unit | 256 |
| top-level declarations per source unit | 1,024 |
| total linked top-level declarations | 8,192 |
| entities in root | 128 |
| states per flattened entity | 256 |
| handlers/events per flattened entity | 256 |
| behavior uses per behavior/entity | 64 |
| flattened behaviors per entity | 256 |
| record fields | 256 |
| enum variants | 256 |
| function parameters | 64 |
| event parameters | 64 |
| capability parameters | 64 |
| call arguments | 64 |
| lexical block nesting | 64 |
| expression nesting | 128 |
| type nesting | 128 |
| match arms | 256 |
| static loop iterations per `for` | 1,024 |
| nested static loops | 8 |
| expanded statement nodes per handler | 16,384 |
| pure function declarations | 2,048 |
| pure function call-graph depth | 64 |
| constant-evaluation steps per initializer | 65,536 |
| emitted runtime instructions per handler after lowering | 8,192 |
| local bindings per lowered handler | 256 |
| runtime local event chain | 128 |
| canonical linked semantic JSON bytes | 16,000,000 |

## Rules

1. A budget violation is a compile/link error, never truncation.
2. Budgets are checked before potentially explosive expansion where possible.
3. Behavior expansion, function inlining and loop unrolling must each account for the final expanded-node/instruction budgets.
4. A compiler may enforce tighter implementation-development limits only in a non-conformant preview mode; a conformant V1 implementation must accept every program within these normative limits or reject it for a different normative rule.
5. Hosts may impose tighter runtime resource limits after compilation, but those limits are host policy and cannot change source-language semantic validity.
6. Integer arithmetic used for budget calculation must itself be overflow-safe.
7. The V0.2 certified budgets remain unchanged for V0.2 compilation.
