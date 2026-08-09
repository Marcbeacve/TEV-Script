# Hot Update Batch 5C→5E V1

## Dependency order

The batch deliberately closes update authority in this order:

```text
5C signed canonical package
  ↓
5D durable monotonic replay authority
  ↓
5E network transport of untrusted bytes
```

Network transport never receives direct runtime authority.

## Gate 5C — signed canonical package

The signed body contains:

- schema;
- channel id;
- program id;
- epoch;
- sequence;
- program semantic hash;
- full canonical IR hash;
- full canonical IR.

V1 uses ECDSA over NIST P-256 with SHA-256 (`ES256`) and an explicit
IEEE-P1363 fixed-width 64-byte `r || s` signature.

The runtime receives only a public-key verifier. The fixed private keys used
by the campaign exist exclusively inside the fixture-generation executable.

Production key provisioning, key rotation and compromise recovery are not
certified by Gate 5C.

## Gate 5D — replay resistance with durable local continuity

An accepted package is stored as a canonical durable record containing the
whole signed package, its SHA-256, epoch and sequence.

Rules:

- bootstrap: epoch 1 / sequence 1;
- same epoch: sequence strictly increases;
- epoch may advance by exactly one;
- a new epoch starts at sequence 1;
- old epoch, duplicate/replay, invalid epoch transition and stale update plan
  fail closed.

The runtime swap and durable-state write are coupled. If the durable write
fails, the just-committed runtime is rolled back.

At restart the stored signed package is parsed, signature-verified and restored
into a fresh runtime host before remote update checking continues.

Gate 5D does **not** claim protection against an attacker capable of rolling
back, deleting or replacing the durable store itself. That requires a stronger
monotonic authority such as protected hardware or an independently trusted
server-side monotonic anchor.

## Gate 5E — transport boundary

Gate 5E uses a real Windows x64 IL2CPP Player and `UnityWebRequest` against a
loopback HTTP server.

The transport supplies untrusted bytes only:

```text
download
→ strict canonical package parse
→ signature verification
→ durable replay check
→ Gate-5A PrepareSwap
→ runtime commit
→ durable installed-package commit
```

The campaign includes:

- valid package activation;
- replay rejection;
- signed-body tampering rejection;
- truncated JSON rejection;
- HTTP 500 rejection;
- a second valid monotonic update;
- Player restart and installed-package restoration;
- replay rejection after restart;
- next-epoch activation.

Gate 5E proves the network/update integration boundary and IL2CPP execution on
loopback HTTP. Public WAN routing, TLS/PKI, DNS, CDN behavior and service
availability remain outside this gate.
