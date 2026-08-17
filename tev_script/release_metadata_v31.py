from __future__ import annotations

LANGUAGE_VERSION = "3.1.0"
RELEASE_PROFILE = "stable_request"
RELEASE_STATUS = "STABLE_ADMISSION_REQUESTED"
STABLE = True
PUBLICATION_AUTHORITY = False
MERGE_AUTHORITY = False
TECHNICAL_PARENT_COMMIT = "6c82905cb1343c989b183b7a50b4d67d7b1a5ce9"
TECHNICAL_PARENT_RECEIPT_SHA256 = "1f0c60f8f50322a5dfde69073cbc84e419aebdcf0f46bb99613167a13d8efc46"


def _is_sha(value: str, length: int) -> bool:
    return len(value) == length and all(c in "0123456789abcdef" for c in value)


def validate_release_metadata_v31() -> dict[str, object]:
    if LANGUAGE_VERSION != "3.1.0":
        raise RuntimeError("TEVS_V31_RELEASE_LANGUAGE_VERSION")
    if RELEASE_PROFILE == "candidate":
        if RELEASE_STATUS != "IMPLEMENTATION_CANDIDATE_CERTIFICATION_REQUIRED":
            raise RuntimeError("TEVS_V31_RELEASE_CANDIDATE_STATUS")
        if STABLE or PUBLICATION_AUTHORITY or MERGE_AUTHORITY:
            raise RuntimeError("TEVS_V31_RELEASE_CANDIDATE_AUTHORITY")
        if TECHNICAL_PARENT_COMMIT or TECHNICAL_PARENT_RECEIPT_SHA256:
            raise RuntimeError("TEVS_V31_RELEASE_CANDIDATE_PARENT")
    elif RELEASE_PROFILE == "stable_request":
        if RELEASE_STATUS != "STABLE_ADMISSION_REQUESTED":
            raise RuntimeError("TEVS_V31_RELEASE_STABLE_STATUS")
        if not STABLE or PUBLICATION_AUTHORITY or MERGE_AUTHORITY:
            raise RuntimeError("TEVS_V31_RELEASE_STABLE_AUTHORITY")
        if not _is_sha(TECHNICAL_PARENT_COMMIT, 40):
            raise RuntimeError("TEVS_V31_RELEASE_PARENT_COMMIT")
        if not _is_sha(TECHNICAL_PARENT_RECEIPT_SHA256, 64):
            raise RuntimeError("TEVS_V31_RELEASE_PARENT_RECEIPT")
    else:
        raise RuntimeError("TEVS_V31_RELEASE_PROFILE")
    return {
        "language_version": LANGUAGE_VERSION,
        "release_profile": RELEASE_PROFILE,
        "release_status": RELEASE_STATUS,
        "stable": STABLE,
        "publication_authority": PUBLICATION_AUTHORITY,
        "merge_authority": MERGE_AUTHORITY,
        "technical_parent_commit": TECHNICAL_PARENT_COMMIT,
        "technical_parent_receipt_sha256": TECHNICAL_PARENT_RECEIPT_SHA256,
    }


__all__ = [
    "LANGUAGE_VERSION",
    "MERGE_AUTHORITY",
    "PUBLICATION_AUTHORITY",
    "RELEASE_PROFILE",
    "RELEASE_STATUS",
    "STABLE",
    "TECHNICAL_PARENT_COMMIT",
    "TECHNICAL_PARENT_RECEIPT_SHA256",
    "validate_release_metadata_v31",
]
