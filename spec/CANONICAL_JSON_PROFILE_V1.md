# TEV Canonical JSON Profile V1

## Scope

`TEV_CANONICAL_JSON_V1` defines the exact byte representation used for semantic
hashes, conformance receipts, manifests, and cross-runtime equality. It is a
closed profile, not an appeal to a host language's default JSON serializer.

## Input domain

The canonicalizer accepts only:

- `null`, booleans, strings;
- structural integers in `[-9007199254740991, 9007199254740991]`;
- arrays preserving element order;
- objects with unique string keys;
- semantic `Int` and `Rat` values already encoded using the tagged portable
  value model.

Floating-point JSON numbers, negative zero, duplicate object members,
non-string object keys, NaN, infinities, and host-specific values are forbidden.

## Strict file-loading boundary

Before canonicalization or execution, JSON files used as program IR, scenarios,
receipts, schemas, or vectors must be decoded as valid UTF-8 and parsed without
lossy host coercions. A loader must reject:

1. malformed UTF-8 or JSON syntax;
2. duplicate object members before constructing the host object;
3. any decimal fraction or exponent notation;
4. structural integers outside the portable safe range;
5. the non-canonical structural spelling `-0`;
6. non-standard constants such as `NaN` or `Infinity`.

Arbitrary semantic integers remain valid only as canonical decimal strings in
`{"$int":"..."}`. Exact rationals remain valid only through `{"$rat":[...,...]}`.

## Serialization

1. Emit UTF-8 with no byte-order mark.
2. Emit no insignificant whitespace.
3. Serialize `null`, booleans, and structural integers in lowercase JSON form.
4. Escape `"`, `\\`, backspace, form feed, newline, carriage return, and tab
   using the short JSON escapes.
5. Escape every other code unit outside printable ASCII `U+0020..U+007E` as a
   lowercase `\\uXXXX` sequence. Astral characters therefore use two escaped
   UTF-16 surrogate code units.
6. Sort object keys lexicographically by Unicode scalar value. Preserve strings
   exactly; perform no Unicode normalization.
7. Serialize arrays in source order and objects in sorted key order.
8. Compute hashes as lowercase SHA-256 hexadecimal over canonical UTF-8 bytes.
9. A canonical receipt is the canonical JSON text followed by exactly one LF.

## Relationship to RFC 8785

This profile has the same objective as the JSON Canonicalization Scheme but is
not RFC 8785/JCS compatible. TEV deliberately forbids floating-point numbers,
uses tagged exact arithmetic, escapes all non-ASCII code units, and sorts keys
by Unicode scalar value. Implementations must identify this profile explicitly
as `TEV_CANONICAL_JSON_V1` and must not label its output as JCS.

## Conformance

`conformance/canonical.vectors.json` is normative. A runtime must reproduce the
listed text and SHA-256 values exactly and pass the strict-input negatives
before its canonicalizer can be used as hash authority.
