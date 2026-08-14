from __future__ import annotations

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
import tools.validate_ir_v3_wasi as wasi_common  # noqa: E402

BROWSER_PROJECT = (
    ROOT
    / "runtimes"
    / "csharp"
    / "TevScript.BrowserWasmGate"
    / "TevScript.BrowserWasmGate.csproj"
)
WASI_PROJECT = (
    ROOT
    / "runtimes"
    / "csharp"
    / "TevScript.WasiGate"
    / "TevScript.WasiGate.csproj"
)
BROWSER_GATE = "gate6b"
WASI_ASSEMBLY = "TevScript.WasiGate"


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
        print(label + "_STDOUT=" + completed.stdout[-10000:].replace("\n", "\\n"))
    if completed.stderr:
        print(label + "_STDERR=" + completed.stderr[-10000:].replace("\n", "\\n"))
    return 1


def require(stdout: str, marker: str) -> None:
    if marker not in stdout.splitlines():
        raise RuntimeError("missing V0.2 portable-host witness " + marker)


def validate_browser(dotnet: str, browser: str) -> int:
    with tempfile.TemporaryDirectory(prefix="tev_v0_2_browser_") as temp_raw:
        temp = Path(temp_raw)
        publish = temp / "publish"
        build = run([
            dotnet,
            "publish",
            str(BROWSER_PROJECT),
            "--configuration",
            "Release",
            "--nologo",
            "--verbosity",
            "minimal",
            "-p:RunAOTCompilation=true",
            f"-p:PublishDir={publish}",
        ])
        if build.returncode != 0:
            return fail_process("TEV_SCRIPT_V0_2_BROWSER_WASM_BUILD", build)

        root = browser_common._find_publish_root(publish)
        wasm = browser_common._require_wasm(root)
        print("TEV_SCRIPT_V0_2_BROWSER_WASM_BUILD=PASS")
        print("TEV_SCRIPT_V0_2_BROWSER_WASM_MAGIC=PASS path=" + wasm)
        print("TEV_SCRIPT_V0_2_BROWSER_WASM_AOT_REQUESTED=PASS")

        token = secrets.token_hex(16)
        port_file = temp / "port.txt"
        witness_file = temp / "witness.jsonl"
        server_stdout = temp / "server.out.log"
        server_stderr = temp / "server.err.log"
        browser_stdout = temp / "browser.out.log"
        browser_stderr = temp / "browser.err.log"
        profile = temp / "browser-profile"
        server_process: subprocess.Popen[str] | None = None
        browser_process: subprocess.Popen[str] | None = None
        previous_gate = browser_common.GATE
        browser_common.GATE = BROWSER_GATE
        try:
            with (
                server_stdout.open("w", encoding="utf-8") as server_out,
                server_stderr.open("w", encoding="utf-8") as server_err,
            ):
                server_process = subprocess.Popen(
                    [
                        sys.executable,
                        str(browser_common.SERVER),
                        "--root",
                        str(root),
                        "--port-file",
                        str(port_file),
                        "--witness-file",
                        str(witness_file),
                        "--witness-gate",
                        BROWSER_GATE,
                        "--witness-token",
                        token,
                    ],
                    cwd=ROOT,
                    stdout=server_out,
                    stderr=server_err,
                    text=True,
                    encoding="utf-8",
                )
                port = browser_common._wait_port(port_file, server_process)
                base_url = f"http://127.0.0.1:{port}"
                browser_common._wait_health(base_url, server_process)

                profile.mkdir()
                url = base_url + "/?tev_witness_token=" + token
                with (
                    browser_stdout.open("w", encoding="utf-8") as browser_out,
                    browser_stderr.open("w", encoding="utf-8") as browser_err,
                ):
                    browser_process = subprocess.Popen(
                        [
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
                        ],
                        cwd=root,
                        stdout=browser_out,
                        stderr=browser_err,
                        text=True,
                        encoding="utf-8",
                    )
                    receipt = browser_common._wait_witness(
                        witness_file,
                        server_process,
                        browser_process,
                        token,
                        timeout=240.0,
                    )
            if receipt.get("detail") != "TEV_CORE_BROWSER_WASM_PASS":
                print("TEV_SCRIPT_V0_2_BROWSER_WASM_WITNESS_DETAIL=FAIL")
                print("OBSERVED_DETAIL=" + str(receipt.get("detail")))
                return 1
            print("TEV_SCRIPT_V0_2_BROWSER_WASM_HTTP_WITNESS=PASS")
            print("TEV_SCRIPT_V0_2_BROWSER_WASM_GATE=PASS")
            return 0
        except Exception as error:  # noqa: BLE001
            print("TEV_SCRIPT_V0_2_BROWSER_WASM_GATE=FAIL")
            print("TEV_SCRIPT_V0_2_BROWSER_WASM_ERROR=" + type(error).__name__ + ":" + str(error))
            for label, path in (
                ("SERVER_STDOUT", server_stdout),
                ("SERVER_STDERR", server_stderr),
                ("BROWSER_STDOUT", browser_stdout),
                ("BROWSER_STDERR", browser_stderr),
            ):
                if path.is_file():
                    output = path.read_text(encoding="utf-8", errors="replace")[-6000:]
                    if output:
                        print("TEV_SCRIPT_V0_2_BROWSER_" + label + "=" + output.replace("\n", "\\n"))
            return 1
        finally:
            browser_common.GATE = previous_gate
            browser_common._stop_browser_process(browser_process, profile)
            browser_common._stop_process(server_process)


def validate_wasi(dotnet: str, wasmtime: str) -> int:
    required = wasi_common._required_wasi_sdk(dotnet)
    if required is None:
        print("TEV_SCRIPT_V0_2_WASI_GATE=SKIPPED_DOTNET_WASI_PACK_UNAVAILABLE")
        return 0
    required_version, pack = required
    wasi_sdk = wasi_common._resolve_wasi_sdk(required_version)
    if wasi_sdk is None:
        print("TEV_SCRIPT_V0_2_WASI_GATE=SKIPPED_WASI_SDK_UNAVAILABLE")
        return 0

    with tempfile.TemporaryDirectory(prefix="tev_v0_2_wasi_") as temp_raw:
        temp = Path(temp_raw)
        publish = temp / "publish"
        env = dict(os.environ)
        sdk_binding = str(wasi_sdk).rstrip("\\/") + os.sep
        env["WASI_SDK_PATH"] = sdk_binding
        build = run(
            [
                dotnet,
                "publish",
                str(WASI_PROJECT),
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
            return fail_process("TEV_SCRIPT_V0_2_WASI_BUILD", build)

        wasm = wasi_common._find_dotnet_wasm(publish)
        run_root = wasm.parent
        print("TEV_SCRIPT_V0_2_WASI_SDK_RESOLVED=PASS")
        print("TEV_SCRIPT_V0_2_WASI_DOTNET_PACK=" + pack.name)
        print("TEV_SCRIPT_V0_2_WASI_BUILD=PASS")
        print("TEV_SCRIPT_V0_2_WASI_WASM_MAGIC=PASS")

        executed = run(
            [
                wasmtime,
                "run",
                "-S",
                "http",
                "--dir",
                ".",
                "dotnet.wasm",
                WASI_ASSEMBLY,
            ],
            cwd=run_root,
            env=env,
        )
        if executed.returncode != 0:
            return fail_process("TEV_SCRIPT_V0_2_WASI_EXECUTION", executed)
        try:
            for witness in (
                "GATE6C_WASI_ACTIVE=PASS",
                "GATE6C_CORE_PARSE=PASS",
                "GATE6C_RUNTIME_STATE=PASS",
                "GATE6C_CANONICAL_JSON=PASS",
                "GATE6C_UNITY_DEPENDENCY=ABSENT_PASS",
                "GATE6C_BROWSER_DEPENDENCY=ABSENT_PASS",
                "TEV_SCRIPT_PURE_CORE_WASI_GATE_6C=PASS",
            ):
                require(executed.stdout, witness)
        except RuntimeError as error:
            print("TEV_SCRIPT_V0_2_WASI_GATE=FAIL_WITNESS")
            print("TEV_SCRIPT_V0_2_WASI_ERROR=" + str(error))
            return 1
        print("TEV_SCRIPT_V0_2_WASI_EXECUTION=PASS")
        print("TEV_SCRIPT_V0_2_WASI_GATE=PASS")
        return 0


def main() -> int:
    dotnet = shutil.which("dotnet")
    wasmtime = shutil.which("wasmtime")
    browser = browser_common._find_browser()
    if dotnet is None:
        print("TEV_SCRIPT_V0_2_PORTABLE_HOSTS=SKIPPED_DOTNET_UNAVAILABLE")
        return 0
    if browser is None:
        print("TEV_SCRIPT_V0_2_BROWSER_WASM_GATE=SKIPPED_CHROMIUM_UNAVAILABLE")
        return 0
    if wasmtime is None:
        print("TEV_SCRIPT_V0_2_WASI_GATE=SKIPPED_WASMTIME_UNAVAILABLE")
        return 0

    browser_result = validate_browser(dotnet, browser)
    if browser_result != 0:
        return browser_result
    wasi_result = validate_wasi(dotnet, wasmtime)
    if wasi_result != 0:
        return wasi_result
    print("TEV_SCRIPT_V0_2_PORTABLE_HOSTS=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
