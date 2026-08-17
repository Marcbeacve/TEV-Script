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


def test_release_receipt_v2_schema_binds_conformance_and_environment() -> None:
    value = json.loads(
        (ROOT / "schemas" / "tev-script-platform-release-receipt-v2.schema.json").read_text(
            encoding="utf-8"
        )
    )
    assert value["properties"]["schema"]["const"] == "TEV_SCRIPT_PLATFORM_RELEASE_RECEIPT_V2"
    assert "conformance_sha256" in value["required"]
    assert "build_environment_descriptor_sha256" in value["required"]
    assert value["properties"]["package_version"]["const"] == "3.1.1"
