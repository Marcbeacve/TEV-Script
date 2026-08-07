from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def emit(line: str) -> None:
    print(line, flush=True)


def run(label: str, arguments: list[str], *, cwd: Path = ROOT, env: dict[str, str] | None = None) -> str:
    completed = subprocess.run(
        arguments,
        cwd=cwd,
        env=env,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.stdout:
        print(completed.stdout, end="" if completed.stdout.endswith("\n") else "\n", flush=True)
    if completed.returncode != 0:
        raise RuntimeError(f"{label}_FAILED exit={completed.returncode}")
    emit(label + "=PASS")
    return completed.stdout


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def version_key(name: str) -> tuple[int, ...]:
    values = []
    for part in re.split(r"[.-]", name):
        if part.isdigit():
            values.append(int(part))
        else:
            break
    return tuple(values)


def dotnet_root() -> Path:
    selected = shutil.which("dotnet")
    if selected is None:
        raise RuntimeError("DOTNET_NOT_FOUND")
    return Path(selected).resolve().parent


def discover_required_wasi_sdk() -> str:
    pack_root = dotnet_root() / "packs" / "Microsoft.NET.Runtime.WebAssembly.Wasi.Sdk"
    packs = sorted(
        [item for item in pack_root.iterdir() if item.is_dir()],
        key=lambda item: version_key(item.name),
        reverse=True,
    )
    if not packs:
        raise RuntimeError("WASI_DOTNET_PACK_NOT_FOUND")
    patterns = [
        re.compile(r"<_ExpectedWasiSdkVersion(?:\s+[^>]*)?>\s*([0-9]+(?:\.[0-9]+)+)\s*</_ExpectedWasiSdkVersion>", re.I),
        re.compile(r"wasi-sdk version\s+([0-9]+(?:\.[0-9]+)+)", re.I),
    ]
    for pack in packs:
        for name in ("WasiApp.targets", "WasmApp.Common.targets"):
            target = pack / "Sdk" / name
            if not target.is_file():
                continue
            source = target.read_text(encoding="utf-8", errors="ignore")
            for pattern in patterns:
                match = pattern.search(source)
                if match:
                    return match.group(1)
    raise RuntimeError("WASI_REQUIRED_VERSION_DISCOVERY_FAILED")


def valid_wasi_root(root: Path, required: str) -> bool:
    try:
        if not root.is_dir():
            return False
        version = (root / "VERSION").read_text(encoding="utf-8").strip()
        return (
            version.startswith(required)
            and (root / "bin" / "clang.exe").is_file()
            and (root / "share" / "wasi-sysroot").is_dir()
        )
    except OSError:
        return False


def resolve_wasi_sdk(required: str) -> Path:
    candidates: list[Path] = []
    env_path = os.environ.get("WASI_SDK_PATH")
    if env_path:
        candidates.append(Path(env_path.rstrip("\\/")))
    local = os.environ.get("LOCALAPPDATA")
    if local:
        candidates.append(Path(local) / "Programs" / "wasi-sdk" / required)
        candidates.append(Path(local) / "Programs" / "wasi-sdk")
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate).lower()
        if key in seen:
            continue
        seen.add(key)
        if valid_wasi_root(candidate, required):
            return candidate.resolve()
        if candidate.is_dir():
            nested = [item for item in candidate.iterdir() if valid_wasi_root(item, required)]
            if len(nested) == 1:
                return nested[0].resolve()
    raise RuntimeError(f"WASI_SDK_REQUIRED_VERSION_NOT_FOUND={required}")


def require_marker(output: str, marker: str) -> None:
    if marker not in output.splitlines():
        raise RuntimeError("LANGUAGE_COMPLETENESS_MARKER_MISSING=" + marker)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()

    emit("LANGUAGE_COMPLETENESS_POLICY=DELTA_FIRST_THEN_ONE_FULL_REGRESSION")
    run(
        "LANGUAGE_COMPLETENESS_STATIC",
        [sys.executable, "tools/validate_language_completeness_v1.py"],
    )

    py = run(
        "LANGUAGE_COMPLETENESS_PYTHON_DELTA",
        [sys.executable, "tools/run_language_closure_python.py"],
    )
    require_marker(py, "TEV_SCRIPT_LANGUAGE_CLOSURE_PYTHON=PASS")

    node = shutil.which("node")
    if node is None:
        raise RuntimeError("NODE_NOT_FOUND")
    js = run(
        "LANGUAGE_COMPLETENESS_JAVASCRIPT_DELTA",
        [node, "tools/run_language_closure_javascript.mjs"],
    )
    require_marker(js, "TEV_SCRIPT_LANGUAGE_CLOSURE_JAVASCRIPT=PASS")

    closure_project = ROOT / "runtimes/csharp/TevScript.LanguageClosureGate/TevScript.LanguageClosureGate.csproj"
    run(
        "LANGUAGE_COMPLETENESS_CSHARP_BUILD_DELTA",
        ["dotnet", "build", str(closure_project), "-c", "Release", "--nologo"],
    )
    cs = run(
        "LANGUAGE_COMPLETENESS_CSHARP_DELTA",
        ["dotnet", "run", "--project", str(closure_project), "-c", "Release", "--", str(ROOT)],
    )
    require_marker(cs, "TEV_SCRIPT_LANGUAGE_CLOSURE_CSHARP=PASS")

    with tempfile.TemporaryDirectory(prefix="tev-script-language-closure-") as temp:
        temp_root = Path(temp)
        browser_publish = temp_root / "browser-publish"
        browser_project = ROOT / "runtimes/csharp/TevScript.BrowserWasmGate/TevScript.BrowserWasmGate.csproj"
        run(
            "LANGUAGE_COMPLETENESS_BROWSER_WASM_AOT_COMPILE_SMOKE",
            ["dotnet", "publish", str(browser_project), "-c", "Release", "--nologo", f"-p:PublishDir={browser_publish}"],
        )

        required_wasi = discover_required_wasi_sdk()
        wasi_root = resolve_wasi_sdk(required_wasi)
        clang = wasi_root / "bin" / "clang.exe"
        if not clang.is_file():
            raise RuntimeError("WASI_CLANG_BINDING_FAILED=" + str(clang))
        env = dict(os.environ)
        env["WASI_SDK_PATH"] = str(wasi_root) + os.sep
        emit("LANGUAGE_COMPLETENESS_WASI_SDK_REQUIRED=" + required_wasi)
        emit("LANGUAGE_COMPLETENESS_WASI_SDK_PATH=" + env["WASI_SDK_PATH"])
        emit("LANGUAGE_COMPLETENESS_WASI_SDK_TRAILING_SEPARATOR=PASS")
        wasi_publish = temp_root / "wasi-publish"
        wasi_project = ROOT / "runtimes/csharp/TevScript.WasiGate/TevScript.WasiGate.csproj"
        run(
            "LANGUAGE_COMPLETENESS_WASI_AOT_COMPILE_SMOKE",
            ["dotnet", "publish", str(wasi_project), "-c", "Release", "--nologo", f"-p:PublishDir={wasi_publish}"],
            env=env,
        )

    emit("LANGUAGE_COMPLETENESS_DELTA_PROBES=PASS")
    emit("LANGUAGE_COMPLETENESS_FULL_REGRESSION_RUN_COUNT=1")
    portable = run(
        "LANGUAGE_COMPLETENESS_PORTABLE_POSITIVE_REGRESSION",
        [sys.executable, "RUN_PORTABLE_CONFORMANCE.py"],
    )
    require_marker(portable, "TEV_SCRIPT_PORTABLE_V0_2=PASS_PYTHON_JAVASCRIPT")

    csharp_conformance = ROOT / "runtimes/csharp/TevScript.Core.Conformance/TevScript.Core.Conformance.csproj"
    csharp = run(
        "LANGUAGE_COMPLETENESS_CSHARP_POSITIVE_REGRESSION",
        ["dotnet", "run", "--project", str(csharp_conformance), "-c", "Release", "--", str(ROOT)],
    )
    require_marker(csharp, "TEV_SCRIPT_CSHARP_GATE_2=PASS")

    evidence = {
        "schema": "TEV_SCRIPT_LANGUAGE_COMPLETENESS_EVIDENCE_V1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "language_version": "0.2.0",
        "ir_schema": "TEV_SCRIPT_PROGRAM_IR_V2",
        "source_grammar_complete": True,
        "static_semantics_complete": True,
        "source_to_ir_closure": True,
        "capability_model_complete": True,
        "ir_operational_semantics_complete": True,
        "ir_static_flow_verifier": True,
        "abi_canonical_ids": True,
        "negative_cross_runtime_conformance": True,
        "negative_cases": 8,
        "python": "PASS",
        "javascript": "PASS",
        "csharp": "PASS",
        "browser_wasm_aot_compile_smoke": "PASS",
        "wasi_aot_compile_smoke": "PASS",
        "positive_language_regression_runs": 1,
        "gate5_dynamic_rerun": 0,
        "gate6_dynamic_rerun": 0,
        "gate7_dynamic_rerun": 0,
        "stable_release": False,
        "status": "PASS_PRECOMMIT",
    }
    args.evidence.parent.mkdir(parents=True, exist_ok=True)
    args.evidence.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    emit("LANGUAGE_COMPLETENESS_EVIDENCE=" + str(args.evidence))
    emit("LANGUAGE_COMPLETENESS_EVIDENCE_SHA256=" + sha256(args.evidence))
    emit("SOURCE_GRAMMAR_COMPLETE=PASS")
    emit("STATIC_SEMANTICS_COMPLETE=PASS")
    emit("SOURCE_TO_IR_CLOSURE=PASS")
    emit("CAPABILITY_MODEL_COMPLETE=PASS")
    emit("IR_OPERATIONAL_SEMANTICS_COMPLETE=PASS")
    emit("IR_STATIC_VERIFIER=PASS")
    emit("ABI_CANONICAL_BOUNDARY=PASS")
    emit("NEGATIVE_CROSS_RUNTIME_CONFORMANCE=PASS")
    emit("NO_UNSPECIFIED_VALID_PROGRAM_BEHAVIOR=PASS")
    emit("TEV_SCRIPT_LANGUAGE_COMPLETE=PASS_PRECOMMIT")
    emit("STABLE_RELEASE=NO")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"TEV_SCRIPT_LANGUAGE_COMPLETENESS_V1=FAIL:{type(error).__name__}:{error}", file=sys.stderr, flush=True)
        raise
