from __future__ import annotations

from dataclasses import dataclass

from .canonical import canonical_hash

_HEX = frozenset("0123456789abcdef")
_STRONG_METHODS = frozenset({"proved", "attested", "exhaustive"})
_METHODS = _STRONG_METHODS | {"sampled", "assumed"}
_STATUSES = frozenset({"active", "revoked", "falsified"})


def _hash64(value: str, name: str) -> str:
    text = str(value)
    if len(text) != 64 or any(ch not in _HEX for ch in text):
        raise ValueError(name)
    return text


@dataclass(frozen=True, slots=True)
class ProofBoundaryWitnessV0:
    proof_hash: str
    verifier_hash: str
    scope_hash: str
    method: str
    status: str = "active"

    def __post_init__(self) -> None:
        _hash64(self.proof_hash, "proof_hash")
        _hash64(self.verifier_hash, "verifier_hash")
        _hash64(self.scope_hash, "scope_hash")
        if self.method not in _METHODS:
            raise ValueError("proof method")
        if self.status not in _STATUSES:
            raise ValueError("proof status")

    @property
    def witness_hash(self) -> str:
        return canonical_hash(
            {
                "schema": "TEV_SCRIPT_PROOF_BOUNDARY_WITNESS_V0",
                "proof_hash": self.proof_hash,
                "verifier_hash": self.verifier_hash,
                "scope_hash": self.scope_hash,
                "method": self.method,
                "status": self.status,
            }
        )

    def intrinsically_strong(self, expected_scope_hash: str) -> bool:
        return (
            self.scope_hash == expected_scope_hash
            and self.status == "active"
            and self.method in _STRONG_METHODS
        )


@dataclass(frozen=True, slots=True)
class VerifierTrustPolicyV0:
    trusted_verifier_hashes: tuple[str, ...]

    def __post_init__(self) -> None:
        canonical = tuple(
            sorted(
                set(
                    _hash64(value, "trusted_verifier_hash")
                    for value in self.trusted_verifier_hashes
                )
            )
        )
        object.__setattr__(self, "trusted_verifier_hashes", canonical)

    @property
    def policy_hash(self) -> str:
        return canonical_hash(
            {
                "schema": "TEV_SCRIPT_VERIFIER_TRUST_POLICY_V0",
                "trusted_verifier_hashes": list(self.trusted_verifier_hashes),
            }
        )

    def accepts(
        self,
        witness: ProofBoundaryWitnessV0,
        expected_scope_hash: str,
    ) -> bool:
        return (
            witness.intrinsically_strong(expected_scope_hash)
            and witness.verifier_hash in self.trusted_verifier_hashes
        )


__all__ = ["ProofBoundaryWitnessV0", "VerifierTrustPolicyV0"]
