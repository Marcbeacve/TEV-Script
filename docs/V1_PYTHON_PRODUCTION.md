# TEV Script V1 — Python production host

Status: **implementation candidate**. This document does not authorize a V1 stable release and does not replace `PRECERTIFY` / `CERTIFY_FULL`.

## 1. Production boundary

The Python product is split deliberately into a build-time compiler surface and a runtime-only host surface:

```text
BUILD / TOOLING

explicit finite .tevs source set
        |
        v
Python reference frontend
        |
        v
TEV_SCRIPT_LINKED_PROGRAM_V1
        |
        v
TEV_SCRIPT_PROGRAM_IR_V3
        |
        v
canonical IR artifact

-------------------------------- authority boundary --------------------------------

PRODUCTION RUNTIME

canonical validated IR V3 artifact
        |
        v
PythonProgramArtifactV1
        |
        +---- exact required capability ABI
        |
        v
PythonRuntimeHostV1
        |
        +---- explicit host capabilities only
        |
        +---- bounded deterministic TEV execution
        |
        +---- RuntimeCheckpointV2 capture / exact restore
```

`PythonRuntimeHostV1` has no source-compilation method. A deployed runtime can therefore be packaged without granting a TEV program permission to compile new source dynamically. The IR V3 boundary itself also requires `runtime_source_compilation=false`, `dynamic_code=false`, `reflection=false`, `automatic_authority_escalation=false` and `host_object_references=false`.

## 2. Build-time API

The production profile deliberately targets IR V3 even when a program would be erasable to IR V2. This gives the Python production host one runtime ABI and one checkpoint format.

```python
from tev_script import build_python_program_v1

artifact = build_python_program_v1(
    {
        "main.tevs": b'''script Counter version "1.0.0";
entity E {
    state count: Int = 0;
    on inc { count = count + 1; }
}
''',
    }
)

print(artifact.program_id)
print(artifact.source_semantic_hash)
print(artifact.ir_semantic_hash)
print(artifact.canonical_ir_json)
```

For filesystem inputs use `build_python_program_v1_paths([...])`. Project builds may continue to use the canonical `tev-script-v1 build` manifest workflow and force `--target irv3` for a Python production artifact.

Source compilation is tooling authority. It is not an ambient service offered by the runtime host.

## 3. Loading a deployed artifact

Use `PythonProgramArtifactV1.parse(text)` at the deployment boundary.

The parser:

- uses the strict TEV JSON parser;
- rejects duplicate keys, floats and non-standard JSON constants through the canonical JSON input rules;
- requires a valid `TEV_SCRIPT_PROGRAM_IR_V3` program;
- validates semantic/debug/source identities through the canonical IR V3 validator;
- accepts only canonical JSON or the repository artifact spelling of canonical JSON followed by exactly one final LF;
- derives the required runtime capability contracts from the validated IR rather than from a second manifest.

```python
from pathlib import Path
from tev_script import PythonProgramArtifactV1

artifact = PythonProgramArtifactV1.parse(
    Path("program.ir.json").read_text(encoding="utf-8")
)
```

Do not deserialize an IR document into a Python object and bypass this validation at an external trust boundary.

## 4. Least-authority capability binding

All physical authority enters through the capability map supplied by the host application.

```python
from tev_script import PythonRuntimeHostV1

host = PythonRuntimeHostV1(
    artifact,
    {
        "world.temperature": read_temperature,
        "telemetry.publish": publish_telemetry,
    },
)
```

The default policy is exact least authority:

- every capability required by the IR must be bound before execution;
- every supplied binding must be callable;
- unused capability bindings are rejected;
- the underlying IR runtime validates the capability id and typed return value;
- the TEV program cannot discover Python objects, modules, filesystem handles, sockets, clocks or environment variables unless the host deliberately exposes equivalent authority through a capability.

`reject_unused_capabilities=False` exists only for hosts that intentionally use one broader preconstructed binding table. The recommended production policy is the default `True`.

Capability implementations are **trusted host code**. A Python callback that blocks forever, performs unsafe I/O or allocates without bound is outside the TEV machine and cannot be made safe by the script instruction budget. Untrusted capability implementations must be isolated by the embedding application, for example in a separate constrained process. This is an explicit trust boundary, not hidden authority in TEV Script.

## 5. Runtime execution

```python
host.invoke("E", "inc")
state = host.state("E")
canonical = host.canonical_state("E")
```

The host delegates execution to `ScriptRuntimeV3`; it does not duplicate interpreter semantics. Therefore the existing V3 rules remain authoritative:

- validated closed type table;
- typed state/locals/parameters/capabilities/events;
- per-handler instruction budget;
- bounded event chain;
- forward-only CFG;
- no recursion;
- no unbounded loop;
- exact rational arithmetic;
- canonical algebraic values.

## 6. Checkpoint and process restart

```python
checkpoint_text = host.capture_checkpoint_json()

# Later, including in a fresh process created with the exact same IR artifact:
host.restore_checkpoint(checkpoint_text)
```

`RuntimeCheckpointV2` is accepted only when all of the following match exactly:

- program id;
- IR schema;
- IR semantic hash;
- source schema;
- source semantic hash;
- entity set;
- state set;
- state type;
- canonical state value.

This is exact restoration, not schema migration. Runtime update/migration remains the separate governed hot-swap/update mechanism.

## 7. Distribution gate

Run from a clean exact commit with Python 3.11+:

```text
python RUN_TEV_SCRIPT_V1_PYTHON_PRODUCTION.py
```

The gate is intentionally stronger than an in-repository unit-test pass. It performs:

1. Python-version, Git, pip and setuptools preflight;
2. clean-worktree and exact Git identity capture;
3. certified V0.2 oracle ancestry check;
4. V1 governance validation, including the Python production surface/gate bindings;
5. the complete current V1 Python/frontend/IR V3/V0.2 Python closure;
6. an explicit zero-runtime-dependency assertion for the reference Python package;
7. two independent `git archive HEAD` source extractions;
8. two offline, no-build-isolation wheel builds with fixed `SOURCE_DATE_EPOCH`, `PYTHONHASHSEED=0` and pip configuration disabled;
9. exact wheel filename and SHA-256 byte equality;
10. a portable `py3-none-any` wheel-tag assertion;
11. creation of a fresh venv;
12. offline installation of the wheel with no dependencies;
13. installed package-version verification;
14. installed console-script presence verification;
15. installed V1 descriptor execution and rejection of any unauthorized stable claim;
16. installed `tev-script-v1` compilation of both a counter and a typed-capability program to explicit IR V3 outside the repository checkout;
17. verification that the imported `tev_script` module actually resides under the fresh venv and is not shadowed by the source checkout;
18. loading persisted IR through `PythonProgramArtifactV1`;
19. installed `PythonRuntimeHostV1` execution;
20. checkpoint capture, continued execution, exact restore and continuation after restore;
21. rejection of surplus capability authority;
22. rejection of missing capability authority;
23. successful execution of an explicitly bound typed capability;
24. a 10,000-event installed-wheel soak with exact final-state witness;
25. clean-worktree and identical HEAD/tree verification after the campaign;
26. emission of `TEV_SCRIPT_V1_PYTHON_PRODUCTION_RECEIPT_V1` bound to commit, tree, Python/build-tool versions, wheel SHA-256, authority witnesses and soak cardinality.

The soak is a deterministic semantic endurance witness, not a hardware-independent latency benchmark. It deliberately has no wall-clock threshold because a fixed timing threshold would make certification depend on machine load/hardware rather than TEV semantics.

The wheel build is explicitly offline (`PIP_NO_INDEX=1`, `--no-deps`, `--no-build-isolation`). If the local build backend needed by `pyproject.toml` is absent or incompatible, the gate fails rather than downloading a different toolchain silently.

## 8. Meaning of PASS

A successful gate ends with:

```text
TEV_SCRIPT_V1_PYTHON_PRODUCTION=PASS_CANDIDATE
CERTIFY_FULL=NO
LANGUAGE_STABLE=NO
```

`PASS_CANDIDATE` means the exact commit demonstrated the Python distribution and production-host properties above. It does **not** mean:

- V1 has been promoted to stable;
- cross-runtime V1 certification is complete;
- the package version may be relabeled `1.0.0` without another exact-commit validation;
- arbitrary Python capability implementations are sandboxed;
- a different wheel or commit inherits the receipt.

## 9. Stable release sequence

The intended release sequence is:

```text
implementation commit
    -> Python production gate
    -> V1 PRECERTIFY
    -> V1 CERTIFY_FULL
    -> explicit stable-version/promotion commit
    -> Python production gate again on promoted commit
    -> PRECERTIFY again
    -> CERTIFY_FULL again
    -> release/tag/publication authorization
```

No certification is transitive across a source/version change.

## 10. Operational deployment checklist

For an actual Python service or desktop application:

- distribute the exact wheel identified by the production receipt;
- store the canonical IR V3 artifact and its lowering/build evidence with the release;
- construct capability maps explicitly per application role;
- keep default unused-capability rejection unless a broader capability table is a deliberate architectural decision;
- do not expose source compilation to untrusted runtime requests;
- persist Runtime Checkpoint V2 only when exact restart is required;
- keep application-level timeouts/process isolation around untrusted or failure-prone host capabilities;
- log commit/tree, wheel SHA-256, IR semantic hash and source semantic hash with deployment metadata;
- re-run the production gate after any Python package, build-system, runtime or source change.
