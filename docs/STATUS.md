# Status

```text
VERSION=0.2.0-preview
LANGUAGE_STABLE=NO
PYTHON_TESTS=29_PASS
JAVASCRIPT_TESTS=21_PASS
CONFORMANCE_SCENARIOS=4_PASS
THREE_RUNTIME_CONFORMANCE=PASS
UNITY_EDITOR_CONFORMANCE=PASS_CERTIFIED
UNITY_PLAYMODE=PASS_CERTIFIED
UNITY_MONO_PLAYER=PASS_CERTIFIED
UNITY_IL2CPP_PLAYER=PASS_CERTIFIED
TRANSACTIONAL_PROGRAM_SWAP_GATE5A=PASS_OBSERVED_LOCAL_PRECOMMIT
GATE5A_GATE_BINARY_VERSION=V4
GATE5A_STATE_MIGRATION=EXACT_EXISTING_TYPES_PASS
GATE5A_ADDITIVE_STATE=PASS
GATE5A_CAPABILITY_CEILING=EXPLICIT_PASS
GATE5A_ROLLBACK=EXACT_PREVIOUS_RUNTIME_PASS
GATE5A_STALE_PLAN=FAIL_CLOSED_PASS
GATE5A_DYNAMIC_CODE=ABSENT_PASS
GATE5A_NETWORK=NOT_IN_SCOPE
GATE5A_SIGNATURE_AUTHORITY=NOT_IN_SCOPE
GATE5A_WASM=NOT_IN_SCOPE
BROWSER_EXECUTION_CAMPAIGN=PENDING
REMOTE_SIGNED_IR=PENDING
STABLE_RELEASE=NO
```

Gate-5A observes a portable transactional supervisor over fixed-program
`TevScriptRuntime` instances. A candidate IR is parsed and validated before an
isolated candidate runtime is constructed. Existing state is migrated only
across exact state-name/type continuity, new states keep candidate initial
values, capability declarations remain under an explicit host ceiling, commit
is an authoritative reference swap, and one exact previous runtime object is
retained for rollback.

Precommit evidence SHA-256:
`794297c539d4f9c2a891d7952cdea080b6f109617c8e1687d30cf7a8c28b6d8a`.

This file does not claim network delivery, signatures, anti-replay, WebAssembly
or stable release. Exact Gate-5A commit authority requires the post-commit
clean-tree rerun and external certification receipt.
