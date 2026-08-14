from __future__ import annotations

import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tev_script.ir_v3_conformance import run_ir_v3_conformance  # noqa: E402
from tev_script.json_io import load_strict_json  # noqa: E402
from tev_script.runtime_checkpoint_v2 import RuntimeCheckpointV2  # noqa: E402
from tev_script.runtime_v3 import ScriptRuntimeV3  # noqa: E402

CASES_PATH = ROOT / "conformance" / "ir-v3-validator-cases.json"
SCENARIO_PATH = ROOT / "conformance" / "ir-v3-portable.scenario.json"
PROJECT = (
    ROOT
    / "runtimes"
    / "csharp"
    / "TevScript.V3BrowserWasmGate"
    / "TevScript.V3BrowserWasmGate.csproj"
)
SERVER = ROOT / "tools" / "serve_wasm_static.py"
GATE = "irv3browser"
SHA256_LENGTH = 64


def _run(arguments: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        arguments,
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


def _skip(reason: str) -> int:
    print("TEV_SCRIPT_IR_V3_BROWSER_WASM_GATE=SKIPPED_" + reason)
    return 0


def _process_failure(label: str, completed: subprocess.CompletedProcess[str]) -> int:
    print(label + "=FAIL")
    if completed.stdout:
        print(label + "_STDOUT=" + completed.stdout[-8000:].replace("\n", "\\n"))
    if completed.stderr:
        print(label + "_STDERR=" + completed.stderr[-8000:].replace("\n", "\\n"))
    return 1


def _find_browser() -> str | None:
    requested = os.environ.get("TEV_BROWSER_EXE") or os.environ.get("BROWSER_EXE")
    if requested:
        path = Path(requested)
        if path.is_file():
            return str(path.resolve())
        raise RuntimeError(f"requested browser executable does not exist: {requested}")

    if os.name == "nt":
        candidates = [
            Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Microsoft/Edge/Application/msedge.exe",
            Path(os.environ.get("PROGRAMFILES", "")) / "Microsoft/Edge/Application/msedge.exe",
            Path(os.environ.get("PROGRAMFILES", "")) / "Google/Chrome/Application/chrome.exe",
            Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Google/Chrome/Application/chrome.exe",
            Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/Application/chrome.exe",
        ]
        for candidate in candidates:
            if str(candidate) and candidate.is_file():
                return str(candidate.resolve())

    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome", "msedge"):
        resolved = shutil.which(name)
        if resolved:
            return resolved
    return None


def _find_publish_root(publish: Path) -> Path:
    candidates: list[Path] = []
    for index in publish.rglob("index.html"):
        parent = index.parent
        if (parent / "main.mjs").is_file() and (parent / "_framework" / "dotnet.js").is_file():
            candidates.append(parent)
    if len(candidates) != 1:
        raise RuntimeError(
            "browser publish root discovery expected exactly one root, observed="
            + repr([str(item) for item in candidates])
        )
    return candidates[0]


def _require_wasm(root: Path) -> str:
    candidates = sorted(root.rglob("*.wasm"))
    if not candidates:
        raise RuntimeError("browser publish contains no wasm binary")
    valid = []
    for candidate in candidates:
        data = candidate.read_bytes()[:4]
        if data == b"\x00asm":
            valid.append(candidate)
    if not valid:
        raise RuntimeError("browser publish contains no valid wasm magic")
    return str(valid[0].relative_to(root)).replace("\\", "/")


def _wait_port(port_file: Path, process: subprocess.Popen[str], timeout: float = 20.0) -> int:
    deadline = time.monotonic() + timeout
    while time.monotonic() <= deadline:
        if process.poll() is not None:
            raise RuntimeError(f"static server exited early with code {process.returncode}")
        if port_file.is_file():
            raw = port_file.read_text(encoding="ascii").strip()
            if raw.isdigit() and 0 < int(raw) < 65536:
                return int(raw)
        time.sleep(0.1)
    raise RuntimeError("static server port timeout")


def _wait_health(url: str, process: subprocess.Popen[str], timeout: float = 20.0) -> None:
    deadline = time.monotonic() + timeout
    last_error = ""
    while time.monotonic() <= deadline:
        if process.poll() is not None:
            raise RuntimeError(f"static server exited before health with code {process.returncode}")
        try:
            request = urllib.request.Request(url + "/__tev_health", method="GET")
            with urllib.request.urlopen(request, timeout=2) as response:
                if response.status == 204:
                    return
                last_error = f"status={response.status}"
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            last_error = type(error).__name__ + ":" + str(error)
        time.sleep(0.1)
    raise RuntimeError("static server health timeout: " + last_error)


def _wait_witness(
    witness_file: Path,
    server_process: subprocess.Popen[str],
    browser_process: subprocess.Popen[str],
    token: str,
    timeout: float = 180.0,
) -> dict[str, object]:
    deadline = time.monotonic() + timeout
    browser_exit_seen_at: float | None = None
    while time.monotonic() <= deadline:
        if server_process.poll() is not None:
            raise RuntimeError(f"static server exited during witness wait code={server_process.returncode}")
        if witness_file.is_file():
            lines = [line for line in witness_file.read_text(encoding="utf-8").splitlines() if line.strip()]
            if len(lines) > 1:
                raise RuntimeError(f"multiple browser witness receipts observed: {len(lines)}")
            if len(lines) == 1:
                receipt = json.loads(lines[0])
                if receipt.get("schema") != "TEV_SCRIPT_BROWSER_WITNESS_V1":
                    raise RuntimeError("browser witness schema mismatch")
                if receipt.get("gate") != GATE:
                    raise RuntimeError("browser witness gate mismatch")
                if not secrets.compare_digest(str(receipt.get("token", "")), token):
                    raise RuntimeError("browser witness token mismatch")
                if receipt.get("status") == "FAIL":
                    raise RuntimeError("browser witness reported FAIL detail=" + str(receipt.get("detail")))
                if receipt.get("status") != "PASS":
                    raise RuntimeError("browser witness status invalid")
                return receipt
        if browser_process.poll() is not None:
            if browser_exit_seen_at is None:
                browser_exit_seen_at = time.monotonic()
            elif time.monotonic() - browser_exit_seen_at > 3.0:
                raise RuntimeError(
                    f"browser exited before witness code={browser_process.returncode}"
                )
        time.sleep(0.1)
    raise RuntimeError("browser witness timeout")


def _stop_process(process: subprocess.Popen[str] | None) -> None:
    if process is None or process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            capture_output=True,
            check=False,
        )
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass
        return
    process.terminate()
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=3)


def _stop_browser_process(process: subprocess.Popen[str] | None, profile: Path) -> None:
    _stop_process(process)
    if os.name != "nt":
        return
    environment = os.environ.copy()
    environment["TEV_BROWSER_PROFILE_CLEANUP"] = str(profile.resolve())
    arguments = [
        "powershell.exe",
        "-NoProfile",
        "-NonInteractive",
        "-Command",
        "$needle=$env:TEV_BROWSER_PROFILE_CLEANUP; "
        "$deadline=(Get-Date).AddSeconds(30); "
        "do { "
        "$targets=@(Get-CimInstance Win32_Process | "
        "Where-Object { $_.CommandLine -and $_.CommandLine.Contains($needle) }); "
        "if ($targets.Count -eq 0) { exit 0 }; "
        "$targets | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }; "
        "Start-Sleep -Milliseconds 250 "
        "} while ((Get-Date) -lt $deadline); exit 1",
    ]
    try:
        completed = subprocess.run(
            arguments,
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=35,
        )
    except subprocess.TimeoutExpired as error:
        raise RuntimeError(
            "browser profile cleanup timed out; stdout="
            + _cleanup_output(error.stdout)
            + "; stderr="
            + _cleanup_output(error.stderr)
        ) from error
    if completed.returncode != 0:
        raise RuntimeError(
            f"browser profile cleanup exited {completed.returncode}; stdout="
            + _cleanup_output(completed.stdout)
            + "; stderr="
            + _cleanup_output(completed.stderr)
        )


def _cleanup_output(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        text = value.decode("utf-8", errors="replace")
    else:
        text = value
    return text[-4000:].replace("\r", "\\r").replace("\n", "\\n")


def main() -> int:
    if shutil.which("dotnet") is None:
        return _skip("DOTNET_UNAVAILABLE")
    browser = _find_browser()
    if browser is None:
        return _skip("CHROMIUM_UNAVAILABLE")

    cases = load_strict_json(CASES_PATH)
    scenario = load_strict_json(SCENARIO_PATH)
    program = cases["valid_program"]
    expected_receipt = run_ir_v3_conformance(program, scenario)
    expected_receipt_hash = expected_receipt.receipt_hash

    checkpoint_runtime = ScriptRuntimeV3(program)
    checkpoint_runtime.invoke("E", "start")
    expected_checkpoint = RuntimeCheckpointV2.capture(checkpoint_runtime)
    expected_checkpoint_hash = expected_checkpoint.checkpoint_hash
    if len(expected_receipt_hash) != SHA256_LENGTH or len(expected_checkpoint_hash) != SHA256_LENGTH:
        print("TEV_SCRIPT_IR_V3_BROWSER_ORACLE_HASH=FAIL")
        return 1
    print("TEV_SCRIPT_IR_V3_BROWSER_HOST_ORACLES=PASS")
    print("TEV_SCRIPT_IR_V3_BROWSER_EXPECTED_RECEIPT_HASH=" + expected_receipt_hash)
    print("TEV_SCRIPT_IR_V3_BROWSER_EXPECTED_CHECKPOINT_HASH=" + expected_checkpoint_hash)

    portable_surface = _run([sys.executable, str(ROOT / "tools" / "validate_ir_v3_csharp_portable_surface.py")])
    if portable_surface.returncode != 0:
        return _process_failure("TEV_SCRIPT_IR_V3_BROWSER_CSHARP_PORTABLE_SURFACE", portable_surface)
    if "TEV_SCRIPT_IR_V3_CSHARP_PORTABLE_SURFACE=PASS" not in portable_surface.stdout:
        print("TEV_SCRIPT_IR_V3_BROWSER_CSHARP_PORTABLE_SURFACE=FAIL_MISSING_WITNESS")
        return 1
    print("TEV_SCRIPT_IR_V3_BROWSER_CSHARP_PORTABLE_SURFACE=PASS")

    with tempfile.TemporaryDirectory(prefix="tev_irv3_browser_") as temp_raw:
        temp = Path(temp_raw)
        # Keep Mono AOT intermediates below MAX_PATH even when an isolated
        # executor materializes the repository under a deeply nested root.
        artifacts = temp / "artifacts"
        publish = temp / "publish"
        build = _run(
            [
                "dotnet",
                "publish",
                str(PROJECT),
                "--configuration",
                "Release",
                "--nologo",
                "--verbosity",
                "minimal",
                "--artifacts-path",
                str(artifacts),
                "-p:RunAOTCompilation=true",
                f"-p:PublishDir={publish}",
            ]
        )
        if build.returncode != 0:
            return _process_failure("TEV_SCRIPT_IR_V3_BROWSER_WASM_BUILD", build)
        root = _find_publish_root(publish)
        wasm = _require_wasm(root)
        print("TEV_SCRIPT_IR_V3_BROWSER_WASM_BUILD=PASS")
        print("TEV_SCRIPT_IR_V3_BROWSER_WASM_MAGIC=PASS path=" + wasm)
        print("TEV_SCRIPT_IR_V3_BROWSER_WASM_AOT_REQUESTED=PASS")

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
        try:
            with server_stdout.open("w", encoding="utf-8") as server_out, server_stderr.open("w", encoding="utf-8") as server_err:
                server_process = subprocess.Popen(
                    [
                        sys.executable,
                        str(SERVER),
                        "--root",
                        str(root),
                        "--port-file",
                        str(port_file),
                        "--witness-file",
                        str(witness_file),
                        "--witness-gate",
                        GATE,
                        "--witness-token",
                        token,
                    ],
                    cwd=ROOT,
                    stdout=server_out,
                    stderr=server_err,
                    text=True,
                    encoding="utf-8",
                )
                port = _wait_port(port_file, server_process)
                base_url = f"http://127.0.0.1:{port}"
                _wait_health(base_url, server_process)
                print("TEV_SCRIPT_IR_V3_BROWSER_HTTP_SERVER=PASS")

                profile.mkdir()
                url = base_url + "/?tev_witness_token=" + token
                arguments = [
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
                ]
                with browser_stdout.open("w", encoding="utf-8") as browser_out, browser_stderr.open("w", encoding="utf-8") as browser_err:
                    browser_process = subprocess.Popen(
                        arguments,
                        cwd=root,
                        stdout=browser_out,
                        stderr=browser_err,
                        text=True,
                        encoding="utf-8",
                    )
                    receipt = _wait_witness(
                        witness_file,
                        server_process,
                        browser_process,
                        token,
                    )
            expected_detail = (
                "receipt=" + expected_receipt_hash
                + ";checkpoint=" + expected_checkpoint_hash
            )
            if receipt.get("detail") != expected_detail:
                print("TEV_SCRIPT_IR_V3_BROWSER_WITNESS_DETAIL=FAIL")
                print("EXPECTED_DETAIL=" + expected_detail)
                print("OBSERVED_DETAIL=" + str(receipt.get("detail")))
                return 1
            print("TEV_SCRIPT_IR_V3_BROWSER_HTTP_WITNESS=PASS")
            print("TEV_SCRIPT_IR_V3_BROWSER_RECEIPT_PARITY=PASS")
            print("TEV_SCRIPT_IR_V3_BROWSER_CHECKPOINT_PARITY=PASS")
            print("TEV_SCRIPT_IR_V3_BROWSER_WASM_GATE=PASS")
            return 0
        except Exception as error:  # noqa: BLE001
            print("TEV_SCRIPT_IR_V3_BROWSER_WASM_GATE=FAIL")
            print("TEV_SCRIPT_IR_V3_BROWSER_ERROR=" + type(error).__name__ + ":" + str(error))
            for label, path in (
                ("SERVER_STDOUT", server_stdout),
                ("SERVER_STDERR", server_stderr),
                ("BROWSER_STDOUT", browser_stdout),
                ("BROWSER_STDERR", browser_stderr),
            ):
                if path.is_file():
                    text = path.read_text(encoding="utf-8", errors="replace")[-6000:]
                    if text:
                        print("TEV_SCRIPT_IR_V3_BROWSER_" + label + "=" + text.replace("\n", "\\n"))
            return 1
        finally:
            _stop_browser_process(browser_process, profile)
            _stop_process(server_process)


if __name__ == "__main__":
    raise SystemExit(main())
