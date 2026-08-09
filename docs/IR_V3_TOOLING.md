# TEV Script IR V3 read-only tooling

Module CLI:

```powershell
python -m tev_script.runtime_cli_v3 ...
```

Status: developer/integration tooling for the V1/IR V3 implementation candidate.

This CLI deliberately performs **validation and scripted conformance only**. It is not a general-purpose host for executing arbitrary TEV programs with ambient capabilities.

---

## Describe

```powershell
python -m tev_script.runtime_cli_v3 describe .\Program.ir.json
```

The command first validates the IR and then prints a compact canonical summary:

```text
program id
IR semantic hash
source schema/hash
type count
entity/state/handler counts
capability ids
maximum value nesting
host_object_references=false
```

It does not dump source paths, filesystem metadata or host object identities.

---

## Validate

```powershell
python -m tev_script.runtime_cli_v3 validate .\Program.ir.json
```

Optional source-semantic pin:

```powershell
python -m tev_script.runtime_cli_v3 validate `
  .\Program.ir.json `
  --source-hash <linked-semantic-sha256>
```

Validation covers the complete IR V3 validator/type/CFG contract, not merely JSON Schema shape.

A mismatching expected source hash fails closed.

---

## Run a scripted conformance scenario

```powershell
python -m tev_script.runtime_cli_v3 conformance `
  .\Program.ir.json `
  .\scenario.json `
  -o .\receipt.json
```

Scenario schema:

```text
TEV_SCRIPT_IR_V3_SCENARIO_V1
```

Receipt schema:

```text
TEV_SCRIPT_IR_V3_CONFORMANCE_RECEIPT_V1
```

A conformance scenario explicitly scripts capability calls/returns and event steps. It therefore provides a deterministic test host rather than ambient runtime authority.

The compact command result reports the receipt hash. The canonical receipt file contains the full deterministic execution evidence.

To also print the canonical receipt after the summary:

```powershell
python -m tev_script.runtime_cli_v3 conformance `
  .\Program.ir.json `
  .\scenario.json `
  --print-receipt
```

Stdout then contains exactly two JSON lines:

```text
line 1: compact run result
line 2: canonical conformance receipt
```

---

## Why there is no generic `run` command

A command such as:

```text
run program.ir --load-python-module anything
```

would create a new capability-authority surface outside the language/runtime contracts.

TEV Script deliberately requires real hosts to bind capabilities through explicit adapters and ceilings. The portable CLI therefore stops at:

```text
validate
scripted conformance
```

Real execution belongs in a host integration that owns and documents its capability policy.

---

## Relationship to other identities

`validate` checks target program identity:

```text
IR semantic_hash
source_semantic_hash
```

`conformance` adds execution identity:

```text
scenario_hash
step state hashes
capability transcript
final_state_hash
receipt_hash
```

These should not be replaced by a single undifferentiated build hash.
