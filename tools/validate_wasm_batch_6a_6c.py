from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def function_slice(source: str, name: str) -> str:
    start = source.index(f"function {name} {{")
    end = source.find("\nfunction ", start + 10)
    if end < 0:
        end = len(source)
    return source[start:end]


def main() -> int:
    runner = (ROOT / "RUN_TEV_SCRIPT_WASM_BATCH_6A_6C_V1.ps1").read_text(
        encoding="utf-8"
    )
    headless_runner = function_slice(runner, "Invoke-HeadlessHttpWitness")
    waiter = function_slice(runner, "Wait-TevHttpWitness")
    selftest = function_slice(runner, "Test-HttpWitnessServerContract")

    core = ROOT / "runtimes/csharp/TevScript.Core"
    unity_core = ROOT / "unity/Package/Runtime/Core"
    core_names = sorted(p.name for p in core.glob("*.cs"))
    unity_names = sorted(p.name for p in unity_core.glob("*.cs"))
    require(core_names == unity_names, "core_name_set")
    require(len(core_names) == 11, f"core_count:{len(core_names)}")
    for name in core_names:
        require(
            (core / name).read_bytes() == (unity_core / name).read_bytes(),
            f"core_mirror:{name}",
        )

    core_json = (core / "TevScriptJson.cs").read_text(encoding="utf-8")
    require("using System.Security.Cryptography;" not in core_json,
            "core_sha256_host_crypto_using_present")
    require("SHA256.Create()" not in core_json,
            "core_sha256_host_provider_present")
    for marker in (
        "ComputeSha256(Encoding.UTF8.GetBytes(text))",
        "Host-independent SHA-256 for TEV canonical identity",
        "private static byte[] ComputeSha256(byte[] input)",
        "0x428a2f98U",
        "0xc67178f2U",
        "private static uint RotateRight(uint value, int bits)",
        "private static void WriteUInt32BigEndian(",
    ):
        require(marker in core_json, f"core_sha256_portable:{marker}")

    gate6a = (
        ROOT / "unity/PlayerGates/Web/Runtime/TevScriptUnityWebGate.cs"
    ).read_text(encoding="utf-8")
    gate6a_builder = (
        ROOT / "unity/PlayerGates/Web/Editor/TevScriptUnityWebBuildGate.cs"
    ).read_text(encoding="utf-8")
    jslib = (
        ROOT / "unity/PlayerGates/Web/Plugins/WebGL/TevScriptGate6A.jslib"
    ).read_text(encoding="utf-8")

    for marker in (
        "RuntimePlatform.WebGLPlayer",
        'DllImport("__Internal")',
        "UNITY_GATE6A_CORE_PARSE=PASS",
        "UNITY_GATE6A_RUNTIME_STATE=PASS",
        "TEV_SCRIPT_UNITY_WEB_GATE_6A=PASS",
    ):
        require(marker in gate6a, f"gate6a_marker:{marker}")
    require("BuildTarget.WebGL" in gate6a_builder, "gate6a_build_target")
    require("WebGLCompressionFormat.Disabled" in gate6a_builder, "gate6a_compression")
    require("data-tev-gate6a" in jslib, "gate6a_internal_dom_state")

    gate6b_project = (
        ROOT / "runtimes/csharp/TevScript.BrowserWasmGate/TevScript.BrowserWasmGate.csproj"
    ).read_text(encoding="utf-8")
    gate6b_program = (
        ROOT / "runtimes/csharp/TevScript.BrowserWasmGate/Program.cs"
    ).read_text(encoding="utf-8")
    gate6b_main = (
        ROOT / "runtimes/csharp/TevScript.BrowserWasmGate/main.mjs"
    ).read_text(encoding="utf-8")
    gate6b_index = (
        ROOT / "runtimes/csharp/TevScript.BrowserWasmGate/index.html"
    ).read_text(encoding="utf-8")

    for marker in (
        'Sdk="Microsoft.NET.Sdk.WebAssembly"',
        "<RuntimeIdentifier>browser-wasm</RuntimeIdentifier>",
        "<RunAOTCompilation>true</RunAOTCompilation>",
        '<Content Include="main.mjs"',
        'TargetPath="wwwroot/main.mjs"',
        'TargetPath="wwwroot/index.html"',
        '<OverrideHtmlAssetPlaceholders>false</OverrideHtmlAssetPlaceholders>',
        'CopyToPublishDirectory="Always"',
    ):
        require(marker in gate6b_project, f"gate6b_project:{marker}")
    require("UnityEngine" not in gate6b_program, "gate6b_unity_dependency")
    require("OperatingSystem.IsBrowser()" in gate6b_program, "gate6b_browser_guard")
    require(
        "TEV_SCRIPT_PURE_CORE_BROWSER_WASM_GATE_6B=PASS" in gate6b_program,
        "gate6b_pass_marker",
    )
    for marker in (
        "tev_witness_token",
        "URLSearchParams",
        "fetch('/__tev_witness?'",
        "gate: 'gate6b'",
        "emitWitness('PASS'",
        "emitWitness('FAIL'",
        "dotnet.run()",
    ):
        require(marker in gate6b_main, f"gate6b_http_witness:{marker}")
    require("__tev_hold" not in gate6b_index, "gate6b_hold_removed")
    require("__tev_hold" not in gate6b_main, "gate6b_hold_js_removed")

    server = (ROOT / "tools/serve_wasm_static.py").read_text(encoding="utf-8")
    for marker in (
        'parsed.path == "/__tev_health"',
        'parsed.path == "/__tev_witness"',
        '"--witness-file"',
        '"--witness-gate"',
        '"--witness-token"',
        "hmac.compare_digest",
        "Handler.witness_consumed",
        "TOKEN_ALREADY_CONSUMED",
        "TOKEN_MISMATCH",
        "DETAIL_EMPTY",
        "observed_unix_ns",
        "os.fsync(handle.fileno())",
        '"TEV_SCRIPT_BROWSER_WITNESS_V1"',
        "WASM_HTTP_WITNESS_PERSISTED=PASS",
    ):
        require(marker in server, f"http_witness_server:{marker}")
    require("__tev_hold" not in server, "obsolete_hold_endpoint_present")

    require(
        "(Get-Content -LiteralPath $portFile -Raw).Trim()" not in runner,
        "unsafe_null_port_trim_present",
    )
    for marker in (
        "STATIC_SERVER_PORT_FILE_EMPTY_RETRY=YES",
        "STATIC_SERVER_PORT_READY=PASS",
        "STATIC_SERVER_PORT_READY_TIMEOUT",
        "[string]::IsNullOrWhiteSpace",
        "STATIC_SERVER_PROCESS_ALIVE=PASS",
        "STATIC_SERVER_HTTP_READY=PASS",
        "STATIC_SERVER_HTTP_READY_TIMEOUT",
        "STATIC_SERVER_EXITED_AFTER_PORT",
        "/__tev_health",
    ):
        require(marker in runner, f"server_readiness_marker:{marker}")

    require("/__tev_hold" not in server, "v20_server_hold_endpoint_removed")
    require("tev-gate6b-hold" not in gate6b_main, "v20_main_dead_hold_removed")
    require("TEV_CORE_BROWSER_WASM_PASS" in runner, "v20_gate6b_detail_binding_missing")
    require("HEADLESS_BROWSER_URL=$url" not in runner, "v20_nonce_url_log_leak")

    # V20 browser authority: no DOM scraping, dump-dom, CDP or launcher PID authority.
    for forbidden in (
        "Invoke-HeadlessDom",
        "Receive-CdpTextMessage",
        "Invoke-CdpCommand",
        "ClientWebSocket",
        "DevToolsActivePort",
        "--remote-debugging-port",
        "--remote-allow-origins",
        "Page.navigate",
        "Runtime.evaluate",
        "document.documentElement.outerHTML",
        "--dump-dom",
        "--virtual-time-budget=",
        "HEADLESS_CDP_",
        "CHROME_DEVTOOLS_PROTOCOL",
        "__tev_hold",
    ):
        require(forbidden not in runner, f"forbidden_browser_authority:{forbidden}")

    for marker in (
        "HEADLESS_BROWSER_AUTHORITY=LOOPBACK_HTTP_WITNESS",
        "HEADLESS_WAIT_MODE=REAL_TIME_HTTP_WITNESS_POLL",
        "HEADLESS_WITNESS_NONCE_BITS=128",
        "New-TevWitnessToken",
        "Wait-TevHttpWitness",
        "Invoke-HeadlessHttpWitness",
        "HEADLESS_HTTP_WITNESS=PASS",
        "HEADLESS_HTTP_WITNESS_FAIL",
        "HEADLESS_HTTP_WITNESS_TIMEOUT",
        "HEADLESS_HTTP_WITNESS_TOKEN_MISMATCH",
        "HEADLESS_HTTP_WITNESS_GATE_MISMATCH",
        "tev_witness_token=",
        "[Uri]::EscapeDataString($token)",
        "--user-data-dir=$profile",
    ):
        require(marker in runner, f"headless_http_contract:{marker}")

    for marker in (
        "WASM_HTTP_WITNESS_WRONG_NONCE_IGNORED=PASS",
        "WASM_HTTP_WITNESS_FIRST_USE=PASS",
        "WASM_HTTP_WITNESS_NONCE_REUSE_IGNORED=PASS",
        "WASM_HTTP_WITNESS_EXPLICIT_FAIL_ABORT=PASS",
        "WASM_HTTP_WITNESS_ABSENCE_TIMEOUT=PASS",
        "WASM_HTTP_WITNESS_SERVER_CONTRACT=PASS",
    ):
        require(marker in selftest, f"witness_selftest:{marker}")

    for marker in (
        'gate: "gate6a"',
        'status: String(state)',
        'token: witnessToken',
        'detail: String(reason)',
        'fetch("/__tev_witness?"',
        'release(state, "TEV_JSLIB")',
        'release("FAIL", "WINDOW_ERROR")',
        'release("FAIL", "UNHANDLED_REJECTION")',
        "GATE6A_BROWSER_HTTP_WITNESS=PASS",
        "GATE6A_BROWSER_DOM=PASS",
    ):
        require(marker in runner, f"gate6a_http_witness:{marker}")

    for marker in (
        'gate: "gate6a-webgl2-probe"',
        'canvas.getContext("webgl2")',
        'detail = passed ? "WEBGL2_CONTEXT_PASS" : "WEBGL2_CONTEXT_FAIL"',
        '-Gate "gate6a-webgl2-probe"',
        'GATE6A_BROWSER_WEBGL2_CONTEXT=PASS',
    ):
        require(marker in runner, f"gate6a_webgl2_witness:{marker}")

    for marker in (
        '-Gate "gate6b"',
        "GATE6B_BROWSER_HTTP_WITNESS=PASS",
        "GATE6B_BROWSER_DOM=PASS",
        "GATE6B_AOT=PASS_REQUESTED_AND_BROWSER_EXECUTED",
    ):
        require(marker in runner, f"gate6b_browser_runner:{marker}")

    require('"--disable-gpu"' not in runner, "gate6a_forbidden_disable_gpu")
    for marker in (
        '"--use-gl=angle"',
        '"--use-angle=swiftshader"',
        '"--enable-unsafe-swiftshader"',
        '"--ignore-gpu-blocklist"',
        "HEADLESS_WEBGL_BACKEND=SWANGLE_SWIFTSHADER",
    ):
        require(marker in headless_runner, f"gate6a_browser_marker:{marker}")

    # Gate 6B publish-layout fixes remain intact.
    for marker in (
        '-p:PublishDir=$publish6b',
        '$publish6b = Join-Path $runRoot "gate6b-publish"',
        '$wwwroot6b = Join-Path $publish6b "wwwroot"',
        '$framework6b = Join-Path $webRoot6b "_framework"',
        '-Filter "dotnet*.js"',
        "GATE6B_DOTNET_JS_PATH=",
        "GATE6B_PUBLISH_LAYOUT=PASS",
        "GATE6B_PRIMARY_WASM=",
        "GATE6B_MAIN_MJS_PUBLISHED=PASS",
        "GATE6B_WEB_ROOT=",
        "GATE6B_DOTNET_JS_IMPORT_REBOUND=PASS",
        "GATE6B_PUBLISH_FILE=",
        "GATE6B_PUBLISH_MISSING=",
        "GATE6B_PUBLISH_LAYOUT_INVALID",
    ):
        require(marker in runner, f"gate6b_publish_contract:{marker}")

    gate6c_project = (
        ROOT / "runtimes/csharp/TevScript.WasiGate/TevScript.WasiGate.csproj"
    ).read_text(encoding="utf-8")
    gate6c_program = (
        ROOT / "runtimes/csharp/TevScript.WasiGate/Program.cs"
    ).read_text(encoding="utf-8")
    require(
        "<RuntimeIdentifier>wasi-wasm</RuntimeIdentifier>" in gate6c_project,
        "gate6c_rid",
    )
    require("OperatingSystem.IsWasi()" in gate6c_program, "gate6c_wasi_guard")
    require("UnityEngine" not in gate6c_program, "gate6c_unity_dependency")
    require(
        "TEV_SCRIPT_PURE_CORE_WASI_GATE_6C=PASS" in gate6c_program,
        "gate6c_pass_marker",
    )

    require('& $wasmtimeExe $primaryWasm6c.FullName' not in runner,
            "gate6c_forbidden_direct_wasmtime_invocation")
    require(
        'Join-Path $publish6c "run-wasmtime.sh"' not in runner,
        "gate6c_forbidden_publishdir_run_script_assumption",
    )
    for marker in (
        '-p:PublishDir=$publish6c',
        '$publish6c = Join-Path $runRoot "gate6c-publish"',
        '$publishStartedUtc6c = [DateTime]::UtcNow',
        '$runScriptSearchRoot6c = Join-Path $projectDir6c "bin"',
        '-Filter "run-wasmtime.sh"',
        'GATE6C_DOTNET_RUN_SCRIPT_FRESH_MATCH_MISSING',
        'GATE6C_DOTNET_RUN_SCRIPT_SOURCE=SDK_WASM_APP_DIR_PASS',
        "GATE6C_DOTNET_RUN_SCRIPT=PASS",
        "GATE6C_DOTNET_RUN_CONTRACT=NON_SINGLE_FILE_PASS",
        "wasmtime run --dir . dotnet.wasm",
        "GATE6C_DOTNET_HOST_WASM=PASS",
        '"-S"',
        '"http"',
        "GATE6C_WASMTIME_WASI_HTTP=ENABLED_FOR_LINKAGE",
        "GATE6C_WASMTIME_DIR_PREOPEN=CONFIGURED_CURRENT_PUBLISH_DIR",
        "-WorkingDirectory $publish6c",
        "GATE6C_WASMTIME_COMMAND=wasmtime run -S http --dir . dotnet.wasm",
        "GATE6C_WASMTIME_EXECUTION=PASS",
    ):
        require(marker in runner, f"gate6c_wasmtime_contract:{marker}")

    for marker in (
        "Get-DotNetWasiSdkRequirement",
        "_ExpectedWasiSdkVersion",
        "DOTNET_WASI_VERSION_AUTHORITY_PROPERTY=",
        "DOTNET_WASI_PACK_VERSION=",
        "DOTNET_WASI_REQUIRED_SDK_VERSION=",
        "Get-WasiSdkVersionText",
        'Join-Path $Root "VERSION"',
        "WASI_SDK=PASS",
        "WASI_SDK_VERSION_FILE=PASS",
        "WASI_SDK_VERSION_MATCH=PASS",
        "WASI_SDK_REQUIRED_VERSION_NOT_FOUND=",
        "bin\\clang.exe",
        "share\\wasi-sysroot",
    ):
        require(marker in runner, f"wasi_sdk_preflight_marker:{marker}")

    for marker in (
        "UNITY_WEBGL_SUPPORT=PASS",
        "WASM_TOOLS_WORKLOAD=PASS",
        "WASI_EXPERIMENTAL_WORKLOAD=PASS",
        "HEADLESS_BROWSER=PASS",
        "WASMTIME=PASS",
        "TEV_SCRIPT_WASM_BATCH_6A_6C=PASS",
        "WASM_BATCH_CORE_SHA256_PORTABILITY_REGRESSION=PASS",
        "CORE_SHA256_PROVIDER=TEV_MANAGED_HOST_INDEPENDENT",
        "CSHARP_CANONICAL_VECTORS=12_PASS",
    ):
        require(marker in runner, f"runner_marker:{marker}")

    print("WASM_BATCH_CORE_PRODUCT_CHANGES=2_PHYSICAL_1_LOGICAL")
    print("WASM_BATCH_CORE_MIRROR=11_BYTE_IDENTICAL_PASS")
    print("WASM_BATCH_CORE_SHA256_PROVIDER=TEV_MANAGED_HOST_INDEPENDENT_PASS")
    print("GATE6A_STATIC=PASS")
    print("GATE6A_HEADLESS_WEBGL2_HARNESS=SWANGLE_SWIFTSHADER_PASS")
    print("HEADLESS_BROWSER_AUTHORITY=LOOPBACK_HTTP_WITNESS")
    print("HEADLESS_HTTP_NONCE_128BIT_HARNESS=PASS")
    print("HEADLESS_HTTP_WRONG_NONCE_IGNORE_HARNESS=PASS")
    print("HEADLESS_HTTP_NONCE_REUSE_REJECT_HARNESS=PASS")
    print("HEADLESS_HTTP_EXPLICIT_FAIL_ABORT_HARNESS=PASS")
    print("HEADLESS_HTTP_ABSENCE_TIMEOUT_HARNESS=PASS")
    print("HEADLESS_HTTP_RECEIPT_FSYNC_HARNESS=PASS")
    print("GATE6B_EXPLICIT_PUBLISH_DIR_HARNESS=PASS")
    print("GATE6B_WWWROOT_STATIC_WEB_ROOT=PASS")
    print("GATE6C_DOTNET_GENERATED_WASMTIME_CONTRACT=PASS")
    print("GATE6C_WASMTIME_WASI_HTTP_LINKAGE_HARNESS=PASS")
    print("GATE6B_STATIC=PASS")
    print("GATE6C_STATIC=PASS")
    print("GATE6D=NOT_IN_SCOPE")
    print("TEV_SCRIPT_WASM_BATCH_6A_6C_STATIC=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
