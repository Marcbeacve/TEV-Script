from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_repository_full_certification_targets_current_platform_completion() -> None:
    policy = json.loads((ROOT / "REPOSITORY_CHANNEL.json").read_text(encoding="utf-8"))
    rules = {row["rule_id"]: row for row in policy["validation"]["rules"]}

    assert "platform-completion" in rules
    rule = rules["platform-completion"]
    assert rule["horizon"] == "PLATFORM_COMPLETION"
    assert rule["commands"] == [["python", "RUN_TEV_SCRIPT_PLATFORM_COMPLETION.py"]]

    serialized = json.dumps(rule, sort_keys=True)
    assert "RUN_TEV_SCRIPT_V1_CERTIFY_FULL.py" not in serialized
    assert "RUN_TEV_SCRIPT_V1_PYTHON_CERTIFY_FULL.py" not in serialized


def test_current_platform_rule_tracks_current_platform_authority_surfaces() -> None:
    policy = json.loads((ROOT / "REPOSITORY_CHANNEL.json").read_text(encoding="utf-8"))
    rule = next(
        row for row in policy["validation"]["rules"]
        if row["rule_id"] == "platform-completion"
    )
    includes = set(rule["include"])
    assert {
        "REPOSITORY_CHANNEL.json",
        "pyproject.toml",
        "requirements-certification.txt",
        "RUN_TEV_SCRIPT_PLATFORM_COMPLETION.py",
        "tev_script/platform_*.py",
        "tev_script/version.py",
        "spec/**",
        "schemas/**",
        "conformance/**",
        "docs/VALIDATION.md",
    } <= includes
