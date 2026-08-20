# Validation

> **Current-candidate note:** the PASS lines and receipt hashes already recorded below are preserved historical evidence. They do **not** certify the current `3.1.2` documentation candidate or its present Git HEAD. Authority for the current candidate requires rerunning the causally selected commands listed at the end of this document on the exact clean commit/tree.

## Current certified surface

```text
PYTHON_TESTS=29 PASS
JAVASCRIPT_TESTS=21 PASS
CANONICAL_JSON_VECTORS=PASS
STRICT_JSON_INPUT_BOUNDARY=PASS
CONFORMANCE_SCENARIOS=4 PASS
PYTHON_JAVASCRIPT_BYTE_PARITY=PASS
CSHARP_CORE_BUILD=PASS_OBSERVED_WINDOWS_DOTNET_10_0_302
CSHARP_GATE1_SMOKE=PASS
CSHARP_CANONICAL_VECTORS=12 PASS
CSHARP_STRICT_JSON_BOUNDARY=PASS
CSHARP_STRICT_UTF8_BOUNDARY=PASS
CSHARP_IR_NEGATIVE_CAMPAIGN=PASS
CSHARP_MISSING_CAPABILITY_FAIL_CLOSED=PASS
CSHARP_PYTHON_JAVASCRIPT_BYTE_PARITY=PASS
DETERMINISTIC_UTF8_LF_OUTPUT=PASS
REDIRECTED_STDIO_UNICODE=PASS
POWERSHELL_MATERIALIZER_STATIC_STRUCTURE=PASS
```

Authoritative receipt hashes remain:

```text
PLAYER_RECEIPT_HASH=b275ccc6530ad84c0f96320ba1c8893b401638a926a99a78479d99fbd3c4aba5
MATRIX_RECEIPT_HASH=70df629159b6088aa3807deea217d4cdb06f28a41042aac1f6ebff6332179500
PLAYER_IDLE_RECEIPT_HASH=647d3211f7411b88c155d658ba4c9494482378cde75c9f427dc4e38475acd17c
EVENT_CHAIN_RECEIPT_HASH=5fcbd07512192ec298ff18bc313c71418e079e04d303aa3514a49ab91462371d
```

## C# conformance evidence

Observed on Windows x64 with .NET SDK 10.0.302 / `Microsoft.NETCore.App
10.0.10`. `TevScript.Core` targets `netstandard2.1`; the smoke and conformance
hosts target `net8.0` with `RollForward=Major` so newer installed runtimes can
execute the test hosts.

C# consumes the same `TEV_SCRIPT_CONFORMANCE_SCENARIO_V1` fixtures as the other
runtimes and produces the exact same canonical bytes for all four receipts. It
also passes the canonical-vector and negative-boundary campaign.

Evidence:

```text
evidence/reference-v0.2/csharp-conformance-windows-dotnet10.json
```

## JSON Schema continuity and historical V1 certification

`RUN_PORTABLE_CONFORMANCE.py` uses the external `jsonschema` package when it is
available. Historical V0.2 evidence that was produced without that optional
development dependency remains historical evidence and is not rewritten as a
PASS.

For ordinary development/diagnostic runs, the portable tool may still report:

```text
JSON_SCHEMA_VALIDATION=SKIPPED_DEPENDENCY_UNAVAILABLE
```

That status is **not sufficient for the historical V1 global certification**.
`RUN_TEV_SCRIPT_V1_PRECERTIFY.py` treats `jsonschema` as a certification-tool
dependency and requires:

```text
JSON_SCHEMA_VALIDATION=PASS
```

It also runs `RUN_TEV_SCRIPT_V1_FRONTEND_CLOSURE.py --require-zero-skips` and
requires explicit zero skip counts for the V1, IR V3 and V0.2 Python regression
suites. This prevents unittest skips written to stderr from being mistaken for
a complete global PASS.

`jsonschema` and `cryptography` are **not** added to the TEV Script Python runtime
dependency set. The production wheel's zero-runtime-dependency contract and the
certification environment's stronger test/tool requirements are separate
concerns. The exact current certification-only Python dependency set is pinned
in `requirements-certification.txt`.

V0.2 Browser-WASM and WASI execution remain separate mandatory dynamic
witnesses provided by `tools/validate_v0_2_portable_hosts.py` where a historical
V1 stable-profile recertification explicitly requires them.

## Historical V1 commands

Development/diagnostic V0.2 checks:

```powershell
python .\RUN_PORTABLE_CONFORMANCE.py
python .\tools\validate_v0_2_portable_hosts.py

pwsh -NoProfile -ExecutionPolicy Bypass `
  -File .\RUN_TEV_SCRIPT_CSHARP_CONFORMANCE_V1.ps1
```

Historical V1 stable/candidate gates remain versioned tools and may be run only
with the profile and package identity they explicitly require. They are **not**
the current repository-wide 3.1.2 completion gate.

For an exact committed V0.2/C# candidate, rerun with:

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass `
  -File .\RUN_TEV_SCRIPT_CSHARP_CONFORMANCE_V1.ps1 `
  -RequireClean
```

No GitHub Action is authoritative or required.

## TEV_SCRIPT_LANGUAGE_COMPLETENESS_V1

Language-closure evidence is stored at `evidence/reference-v0.2/language-completeness-v1-windows-dotnet10.json`. The dynamic language regression ran once. Gates 5, 6 and 7 were not dynamically rerun. Functional payload SHA-256 identity: `e7af8fbe431507d52981600bef9721960a44dcccba7d97dd6ce6a79bcd413eef`. Stable release remains NO.

## TEVScript 3.1 documentation validation

The documentation validator is a leaf quality gate. It verifies documentation/source binding, executable documentation cases, public CLI/API coverage, current V31 diagnostics, historical classification and final documentation shape without changing semantic/platform authority. The repository-closeout test additionally points the validator at the real repository tree, checks final navigation/diagnostic pages, binds displayed negative examples to their canonical `case.json`, rejects stale phase placeholders and protects the current host-support matrix from overclaiming V5 targets.

Development focal validation:

```powershell
python -m pytest -q tests/test_documentation_v31.py tests/test_documentation_coverage_v31.py tests/test_documentation_source_bindings_v31.py tests/test_documentation_example_cases_v31.py tests/test_documentation_diagnostics_v31.py tests/test_documentation_public_surface_v31.py tests/test_documentation_closure_v31.py tests/test_documentation_run_cases_v31.py tests/test_documentation_cli_aliases_v31.py tests/test_documentation_repository_closeout_v31.py tests/test_documentation_validator_cli_v31.py
python -m tools.validate_documentation_v31 --root .
```

The validator is launched as a module so the repository root remains on Python's import path and the executable documentation cases can import the local `tev_script` package from the exact checkout being validated.

Required platform regression before documentation closeout:

```powershell
python -m pytest -q tests/test_platform_version_identity.py tests/test_platform_normative_spec.py tests/test_platform_version_matrix.py tests/test_platform_tooling.py tests/test_repository_channel_current_platform.py
python -m tev_script.cli platform-check --root .
```

## Current 3.1 platform-completion environment

The exact certification-only Python dependencies are installed from the committed
source of truth rather than selected ad hoc:

```powershell
python -m pip install --upgrade -r .\requirements-certification.txt
python -m pip check
```

The platform completion gate additionally depends on the host/runtime tools used
by its child gates. Missing required evidence fails closed; it must not be turned
into a synthetic PASS.

### Repository-selected causal validation for this diff

The current documentation branch changes more than `full_after_changed_files = 64` files and touches `docs/**`, `tests/**`, `examples/**`, `tools/**`, platform code and normative/specification paths. Therefore `REPOSITORY_CHANNEL.json` selects all three validation rules. On the exact clean candidate, execute the rule commands themselves:

```powershell
python -c "from pathlib import Path; Path('README.md').read_text(encoding='utf-8')"
python .\RUN_PORTABLE_CONFORMANCE.py
python .\RUN_TEV_SCRIPT_PLATFORM_COMPLETION.py
```

`RUN_TEV_SCRIPT_PLATFORM_COMPLETION.py` is the current package/language aggregate. It requires the exact nine 3.1 platform gates (`VERSION_IDENTITY`, `NORMATIVE_SPEC`, `VERSION_MATRIX`, `TOOLING_3X`, `CONFORMANCE`, `DIFFERENTIAL_FUZZ`, `SEMANTIC_INVARIANTS`, `REPRODUCIBLE_RELEASE`, `FULL_REGRESSION`) to close on one exact commit/tree. `FULL_REGRESSION` is repository-wide and requires a non-empty suite with zero failures, zero errors and zero skips while HEAD/tree and worktree cleanliness remain unchanged.

The focal documentation/platform commands above are additional closeout evidence; they do not replace these repository-selected commands. No result from a previous commit can certify a later documentation edit. `MERGE_AUTHORITY` and `PUBLICATION_AUTHORITY` remain false until separately authorized.
