# TEV Script V1 linked canonicalization — compatibility alias

Status: **non-normative compatibility alias**.

The normative V1 canonical linked-program authority is:

```text
spec/TEV_SCRIPT_V1_CANONICAL_LINKED_PROGRAM.md
```

This path was materialized after a certification attempt exposed a stale governance reference to `spec/TEV_SCRIPT_LINKED_CANONICALIZATION_V1.md`. The repository already contained the complete canonical linked-program contract under the authoritative filename above.

No independent semantic rules are defined here. Implementations, governance and certification must use `TEV_SCRIPT_V1_CANONICAL_LINKED_PROGRAM.md`, together with:

```text
spec/TEV_SCRIPT_V1_LINK_MODEL.md
spec/CANONICAL_JSON_PROFILE_V1.md
schemas/tev_script_linked_program_v1.schema.json
conformance/v1-linked-program-cases.json
```

This alias is retained only to document the historical path mismatch and to avoid silently deleting a repository artifact introduced while repairing that mismatch.
