from __future__ import annotations

import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tev_script.ir_v3_conformance import run_ir_v3_conformance  # noqa: E402
from tev_script.json_io import load_strict_json  # noqa: E402
from tev_script.runtime_checkpoint_v2 import RuntimeCheckpointV2  # noqa: E402
from tev_script.runtime_v3 import ScriptRuntimeV3  # noqa: E402

CASES_PATH = ROOT / "conformance" / "ir-v3-validator-cases.json"
SCENARIO_PATH = ROOT / "conformance" / "ir-v3-portable.scenario.json"
PROJECT = ROOT / "runtimes" / "csharp" / "TevScript.V3WasiGate" / "TevScript.V3WasiGate.csproj"
ASSEMBLY_NAME = "TevScript.V3WasiGate"
EXPECTED_TFM_MAJOR = "10"


def _run(
    arguments: list[str],
    *,
    cwd: Path = ROOT,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        arguments,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


def _skip(reason: str) -> int:
    print("TEV_SCRIPT_IR_V3_WASI_GATE=SKIPPED_" + reason)
    return 0


def _process_failure(label: str, completed: subprocess.CompletedProcess[str]) -> int:
    print(label + "=FAIL")
    if completed.stdout:
        print(label + "_STDOUT=" + completed.stdout[-10000:].replace("\n", "\\n"))
    if completed.stderr:
        print(label + "_STDERR=" + completed.stderr[-10000:].replace("\n", "\\n"))
    return 1


def _dotnet_roots(dotnet: str) -> list[Path]:
    candidates: list[Path] = []
    dotnet_root = os.environ.get("DOTNET_ROOT")
    if dotnet_root:
        candidates.append(Path(dotnet_root))
    candidates.append(Path(dotnet).resolve().parent)
    info = _run([dotnet, "--info"])
    if info.returncode == 0:
        for line in info.stdout.splitlines():
            match = re.match(r"\s*Base Path:\s*(.+?)\s*$", line)
            if match:
                base = Path(match.group(1).strip())
                if len(base.parents) >= 2:
                    candidates.append(base.parent.parent)
    result: list[Path] = []
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        if resolved not in result:
            result.append(resolved)
    return result


def _required_wasi_sdk(dotnet: str) -> tuple[str, Path] | None:
    pack_candidates: list[Path] = []
    for root in _dotnet_roots(dotnet):
        pack_root = root / "packs" / "Microsoft.NET.Runtime.WebAssembly.Wasi.Sdk"
        if not pack_root.is_dir():
            continue
        for child in pack_root.iterdir():
            if child.is_dir() and child.name.startswith(EXPECTED_TFM_MAJOR + "."):
                targets = child / "Sdk" / "WasiApp.targets"
                if targets.is_file():
                    pack_candidates.append(child)
    if not pack_candidates:
        return None

    def version_key(path: Path) -> tuple[int, ...]:
        numbers = re.findall(r"\d+", path.name)
        return tuple(int(item) for item in numbers[:4])

    pack = sorted(pack_candidates, key=version_key, reverse=True)[0]
    targets = pack / "Sdk" / "WasiApp.targets"
    text = targets.read_text(encoding="utf-8", errors="replace")
    versions = sorted(set(re.findall(
        r"(?is)<_ExpectedWasiSdkVersion(?:\s+[^>]*)?>\s*([0-9]+(?:\.[0-9]+)+)\s*</_ExpectedWasiSdkVersion>",
        text,
    )))
    if len(versions) != 1:
        raise RuntimeError(
            f"expected exactly one _ExpectedWasiSdkVersion in {targets}, observed={versions}"
        )
    return versions[0], pack


def _valid_wasi_sdk(root: Path, required: str) -> bool:
    if not root.is_dir():
        return False
    version_file = root / "VERSION"
    clang = root / "bin" / ("clang.exe" if os.name == "nt" else "clang")
    if not clang.is_file():
        alternate = root / "bin" / "clang.exe"
        if alternate.is_file():
            clang = alternate
    sysroot = root / "share" / "wasi-sysroot"
    if not version_file.is_file() or not clang.is_file() or not sysroot.is_dir():
        return False
    return version_file.read_text(encoding="utf-8", errors="replace").strip().startswith(required)


def _resolve_wasi_sdk(required: str) -> Path | None:
    candidates: list[Path] = []
    if os.environ.get("WASI_SDK_PATH"):
        candidates.append(Path(os.environ["WASI_SDK_PATH"].rstrip("\\/")))
    local = os.environ.get("LOCALAPPDATA")
    if local:
        candidates.extend([
            Path(local) / "Programs" / "wasi-sdk" / required,
            Path(local) / "Programs" / "wasi-sdk",
        ])
    candidates.extend([
        Path.home() / ".local" / "wasi-sdk" / required,
        Path.home() / ".local" / "wasi-sdk",
        Path("/opt/wasi-sdk"),
        Path("/usr/local/wasi-sdk"),
    ])
    seen: set[Path] = set()
    for candidate in candidates:
        try:
            candidate = candidate.resolve()
        except OSError:
            continue
        if candidate in seen:
            continue
        seen.add(candidate)
        if _valid_wasi_sdk(candidate, required):
            return candidate
        if candidate.is_dir():
            for child in candidate.iterdir():
                if child.is_dir() and _valid_wasi_sdk(child, required):
                    return child.resolve()
    return None


def _find_dotnet_wasm(publish: Path) -> Path:
    candidates = sorted(publish.rglob("dotnet.wasm"))
    if len(candidates) != 1:
        raise RuntimeError(
            "WASI publish expected exactly one dotnet.wasm, observed="
            + repr([str(item) for item in candidates])
        )
    if candidates[0].read_bytes()[:4] != b"\x00asm":
        raise RuntimeError("WASI dotnet.wasm magic mismatch")
    return candidates[0]


def _marker(stdout: str, prefix: str) -> str:
    matches = [line[len(prefix):] for line in stdout.splitlines() if line.startswith(prefix)]
    if len(matches) != 1:
        raise RuntimeError(f"expected one marker {prefix!r}, observed={matches}")
    return matches[0]


def _require(stdout: str, marker: str) -> None:
    if marker not in stdout.splitlines():
        raise RuntimeError("missing WASI witness " + marker)


def main() -> int:
    dotnet = shutil.which("dotnet")
    if dotnet is None:
        return _skip("DOTNET_UNAVAILABLE")
    wasmtime = shutil.which("wasmtime")
    if wasmtime is None:
        return _skip("WASMTIME_UNAVAILABLE")

    required = _required_wasi_sdk(dotnet)
    if required is None:
        return _skip("DOTNET_WASI_PACK_UNAVAILABLE")
    required_version, pack = required
    wasi_sdk = _resolve_wasi_sdk(required_version)
    if wasi_sdk is None:
        return _skip("WASI_SDK_" + required_version.replace(".", "_") + "_UNAVAILABLE")
    print("TEV_SCRIPT_IR_V3_WASI_SDK_REQUIRED=" + required_version)
    print("TEV_SCRIPT_IR_V3_WASI_DOTNET_PACK=" + pack.name)
    print("TEV_SCRIPT_IR_V3_WASI_SDK_RESOLVED=PASS")

    cases = load_strict_json(CASES_PATH)
    scenario = load_strict_json(SCENARIO_PATH)
    program = cases["valid_program"]
    expected_receipt = run_ir_v3_conformance(program, scenario)
    expected_receipt_hash = expected_receipt.receipt_hash
    runtime = ScriptRuntimeV3(program)
    runtime.invoke("E", "start")
    expected_checkpoint = RuntimeCheckpointV2.capture(runtime)
    expected_checkpoint_hash = expected_checkpoint.checkpoint_hash
    print("TEV_SCRIPT_IR_V3_WASI_HOST_ORACLES=PASS")
    print("TEV_SCRIPT_IR_V3_WASI_EXPECTED_RECEIPT_HASH=" + expected_receipt_hash)
    print("TEV_SCRIPT_IR_V3_WASI_EXPECTED_CHECKPOINT_HASH=" + expected_checkpoint_hash)

    surface = _run([sys.executable, str(ROOT / "tools" / "validate_ir_v3_csharp_portable_surface.py")])
    if surface.returncode != 0:
        return _process_failure("TEV_SCRIPT_IR_V3_WASI_CSHARP_PORTABLE_SURFACE", surface)
    if "TEV_SCRIPT_IR_V3_CSHARP_PORTABLE_SURFACE=PASS" not in surface.stdout:
        print("TEV_SCRIPT_IR_V3_WASI_CSHARP_PORTABLE_SURFACE=FAIL_MISSING_WITNESS")
        return 1
    print("TEV_SCRIPT_IR_V3_WASI_CSHARP_PORTABLE_SURFACE=PASS")

    with tempfile.TemporaryDirectory(prefix="tev_irv3_wasi_") as temp_raw:
        temp = Path(temp_raw)
        publish = temp / "publish"
        env = dict(os.environ)
        sdk_binding = str(wasi_sdk).rstrip("\\/") + os.sep
        env["WASI_SDK_PATH"] = sdk_binding
        build = _run(
            [
                dotnet,
                "publish",
                str(PROJECT),
                "--configuration",
                "Release",
                "--nologo",
                "--verbosity",
                "minimal",
                f"-p:PublishDir={publish}",
                f"-p:WASI_SDK_PATH={sdk_binding}",
            ],
            env=env,
        )
        if build.returncode != 0:
            return _process_failure("TEV_SCRIPT_IR_V3_WASI_BUILD", build)
        wasm = _find_dotnet_wasm(publish)
        run_root = wasm.parent
        shutil.copyfile(CASES_PATH, run_root / CASES_PATH.name)
        shutil.copyfile(SCENARIO_PATH, run_root / SCENARIO_PATH.name)
        checkpoint_path = run_root / "ir-v3-wasi.checkpoint.json"
        print("TEV_SCRIPT_IR_V3_WASI_BUILD=PASS")
        print("TEV_SCRIPT_IR_V3_WASI_WASM_MAGIC=PASS")

        base_command = [
            wasmtime,
            "run",
            "--dir",
            ".",
            "dotnet.wasm",
            ASSEMBLY_NAME,
        ]
        fresh = _run(
            [
                *base_command,
                "fresh",
                CASES_PATH.name,
                SCENARIO_PATH.name,
                checkpoint_path.name,
            ],
            cwd=run_root,
            env=env,
        )
        if fresh.returncode != 0:
            return _process_failure("TEV_SCRIPT_IR_V3_WASI_FRESH", fresh)
        try:
            _require(fresh.stdout, "TEV_SCRIPT_IR_V3_WASI_ACTIVE=PASS")
            _require(fresh.stdout, "TEV_SCRIPT_IR_V3_WASI_MODE=FRESH")
            _require(fresh.stdout, "TEV_SCRIPT_IR_V3_WASI_VALIDATOR=PASS")
            _require(fresh.stdout, "TEV_SCRIPT_IR_V3_WASI_CONFORMANCE=PASS")
            _require(fresh.stdout, "TEV_SCRIPT_IR_V3_WASI_CHECKPOINT_CAPTURE=PASS")
            _require(fresh.stdout, "TEV_SCRIPT_IR_V3_WASI_GATE=PASS")
            fresh_receipt_hash = _marker(fresh.stdout, "TEV_SCRIPT_IR_V3_WASI_RECEIPT_HASH=")
            fresh_checkpoint_hash = _marker(fresh.stdout, "TEV_SCRIPT_IR_V3_WASI_CHECKPOINT_HASH=")
        except RuntimeError as error:
            print("TEV_SCRIPT_IR_V3_WASI_FRESH=FAIL_WITNESS")
            print("TEV_SCRIPT_IR_V3_WASI_ERROR=" + str(error))
            return 1
        if not checkpoint_path.is_file():
            print("TEV_SCRIPT_IR_V3_WASI_FRESH=FAIL_CHECKPOINT_MISSING")
            return 1
        print("TEV_SCRIPT_IR_V3_WASI_FRESH=PASS")

        wasi_checkpoint_bytes = checkpoint_path.read_text(encoding="utf-8")
        try:
            parsed_wasi_checkpoint = RuntimeCheckpointV2.parse(wasi_checkpoint_bytes)
        except Exception as error:  # noqa: BLE001
            print("TEV_SCRIPT_IR_V3_WASI_CHECKPOINT_PARSE=FAIL")
            print("TEV_SCRIPT_IR_V3_WASI_ERROR=" + type(error).__name__ + ":" + str(error))
            return 1
        if parsed_wasi_checkpoint.checkpoint_hash != expected_checkpoint_hash:
            print("TEV_SCRIPT_IR_V3_WASI_CHECKPOINT_CANONICAL_BYTES=FAIL_HASH")
            return 1
        if wasi_checkpoint_bytes != expected_checkpoint.to_canonical_json():
            print("TEV_SCRIPT_IR_V3_WASI_CHECKPOINT_CANONICAL_BYTES=FAIL_BYTES")
            return 1
        print("TEV_SCRIPT_IR_V3_WASI_CHECKPOINT_CANONICAL_BYTES=PASS")

        restore = _run(
            [
                *base_command,
                "restore",
                CASES_PATH.name,
                SCENARIO_PATH.name,
                checkpoint_path.name,
            ],
            cwd=run_root,
            env=env,
        )
        if restore.returncode != 0:
            return _process_failure("TEV_SCRIPT_IR_V3_WASI_RESTORE", restore)
        try:
            _require(restore.stdout, "TEV_SCRIPT_IR_V3_WASI_ACTIVE=PASS")
            _require(restore.stdout, "TEV_SCRIPT_IR_V3_WASI_MODE=RESTORE")
            _require(restore.stdout, "TEV_SCRIPT_IR_V3_WASI_VALIDATOR=PASS")
            _require(restore.stdout, "TEV_SCRIPT_IR_V3_WASI_CONFORMANCE=PASS")
            _require(restore.stdout, "TEV_SCRIPT_IR_V3_WASI_CHECKPOINT_RESTORE=PASS")
            _require(restore.stdout, "TEV_SCRIPT_IR_V3_WASI_RESTART_CONTINUATION=PASS")
            _require(restore.stdout, "TEV_SCRIPT_IR_V3_WASI_GATE=PASS")
            restore_receipt_hash = _marker(restore.stdout, "TEV_SCRIPT_IR_V3_WASI_RECEIPT_HASH=")
            restore_checkpoint_hash = _marker(restore.stdout, "TEV_SCRIPT_IR_V3_WASI_CHECKPOINT_HASH=")
        except RuntimeError as error:
            print("TEV_SCRIPT_IR_V3_WASI_RESTORE=FAIL_WITNESS")
            print("TEV_SCRIPT_IR_V3_WASI_ERROR=" + str(error))
            return 1
        print("TEV_SCRIPT_IR_V3_WASI_RESTORE=PASS")

        if fresh_receipt_hash != expected_receipt_hash or restore_receipt_hash != expected_receipt_hash:
            print("TEV_SCRIPT_IR_V3_WASI_RECEIPT_PARITY=FAIL")
            return 1
        if fresh_checkpoint_hash != expected_checkpoint_hash or restore_checkpoint_hash != expected_checkpoint_hash:
            print("TEV_SCRIPT_IR_V3_WASI_CHECKPOINT_PARITY=FAIL")
            return 1
        if fresh_receipt_hash != restore_receipt_hash or fresh_checkpoint_hash != restore_checkpoint_hash:
            print("TEV_SCRIPT_IR_V3_WASI_FRESH_RESTORE_IDENTITY=FAIL")
            return 1

        print("TEV_SCRIPT_IR_V3_WASI_RECEIPT_PARITY=PASS")
        print("TEV_SCRIPT_IR_V3_WASI_CHECKPOINT_PARITY=PASS")
        print("TEV_SCRIPT_IR_V3_WASI_FRESH_RESTORE_IDENTITY=PASS")
        print("TEV_SCRIPT_IR_V3_WASI_RESTART_CONTINUATION=PASS")
        print("TEV_SCRIPT_IR_V3_WASI_GATE=PASS")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
