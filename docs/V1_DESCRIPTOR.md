# TEV Script V1 machine-readable descriptor

Status: build/editor integration contract for the V1 implementation candidate.

## Query

```powershell
python -m tev_script.describe_v1
```

The command writes one canonical JSON document followed by one LF.

Schema:

```text
TEV_SCRIPT_DESCRIPTOR_V3
```

JSON Schema:

```text
schemas/tev_script_descriptor_v3.schema.json
```

Python construction API:

```python
from tev_script.descriptor_v1 import v1_descriptor, v1_descriptor_json
```

## Purpose

The descriptor lets build systems, editor integrations and host adapters discover the implemented V1 profile without scraping Markdown.

It answers machine questions such as:

```text
Which language version is this?
Is it claimed stable?
Which runtime IR profiles exist?
Can imports resolve over the network?
Are recursion/reflection/unbounded loops allowed?
What are the compiler budgets?
Which project/receipt schemas should tooling expect?
What is the V0.2 certification oracle preserved by this branch?
```

It does **not** replace the normative grammar/semantic contracts.

## Identity

The descriptor contains:

```text
descriptor_hash
```

The hash is SHA-256 over canonical descriptor JSON before adding the `descriptor_hash` field itself.

That identity describes the reported tooling/language profile. It is not a program semantic hash and must never be substituted for:

```text
project_input_hash
linked_semantic_hash
IR semantic_hash
lowering receipt hash
conformance receipt hash
checkpoint hash
```

## Release state

The V1 descriptor deliberately reports:

```json
{
  "language_version": "1.0.0",
  "release_status": "IMPLEMENTATION_CANDIDATE_UNCERTIFIED",
  "stable": false
}
```

A future stable-admission commit must not change these claims without passing the certification/admission protocol for the resulting commit.

## Runtime targets

The descriptor reports both targets:

```text
TEV_SCRIPT_PROGRAM_IR_V2
TEV_SCRIPT_PROGRAM_IR_V3
```

and the automatic selection rule:

```text
IR_V2_IF_LOSSLESSLY_ERASABLE_ELSE_IR_V3
```

This is the same policy used by the V1 compilation pipeline and CLI.

## Boundaries

The V1 candidate reports the absence of:

```text
async/await
classes/inheritance
dynamic code
exceptions as language control flow
host-native object references
implicit concurrency
implicit physical effects
reflection
recursion
runtime source compilation
threads
unbounded loops
user-defined generics
general maps
general variable-size collections
```

These booleans are intended for tooling/capability negotiation. They are not permission flags that a host may override while still claiming the same TEV Script profile.

## Budgets

The descriptor budgets are generated from `tev_script/contracts_v1.py` constants rather than copied into an independent Python table.

They include source/link, syntax depth, type depth, function, behavior, loop, local, instruction and event-chain bounds.

The normative explanation remains:

```text
spec/TEV_SCRIPT_V1_BUDGETS.md
```

## Build tooling

The descriptor reports:

```text
TEV_SCRIPT_PROJECT_V1
TEV_SCRIPT_LOWERING_RECEIPT_V1
TEV_SCRIPT_LOWERING_RECEIPT_V2
EVIDENCE_SAFE_RECEIPT_LAST_V1
```

This lets an integration distinguish source-semantic contracts from project/build/evidence contracts.

## Tests

`tests/test_v1_descriptor.py` verifies:

- descriptor self-hash;
- candidate/stable claims;
- all negative boundaries;
- selected budgets against code constants;
- linked/target profiles;
- build-tooling contracts;
- schema identity;
- one-document canonical CLI output.
