from __future__ import annotations

import json
import subprocess
from pathlib import Path

BASE = "f6fec7c196b6caa7f2ffe39f449ac243cdb7ae7a"
TARGET = "agent/tev-script-distributed-determinism-gate7a-7e-v1"
PRECOMMIT = ['RUN_TEV_SCRIPT_DISTRIBUTED_DETERMINISM_GATE7A_7E_V1.ps1', 'conformance/distributed-lockstep.counterfactual.json', 'conformance/distributed-lockstep.scenario.json', 'docs/DISTRIBUTED_DETERMINISM_GATE7A_7E_V1.md', 'runtimes/csharp/TevScript.BrowserDeterminismGate/Program.cs', 'runtimes/csharp/TevScript.BrowserDeterminismGate/TevScript.BrowserDeterminismGate.csproj', 'runtimes/csharp/TevScript.BrowserDeterminismGate/index.html', 'runtimes/csharp/TevScript.BrowserDeterminismGate/main.mjs', 'runtimes/csharp/TevScript.Core/TevScriptRuntimeCheckpoint.cs', 'runtimes/csharp/TevScript.DeterminismGate.Shared/Gate7Shared.cs', 'runtimes/csharp/TevScript.DeterminismHostGate/Program.cs', 'runtimes/csharp/TevScript.DeterminismHostGate/TevScript.DeterminismHostGate.csproj', 'runtimes/csharp/TevScript.WasiDeterminismGate/Program.cs', 'runtimes/csharp/TevScript.WasiDeterminismGate/TevScript.WasiDeterminismGate.csproj', 'tools/gate7_divergence.py', 'tools/run_gate7_javascript_receipt.mjs', 'tools/run_gate7_python_receipt.py', 'tools/serve_gate7_browser.py', 'tools/validate_distributed_determinism_gate7a_7e.py', 'unity/Package/Runtime/Core/TevScriptRuntimeCheckpoint.cs']
FINAL = ['MANIFEST_SHA256.json', 'PROJECT_STATE.md', 'RUN_TEV_SCRIPT_DISTRIBUTED_DETERMINISM_GATE7A_7E_V1.ps1', 'conformance/distributed-lockstep.counterfactual.json', 'conformance/distributed-lockstep.scenario.json', 'descriptor.json', 'docs/DISTRIBUTED_DETERMINISM_GATE7A_7E_V1.md', 'docs/STATUS.md', 'evidence/reference-v0.2/distributed-determinism-gate7a-7e-windows-dotnet10.json', 'runtimes/csharp/TevScript.BrowserDeterminismGate/Program.cs', 'runtimes/csharp/TevScript.BrowserDeterminismGate/TevScript.BrowserDeterminismGate.csproj', 'runtimes/csharp/TevScript.BrowserDeterminismGate/index.html', 'runtimes/csharp/TevScript.BrowserDeterminismGate/main.mjs', 'runtimes/csharp/TevScript.Core/TevScriptRuntimeCheckpoint.cs', 'runtimes/csharp/TevScript.DeterminismGate.Shared/Gate7Shared.cs', 'runtimes/csharp/TevScript.DeterminismHostGate/Program.cs', 'runtimes/csharp/TevScript.DeterminismHostGate/TevScript.DeterminismHostGate.csproj', 'runtimes/csharp/TevScript.WasiDeterminismGate/Program.cs', 'runtimes/csharp/TevScript.WasiDeterminismGate/TevScript.WasiDeterminismGate.csproj', 'tools/gate7_divergence.py', 'tools/run_gate7_javascript_receipt.mjs', 'tools/run_gate7_python_receipt.py', 'tools/serve_gate7_browser.py', 'tools/validate_distributed_determinism_gate7a_7e.py', 'unity/Package/Runtime/Core/TevScriptRuntimeCheckpoint.cs']


def git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"GIT_FAILED args={args} stderr={result.stderr.strip()}"
        )
    return result.stdout.strip()


def dirty_paths(root: Path) -> list[str]:
    raw = git(root, "status", "--porcelain=v1", "--untracked-files=all")
    paths: list[str] = []
    if not raw:
        return paths
    for line in raw.splitlines():
        value = line[3:]
        if " -> " in value:
            value = value.split(" -> ", 1)[1]
        paths.append(value.replace("\\", "/"))
    return sorted(paths)


def require_text(path: Path, needle: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    if needle not in text:
        raise RuntimeError(f"{label}_MISSING:{needle}")


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    branch = git(root, "branch", "--show-current")
    head = git(root, "rev-parse", "HEAD")
    dirty = dirty_paths(root)

    if branch != TARGET:
        raise RuntimeError(
            f"GATE7_BRANCH_MISMATCH expected={TARGET} observed={branch}"
        )

    mode: str
    if head == BASE and dirty == sorted(PRECOMMIT):
        mode = "PRECOMMIT_DIRTY_20"
    elif not dirty:
        parent = git(root, "rev-parse", "HEAD^")
        changed = sorted(
            item.replace("\\", "/")
            for item in git(
                root, "diff", "--name-only", BASE + "..HEAD"
            ).splitlines()
            if item
        )
        if parent != BASE:
            raise RuntimeError(
                f"GATE7_CLEAN_PARENT_MISMATCH expected={BASE} observed={parent}"
            )
        if changed != FINAL:
            raise RuntimeError(
                "GATE7_CLEAN_CHANGED_PATHS_MISMATCH "
                f"expected={FINAL} observed={changed}"
            )
        mode = "CLEAN_CHILD_COMMIT_25"
    else:
        raise RuntimeError(
            f"GATE7_WORKTREE_MODE_UNRECOGNIZED head={head} dirty={dirty}"
        )

    csharp_checkpoint = root / "runtimes/csharp/TevScript.Core/TevScriptRuntimeCheckpoint.cs"
    unity_checkpoint = root / "unity/Package/Runtime/Core/TevScriptRuntimeCheckpoint.cs"
    if csharp_checkpoint.read_bytes() != unity_checkpoint.read_bytes():
        raise RuntimeError("GATE7_CHECKPOINT_MIRROR_MISMATCH")

    require_text(csharp_checkpoint, "TEV_SCRIPT_RUNTIME_CHECKPOINT_V1", "GATE7_CHECKPOINT_SCHEMA")
    require_text(csharp_checkpoint, "TEVS_CS_CHECKPOINT_SEMANTIC_HASH", "GATE7_CHECKPOINT_EXACT_SEMANTIC")
    require_text(csharp_checkpoint, "ValidateExactProgram", "GATE7_CHECKPOINT_EXACT_SET")
    require_text(csharp_checkpoint, "RestoreCompatibleSnapshot", "GATE7_CHECKPOINT_RESTORE")

    scenario = json.loads(
        (root / "conformance/distributed-lockstep.scenario.json").read_text(
            encoding="utf-8"
        )
    )
    counter = json.loads(
        (root / "conformance/distributed-lockstep.counterfactual.json").read_text(
            encoding="utf-8"
        )
    )
    if len(scenario["invocations"]) != 10:
        raise RuntimeError("GATE7_SCENARIO_STEP_COUNT")
    if scenario["scenario_id"] != counter["scenario_id"]:
        raise RuntimeError("GATE7_COUNTERFACTUAL_SCENARIO_ID_DRIFT")

    differences = []
    for index, (left, right) in enumerate(
        zip(scenario["invocations"], counter["invocations"]), start=1
    ):
        if left != right:
            differences.append(index)
    if differences != [7]:
        raise RuntimeError(
            f"GATE7_COUNTERFACTUAL_DIFFERENCE_MISMATCH observed={differences}"
        )

    require_text(
        root / "runtimes/csharp/TevScript.DeterminismGate.Shared/Gate7Shared.cs",
        "DivergenceStepOneBased = 7",
        "GATE7_SHARED_DIVERGENCE_INDEX",
    )
    require_text(
        root / "runtimes/csharp/TevScript.DeterminismHostGate/Program.cs",
        "GATE7A_CSHARP_REPLAY_64=PASS",
        "GATE7_REPLAY_CAMPAIGN",
    )
    require_text(
        root / "runtimes/csharp/TevScript.BrowserDeterminismGate/main.mjs",
        "/__tev_gate7_witness",
        "GATE7_BROWSER_WITNESS",
    )
    require_text(
        root / "runtimes/csharp/TevScript.BrowserDeterminismGate/Program.cs",
        "GATE7_BROWSER_FAILURE_STAGE=",
        "GATE7_BROWSER_STAGE_DIAGNOSTIC",
    )
    require_text(
        root / "runtimes/csharp/TevScript.BrowserDeterminismGate/main.mjs",
        "DOTNET_GATE_FAIL_${stage}_${type}_${code}",
        "GATE7_BROWSER_WITNESS_DIAGNOSTIC",
    )
    require_text(
        root / "RUN_TEV_SCRIPT_DISTRIBUTED_DETERMINISM_GATE7A_7E_V1.ps1",
        "FAIL_CAPTURED_CONTINUING_TO_WASI",
        "GATE7_BROWSER_FAIL_CONTINUE_WASI",
    )
    require_text(
        root / "runtimes/csharp/TevScript.WasiDeterminismGate/Program.cs",
        "GATE7_WASI_CHECKPOINT_RELOAD=PASS",
        "GATE7_WASI_RESTART",
    )

    changed_core = [
        item
        for item in (dirty if mode.startswith("PRECOMMIT") else FINAL)
        if item.startswith("runtimes/csharp/TevScript.Core/")
        or item.startswith("unity/Package/Runtime/Core/")
    ]
    expected_core = sorted([
        "runtimes/csharp/TevScript.Core/TevScriptRuntimeCheckpoint.cs",
        "unity/Package/Runtime/Core/TevScriptRuntimeCheckpoint.cs",
    ])
    if sorted(changed_core) != expected_core:
        raise RuntimeError(
            f"GATE7_CORE_CHANGE_BOUNDARY_MISMATCH observed={changed_core}"
        )

    for rel in PRECOMMIT:
        text = (root / rel).read_text(
            encoding="utf-8", errors="ignore"
        )
        lowered = text.lower()
        forbidden_tokens = (
            "git " + "push",
            "git " + "merge",
            "gh " + "pr",
            "git " + "tag",
            "github " + "release",
        )
        for forbidden in forbidden_tokens:
            if forbidden in lowered:
                raise RuntimeError(
                    f"GATE7_REMOTE_WRITE_FORBIDDEN path={rel} token={forbidden}"
                )

    print(f"GATE7_VALIDATION_MODE={mode}")
    print("GATE7_EXPECTED_PRECOMMIT_CHANGES=20")
    print("GATE7_EXPECTED_CLEAN_COMMIT_CHANGES=25")
    print("GATE7_CORE_PRODUCT_CHANGES=2_PHYSICAL_1_LOGICAL")
    print("GATE7_CHECKPOINT_MIRROR=BYTE_IDENTICAL_PASS")
    print("GATE7_COUNTERFACTUAL_ONLY_STEP7=PASS")
    print("GATE7_REMOTE_WRITE_GUARD=PASS")
    print("GATE7_R3_BROWSER_DIAGNOSTIC=PASS")
    print("GATE7_R3_BROWSER_FAIL_CONTINUE_WASI=PASS")
    print("TEV_SCRIPT_DISTRIBUTED_DETERMINISM_GATE7_STATIC=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
