from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEV = ROOT / "tev_script"
BRIDGE = TEV / "semantic_causal_bridge_v0.py"


def require(condition: bool, label: str, detail: str = "") -> None:
    if not condition:
        raise RuntimeError(label + (":" + detail if detail else ""))
    print(label + "=PASS")


def main() -> int:
    require(BRIDGE.is_file(), "POST_V1_BRIDGE_FILE")
    bridge = BRIDGE.read_text(encoding="utf-8")
    for forbidden in ("TEVProver", "CUOFC", "IA_TEV", "IA-TEV", "semantic_runtime"):
        require(forbidden not in bridge, "POST_V1_BRIDGE_EXTERNAL_AUTHORITY_ABSENT", forbidden)

    causal_files = sorted(TEV.glob("causal_*_v1.py"))
    require(bool(causal_files), "POST_V1_CAUSAL_MODULES_PRESENT")
    for path in causal_files:
        text = path.read_text(encoding="utf-8")
        require(".semantic_" not in text, "POST_V1_CAUSAL_TO_SEMANTIC_IMPORT_ABSENT", path.name)

    semantic_files = sorted(TEV.glob("semantic_*_v0.py"))
    require(bool(semantic_files), "POST_V1_SEMANTIC_MODULES_PRESENT")
    for path in semantic_files:
        if path.name == "semantic_causal_bridge_v0.py":
            continue
        text = path.read_text(encoding="utf-8")
        require(".causal_" not in text, "POST_V1_SEMANTIC_TO_CAUSAL_IMPORT_ABSENT", path.name)

    required_bridge_imports = (
        "from .causal_model_v1 import",
        "from .semantic_kernel_v0 import",
        "from .semantic_residual_v0 import",
    )
    for marker in required_bridge_imports:
        require(marker in bridge, "POST_V1_BRIDGE_REQUIRED_IMPORT", marker)

    require(
        "from .causal_runtime_v1 import" not in bridge,
        "POST_V1_BRIDGE_RUNTIME_DECOUPLED",
    )
    require(
        "residual_from_preparability_result_v1" in bridge
        and "residual_from_refinement_receipt_v1" in bridge
        and "residual_from_commit_result_v1" in bridge,
        "POST_V1_BRIDGE_RESIDUAL_CLOSURE_SURFACE",
    )

    print("POST_V1_INTEGRATION_AUTHORITY=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
