from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import tools.validate_ir_v3_wasi as wasi_common  # noqa: E402
from tev_script.json_io import parse_strict_json  # noqa: E402
from tev_script.runtime_checkpoint_v2 import RuntimeCheckpointV2  # noqa: E402

PROGRAM_GENERATOR = ROOT / "tools" / "generate_ir_v3_update_programs.py"
FIXTURE_PROJECT = ROOT / "runtimes" / "csharp" / "TevScript.V3UpdateFixtureTool" / "TevScript.V3UpdateFixtureTool.csproj"
FIXTURE_DLL = ROOT / "runtimes" / "csharp" / "TevScript.V3UpdateFixtureTool" / "bin" / "Release" / "net8.0" / "TevScript.V3UpdateFixtureTool.dll"
PROJECT = ROOT / "runtimes" / "csharp" / "TevScript.V3WasiSignedUpdateGate" / "TevScript.V3WasiSignedUpdateGate.csproj"
ASSEMBLY_NAME = "TevScript.V3WasiSignedUpdateGate"


def run(
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


def fail_process(label: str, completed: subprocess.CompletedProcess[str]) -> int:
    print(label + "=FAIL")
    if completed.stdout:
        print(label + "_STDOUT=" + completed.stdout[-12000:].replace("\n", "\\n"))
    if completed.stderr:
        print(label + "_STDERR=" + completed.stderr[-12000:].replace("\n", "\\n"))
    return 1


def require(stdout: str, marker: str) -> None:
    if marker not in stdout.splitlines():
        raise RuntimeError("missing WASI signed-update witness " + marker)


def marker(stdout: str, prefix: str) -> str:
    values = [line[len(prefix):] for line in stdout.splitlines() if line.startswith(prefix)]
    if len(values) != 1:
        raise RuntimeError(f"expected one {prefix!r}, observed={values}")
    return values[0]


def main() -> int:
    dotnet = shutil.which("dotnet")
    wasmtime = shutil.which("wasmtime")
    if dotnet is None:
        print("TEV_SCRIPT_IR_V3_WASI_SIGNED_UPDATE_GATE=SKIPPED_DOTNET_UNAVAILABLE")
        return 0
    if wasmtime is None:
        print("TEV_SCRIPT_IR_V3_WASI_SIGNED_UPDATE_GATE=SKIPPED_WASMTIME_UNAVAILABLE")
        return 0

    required = wasi_common._required_wasi_sdk(dotnet)
    if required is None:
        print("TEV_SCRIPT_IR_V3_WASI_SIGNED_UPDATE_GATE=SKIPPED_DOTNET_WASI_PACK_UNAVAILABLE")
        return 0
    required_version, pack = required
    wasi_sdk = wasi_common._resolve_wasi_sdk(required_version)
    if wasi_sdk is None:
        print("TEV_SCRIPT_IR_V3_WASI_SIGNED_UPDATE_GATE=SKIPPED_WASI_SDK_UNAVAILABLE")
        return 0
    print("TEV_SCRIPT_IR_V3_WASI_SIGNED_UPDATE_SDK_RESOLVED=PASS")
    print("TEV_SCRIPT_IR_V3_WASI_SIGNED_UPDATE_DOTNET_PACK=" + pack.name)

    surface = run([sys.executable, str(ROOT / "tools" / "validate_ir_v3_csharp_portable_surface.py")])
    if surface.returncode != 0:
        return fail_process("TEV_SCRIPT_IR_V3_WASI_SIGNED_UPDATE_SURFACE", surface)
    if "TEV_SCRIPT_IR_V3_CSHARP_SIGNED_UPDATE=PASS" not in surface.stdout:
        print("TEV_SCRIPT_IR_V3_WASI_SIGNED_UPDATE_SURFACE=FAIL_MISSING_WITNESS")
        return 1
    print("TEV_SCRIPT_IR_V3_WASI_SIGNED_UPDATE_SURFACE=PASS")

    with tempfile.TemporaryDirectory(prefix="tev_irv3_signed_wasi_") as temp_raw:
        temp = Path(temp_raw)
        fixture_dir = temp / "fixtures"
        env = dict(os.environ)
        env["PYTHONPATH"] = str(ROOT) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
        sdk_binding = str(wasi_sdk).rstrip("\\/") + os.sep
        env["WASI_SDK_PATH"] = sdk_binding

        generated = run(
            [sys.executable, str(PROGRAM_GENERATOR), "--out", str(fixture_dir)],
            env=env,
        )
        if generated.returncode != 0:
            return fail_process("TEV_SCRIPT_IR_V3_WASI_SIGNED_UPDATE_PROGRAMS", generated)
        print("TEV_SCRIPT_IR_V3_WASI_SIGNED_UPDATE_PROGRAMS=PASS")

        fixture_build = run([
            dotnet, "build", str(FIXTURE_PROJECT),
            "--configuration", "Release", "--nologo", "--verbosity", "quiet",
        ], env=env)
        if fixture_build.returncode != 0:
            return fail_process("TEV_SCRIPT_IR_V3_WASI_SIGNED_UPDATE_FIXTURE_BUILD", fixture_build)
        signer_env = dict(env)
        signer_env.setdefault("DOTNET_ROLL_FORWARD", "Major")
        signer = run([dotnet, str(FIXTURE_DLL), "--dir", str(fixture_dir)], env=signer_env)
        if signer.returncode != 0:
            return fail_process("TEV_SCRIPT_IR_V3_WASI_SIGNED_UPDATE_FIXTURE_SIGN", signer)
        if "TEV_SCRIPT_IR_V3_UPDATE_FIXTURE_SIGNER=PASS" not in signer.stdout:
            print("TEV_SCRIPT_IR_V3_WASI_SIGNED_UPDATE_FIXTURE_SIGN=FAIL_MISSING_WITNESS")
            return 1
        print("TEV_SCRIPT_IR_V3_WASI_SIGNED_UPDATE_FIXTURE_SIGN=PASS")

        package_text = (fixture_dir / "package1.json").read_text(encoding="utf-8")
        package_object = parse_strict_json(package_text)
        expected_package_sha = hashlib.sha256(package_text.encode("utf-8")).hexdigest()
        expected_target_hash = package_object["body"]["target_ir_semantic_hash"]
        target_ir = package_object["body"]["ir"]
        print("TEV_SCRIPT_IR_V3_WASI_SIGNED_UPDATE_HOST_ORACLE=PASS")

        publish = temp / "publish"
        build = run([
            dotnet, "publish", str(PROJECT),
            "--configuration", "Release", "--nologo", "--verbosity", "minimal",
            f"-p:PublishDir={publish}",
            f"-p:WASI_SDK_PATH={sdk_binding}",
            f"-p:TevV3UpdateFixtureDir={fixture_dir}",
        ], env=env)
        if build.returncode != 0:
            return fail_process("TEV_SCRIPT_IR_V3_WASI_SIGNED_UPDATE_BUILD", build)
        wasm = wasi_common._find_dotnet_wasm(publish)
        run_root = wasm.parent
        for name in ("base.ir.json", "package1.json"):
            target = run_root / name
            if not target.is_file():
                shutil.copyfile(fixture_dir / name, target)
        installed_path = run_root / "ir-v3-installed-update.json"
        checkpoint_path = run_root / "ir-v3-installed-target.checkpoint.json"
        print("TEV_SCRIPT_IR_V3_WASI_SIGNED_UPDATE_BUILD=PASS")
        print("TEV_SCRIPT_IR_V3_WASI_SIGNED_UPDATE_WASM_MAGIC=PASS")

        base_command = [wasmtime, "run", "-S", "http", "--dir", ".", "dotnet.wasm", ASSEMBLY_NAME]
        fresh = run([
            *base_command,
            "fresh",
            installed_path.name,
            checkpoint_path.name,
        ], cwd=run_root, env=env)
        if fresh.returncode != 0:
            return fail_process("TEV_SCRIPT_IR_V3_WASI_SIGNED_UPDATE_FRESH", fresh)
        try:
            for witness in (
                "TEV_SCRIPT_IR_V3_WASI_SIGNED_UPDATE_ACTIVE=PASS",
                "TEV_SCRIPT_IR_V3_WASI_SIGNED_UPDATE_MODE=FRESH",
                "TEV_SCRIPT_IR_V3_WASI_SIGNED_UPDATE_SIGNATURE=PASS",
                "TEV_SCRIPT_IR_V3_WASI_SIGNED_UPDATE_LIVE_COMMIT=PASS",
                "TEV_SCRIPT_IR_V3_WASI_SIGNED_UPDATE_INSTALLED_RECORD=PASS",
                "TEV_SCRIPT_IR_V3_WASI_SIGNED_UPDATE_CHECKPOINT_CAPTURE=PASS",
                "TEV_SCRIPT_IR_V3_WASI_SIGNED_UPDATE_GATE=PASS",
            ):
                require(fresh.stdout, witness)
            fresh_package = marker(fresh.stdout, "TEV_SCRIPT_IR_V3_WASI_SIGNED_UPDATE_PACKAGE_SHA256=")
            fresh_target = marker(fresh.stdout, "TEV_SCRIPT_IR_V3_WASI_SIGNED_UPDATE_TARGET_HASH=")
            fresh_checkpoint = marker(fresh.stdout, "TEV_SCRIPT_IR_V3_WASI_SIGNED_UPDATE_CHECKPOINT_HASH=")
        except RuntimeError as error:
            print("TEV_SCRIPT_IR_V3_WASI_SIGNED_UPDATE_FRESH=FAIL_WITNESS")
            print("TEV_SCRIPT_IR_V3_WASI_SIGNED_UPDATE_ERROR=" + str(error))
            return 1
        if fresh_package != expected_package_sha or fresh_target != expected_target_hash:
            print("TEV_SCRIPT_IR_V3_WASI_SIGNED_UPDATE_FRESH=FAIL_ORACLE")
            return 1
        if not installed_path.is_file() or not checkpoint_path.is_file():
            print("TEV_SCRIPT_IR_V3_WASI_SIGNED_UPDATE_FRESH=FAIL_DURABLE_FILES")
            return 1
        print("TEV_SCRIPT_IR_V3_WASI_SIGNED_UPDATE_FRESH=PASS")

        installed_object = parse_strict_json(installed_path.read_text(encoding="utf-8"))
        if installed_object["package_sha256"] != expected_package_sha or installed_object["package_json"] != package_text:
            print("TEV_SCRIPT_IR_V3_WASI_SIGNED_UPDATE_INSTALLED_BYTES=FAIL")
            return 1
        print("TEV_SCRIPT_IR_V3_WASI_SIGNED_UPDATE_INSTALLED_BYTES=PASS")

        checkpoint_text = checkpoint_path.read_text(encoding="utf-8")
        try:
            checkpoint = RuntimeCheckpointV2.parse(checkpoint_text)
            restored = checkpoint.restore_exact(target_ir)
            restored.invoke("E", "start")
            out = restored.state("E")["out"]
            if out != 11:
                raise RuntimeError(f"Python restart expected out=11, got {out!r}")
        except Exception as error:  # noqa: BLE001
            print("TEV_SCRIPT_IR_V3_WASI_SIGNED_UPDATE_PYTHON_CHECKPOINT=FAIL")
            print("TEV_SCRIPT_IR_V3_WASI_SIGNED_UPDATE_ERROR=" + type(error).__name__ + ":" + str(error))
            return 1
        if checkpoint.checkpoint_hash != fresh_checkpoint:
            print("TEV_SCRIPT_IR_V3_WASI_SIGNED_UPDATE_CHECKPOINT_HASH=FAIL")
            return 1
        print("TEV_SCRIPT_IR_V3_WASI_SIGNED_UPDATE_PYTHON_CHECKPOINT=PASS")

        restore = run([
            *base_command,
            "restore",
            installed_path.name,
            checkpoint_path.name,
        ], cwd=run_root, env=env)
        if restore.returncode != 0:
            return fail_process("TEV_SCRIPT_IR_V3_WASI_SIGNED_UPDATE_RESTORE", restore)
        try:
            for witness in (
                "TEV_SCRIPT_IR_V3_WASI_SIGNED_UPDATE_ACTIVE=PASS",
                "TEV_SCRIPT_IR_V3_WASI_SIGNED_UPDATE_MODE=RESTORE",
                "TEV_SCRIPT_IR_V3_WASI_SIGNED_UPDATE_SIGNATURE=PASS",
                "TEV_SCRIPT_IR_V3_WASI_SIGNED_UPDATE_INSTALLED_REVERIFY=PASS",
                "TEV_SCRIPT_IR_V3_WASI_SIGNED_UPDATE_CHECKPOINT_RESTORE=PASS",
                "TEV_SCRIPT_IR_V3_WASI_SIGNED_UPDATE_RESTART_CONTINUATION=PASS",
                "TEV_SCRIPT_IR_V3_WASI_SIGNED_UPDATE_GATE=PASS",
            ):
                require(restore.stdout, witness)
            restore_package = marker(restore.stdout, "TEV_SCRIPT_IR_V3_WASI_SIGNED_UPDATE_PACKAGE_SHA256=")
            restore_target = marker(restore.stdout, "TEV_SCRIPT_IR_V3_WASI_SIGNED_UPDATE_TARGET_HASH=")
            restore_checkpoint = marker(restore.stdout, "TEV_SCRIPT_IR_V3_WASI_SIGNED_UPDATE_CHECKPOINT_HASH=")
        except RuntimeError as error:
            print("TEV_SCRIPT_IR_V3_WASI_SIGNED_UPDATE_RESTORE=FAIL_WITNESS")
            print("TEV_SCRIPT_IR_V3_WASI_SIGNED_UPDATE_ERROR=" + str(error))
            return 1
        if (
            restore_package != expected_package_sha
            or restore_target != expected_target_hash
            or restore_checkpoint != fresh_checkpoint
        ):
            print("TEV_SCRIPT_IR_V3_WASI_SIGNED_UPDATE_RESTORE=FAIL_ORACLE")
            return 1

        print("TEV_SCRIPT_IR_V3_WASI_SIGNED_UPDATE_RESTORE=PASS")
        print("TEV_SCRIPT_IR_V3_WASI_SIGNED_UPDATE_PACKAGE_PARITY=PASS")
        print("TEV_SCRIPT_IR_V3_WASI_SIGNED_UPDATE_TARGET_PARITY=PASS")
        print("TEV_SCRIPT_IR_V3_WASI_SIGNED_UPDATE_CHECKPOINT_PARITY=PASS")
        print("TEV_SCRIPT_IR_V3_WASI_SIGNED_UPDATE_RESTART_CONTINUATION=PASS")
        print("TEV_SCRIPT_IR_V3_WASI_SIGNED_UPDATE_GATE=PASS")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
