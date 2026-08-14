# TEV Script V2 Complete Closure Design

**Date:** 2026-08-14

**Status:** Approved for implementation by the repository owner on 2026-08-14.

## Objective

Replace the earlier V2 probe tree with a new exact candidate that is safe against
filesystem path races, enforces the 1 MiB observation budget before admitting
content, defines its own normative authority, exposes a complete V2 CLI, and is
certified by an independent V2 gate. Publication, pull-request creation, and merge
remain outside the authorization for this phase.

## Safety model

`file.read` and `file.replace` operate on a root-scoped filesystem capability.
The authority is the opened root directory object, not merely a path string.
Every operation must remain anchored to that object while resolving descendants.

The shared filesystem layer will expose an opaque scoped-root object and two
operations:

```python
open_scoped_root_v2(root: str | os.PathLike[str]) -> ScopedFilesystemRootV2
read_scoped_file_v2(root: ScopedFilesystemRootV2, relative: str, *, maximum_bytes: int) -> ScopedFileReadV2
replace_scoped_file_v2(root: ScopedFilesystemRootV2, relative: str, data: bytes) -> ScopedFileReplaceV2
```

The object owns an OS directory handle until closed. Its authority hash binds the
canonical host path, platform, volume/device identity, and directory file identity.
Reopening the same spelling after the directory object has been replaced therefore
does not silently reuse the former grant.

On POSIX, resolution uses `dir_fd`, `O_DIRECTORY`, and `O_NOFOLLOW` one component
at a time. Reads use a descriptor opened relative to the pinned parent. Replacements
create and fsync a unique temporary file relative to the pinned parent, then rename
it with `src_dir_fd` and `dst_dir_fd` before fsyncing the directory.

On Windows, resolution uses standard-library `ctypes` bindings to Win32 handles.
Directories and files are opened with `FILE_FLAG_OPEN_REPARSE_POINT`; opened handles
are checked for reparse tags and regular-file/directory kind. Final paths and stable
file identities are checked against the pinned root. Temporary files are validated
by handle and renamed relative to the pinned parent with
`SetFileInformationByHandle`; cleanup targets the opened temporary handle. No
security decision relies on an earlier `lstat` followed by a path-name operation.

If the required primitives or post-open identity checks are unavailable, the
operation fails closed with a stable TEV diagnostic. There is no path-based fallback.

## Bounded observation admission

`file.read` opens the target securely and consumes at most
`MAX_FILE_READ_BYTES_V2 + 1` bytes. The extra byte is only an overflow witness. If it
exists, the operation emits `TEVS_FILE_READ_BUDGET` without decoding, hashing, or
materializing the rest of the file. File metadata size is an optional early reject,
never the sole authority because files may change while open.

The admitted byte sequence is decoded as UTF-8 and hashed only after the bounded
read succeeds. Evidence continues to bind the canonical relative path, root scope,
provider descriptor, exact byte count, and SHA-256 content identity.

## Replace semantics and linearization

`file.replace` accepts exactly one intent. The linearization point is the atomic
same-directory rename of a fully written and fsynced temporary file. Verification
uses the still-open temporary/replaced file handle, not a new path lookup. A
same-content no-op is permitted only when a securely opened target handle proves the
content at its own linearization point. Concurrent changes after either
linearization point are external operations and do not reinterpret the receipt.

Existing final-component symlinks/reparse points are rejected. Parent replacements,
junction swaps, and symlink swaps cannot redirect an operation outside the pinned
root. A race either continues on the already-pinned authorized directory or fails
closed.

## Normative V2 authority

V2 receives versioned authority independent of the V1 release claim:

- `spec/TEV_SCRIPT_V2_LANGUAGE.md` defines source grammar, static semantics,
  boundedness, capability boundaries, and excluded behavior;
- `spec/TEV_SCRIPT_PROGRAM_IR_V4.md` defines all Program IR V4 profiles,
  canonical JSON, validation, execution, and receipt rules;
- `spec/TEV_SCRIPT_V2_FILESYSTEM_CAPABILITIES.md` defines the handle-anchored
  filesystem threat model and linearization rules;
- `spec/TEV_SCRIPT_V2_FEATURE_MATRIX.json` enumerates normative implementation,
  schema, conformance, gate, and public-interface paths;
- JSON Schemas validate the descriptor, Program IR V4 envelope/profile closure,
  filesystem artifacts, and V2 certification receipt;
- `CANONICAL_INDEX.json` indexes the V2 authority without replacing V0.2 or V1;
- `tev-script-v2` is an installed entry point, and its descriptor reports the
  normative paths and schema identities.

The specifications are the authority. Python remains a reference implementation.

## V2 certification

`RUN_TEV_SCRIPT_V2_CERTIFY_FULL.py` is a separate gate. It does not treat a V1
certificate as proof of V2. It binds the exact Git commit and tree and fails on a
dirty worktree. Its canonical receipt records these mandatory gates:

1. authority inventory and canonical-index closure;
2. JSON Schema self-validation and governed fixture validation;
3. descriptor and installed/module CLI surface;
4. V2 source/static-semantics and Program IR V4 conformance tests;
5. filesystem handle safety, deterministic race injections, and 1 MiB pre-admission;
6. V2 negative/fail-closed tests;
7. complete V2 regression selection with zero skips;
8. V1 non-regression certificate identity supplied by a fresh V1 certification run.

The V2 gate emits `CERTIFY_V2=PASS` only when every mandatory gate passes. It emits
no stable-language or publication claim. Receipt bytes use strict canonical JSON and
are validated against the V2 certification schema before success.

## Browser teardown closure

The Windows browser-profile cleanup helper must treat PowerShell failure, timeout,
or surviving matching processes as a gate failure with diagnostics. The Python
subprocess receives a bounded timeout greater than the PowerShell internal deadline.
Tests cover success, nonzero exit, and timeout. Browser gates continue to match only
the exact unique profile path and must not select unrelated browser processes.

## Verification and freeze

Implementation proceeds test-first and in reviewable commits. The final phase runs:

- focused filesystem and race tests with zero skips;
- focused authority/schema/CLI/certification negatives;
- the entire Python regression suite;
- fresh V1 global and Python product certification;
- fresh V2 certification;
- `git diff --check` and repository connectivity checks.

The resulting branch must be clean. The final handoff records base SHA, HEAD SHA,
tree SHA, changed-path count, certificate hashes, and artifact hashes. It performs no
push, PR, merge, tag, release, or publication.
