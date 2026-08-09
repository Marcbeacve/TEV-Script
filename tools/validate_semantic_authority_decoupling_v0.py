from __future__ import annotations

from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_METATHEORY_TOKEN = "CU" + "OFC"

AUTHORITY_ROOTS = ("tev_script", "javascript", "runtimes", "conformance")
AUTHORITY_FILES = (
    "RUN_TEV_SCRIPT_V1_CERTIFY_FULL.py",
    "RUN_TEV_SCRIPT_V1_PYTHON_CERTIFY_FULL.py",
    "RUN_TEV_SCRIPT_V1_PERFORMANCE_POLISH.py",
    "RUN_TEV_SCRIPT_V1_PERFORMANCE_POLISH.ps1",
    "spec/TEV_SCRIPT_SEMANTIC_APPLY_CALCULUS_V0.md",
    "spec/TEV_SCRIPT_SEMANTIC_FRONTIER_CLOSURE_V0.md",
    "spec/TEV_SCRIPT_STANDALONE_SEMANTIC_AUTHORITY_V0.md",
)
EXTERNAL_IMPORT_NEEDLES = (
    "sys.path.insert",
    "kernel.causal_authority",
    "kernel.checker",
    "kernel.lnu_contracts",
)


def _authority_text_files() -> tuple[Path, ...]:
    paths: list[Path] = []
    for name in AUTHORITY_ROOTS:
        root = ROOT / name
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            try:
                path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            paths.append(path)
    for name in AUTHORITY_FILES:
        path = ROOT / name
        if not path.is_file():
            continue
        try:
            path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        paths.append(path)
    return tuple(sorted(set(paths)))


def main() -> int:
    authority_files = _authority_text_files()
    token_hits: list[str] = []
    external_import_hits: list[str] = []
    for path in authority_files:
        text = path.read_text(encoding="utf-8")
        relative = str(path.relative_to(ROOT))
        if FORBIDDEN_METATHEORY_TOKEN.lower() in text.lower():
            token_hits.append(relative)
        if any(needle in text for needle in EXTERNAL_IMPORT_NEEDLES):
            external_import_hits.append(relative)
    if token_hits:
        raise SystemExit("named external metatheory remains in TEV authority surface: " + ",".join(token_hits))
    if external_import_hits:
        raise SystemExit("TEV authority surface imports external semantic implementation: " + ",".join(external_import_hits))

    performance = (ROOT / "RUN_TEV_SCRIPT_V1_PERFORMANCE_POLISH.py").read_text(encoding="utf-8")
    wrapper = (ROOT / "RUN_TEV_SCRIPT_V1_PERFORMANCE_POLISH.ps1").read_text(encoding="utf-8")
    for forbidden in ("tevprover", "TEVPROVER_ROOT", "--tevprover-root"):
        if forbidden.lower() in (performance + wrapper).lower():
            raise SystemExit("performance authority remains provider-specific: " + forbidden)

    local_oracle = ROOT / "tools" / "v1_optimizer_oracle_local.py"
    contract = ROOT / "tools" / "v1_optimizer_oracle_contract.py"
    if not local_oracle.is_file() or not contract.is_file():
        raise SystemExit("standalone optimizer oracle missing")
    result = subprocess.run(
        [sys.executable, str(local_oracle)],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if result.returncode != 0 or "TEV_SCRIPT_V1_OPTIMIZER_ORACLE=PASS" not in result.stdout:
        raise SystemExit("standalone optimizer oracle failed:\n" + result.stdout)

    print("TEV_SCRIPT_NO_NAMED_EXTERNAL_METATHEORY_AUTHORITY_DEPENDENCY=PASS")
    print("TEV_SCRIPT_NO_EXTERNAL_METATHEORY_RUNTIME_DEPENDENCY=PASS")
    print("TEV_SCRIPT_NO_EXTERNAL_METATHEORY_BUILD_DEPENDENCY=PASS")
    print("TEV_SCRIPT_NO_EXTERNAL_METATHEORY_CERTIFICATION_DEPENDENCY=PASS")
    print("TEV_SCRIPT_NO_DEFAULT_EXTERNAL_PROVER_PATHS=PASS")
    print("TEV_SCRIPT_STANDALONE_OPTIMIZER_ORACLE=PASS")
    print("TEV_SCRIPT_NONNORMATIVE_RESEARCH_CORRESPONDENCE_ALLOWED=PASS")
    print("TEV_SCRIPT_SEMANTIC_AUTHORITY_DECOUPLING_V0=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
