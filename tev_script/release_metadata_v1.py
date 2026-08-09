from __future__ import annotations

# Release metadata is deliberately separate from language semantics.
# The certified Stage-C candidate keeps this file in candidate mode. A later
# release-shaped commit may change only these metadata values (plus the governed
# distribution/documentation files) before STABLE_ADMISSION re-certifies that
# exact Git identity.
RELEASE_PROFILE = "candidate"
RELEASE_STATUS = "IMPLEMENTATION_CANDIDATE_UNCERTIFIED"
STABLE = False
CURRENT_V1_CERTIFY_FULL_CLAIM = False
CURRENT_V1_LANGUAGE_STABLE_CLAIM = False

# Populated only by a release-shaped stable commit. Empty values are required in
# candidate mode so no technical certificate is inherited implicitly.
TECHNICAL_PARENT_COMMIT = ""
TECHNICAL_PARENT_CERTIFICATE_SHA256 = ""

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
