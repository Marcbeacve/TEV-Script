# TEVScript 3.1 — Complete Documentation System Design

Date: 2026-08-18
Status: DESIGN APPROVED / USER REVIEW REQUIRED BEFORE IMPLEMENTATION
Base branch: `main`
Base commit: `a0c3951a03403f871ff4a192f75f2c29437f5fdb`
Working branch: `agent/tevscript-docs-python-style-v1`
Current language: `3.1.0`
Current profile: `total_core`
Current package candidate: `3.1.2`
Published immediate predecessor: `3.1.1`

## 1. Objective

Create a complete, precise, maintainable TEVScript documentation system with the usability expected from a mature programming language documentation set.

The documentation must support four distinct reader intents without mixing them:

1. **learn** TEVScript progressively;
2. **look up** exact language and runtime behavior;
3. **solve** a concrete programming or integration task;
4. **verify** which specification, version, artifact, diagnostic, or compatibility rule is authoritative.

The documentation is not allowed to become a second semantic authority. It explains the language; it does not redefine the language.

The primary human-facing documentation will be written in Spanish. Stable identifiers, keywords, type names, CLI commands, API names, schemas, diagnostic codes, file names, and literal program text remain unchanged.

Normative specifications remain in English unless a separately governed translation is later introduced. This avoids creating two competing normative texts.

## 2. Governing authority hierarchy

The documentation system must preserve the repository invariants in `AGENTS.md`.

Authority order is:

```text
normative specifications / grammar / static semantics
schemas / IR / value models / ABI / canonical hashing
conformance contracts and receipts
                    ↓
implementation witnesses
Python / JavaScript / C# / Unity / other runtimes
                    ↓
human documentation
Tutorial / Reference / HOWTO / API / CLI / Glossary
```

Consequences:

1. a tutorial example cannot establish semantics;
2. implementation behavior that contradicts normative authority is a conformance defect, not a documentation feature;
3. documentation that contradicts normative authority is a documentation defect;
4. a public API or CLI behavior not covered by normative or implementation evidence must be marked unsupported or unresolved, never guessed;
5. historical documentation must not look current merely because it remains in the repository.

## 3. Documentation architecture

The current documentation has valuable historical and specialist material, especially for V1 and platform certification, but it does not yet provide one coherent current-language navigation model.

The new user-facing documentation root will be:

```text
docs/manual/
    README.md
    getting-started/
    tutorial/
    language-reference/
    library-reference/
    cli-reference/
    howto/
    integrations/
    diagnostics/
    internals/
    versions/
    glossary.md
    faq.md
    documentation-policy.md
    DOCUMENTATION_COVERAGE_V1.json
```

Paths use stable English technical names. The primary page content is Spanish.

This hierarchy deliberately separates material by reader intent rather than by repository implementation module.

### 3.1 Landing page

`docs/manual/README.md` is the current documentation front door.

It must answer immediately:

- What is TEVScript?
- Which language/package version is this documentation describing?
- What should a new user read first?
- Where is the exact language reference?
- Where is the CLI/API reference?
- Where are integrations?
- Where are errors explained?
- Where are normative specifications?
- How are historical V1/V2/V3 documents distinguished from current 3.1 documentation?

The landing page must not contain release-governance history beyond a concise current identity block and links to the version pages.

### 3.2 Getting Started

Purpose: installation, first successful check/compile/run cycle, editor tooling, project anatomy, and the smallest useful mental model.

Minimum pages:

```text
getting-started/installation.md
getting-started/first-program.md
getting-started/cli-workflow.md
getting-started/project-layout.md
getting-started/editor-lsp.md
getting-started/mental-model.md
```

A reader must be able to go from an installed package to a checked, compiled and executed Total-Core program without reading implementation code or normative specifications.

### 3.3 Tutorial

Purpose: teach the language progressively through executable programs.

The tutorial is explanatory rather than exhaustive. It teaches concepts in dependency order.

Planned sequence:

```text
01-values-and-exactness
02-names-bindings-and-expressions
03-control-and-bounds
04-functions-and-types
05-data-models
06-state-and-events
07-capabilities-and-effects
08-modules-and-composition
09-field-transformation-apply
10-processes-and-continuations
11-v4-units
12-total-core
13-proof-admissions
14-checkpoints-and-replay
15-complete-application
```

Historical constructs that are compatibility-only must be identified as such when they appear.

### 3.4 Language Reference

Purpose: exact, complete lookup of source language rules.

It must be terse enough for lookup but detailed enough that a programmer does not need to inspect parser/compiler source to answer a language question.

Required topics include:

```text
lexical structure
comments
identifiers and reserved words
literals
exact integer/rational values
text values
compound/canonical values
types and type compatibility
expressions
operators and precedence
bindings
declarations
functions
bounded computation
recursion contracts where applicable
effect constructs
state/event constructs
modules/imports where applicable
semantic-process declarations
Field / Transformation / Apply
Total-Core unit declarations
invoke_v4
proof requirements/admissions
resource bounds
failure semantics
source-to-IR boundary
```

Every syntax production documented here must state which current source profile owns it.

### 3.5 Library Reference

Purpose: document public programmatic APIs exposed by the Python reference package and other supported embedding surfaces.

The initial scope is the Python package because it is the current compiler/tooling reference implementation. Other runtime-specific APIs receive their own subsections only where they are public and supported.

For each public symbol:

```text
qualified name
purpose
signature
parameters
return value
exceptions/diagnostics
side effects
canonical identity implications
version/profile applicability
minimal example
related symbols
```

Private compatibility helpers are not promoted to public API merely because they can be imported.

A machine-readable public-surface inventory must be used to detect undocumented public symbols.

### 3.6 CLI Reference

Purpose: exhaustive current CLI lookup.

The generic `tev-script` surface must document:

```text
--version
describe
descriptor
check
compile
run
conformance
platform-check
```

Every command page must include:

```text
synopsis
arguments
options
accepted files/artifacts
stdout/stderr contract
exit codes
canonical JSON output shape where applicable
positive example
negative example
version/profile
related commands
```

Explicit historical commands (`tev-script-v1`, `tev-script-v2`, `tev-script-v3`, etc.) are documented under compatibility/version pages rather than mixed into the current quick-start path.

### 3.7 HOWTO Guides

Purpose: solve task-oriented problems without forcing the reader through the whole tutorial.

Initial HOWTO set:

```text
howto/model-state-machine.md
howto/use-field-transformations.md
howto/design-capabilities.md
howto/handle-domain-failure.md
howto/use-checkpoints.md
howto/build-multifile-project.md
howto/embed-from-python.md
howto/create-deterministic-adapter.md
howto/test-a-tevscript-program.md
howto/debug-a-diagnostic.md
```

HOWTOs explain choices and trade-offs but link back to the exact reference rule for semantics.

### 3.8 Integrations

Purpose: explain supported host boundaries without pretending host behavior is TEVScript language semantics.

Initial integration families:

```text
integrations/python.md
integrations/javascript.md
integrations/csharp.md
integrations/unity.md
integrations/browser-wasm.md
integrations/wasi.md
integrations/filesystem.md
```

Each integration page must explicitly distinguish:

```text
TEVScript semantic contract
adapter/provider responsibility
host-specific approximation/conversion
authority/capability grant
unsupported deployment assumptions
```

### 3.9 Diagnostics Reference

A programmer must not need to grep source code to understand an error code.

The diagnostic reference will organize errors by family and code, for example:

```text
TEVS_V31_SOURCE_VERSION
TEVS_V31_SOURCE_UNIT_DUPLICATE
TEVS_V31_SOURCE_UNIT_SET
TEVS_V31_SOURCE_EFFECT_INPUT_REQUIRED
...
```

Every diagnostic entry contains:

```text
code
phase
meaning
trigger condition
minimal failing source/input
actual expected diagnostic
corrected source/input
related rule
```

Diagnostics must be covered by executable negative tests. A documented error that no longer exists is a failing documentation test.

### 3.10 Internals

Purpose: advanced implementation and contributor material.

Topics include:

```text
frontend pipeline
source semantic identity
canonical JSON
IR V2/V3/V4/V5 relationships
Total-Core composition
runtime quanta
checkpoint identity
proof admission boundary
capability/provider boundary
cross-runtime conformance
reproducible package identity
```

Internals pages explain architecture but must link to normative specifications instead of duplicating them wholesale.

### 3.11 Versions and Compatibility

Package version, language version, source profile, linked-program schema, Program IR version, runtime ABI and checkpoint version are independent domains.

The documentation must make this visible rather than presenting one ambiguous "TEVScript version".

Minimum pages:

```text
versions/current.md
versions/version-domains.md
versions/compatibility.md
versions/v1.md
versions/v2.md
versions/v3.md
versions/v31.md
versions/deprecations.md
```

Historical content already present in the repository remains preserved. New navigation must clearly label it as historical/compatible/current according to `spec/TEV_SCRIPT_VERSION_MATRIX.json`.

## 4. Executable documentation

Documentation examples are test assets.

### 4.1 Canonical example source tree

Add:

```text
examples/docs/v31/
    getting_started/
    tutorial/
    language/
    cli/
    howto/
    diagnostics/
    integrations/
```

Each executable case may contain:

```text
main.tevs                 primary source shown by the manual
<unit>.tevs               optional V4 child sources
effect-input.json         optional effect input
proof-admission.json      optional proof admission
case.json                 execution/validation contract
```

`case.json` is the machine-readable documentation-test contract for that example. It records the appropriate operation (`check`, `compile`, `run`, or expected failure), any unit mappings, external inputs, expected status, expected diagnostic code, and bounded runtime parameters.

### 4.2 Exact source binding

Executable code shown in Markdown must be bound to a canonical example file with an immediately preceding directive:

```text
<!-- tevdoc-source: examples/docs/v31/tutorial/01_exact/main.tevs -->
```

The next fenced source block must be byte-equivalent to the referenced UTF-8 file after only LF/CRLF normalization and optional removal of one terminal newline. No other normalization is allowed.

For a documented negative example, the source binding is followed by:

```text
<!-- tevdoc-expect-diagnostic: TEVS_EXACT_CODE -->
```

The documentation validator must reject:

```text
missing referenced source
source/fence drift
multiple source directives for one fence
negative example without matching case.json expectation
unexpected diagnostic
example that succeeds when failure was documented
example that fails when success was documented
```

This makes the source file the single executable copy while keeping the complete code visible in the documentation.

### 4.3 Positive examples

Every positive example must run through the appropriate current checker/compiler/runtime path and prove the documented outcome.

### 4.4 Negative examples

Every diagnostic example must deliberately fail and assert the exact diagnostic code or fail-closed status being taught.

A negative test passing unexpectedly is a documentation failure.

## 5. Documentation coverage manifest

The exact machine-readable coverage artifact is:

```text
docs/manual/DOCUMENTATION_COVERAGE_V1.json
```

It records coverage for current public surfaces, at minimum:

```text
language constructs
current CLI commands/options
public Python API symbols
current source profiles
current IR/runtime profiles
diagnostic codes
integrations/adapters
version domains
```

Each entry identifies its documentation page and evidence/test where applicable.

Coverage does not create semantic authority. It proves that the human documentation has not omitted an already-authoritative public surface.

The documentation validation gate must fail if a required current surface has no documentation mapping.

## 6. Documentation validator

The exact local validator entry point is:

```text
tools/validate_documentation_v31.py
```

It must be deterministic and network-free.

Responsibilities:

1. validate internal documentation links and referenced repository paths;
2. validate version identity statements against current version sources/matrix;
3. validate coverage-manifest closure;
4. validate every `tevdoc-source` binding;
5. load and validate each example `case.json`;
6. compile/check executable examples;
7. execute runnable examples where deterministic and bounded;
8. assert expected negative diagnostics;
9. reject current pages that refer to obsolete current-version identities;
10. ensure historical pages are marked as historical/compatibility material;
11. report machine-readable PASS/FAIL details.

The validator is a documentation-quality gate only. A top-level convenience runner may expose it through existing platform validation, but it must not become a second language or certification authority.

## 7. Error-correction protocol discovered during documentation

Documentation work is also an audit of the public contract.

Every contradiction found is classified before modification:

```text
DOC_BUG
    documentation contradicts valid authority/implementation

IMPLEMENTATION_BUG
    implementation contradicts normative authority

SPEC_BUG
    normative texts contradict each other or are incomplete

VERSION_GOVERNANCE_BUG
    package/language/predecessor/publication identities disagree

TEST_GAP
    behavior is intended but no regression witness protects it
```

Correction rule:

```text
reproduce contradiction
    ↓
write failing focused test/check
    ↓
identify authoritative expected behavior
    ↓
make minimum correction
    ↓
run focused regression
    ↓
run documentation validation
    ↓
run causally required repository validation
```

No contradiction is "fixed" by editing the prose to match accidental implementation behavior.

## 8. First confirmed defect: published predecessor identity

The design audit has already found a concrete current-main inconsistency.

Current human status/README material identifies package `3.1.1` as the immutable immediate published predecessor of candidate package `3.1.2`.

However `tev_script/version.py` currently contains:

```python
PUBLISHED_PREDECESSOR_PACKAGE_VERSION = "3.1.0"
```

and current platform specification text also contains a `published_predecessor_package = 3.1.0` statement while separately acknowledging `3.1.1` as immediate predecessor.

Expected correction direction:

```text
current package candidate       = 3.1.2
current language                = 3.1.0
immediate published predecessor = 3.1.1
archived V31 predecessor        = 3.1.0
```

This must be implemented only after a focused failing version-identity test is added. The exact files changed will be determined by current-main evidence during implementation, but every current source of the predecessor identity must converge on the distinction above.

This correction must not alter TEVScript language semantics.

## 9. Public-surface inventory

Before declaring documentation complete, implementation must inventory current `main` rather than relying on memory.

The inventory includes:

```text
current generic CLI parser
version/descriptor/platform metadata
source frontend modules
public Python exports
source-profile grammar/static semantics
diagnostic constructors/codes
runtime entry points
checkpoint/public artifact types
adapter entry points
examples
version matrix
normative index
```

The inventory result must drive `DOCUMENTATION_COVERAGE_V1.json`.

An undocumented implementation-private helper does not become public merely because the inventory sees it. Publicness must be based on declared entry points, exports, documented embedding contract, or existing compatibility commitment.

## 10. Language-reference completeness criterion

The language reference is complete only when every current source form accepted by the supported 3.1 frontend is either:

1. documented as current syntax/semantics;
2. explicitly documented as inherited compatibility syntax;
3. explicitly documented as internal/non-user source representation;
4. rejected by the current frontend.

There must be no fifth category "accepted but unexplained".

## 11. API-reference completeness criterion

The Python API reference is complete only when every supported public symbol has one canonical reference entry.

The project must distinguish:

```text
PUBLIC_SUPPORTED
PUBLIC_COMPATIBILITY
INTERNAL
DEPRECATED
```

A leading underscore is evidence of internal intent but is not the sole rule when an existing compatibility contract says otherwise.

## 12. Diagnostic completeness criterion

For current profiles:

```text
all deliberately user-visible structured diagnostic codes
        ⊆
DOCUMENTATION_COVERAGE_V1
```

Compiler-internal exceptions that represent defects rather than user diagnostics are not documented as normal language errors; they belong in contributor/debugging material.

## 13. Style rules

Documentation must be technically precise without reading like certification receipts.

Rules:

1. explain a concept before introducing its formal edge cases;
2. define every TEVScript-specific term on first pedagogical use;
3. use small examples before complete examples;
4. distinguish **language**, **compiler**, **runtime**, **host**, **capability**, and **physical effect** consistently;
5. never use "state" ambiguously when Field state, entity state, host state or checkpoint state differ;
6. never imply floating-point approximation where exact rational semantics applies;
7. never describe capability declaration as capability authority;
8. never describe a hash as proof of truth;
9. never describe proof admission as proof generation;
10. explain failure modes adjacent to successful use;
11. prefer links over duplicating normative paragraphs;
12. examples must show complete required context rather than unexplained ellipses when the omitted material affects validity.

## 14. Historical-document policy

Existing historical documents are valuable evidence and must not be deleted merely to simplify navigation.

Instead:

1. current manual pages link to historical material only where useful;
2. historical documents retain their original claims with explicit historical context where necessary;
3. the README and manual landing page identify current 3.1 documentation first;
4. search/navigation should not make a V1 tutorial look like the default current language reference;
5. compatibility pages explain why an older document still exists.

## 15. Phased implementation

The implementation is large enough to require independently testable phases while remaining on one documentation branch unless governance requires otherwise.

### Phase A — foundation and truth audit

```text
current-main inventory
version/predecessor defect regression + correction
documentation root/navigation
documentation coverage schema/manifest
documentation validator foundation
current-version page
glossary foundation
```

### Phase B — Getting Started + CLI

```text
installation
first program
project layout
CLI workflow
complete current generic CLI reference
executable examples
```

### Phase C — Tutorial

Implement the progressive tutorial and its canonical example assets.

### Phase D — Language Reference

Close current 3.1 source syntax/static-semantics coverage against the authoritative frontend/specifications.

### Phase E — Library/API Reference

Close supported Python embedding/tooling surface and runtime artifact APIs.

### Phase F — Diagnostics

Inventory, classify, document and test current structured user-facing diagnostics.

### Phase G — HOWTO + integrations

Task guides and host boundaries, including Unity and supported runtimes/adapters.

### Phase H — internals, compatibility and full closure

Close architecture, IR/runtime relationships, historical/version navigation, FAQ, complete coverage manifest and full documentation validation.

## 16. Testing strategy

Every implementation phase uses TDD for tooling or behavior changes.

Minimum validation layers:

```text
FOCUSED_DOC_TOOL_TESTS
EXAMPLE_POSITIVE_TESTS
EXAMPLE_NEGATIVE_TESTS
DOC_LINK_AND_PATH_VALIDATION
PUBLIC_SURFACE_COVERAGE
VERSION_IDENTITY_COHERENCE
EXISTING_RELEVANT_TESTS
REPOSITORY_VALIDATION_SELECTED_BY_GOVERNANCE
```

No documentation-only claim may be used to downgrade an existing certification requirement.

Long full-repository validation should be deferred until the end of coherent batches, but focused tests must run immediately after each correction.

## 17. Non-goals

This documentation project does not by itself:

- redesign TEVScript syntax;
- add new semantic primitives;
- replace normative specifications;
- replace `.tev` or `.tevg` workflow kernels;
- make Python the language authority;
- create a new runtime;
- grant physical capabilities;
- change Stable Admission/publication policy;
- merge or publish releases automatically;
- delete historical evidence.

If documentation reveals a semantic defect requiring language design, that defect is split into its own governed design rather than smuggled into documentation work.

## 18. Definition of Done

The project is complete only when all of the following are true on one exact clean source identity:

```text
CURRENT_DOC_LANDING=PASS
GETTING_STARTED_COMPLETE=PASS
TUTORIAL_COMPLETE=PASS
LANGUAGE_REFERENCE_CURRENT_SURFACE=PASS
LIBRARY_REFERENCE_PUBLIC_SURFACE=PASS
CLI_REFERENCE_CURRENT_SURFACE=PASS
HOWTO_CORE_SET=PASS
INTEGRATION_REFERENCE_SUPPORTED_SURFACE=PASS
DIAGNOSTIC_REFERENCE_CURRENT_CODES=PASS
GLOSSARY_CURRENT_TERMS=PASS
VERSION_COMPATIBILITY_DOCS=PASS
HISTORICAL_NAVIGATION_UNAMBIGUOUS=PASS
DOCUMENTATION_COVERAGE_MANIFEST=PASS
EXECUTABLE_POSITIVE_EXAMPLES=PASS
EXECUTABLE_NEGATIVE_EXAMPLES=PASS
INTERNAL_LINKS_AND_PATHS=PASS
VERSION_IDENTITY_COHERENCE=PASS
NO_UNDOCUMENTED_CURRENT_PUBLIC_SURFACE=PASS
NO_DOCUMENTED_NONEXISTENT_CURRENT_SURFACE=PASS
RELEVANT_REGRESSION=PASS
FULL_REQUIRED_REPOSITORY_VALIDATION=PASS
MERGE_AUTHORITY=FALSE
PUBLICATION_AUTHORITY=FALSE
```

The final manual must let a competent programmer learn and use TEVScript without reverse-engineering the repository, while still allowing an expert to trace every important statement back to the normative language/platform authority.

## 19. Immediate next step after user review

After this design is reviewed and accepted, create the detailed implementation plan using the repository's planning workflow.

Implementation starts with Phase A and the already-identified predecessor-version contradiction under TDD. No compiler/runtime semantics are modified unless the evidence classifies a newly discovered issue as an implementation defect against normative authority.