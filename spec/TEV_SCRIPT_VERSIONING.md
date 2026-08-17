# TEVScript Versioning and Compatibility

TEVScript versions independent semantic and implementation domains separately. A matching numeric token does not imply compatibility between domains.

The normative machine-readable matrix is `TEV_SCRIPT_VERSION_MATRIX.json`.

## Domains

- `package`: distributable Python package identity.
- `language`: source-language semantic identity.
- `source_profile`: concrete source grammar/profile compiled under a language version.
- `linked_program`: canonical linked source-semantic representation where applicable.
- `program_ir`: executable canonical IR family/profile.
- `runtime_abi`: runtime contract implementing a particular IR/profile.
- `checkpoint`: persistent continuation/restart representation.

## Status

- `current`: first-class platform 3.1 surface.
- `compatible`: preserved and supported compatibility authority, not current semantics.
- `historical`: immutable predecessor evidence; no current compatibility is inferred.

## Resolution rule

A tool or runtime route is valid only when one exact matrix row matches its domain, version and profile. Unsupported or ambiguous routes fail closed. Numeric equality, filename similarity or implementation reuse never creates compatibility authority.

## Current composition

The current 3.1 composition is `language=3.1.0`, `source_profile=total_core`, `program_ir=5/total_core`, `runtime_abi=v5-total-v1`, and `checkpoint=v5-total-checkpoint-v1`. V4 child programs remain compatible embedded artifacts and retain their own identities.

V3 semantic-process, V2 general-language and V1 linked/portable surfaces remain explicit compatibility or historical rows. They are not silently promoted to 3.1 semantics.
