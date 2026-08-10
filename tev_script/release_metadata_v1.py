from __future__ import annotations

# Release metadata is deliberately separate from language semantics.
# This stable-shaped commit is a claim awaiting STABLE_ADMISSION on this exact
# Git identity. Only a successful stable-admission receipt authorizes the claim
# for tagging/publication.
RELEASE_PROFILE = "stable"
RELEASE_STATUS = "STABLE_1_0_0"
STABLE = True
CURRENT_V1_CERTIFY_FULL_CLAIM = True
CURRENT_V1_LANGUAGE_STABLE_CLAIM = True

# Exact technically certified parent P6. The certificate SHA is the canonical
# JSON receipt SHA-256 emitted by CERTIFY_FULL V2, not the physical file SHA.
TECHNICAL_PARENT_COMMIT = "9c79d43a082e8c609d4b85d2cadd5b462f488252"
TECHNICAL_PARENT_CERTIFICATE_SHA256 = "6c5b8e1ab243d4ccd2108c816c83542c6e3fec1b2a69efc0c09e4a85327c0e07"

STABLE_LANGUAGE_VERSION = "1.0.0"


def validate_release_metadata() -> None:
    if RELEASE_PROFILE == "candidate":
        if RELEASE_STATUS != "IMPLEMENTATION_CANDIDATE_UNCERTIFIED":
            raise RuntimeError("TEVS_V1_RELEASE_METADATA_CANDIDATE_STATUS")
        if STABLE or CURRENT_V1_CERTIFY_FULL_CLAIM or CURRENT_V1_LANGUAGE_STABLE_CLAIM:
            raise RuntimeError("TEVS_V1_RELEASE_METADATA_CANDIDATE_CLAIM")
        if TECHNICAL_PARENT_COMMIT or TECHNICAL_PARENT_CERTIFICATE_SHA256:
            raise RuntimeError("TEVS_V1_RELEASE_METADATA_CANDIDATE_PARENT")
        return

    if RELEASE_PROFILE == "stable":
        if RELEASE_STATUS != "STABLE_1_0_0":
            raise RuntimeError("TEVS_V1_RELEASE_METADATA_STABLE_STATUS")
        if not STABLE or not CURRENT_V1_CERTIFY_FULL_CLAIM or not CURRENT_V1_LANGUAGE_STABLE_CLAIM:
            raise RuntimeError("TEVS_V1_RELEASE_METADATA_STABLE_CLAIM")
        if len(TECHNICAL_PARENT_COMMIT) != 40 or any(
            char not in "0123456789abcdef" for char in TECHNICAL_PARENT_COMMIT
        ):
            raise RuntimeError("TEVS_V1_RELEASE_METADATA_PARENT_COMMIT")
        if len(TECHNICAL_PARENT_CERTIFICATE_SHA256) != 64 or any(
            char not in "0123456789abcdef" for char in TECHNICAL_PARENT_CERTIFICATE_SHA256
        ):
            raise RuntimeError("TEVS_V1_RELEASE_METADATA_PARENT_CERTIFICATE")
        return

    raise RuntimeError("TEVS_V1_RELEASE_METADATA_PROFILE")
