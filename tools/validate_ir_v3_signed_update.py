from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PROJECT = (
    ROOT
    / "runtimes"
    / "csharp"
    / "TevScript.V3UpdateFixtureTool"
    / "TevScript.V3UpdateFixtureTool.csproj"
)
FIXTURE_DLL = (
    ROOT
    / "runtimes"
    / "csharp"
    / "TevScript.V3UpdateFixtureTool"
    / "bin"
    / "Release"
    / "net8.0"
    / "TevScript.V3UpdateFixtureTool.dll"
)
GATE_PROJECT = (
    ROOT
    / "runtimes"
    / "csharp"
    / "TevScript.V3SignedUpdateGate"
    / "TevScript.V3SignedUpdateGate.csproj"
)
GATE_DLL = (
    ROOT
    / "runtimes"
    / "csharp"
    / "TevScript.V3SignedUpdateGate"
    / "bin"
    / "Release"
    / "net8.0"
    / "TevScript.V3SignedUpdateGate.dll"
)


def run(
    arguments: list[str],
    *,
    dotnet_roll_forward: bool = False,
) -> subprocess.CompletedProcess[str]:
    environment = None
    if dotnet_roll_forward:
        environment = os.environ.copy()
        environment.setdefault("DOTNET_ROLL_FORWARD", "Major")
    return subprocess.run(
        arguments,
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        env=environment,
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
        raise RuntimeError("missing signed-update witness " + marker)


def main() -> int:
    dotnet = shutil.which("dotnet")
    if dotnet is None:
        print("TEV_SCRIPT_IR_V3_SIGNED_UPDATE_GATE=SKIPPED_DOTNET_UNAVAILABLE")
        return 0

    surface = run([sys.executable, str(ROOT / "tools" / "validate_ir_v3_csharp_portable_surface.py")])
    if surface.returncode != 0:
        return fail_process("TEV_SCRIPT_IR_V3_SIGNED_UPDATE_CSHARP_SURFACE", surface)
    if "TEV_SCRIPT_IR_V3_CSHARP_SIGNED_UPDATE=PASS" not in surface.stdout:
        print("TEV_SCRIPT_IR_V3_SIGNED_UPDATE_CSHARP_SURFACE=FAIL_MISSING_WITNESS")
        return 1
    print("TEV_SCRIPT_IR_V3_SIGNED_UPDATE_CSHARP_SURFACE=PASS")

    with tempfile.TemporaryDirectory(prefix="tev_irv3_update_") as temp_raw:
        fixture_dir = Path(temp_raw) / "fixtures"
        generate = run(
            [
                sys.executable,
                "-m",
                "tools.generate_ir_v3_update_programs",
                "--out",
                str(fixture_dir),
            ]
        )
        if generate.returncode != 0:
            return fail_process("TEV_SCRIPT_IR_V3_SIGNED_UPDATE_PROGRAM_GENERATION", generate)
        try:
            require(generate.stdout, "TEV_SCRIPT_IR_V3_UPDATE_SOURCE_DERIVATION=PASS")
            require(generate.stdout, "TEV_SCRIPT_IR_V3_UPDATE_PROGRAMS=8")
        except RuntimeError as error:
            print("TEV_SCRIPT_IR_V3_SIGNED_UPDATE_PROGRAM_GENERATION=FAIL_WITNESS")
            print("TEV_SCRIPT_IR_V3_SIGNED_UPDATE_ERROR=" + str(error))
            return 1
        print("TEV_SCRIPT_IR_V3_SIGNED_UPDATE_PROGRAM_GENERATION=PASS")

        fixture_build = run(
            [
                dotnet,
                "build",
                str(FIXTURE_PROJECT),
                "--configuration",
                "Release",
                "--nologo",
                "--verbosity",
                "quiet",
            ]
        )
        if fixture_build.returncode != 0:
            return fail_process("TEV_SCRIPT_IR_V3_SIGNED_UPDATE_FIXTURE_BUILD", fixture_build)
        if not FIXTURE_DLL.is_file():
            print("TEV_SCRIPT_IR_V3_SIGNED_UPDATE_FIXTURE_BUILD=FAIL_DLL_MISSING")
            return 1
        print("TEV_SCRIPT_IR_V3_SIGNED_UPDATE_FIXTURE_BUILD=PASS")

        sign = run(
            [dotnet, str(FIXTURE_DLL), "--dir", str(fixture_dir)],
            dotnet_roll_forward=True,
        )
        if sign.returncode != 0:
            return fail_process("TEV_SCRIPT_IR_V3_SIGNED_UPDATE_FIXTURE_SIGN", sign)
        try:
            require(sign.stdout, "TEV_SCRIPT_IR_V3_UPDATE_FIXTURE_SIGNER=PASS")
            require(sign.stdout, "TEV_SCRIPT_IR_V3_UPDATE_SIGNATURE_FORMAT=IEEE_P1363_FIXED_64")
            require(sign.stdout, "TEV_SCRIPT_IR_V3_UPDATE_TEST_PRIVATE_KEY_SCOPE=FIXTURE_TOOL_ONLY")
        except RuntimeError as error:
            print("TEV_SCRIPT_IR_V3_SIGNED_UPDATE_FIXTURE_SIGN=FAIL_WITNESS")
            print("TEV_SCRIPT_IR_V3_SIGNED_UPDATE_ERROR=" + str(error))
            return 1
        print("TEV_SCRIPT_IR_V3_SIGNED_UPDATE_FIXTURE_SIGN=PASS")

        gate_build = run(
            [
                dotnet,
                "build",
                str(GATE_PROJECT),
                "--configuration",
                "Release",
                "--nologo",
                "--verbosity",
                "quiet",
            ]
        )
        if gate_build.returncode != 0:
            return fail_process("TEV_SCRIPT_IR_V3_SIGNED_UPDATE_BUILD", gate_build)
        if not GATE_DLL.is_file():
            print("TEV_SCRIPT_IR_V3_SIGNED_UPDATE_BUILD=FAIL_DLL_MISSING")
            return 1
        print("TEV_SCRIPT_IR_V3_SIGNED_UPDATE_BUILD=PASS")

        gate = run(
            [dotnet, str(GATE_DLL), "--dir", str(fixture_dir)],
            dotnet_roll_forward=True,
        )
        if gate.returncode != 0:
            return fail_process("TEV_SCRIPT_IR_V3_SIGNED_UPDATE_DYNAMIC", gate)
        witnesses = (
            "TEV_SCRIPT_IR_V3_SIGNED_UPDATE_PACKAGE_V2=PASS",
            "TEV_SCRIPT_IR_V3_SIGNED_UPDATE_MANAGED_ES256=PASS",
            "TEV_SCRIPT_IR_V3_SIGNED_UPDATE_FROM_HASH=PASS",
            "TEV_SCRIPT_IR_V3_SIGNED_UPDATE_CAPABILITY_ABI_CEILING=PASS",
            "TEV_SCRIPT_IR_V3_SIGNED_UPDATE_TRANSACTIONAL_SWAP=PASS",
            "TEV_SCRIPT_IR_V3_SIGNED_UPDATE_REPLAY_ROLLBACK=PASS",
            "TEV_SCRIPT_IR_V3_SIGNED_UPDATE_STORE_ROLLBACK=PASS",
            "TEV_SCRIPT_IR_V3_SIGNED_UPDATE_INSTALLED_TARGET_CHECKPOINT=PASS",
            "TEV_SCRIPT_IR_V3_SIGNED_UPDATE_GATE=PASS",
        )
        try:
            for witness in witnesses:
                require(gate.stdout, witness)
        except RuntimeError as error:
            print("TEV_SCRIPT_IR_V3_SIGNED_UPDATE_DYNAMIC=FAIL_WITNESS")
            print("TEV_SCRIPT_IR_V3_SIGNED_UPDATE_ERROR=" + str(error))
            return 1

        print("TEV_SCRIPT_IR_V3_SIGNED_UPDATE_DYNAMIC=PASS")
        print("TEV_SCRIPT_IR_V3_SIGNED_UPDATE_TEMP_FIXTURES=EPHEMERAL_PASS")
        print("TEV_SCRIPT_IR_V3_SIGNED_UPDATE_GATE=PASS")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
