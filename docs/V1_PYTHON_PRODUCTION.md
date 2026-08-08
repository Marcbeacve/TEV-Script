# TEV Script V1 — Python production host

Status: **technically certifiable host/product surface with candidate and stable-admission profiles**. This document does not itself authorize a V1 stable release. Only `RUN_TEV_SCRIPT_V1_STABLE_ADMISSION.py` may authorize `LANGUAGE_STABLE=YES`.

## 1. Production boundary

The Python product is deliberately split between build-time source authority and a runtime-only IR host:

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
        +---- least-authority preflight
        +---- serialized/non-reentrant host access
        +---- bounded deterministic TEV execution
        +---- RuntimeCheckpointV2 capture / exact restore
```

`PythonRuntimeHostV1` has no source-compilation method. Source compilation remains explicit tooling authority. Runtime IR V3 also keeps `runtime_source_compilation=false`, `dynamic_code=false`, `reflection=false`, `automatic_authority_escalation=false` and `host_object_references=false`.

## 2. Build-time API

The production host deliberately targets IR V3 even when source could erase to IR V2. This gives Python deployment one runtime ABI and one checkpoint format.

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

For filesystem inputs use `build_python_program_v1_paths([...])`. Project builds may use `tev-script-v1 build` and explicitly select IR V3 when preparing a Python production artifact.

## 3. Loading a deployed artifact

Use `PythonProgramArtifactV1.parse(text)` at the deployment boundary. It:

- uses strict TEV JSON parsing;
- rejects duplicate keys, floats and non-standard constants;
- requires `TEV_SCRIPT_PROGRAM_IR_V3`;
- validates source/semantic/debug identities;
- accepts canonical JSON or canonical JSON followed by exactly one final LF;
- derives required capability contracts from validated IR instead of a second manifest.

```python
from pathlib import Path
from tev_script import PythonProgramArtifactV1

artifact = PythonProgramArtifactV1.parse(
    Path("program.ir.json").read_text(encoding="utf-8")
)
```

Do not deserialize untrusted IR into a host-native object and bypass this validation boundary.

## 4. Least-authority capability binding

All physical authority enters through the host-supplied capability map:

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

Default policy:

- every required capability must be bound before execution;
- every binding must be callable;
- unused bindings are rejected by default;
- capability id and typed return value are validated by the runtime;
- the program cannot discover Python modules, filesystem handles, sockets, clocks or environment values unless equivalent authority is deliberately exposed through a capability.

`reject_unused_capabilities=False` exists only for an embedding application that deliberately chooses a broader preconstructed authority table.

Capability implementations remain trusted host code. TEV instruction/event budgets do not sandbox arbitrary Python callbacks. Untrusted callbacks require application-level process/container and OS-resource isolation.

## 5. Runtime execution

```python
host.invoke("E", "inc")
state = host.state("E")
canonical = host.canonical_state("E")
```

The host delegates to `ScriptRuntimeV3`; it does not implement a second interpreter. The existing V3 rules therefore remain authoritative: closed type table, typed state/locals/parameters/capabilities/events, bounded instructions/event chains, forward-only CFG, no recursion, no unbounded loops, exact rationals and canonical algebraic values.

## 6. Serialized host-access boundary

One `PythonRuntimeHostV1` is one serialized TEV execution domain. Operations that can observe or mutate runtime state use a non-reentrant, non-blocking guard:

```text
invoke
state
canonical_state
capture_checkpoint
restore_checkpoint
```

Concurrent or callback-driven reentry fails closed with:

```text
TEVS_PYTHON_V1_HOST_BUSY
```

The host does not block and later select an order based on Python thread scheduling. Such an order would become implicit TEV semantics. If parallel work is needed, use separate hosts or an explicit application scheduler and convert semantically relevant ordering into TEV events/state.

This contract is canonical governance:

```text
python_production_surface.serialized_host_access=true
```

Both reentrant and real concurrent-access rejection are mandatory Python V2 certificate evidence.

## 7. Runtime Checkpoint V2

```python
checkpoint_text = host.capture_checkpoint_json()
host.restore_checkpoint(checkpoint_text)
```

Restore requires exact agreement on program id, IR schema/hash, source schema/hash, entity set, state set, each state type and canonical value. It is an exact restart mechanism, not arbitrary schema migration.

## 8. Candidate and stable profiles

Both Python gates accept:

```text
--profile candidate   # default
--profile stable
```

Profiles change **release/governance expectations**, not runtime semantics.

Candidate profile expects:

```text
Python package version = 0.2.0
release_profile = candidate
stable = false
```

Stable profile expects:

```text
Python package version = 1.0.0
release_profile = stable
stable = true
```

Stable profile additionally requires the frontend zero-skip witness. It still runs the same Python runtime/distribution evidence and does not itself authorize `LANGUAGE_STABLE=YES`.

## 9. Python production admission V2

Authority:

```text
RUN_TEV_SCRIPT_V1_PYTHON_PRODUCTION.py
```

Examples:

```text
python RUN_TEV_SCRIPT_V1_PYTHON_PRODUCTION.py --profile candidate
python RUN_TEV_SCRIPT_V1_PYTHON_PRODUCTION.py --profile stable --artifact-out-dir <external-empty-dir>
```

The gate performs:

1. Python 3.11+, Git, pip and setuptools preflight;
2. clean exact Git identity capture;
3. V0.2 oracle ancestry check;
4. profile-specific governance;
5. V1 frontend/IR V3/V0.2 Python closure;
6. stable profile zero-skip enforcement;
7. zero Python runtime dependencies;
8. two independent `git archive HEAD` source extractions;
9. two offline no-build-isolation/no-dependency wheel builds under fixed build epoch/hash seed;
10. exact wheel filename and SHA-256 equality;
11. `py3-none-any` portability tag;
12. fresh venv creation and offline installation;
13. installed package-version check;
14. installed CLI presence;
15. installed `TEV_SCRIPT_DESCRIPTOR_V3` execution with profile/stable claim check;
16. installed explicit IR V3 compilation outside the checkout;
17. proof imports originate inside the fresh venv;
18. IR-only `PythonRuntimeHostV1` execution;
19. checkpoint capture/restore/continuation;
20. surplus capability rejection;
21. missing capability rejection;
22. callback-driven reentrant host-access rejection with state non-mutation proof;
23. real concurrent same-host access rejection with `TEVS_PYTHON_V1_HOST_BUSY`;
24. typed capability execution;
25. deterministic 10,000-event soak;
26. clean identical HEAD/tree after the campaign;
27. canonical content-addressed production receipt.

Receipt schema:

```text
TEV_SCRIPT_V1_PYTHON_PRODUCTION_RECEIPT_V2
```

It binds:

```text
admission_profile
commit/tree/branch
Python/pip/setuptools identities
package name/version
wheel filename/SHA-256
runtime dependency count
least-authority/reentrancy/concurrency witnesses
checkpoint continuation
10,000-event soak
certify_full=false
language_stable=false
```

Candidate success:

```text
TEV_SCRIPT_V1_PYTHON_PRODUCTION=PASS_CANDIDATE
CERTIFY_FULL=NO
LANGUAGE_STABLE=NO
```

Stable-profile success:

```text
TEV_SCRIPT_V1_PYTHON_PRODUCTION=PASS_STABLE_CANDIDATE
CERTIFY_FULL=NO
LANGUAGE_STABLE=NO
```

### Exact artifact export

`--artifact-out-dir` must point outside the repository and must be empty. After both independent builds have proven reproducibility, the gate copies **the already-verified wheel bytes** to that directory and recomputes the copied SHA-256.

This is intentionally stronger than “rebuild later from the same commit”. Stable publication must use the bytes bound by the stable-admission receipt.

## 10. Python-specific full certification V2

Authority:

```text
RUN_TEV_SCRIPT_V1_PYTHON_CERTIFY_FULL.py
```

Examples:

```text
python RUN_TEV_SCRIPT_V1_PYTHON_CERTIFY_FULL.py --profile candidate
python RUN_TEV_SCRIPT_V1_PYTHON_CERTIFY_FULL.py --profile stable --artifact-out-dir <external-empty-dir>
```

The certifier:

1. captures its own exact clean HEAD/tree/branch;
2. verifies V0.2 ancestry;
3. verifies profile-specific canonical Python authority metadata;
4. runs Python production V2 with the same profile;
5. propagates the external artifact directory when requested;
6. rejects skips in mandatory scope;
7. parses exactly one production receipt and external receipt hash;
8. independently recomputes canonical production receipt SHA-256;
9. requires embedded/external/recomputed hashes to agree;
10. requires exact profile/commit/tree/branch/oracle equality;
11. requires zero dependencies, portable reproducible wheel, isolated install, module origin, installed IR/runtime, least authority, **reentrant and concurrent** access rejection, typed capability, checkpoint continuation and exact 10,000-event soak;
12. validates package version (`0.2.0` candidate, `1.0.0` stable);
13. rechecks worktree/HEAD/tree/governance/state immutability;
14. emits a technical Python certificate.

Certificate schema:

```text
TEV_SCRIPT_V1_PYTHON_CERTIFY_FULL_RECEIPT_V2
```

Success always terminates:

```text
PYTHON_CERTIFY_FULL=PASS
CERTIFY_FULL=NO
LANGUAGE_STABLE=NO
```

The certificate explicitly keeps:

```text
python_certify_full=true
global_certify_full=false
language_stable=false
stable_release_authorized=false
```

Even a successful `--profile stable` Python certificate is therefore subordinate evidence for stable admission, not a stable-language authority.

## 11. Relationship to global and stable certification

Python certification is one bounded product certificate. Global cross-runtime technical certification is separate:

```text
RUN_TEV_SCRIPT_V1_PRECERTIFY.py
RUN_TEV_SCRIPT_V1_CERTIFY_FULL.py
```

Stable release authority is separate again:

```text
RUN_TEV_SCRIPT_V1_STABLE_ADMISSION.py
```

The required stable chain is:

```text
P = technically certified Stage-D tooling commit
  -> exact candidate-profile global CERTIFY_FULL V2 receipt persisted externally

S = release-shaped commit from P
  -> Python package version 1.0.0
  -> JS package version 1.0.0
  -> stable release metadata + exact P certificate identity
  -> stable global CERTIFY_FULL V2 on S
  -> stable Python CERTIFY_FULL V2 on S
  -> exact wheel export
  -> npm test + exact npm pack
  -> STABLE_ADMISSION(S)=PASS
```

Only stable admission may terminate:

```text
CERTIFY_FULL=PASS
STABLE_ADMISSION=PASS
LANGUAGE_STABLE=YES
```

No Python certificate is transitive across source, metadata, package-version, build-system, commit or wheel-byte changes.

## 12. What Python certification does not claim

Neither candidate nor stable-profile Python certification proves:

- global V1 cross-runtime certification;
- stable language admission;
- arbitrary callback sandboxing;
- deterministic scheduling across multiple independent hosts unless the application makes ordering explicit;
- production signing-key custody;
- hostile rollback-resistant durable state;
- public network deployment security;
- identity of a later rebuilt wheel;
- Unity product certification.

## 13. Operational deployment checklist

For an actual Python application:

- deploy the exact wheel identified by the relevant Python/stable receipt;
- retain canonical IR V3 plus source/lowering evidence;
- construct capability maps explicitly per role;
- preserve default unused-capability rejection unless broader authority is deliberate;
- treat one `PythonRuntimeHostV1` as one serialized execution domain;
- do not reenter the active host from a capability callback;
- keep source compilation out of untrusted runtime requests;
- persist Runtime Checkpoint V2 only for exact restart;
- isolate untrusted/failure-prone callbacks at process/OS level;
- log commit/tree, wheel SHA-256, IR semantic hash and source semantic hash;
- re-run the appropriate profile after any source/runtime/build/release-metadata change;
- for stable publication, publish only artifact bytes emitted and hashed by successful `STABLE_ADMISSION`.
