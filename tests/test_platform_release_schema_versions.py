from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_release_receipt_v1_schema_remains_historical() -> None:
    value = json.loads(
        (ROOT / "schemas" / "tev-script-platform-release-receipt-v1.schema.json").read_text(
            encoding="utf-8"
        )
    )
    assert value["properties"]["schema"]["const"] == "TEV_SCRIPT_PLATFORM_RELEASE_RECEIPT_V1"
    assert "conformance_sha256" not in value["required"]
    assert "build_environment_descriptor_sha256" not in value["required"]


def test_release_receipt_v2_schema_supports_pass_hold_and_fail() -> None:
    value = json.loads(
        (ROOT / "schemas" / "tev-script-platform-release-receipt-v2.schema.json").read_text(
            encoding="utf-8"
        )
    )
    assert value["properties"]["schema"]["const"] == "TEV_SCRIPT_PLATFORM_RELEASE_RECEIPT_V2"
    assert value["properties"]["status"]["enum"] == ["PASS", "HOLD", "FAIL"]
    assert value["properties"]["package_version"]["const"] == "3.1.1"
    assert set(value["required"]) == {
        "schema",
        "status",
        "package_version",
        "receipt_sha256",
    }


def test_release_receipt_v2_pass_binds_conformance_and_environment() -> None:
    value = json.loads(
        (ROOT / "schemas" / "tev-script-platform-release-receipt-v2.schema.json").read_text(
            encoding="utf-8"
        )
    )
    required = set(value["allOf"][0]["then"]["required"])
    assert "conformance_sha256" in required
    assert "build_environment_descriptor_sha256" in required
    assert "source_commit" in required
    assert "source_tree" in required
    assert value["allOf"][0]["then"]["properties"]["runtime_dependency_count"]["const"] == 0


def test_release_receipt_v2_nonpass_requires_error_and_forbids_final_identity() -> None:
    value = json.loads(
        (ROOT / "schemas" / "tev-script-platform-release-receipt-v2.schema.json").read_text(
            encoding="utf-8"
        )
    )
    else_contract = value["allOf"][0]["else"]
    assert else_contract["required"] == ["error"]
    forbidden = {
        tuple(row["required"])[0]
        for row in else_contract["not"]["anyOf"]
    }
    assert {"source_commit", "source_tree", "wheel_sha256", "provenance_sha256"}.issubset(forbidden)
