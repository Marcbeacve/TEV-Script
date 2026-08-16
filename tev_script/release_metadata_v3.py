from __future__ import annotations

LANGUAGE_VERSION = "3.0.0"
RELEASE_PROFILE = "stable_request"
RELEASE_STATUS = "STABLE_ADMISSION_REQUESTED"
STABLE = True
PUBLICATION_AUTHORITY = False
MERGE_AUTHORITY = False
TECHNICAL_PARENT_COMMIT = "b02c56c0e96109cb08965f0f1419144826b238f6"
TECHNICAL_PARENT_RECEIPT_SHA256 = "4b863f7342414c7eec0162ba2fd24ba20c59cc2e89951ea645a015117a518a5f"


def validate_release_metadata_v3() -> dict[str, object]:
    if LANGUAGE_VERSION != "3.0.0":
        raise RuntimeError("TEVS_V3_RELEASE_LANGUAGE_VERSION")
    if RELEASE_PROFILE == "candidate":
        if RELEASE_STATUS != "IMPLEMENTATION_CANDIDATE_CERTIFICATION_REQUIRED":
            raise RuntimeError("TEVS_V3_RELEASE_CANDIDATE_STATUS")
        if STABLE or PUBLICATION_AUTHORITY or MERGE_AUTHORITY:
            raise RuntimeError("TEVS_V3_RELEASE_CANDIDATE_AUTHORITY")
        if TECHNICAL_PARENT_COMMIT or TECHNICAL_PARENT_RECEIPT_SHA256:
            raise RuntimeError("TEVS_V3_RELEASE_CANDIDATE_PARENT")
    elif RELEASE_PROFILE == "stable_request":
        if RELEASE_STATUS != "STABLE_ADMISSION_REQUESTED":
            raise RuntimeError("TEVS_V3_RELEASE_STABLE_STATUS")
        if not STABLE or PUBLICATION_AUTHORITY or MERGE_AUTHORITY:
            raise RuntimeError("TEVS_V3_RELEASE_STABLE_AUTHORITY")
        if len(TECHNICAL_PARENT_COMMIT) != 40 or any(c not in "0123456789abcdef" for c in TECHNICAL_PARENT_COMMIT):
            raise RuntimeError("TEVS_V3_RELEASE_PARENT_COMMIT")
        if len(TECHNICAL_PARENT_RECEIPT_SHA256) != 64 or any(c not in "0123456789abcdef" for c in TECHNICAL_PARENT_RECEIPT_SHA256):
            raise RuntimeError("TEVS_V3_RELEASE_PARENT_RECEIPT")
    else:
        raise RuntimeError("TEVS_V3_RELEASE_PROFILE")
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
    "LANGUAGE_VERSION", "MERGE_AUTHORITY", "PUBLICATION_AUTHORITY",
    "RELEASE_PROFILE", "RELEASE_STATUS", "STABLE", "TECHNICAL_PARENT_COMMIT",
    "TECHNICAL_PARENT_RECEIPT_SHA256", "validate_release_metadata_v3",
]
