from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import tools.validate_ir_v3_browser_wasm as browser_common  # noqa: E402

PROGRAM_GENERATOR = ROOT / "tools" / "generate_ir_v3_update_programs.py"
FIXTURE_PROJECT = ROOT / "runtimes" / "csharp" / "TevScript.V3UpdateFixtureTool" / "TevScript.V3UpdateFixtureTool.csproj"
FIXTURE_DLL = ROOT / "runtimes" / "csharp" / "TevScript.V3UpdateFixtureTool" / "bin" / "Release" / "net8.0" / "TevScript.V3UpdateFixtureTool.dll"
PROJECT = ROOT / "runtimes" / "csharp" / "TevScript.V3BrowserSignedUpdateGate" / "TevScript.V3BrowserSignedUpdateGate.csproj"
GATE = "irv3signedbrowser"


def run(arguments: list[str], *, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        arguments,
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


def fail_process(label: str, completed: subprocess.CompletedProcess[str]) -> int:
    print(label + "=FAIL")
    if completed.stdout:
        print(label + "_STDOUT=" + completed.stdout[-10000:].replace("\n", "\\n"))
    if completed.stderr:
        print(label + "_STDERR=" + completed.stderr[-10000:].replace("\n", "\\n"))
    return 1


def main() -> int:
    dotnet = shutil.which("dotnet")
    if dotnet is None:
        print("TEV_SCRIPT_IR_V3_BROWSER_SIGNED_UPDATE_GATE=SKIPPED_DOTNET_UNAVAILABLE")
        return 0
    browser = browser_common._find_browser()
    if browser is None:
        print("TEV_SCRIPT_IR_V3_BROWSER_SIGNED_UPDATE_GATE=SKIPPED_CHROMIUM_UNAVAILABLE")
        return 0

    surface = run([sys.executable, str(ROOT / "tools" / "validate_ir_v3_csharp_portable_surface.py")])
    if surface.returncode != 0:
        return fail_process("TEV_SCRIPT_IR_V3_BROWSER_SIGNED_UPDATE_SURFACE", surface)
    if "TEV_SCRIPT_IR_V3_CSHARP_SIGNED_UPDATE=PASS" not in surface.stdout:
        print("TEV_SCRIPT_IR_V3_BROWSER_SIGNED_UPDATE_SURFACE=FAIL_MISSING_WITNESS")
        return 1
    print("TEV_SCRIPT_IR_V3_BROWSER_SIGNED_UPDATE_SURFACE=PASS")

    with tempfile.TemporaryDirectory(prefix="tev_irv3_signed_browser_") as temp_raw:
        temp = Path(temp_raw)
        fixture_dir = temp / "fixtures"
        env = dict(os.environ)
        env["PYTHONPATH"] = str(ROOT) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
        generated = run(
            [sys.executable, str(PROGRAM_GENERATOR), "--out", str(fixture_dir)],
            env=env,
        )
        if generated.returncode != 0:
            return fail_process("TEV_SCRIPT_IR_V3_BROWSER_SIGNED_UPDATE_PROGRAMS", generated)
        print("TEV_SCRIPT_IR_V3_BROWSER_SIGNED_UPDATE_PROGRAMS=PASS")

        fixture_build = run([
            dotnet, "build", str(FIXTURE_PROJECT),
            "--configuration", "Release", "--nologo", "--verbosity", "quiet",
        ], env=env)
        if fixture_build.returncode != 0:
            return fail_process("TEV_SCRIPT_IR_V3_BROWSER_SIGNED_UPDATE_FIXTURE_BUILD", fixture_build)
        signer_env = dict(env)
        signer_env.setdefault("DOTNET_ROLL_FORWARD", "Major")
        signer = run([dotnet, str(FIXTURE_DLL), "--dir", str(fixture_dir)], env=signer_env)
        if signer.returncode != 0:
            return fail_process("TEV_SCRIPT_IR_V3_BROWSER_SIGNED_UPDATE_FIXTURE_SIGN", signer)
        if "TEV_SCRIPT_IR_V3_UPDATE_FIXTURE_SIGNER=PASS" not in signer.stdout:
            print("TEV_SCRIPT_IR_V3_BROWSER_SIGNED_UPDATE_FIXTURE_SIGN=FAIL_MISSING_WITNESS")
            return 1
        print("TEV_SCRIPT_IR_V3_BROWSER_SIGNED_UPDATE_FIXTURE_SIGN=PASS")

        package_text = (fixture_dir / "package1.json").read_text(encoding="utf-8")
        package_json = json.loads(package_text)
        expected_package_sha = hashlib.sha256(package_text.encode("utf-8")).hexdigest()
        expected_target_hash = package_json["body"]["target_ir_semantic_hash"]
        expected_detail = f"package={expected_package_sha};target={expected_target_hash}"
        print("TEV_SCRIPT_IR_V3_BROWSER_SIGNED_UPDATE_HOST_ORACLE=PASS")

        publish = temp / "publish"
        build = run([
            dotnet, "publish", str(PROJECT),
            "--configuration", "Release", "--nologo", "--verbosity", "minimal",
            "-p:RunAOTCompilation=true",
            f"-p:TevV3UpdateFixtureDir={fixture_dir}",
            f"-p:PublishDir={publish}",
        ], env=env)
        if build.returncode != 0:
            return fail_process("TEV_SCRIPT_IR_V3_BROWSER_SIGNED_UPDATE_WASM_BUILD", build)
        root = browser_common._find_publish_root(publish)
        wasm = browser_common._require_wasm(root)
        print("TEV_SCRIPT_IR_V3_BROWSER_SIGNED_UPDATE_WASM_BUILD=PASS")
        print("TEV_SCRIPT_IR_V3_BROWSER_SIGNED_UPDATE_WASM_MAGIC=PASS path=" + wasm)
        print("TEV_SCRIPT_IR_V3_BROWSER_SIGNED_UPDATE_AOT_REQUESTED=PASS")

        token = secrets.token_hex(16)
        port_file = temp / "port.txt"
        witness_file = temp / "witness.jsonl"
        server_stdout = temp / "server.out.log"
        server_stderr = temp / "server.err.log"
        browser_stdout = temp / "browser.out.log"
        browser_stderr = temp / "browser.err.log"
        server_process = None
        browser_process = None
        previous_gate = browser_common.GATE
        browser_common.GATE = GATE
        try:
            with server_stdout.open("w", encoding="utf-8") as server_out, server_stderr.open("w", encoding="utf-8") as server_err:
                server_process = subprocess.Popen([
                    sys.executable, str(browser_common.SERVER),
                    "--root", str(root),
                    "--port-file", str(port_file),
                    "--witness-file", str(witness_file),
                    "--witness-gate", GATE,
                    "--witness-token", token,
                ], cwd=ROOT, stdout=server_out, stderr=server_err, text=True, encoding="utf-8")
                port = browser_common._wait_port(port_file, server_process)
                base_url = f"http://127.0.0.1:{port}"
                browser_common._wait_health(base_url, server_process)
                print("TEV_SCRIPT_IR_V3_BROWSER_SIGNED_UPDATE_HTTP_SERVER=PASS")

                profile = temp / "browser-profile"
                profile.mkdir()
                url = base_url + "/?tev_witness_token=" + token
                with browser_stdout.open("w", encoding="utf-8") as browser_out, browser_stderr.open("w", encoding="utf-8") as browser_err:
                    browser_process = subprocess.Popen([
                        browser,
                        "--headless=new",
                        "--no-first-run",
                        "--no-default-browser-check",
                        "--disable-background-timer-throttling",
                        "--disable-backgrounding-occluded-windows",
                        "--disable-renderer-backgrounding",
                        "--disable-extensions",
                        "--window-size=1280,720",
                        "--user-data-dir=" + str(profile),
                        url,
                    ], cwd=root, stdout=browser_out, stderr=browser_err, text=True, encoding="utf-8")
                    receipt = browser_common._wait_witness(
                        witness_file, server_process, browser_process, token, timeout=240.0)
            if receipt.get("detail") != expected_detail:
                print("TEV_SCRIPT_IR_V3_BROWSER_SIGNED_UPDATE_WITNESS_DETAIL=FAIL")
                print("EXPECTED_DETAIL=" + expected_detail)
                print("OBSERVED_DETAIL=" + str(receipt.get("detail")))
                return 1
            print("TEV_SCRIPT_IR_V3_BROWSER_SIGNED_UPDATE_HTTP_WITNESS=PASS")
            print("TEV_SCRIPT_IR_V3_BROWSER_SIGNED_UPDATE_PACKAGE_PARITY=PASS")
            print("TEV_SCRIPT_IR_V3_BROWSER_SIGNED_UPDATE_TARGET_PARITY=PASS")
            print("TEV_SCRIPT_IR_V3_BROWSER_SIGNED_UPDATE_GATE=PASS")
            return 0
        except Exception as error:  # noqa: BLE001
            print("TEV_SCRIPT_IR_V3_BROWSER_SIGNED_UPDATE_GATE=FAIL")
            print("TEV_SCRIPT_IR_V3_BROWSER_SIGNED_UPDATE_ERROR=" + type(error).__name__ + ":" + str(error))
            return 1
        finally:
            browser_common.GATE = previous_gate
            browser_common._stop_process(browser_process)
            browser_common._stop_process(server_process)


if __name__ == "__main__":
    raise SystemExit(main())
