from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORE = ROOT / "runtimes" / "csharp" / "TevScript.Core"
UNITY_CORE = ROOT / "unity" / "Package" / "Runtime" / "Core"
OUTPUT = ROOT / "unity" / "CORE_SOURCE_IDENTITY.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    canonical = sorted(CORE.glob("*.cs"), key=lambda p: p.name)
    package = sorted(UNITY_CORE.glob("*.cs"), key=lambda p: p.name)

    if [p.name for p in canonical] != [p.name for p in package]:
        raise RuntimeError("CORE_IDENTITY_NAME_SET_MISMATCH")
    if len(canonical) != 11:
        raise RuntimeError(f"CORE_IDENTITY_EXPECTED_11 observed={len(canonical)}")

    files = []
    for left, right in zip(canonical, package):
        if left.read_bytes() != right.read_bytes():
            raise RuntimeError(
                f"CORE_IDENTITY_BYTE_MISMATCH:{left.name}"
            )
        files.append(
            {
                "canonical": left.relative_to(ROOT).as_posix(),
                "package": right.relative_to(ROOT).as_posix(),
                "sha256": sha256(left),
            }
        )

    payload = {
        "certified_parent_commit":
            "8a560f349a8ca7ad7f893e16648c140d771020cb",
        "files": files,
        "schema": "TEV_SCRIPT_UNITY_CORE_SOURCE_IDENTITY_V1",
    }
    OUTPUT.write_text(
        json.dumps(payload, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print("UNITY_CORE_SOURCE_IDENTITY_REFRESHED=11_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
