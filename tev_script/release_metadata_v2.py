from __future__ import annotations

RELEASE_PROFILE = "stable"
RELEASE_STATUS = "STABLE_2_0_0"
STABLE = True
CURRENT_V2_CERTIFY_FULL_CLAIM = True
CURRENT_V2_LANGUAGE_STABLE_CLAIM = True
TECHNICAL_PARENT_COMMIT = "64d31f9c726ab82719a152bf551dc524abe82373"
TECHNICAL_PARENT_CERTIFICATE_SHA256 = "49ccf5f6e5c4bf9962ccc6823ecade5f61f616787d3f7c5f0b596b51d4ff1bc7"
STABLE_LANGUAGE_VERSION = "2.0.0"

_HEX = frozenset("0123456789abcdef")


def _is_lower_hex(value: object, length: int) -> bool:
    return (
        isinstance(value, str)
        and len(value) == length
        and all(char in _HEX for char in value)
    )


def validate_release_metadata() -> None:
    if STABLE_LANGUAGE_VERSION != "2.0.0":
        raise RuntimeError("TEVS_V2_RELEASE_METADATA_LANGUAGE_VERSION")

    if RELEASE_PROFILE == "candidate":
        if RELEASE_STATUS != "IMPLEMENTATION_CANDIDATE_CERTIFICATION_REQUIRED":
            raise RuntimeError("TEVS_V2_RELEASE_METADATA_CANDIDATE_STATUS")
        if STABLE or CURRENT_V2_CERTIFY_FULL_CLAIM or CURRENT_V2_LANGUAGE_STABLE_CLAIM:
            raise RuntimeError("TEVS_V2_RELEASE_METADATA_CANDIDATE_CLAIM")
        if TECHNICAL_PARENT_COMMIT or TECHNICAL_PARENT_CERTIFICATE_SHA256:
            raise RuntimeError("TEVS_V2_RELEASE_METADATA_CANDIDATE_PARENT")
        return

    if RELEASE_PROFILE == "stable":
        if RELEASE_STATUS != "STABLE_2_0_0":
            raise RuntimeError("TEVS_V2_RELEASE_METADATA_STABLE_STATUS")
        if not STABLE or not CURRENT_V2_CERTIFY_FULL_CLAIM or not CURRENT_V2_LANGUAGE_STABLE_CLAIM:
            raise RuntimeError("TEVS_V2_RELEASE_METADATA_STABLE_CLAIM")
        if not _is_lower_hex(TECHNICAL_PARENT_COMMIT, 40):
            raise RuntimeError("TEVS_V2_RELEASE_METADATA_PARENT_COMMIT")
        if not _is_lower_hex(TECHNICAL_PARENT_CERTIFICATE_SHA256, 64):
            raise RuntimeError("TEVS_V2_RELEASE_METADATA_PARENT_CERTIFICATE")
        return

    raise RuntimeError("TEVS_V2_RELEASE_METADATA_PROFILE")
