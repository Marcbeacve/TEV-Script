# Changelog

## 1.0.0 — stable admission requested

This release-shaped commit is the exact TEV Script V1.0.0 stable candidate built on the fully certified P6 technical parent. Its metadata declares the stable profile, but publication authority remains conditional on `STABLE_ADMISSION=PASS` for this exact Git commit/tree and the exact release artifacts produced by that admission.

Technical parent authority:

```text
P_COMMIT=9c79d43a082e8c609d4b85d2cadd5b462f488252
P_TREE=a242425c98945eda90a7b45e4ef11394ef423bd4
P_CERTIFY_FULL_V2_RECEIPT_SHA256=6c5b8e1ab243d4ccd2108c816c83542c6e3fec1b2a69efc0c09e4a85327c0e07
P_CERTIFY_FULL_V2_RECEIPT_FILE_SHA256=c8a8b6bd307431dc32db17a10640a2890ce6316e6eaebacf0b2dcfa6420d702a
P_PYTHON_CERTIFY_FULL_RECEIPT_SHA256=271d3fbdf6d1e9284b8fede03823fbff1c98ba3fab81a0e2dd1602420a5437c8
P_PYTHON_WHEEL_SHA256=9116ea8f80cc89b26cbff0581108935f905d260f430ef0cf719e0166475b4944
```

V1.0.0 release surface:

- language version `1.0.0` with deterministic multi-file linking;
- pure user functions, records, enums, `Option<T>`, `Result<T,E>`, exhaustive `match`, bounded `for`, behavior composition and typed capabilities;
- canonical `TEV_SCRIPT_LINKED_PROGRAM_V1` source-semantic authority;
- verified lowering to `TEV_SCRIPT_PROGRAM_IR_V2` when losslessly erasable and `TEV_SCRIPT_PROGRAM_IR_V3` for the full algebraic runtime profile;
- Python, JavaScript and C# IR V3 implementations with governed cross-runtime canonical-byte and receipt checks;
- Runtime Checkpoint V2 cross-runtime identity and restart continuation;
- Browser-WASM AOT and WASI/Wasmtime execution gates;
- transactional hot swap and governed signed-update V2/V3 authority surfaces;
- preserved V0.2 language/runtime oracle and compatibility surface;
- Python `1.0.0` reproducible `py3-none-any` distribution profile with zero runtime dependencies;
- deterministic in-tree stdlib-only PEP 517 wheel backend, eliminating the former ambient `setuptools`/`bdist_wheel` build dependency from the certified packaging path;
- JavaScript `@tev-script/runtime` `1.0.0` distribution profile;
- exact parent-certificate binding, exact eight-file release-diff confinement, stable-profile global/Python recertification and exact artifact-byte binding.

P6 certification closed two environmental packaging defects before this release was shaped:

1. the earlier stable attempt could reach `bdist_wheel` failure under an isolated/offline Python installation;
2. P6 replaced external wheel-building authority with an in-tree backend and then completed full candidate-profile certification in a frozen certification environment with explicit Draft 2020-12 JSON Schema tooling.

`RUN_TEV_SCRIPT_V1_STABLE_ADMISSION.py` is the only authority allowed to conclude:

```text
CERTIFY_FULL=PASS
STABLE_ADMISSION=PASS
LANGUAGE_STABLE=YES
```

Until that exact gate passes on this exact release-shaped commit, this changelog entry is a release claim awaiting admission, not a tag, merge or publication authorization.

## 0.2.0-preview — hardened candidate

- Defines `TEV_SCRIPT_PROGRAM_IR_V2` as language-neutral authority.
- Adds exact portable `Int` and `Rat` representations.
- Adds the bounded synchronous capability ABI.
- Adds conformant Python and JavaScript runtimes.
- Adds a self-contained C# runtime targeting `netstandard2.1`.
- Closes observed C#/.NET conformance on Windows for all shared receipts.
- Adds strict C# IR validation, canonical JSON tooling and negative-boundary gates.
- Adds strict Draft 2020-12 schemas for program, scenario and receipt.
- Adds `TEV_CANONICAL_JSON_V1` and normative vectors.
- Adds strict Python and JavaScript JSON input boundaries.
- Makes the npm distribution self-contained and executable after packing.
- Emits CLI artifacts as deterministic UTF-8/LF bytes on every host.

This historical entry remains the preserved V0.2 lineage and does not supersede the V1 stable-admission authority.

---

## TEV Script V2 stable-admission request

```text
V2_STABLE_ADMISSION=REQUESTED
V2_LANGUAGE_VERSION=2.0.0
V2_PYTHON_PACKAGE_VERSION=1.0.0
V2_TECHNICAL_PARENT_COMMIT=64d31f9c726ab82719a152bf551dc524abe82373
V2_TECHNICAL_PARENT_CERTIFICATE_SHA256=49ccf5f6e5c4bf9962ccc6823ecade5f61f616787d3f7c5f0b596b51d4ff1bc7
```

This is the release-only Phase S source shape. It is bound to the exact independently recertified technical parent above. The source claim remains pending until `RUN_TEV_SCRIPT_V2_STABLE_ADMISSION.py` emits `STABLE_ADMISSION=PASS`. No tag, package publication, or main promotion is implied by this metadata alone.
