from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "tev_script" / "semantic_residual_v0.py"
ADAPTERS = ROOT / "tev_script" / "semantic_residual_adapters_v0.py"
SPEC = ROOT / "spec" / "TEV_SCRIPT_SEMANTIC_RESIDUAL_V0.md"


def imports(path: Path) -> tuple[str, ...]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            found.append(("." * node.level) + (node.module or ""))
    return tuple(sorted(found))


def main() -> int:
    core_imports = imports(CORE)
    adapter_imports = imports(ADAPTERS)
    forbidden = ("cuofc", "ia_tev", "planner", "agent")
    for path, names in ((CORE, core_imports), (ADAPTERS, adapter_imports)):
        lowered = "\n".join(names).lower()
        if any(token in lowered for token in forbidden):
            print(f"RESIDUAL_DECOUPLING=FAIL path={path.name} imports={names}")
            return 2
    allowed_core_local = {".canonical", ".semantic_kernel_v0"}
    observed_core_local = {name for name in core_imports if name.startswith(".")}
    if not observed_core_local <= allowed_core_local:
        print(f"RESIDUAL_CORE_IMPORT_SURFACE=FAIL imports={sorted(observed_core_local)}")
        return 3
    allowed_adapter_local = {".semantic_kernel_v0", ".semantic_residual_v0"}
    observed_adapter_local = {name for name in adapter_imports if name.startswith(".")}
    if not observed_adapter_local <= allowed_adapter_local:
        print(f"RESIDUAL_ADAPTER_IMPORT_SURFACE=FAIL imports={sorted(observed_adapter_local)}")
        return 4
    text = SPEC.read_text(encoding="utf-8")
    required = (
        "Residual is not a third primitive",
        "INCOMPARABLE",
        "No universal scalar error",
        "TEV residual core -> CUOFC` = forbidden",
        "no `.tevs` keyword",
    )
    missing = [marker for marker in required if marker not in text]
    if missing:
        print(f"RESIDUAL_SPEC_CONTRACT=FAIL missing={missing}")
        return 5
    print("RESIDUAL_CORE_IMPORT_SURFACE=PASS")
    print("RESIDUAL_ADAPTER_IMPORT_SURFACE=PASS")
    print("RESIDUAL_CUOFC_RUNTIME_DEPENDENCY_ABSENT=PASS")
    print("RESIDUAL_IA_RUNTIME_DEPENDENCY_ABSENT=PASS")
    print("RESIDUAL_SPEC_CONTRACT=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
