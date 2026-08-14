# TEV Script V2 Filesystem Capability Specification

## 1. Scope

This document defines the only conforming V2 physical filesystem profiles:

```text
observation file.read(Text) -> Text
command     file.replace(Text, Text)
```

It supplements the V2 language and Program IR V4 specifications. No path string,
working directory, process environment, or ambient host permission is TEV authority.

## 2. Threat model

The authorized root, any intermediate directory, and the final directory entry may
be concurrently renamed or replaced by another process between any two ordinary
path-name system calls. An attacker may substitute a symbolic link, junction, mount
reparse point, directory, device, or other non-regular object. File size and content
may change while open.

A provider is conforming only if such changes cannot redirect a read or write outside
the opened authorized root object. An implementation that cannot obtain the required
OS primitives fails closed; it does not fall back to `lstat` followed by path access.

## 3. Root authority

The provider opens the root as a directory without following a final symbolic link or
reparse point. It retains that handle for the complete acquisition or provider
lifetime. The root must be a directory and not a reparse object.

`authority_scope_hash` binds canonical root spelling, platform family, volume/device
identity, and directory file identity in:

```json
{
  "schema": "TEV_SCRIPT_SCOPED_FILESYSTEM_ROOT_V2_V1",
  "canonical_root": "…",
  "platform": "windows|posix",
  "volume_identity": "…",
  "file_identity": "…"
}
```

The SHA-256 hash uses canonical JSON without a self-hash field. Replacing a directory
with another object at the same spelling does not preserve authority. Renaming the
opened directory does not redirect the retained handle.

## 4. Relative path admission

The path argument is Text and must be nonempty and contain no NUL. It is split on `/`
or `\`; the canonical receipt spelling joins admitted segments with `/`.

The following are rejected before filesystem access:

- absolute, UNC, rooted, or drive-qualified paths;
- empty, `.` or `..` segments;
- a segment ending in space or dot;
- colon or alternate-data-stream syntax;
- case-insensitive Windows device stems `CON`, `PRN`, `AUX`, `NUL`, `COM1..COM9`, or
  `LPT1..LPT9` with or without an extension.

Every intermediate segment must be opened relative to the currently pinned directory
handle without following the final segment. It must resolve to a non-reparse
directory. A final read target must be a non-reparse regular file.

On POSIX, conforming primitives are descriptor-relative open/rename with
`O_DIRECTORY`, `O_NOFOLLOW`, `O_NONBLOCK` for final read candidates, and directory
FDs. A FIFO, device, socket, or other special final object is rejected from opened
descriptor metadata without waiting for a peer. On Windows, conforming primitives are
root-handle-relative NT opens with `FILE_OPEN_REPARSE_POINT`, post-open type/identity
inspection, and handle-relative rename. Equivalent kernels MAY be used if they prove
the same properties.

## 5. `file.read` acquisition

The entire acquisition retains one root handle. Parallel workers duplicate that
handle; worker count is operational and nonsemantic.

The target is opened once through the handle-relative policy. The provider reads at
most 1,048,577 bytes: the 1,048,576-byte admission budget plus one overflow witness.
It MAY reject earlier from opened-handle metadata, but metadata is never sole proof of
admissibility. It MUST NOT call an unbounded whole-file read before the decision.

If the overflow witness exists, acquisition returns `TEVS_FILE_READ_BUDGET`. Rejected
content is not decoded, hashed, included in evidence, or consumed further. Admitted
bytes must decode as strict UTF-8. Evidence binds exact byte count and SHA-256.

The observation is a snapshot at the opened file handle. Later host changes do not
alter the scenario derived from evidence. Runtime execution replays the scenario and
never reads the host.

## 6. `file.replace` commit

The provider accepts one `file.replace` intent per batch. The authority grant binds:

- exact batch hash;
- exact provider descriptor hash and implementation closure;
- exact root authority scope hash;
- exact `file.replace` contract hash.

The parent is opened and retained by handle-relative traversal. The provider creates
a unique non-reparse temporary regular file relative to that parent, writes all UTF-8
data, flushes it, rewinds and verifies the exact bytes through the same handle, then
atomically renames that handle to the requested final segment relative to the same
parent. POSIX additionally fsyncs the parent directory where supported. Windows uses
the filesystem's same-volume handle-relative rename.

The rename is the replacement linearization point. A concurrent final symlink cannot
redirect the write: it is rejected before planning when observed, or its directory
entry is atomically replaced rather than followed. A concurrent directory target
causes failure. A parent swap cannot affect the pinned parent handle.

A same-content no-op is permitted when a securely opened target proves exact bytes.
Its linearization point is that opened-handle observation. `physical_replace_calls`
does not increment for this replay case. Content-addressed retry after a ledger
boundary therefore yields an identical receipt without a second physical rename.

## 7. Receipts

A file replacement receipt has exact fields:

```text
schema = TEV_SCRIPT_FILE_REPLACE_EFFECT_RECEIPT_V2_V1
intent_hash
command_id = file.replace
authority_scope_hash
relative_path
data_sha256
byte_count
final_sha256
receipt_hash
```

`data_sha256` and `final_sha256` are equal on success. `receipt_hash` binds every
preceding field. A receipt is not proof that no later external process changed the
path; it proves the provider's operation at its declared linearization point.

Read acquisition request/evidence and replacement receipt envelopes conform to
`schemas/tev-script-v2-filesystem-artifacts.schema.json` and their implementation
validators. Unknown fields, malformed hashes, wrong provider pins, scope drift, call
reordering, content drift, and evidence-hash mismatch fail closed.

## 8. Failure and cleanup

Invalid path, inaccessible component, reparse traversal, wrong object kind, root
identity mismatch, unsupported secure primitive, short/nonprogressing write, flush or
rename failure, verification mismatch, oversize read, invalid UTF-8, authority
mismatch, or hash mismatch fails without a PASS receipt or finalized state.

Temporary cleanup addresses the already-open temporary object. It must not perform a
fresh unverified path lookup that can delete another object. Failure after an effect
linearization point is reported as failure and never fabricated as rollback.
