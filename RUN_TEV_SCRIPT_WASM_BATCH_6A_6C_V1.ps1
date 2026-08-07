[CmdletBinding()]
param(
    [string]$RepositoryRoot = "C:\mio\TEV-Script",
    [string]$UnityExe = "",
    [string]$BrowserExe = "",
    [string]$WasiSdkPath = "",
    [switch]$RequireClean,
    [switch]$PreflightOnly
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
if (Get-Variable PSNativeCommandUseErrorActionPreference -ErrorAction SilentlyContinue) {
    $PSNativeCommandUseErrorActionPreference = $false
}

function Require-CleanGit {
    param([string]$Root)
    $dirty = @(git -C $Root status --porcelain=v1 --untracked-files=all)
    if ($LASTEXITCODE -ne 0) { throw "GIT_STATUS_QUERY_FAILED" }
    if ($dirty.Count -ne 0) {
        $dirty | ForEach-Object { Write-Host "DIRTY=$_" }
        throw "WORKTREE_NOT_CLEAN"
    }
}

function Resolve-UnityExe {
    param([string]$Requested)

    if ($Requested) {
        if (-not (Test-Path -LiteralPath $Requested -PathType Leaf)) {
            throw "UNITY_EXE_NOT_FOUND=$Requested"
        }
        return (Resolve-Path -LiteralPath $Requested).Path
    }

    $preferred =
        "C:\Program Files\Unity\Hub\Editor\6000.3.10f1\Editor\Unity.exe"
    if (Test-Path -LiteralPath $preferred -PathType Leaf) {
        return $preferred
    }

    $hubRoot = "C:\Program Files\Unity\Hub\Editor"
    $candidates = @(
        Get-ChildItem -LiteralPath $hubRoot -Directory |
        Where-Object { $_.Name -like "6000.3*" } |
        Sort-Object Name -Descending |
        ForEach-Object { Join-Path $_.FullName "Editor\Unity.exe" } |
        Where-Object { Test-Path -LiteralPath $_ -PathType Leaf }
    )

    if ($candidates.Count -lt 1) {
        throw "UNITY_6000_3_NOT_FOUND"
    }

    return $candidates[0]
}

function Resolve-BrowserExe {
    param([string]$Requested)

    if ($Requested) {
        if (-not (Test-Path -LiteralPath $Requested -PathType Leaf)) {
            throw "BROWSER_EXE_NOT_FOUND=$Requested"
        }
        return (Resolve-Path -LiteralPath $Requested).Path
    }

    $candidates = @(
        "$env:ProgramFiles(x86)\Microsoft\Edge\Application\msedge.exe"
        "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe"
        "$env:ProgramFiles\Google\Chrome\Application\chrome.exe"
        "$env:ProgramFiles(x86)\Google\Chrome\Application\chrome.exe"
    )

    foreach ($candidate in $candidates) {
        if ($candidate -and
            (Test-Path -LiteralPath $candidate -PathType Leaf)) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }

    throw "CHROMIUM_BROWSER_NOT_FOUND"
}

function Get-DotNetWasiSdkRequirement {
    $gateProject = Join-Path $PSScriptRoot `
        "runtimes\csharp\TevScript.WasiGate\TevScript.WasiGate.csproj"

    if (-not (Test-Path -LiteralPath $gateProject -PathType Leaf)) {
        throw "WASI_GATE_PROJECT_NOT_FOUND_FOR_PREFLIGHT=$gateProject"
    }

    $projectText = Get-Content -LiteralPath $gateProject -Raw
    $tfmMatch = [regex]::Match(
        $projectText,
        '<TargetFramework>\s*net([0-9]+)\.[0-9]+\s*</TargetFramework>'
    )

    if (-not $tfmMatch.Success) {
        throw "WASI_GATE_TARGET_FRAMEWORK_DISCOVERY_FAILED"
    }

    $tfmMajor = $tfmMatch.Groups[1].Value

    $dotnetCommand = Get-Command dotnet -ErrorAction Stop
    $dotnetRoot = Split-Path -Parent $dotnetCommand.Source
    $packRoot = Join-Path $dotnetRoot `
        "packs\Microsoft.NET.Runtime.WebAssembly.Wasi.Sdk"

    if (-not (Test-Path -LiteralPath $packRoot -PathType Container)) {
        throw "DOTNET_WASI_PACK_ROOT_MISSING=$packRoot"
    }

    $packs = @(
        Get-ChildItem -LiteralPath $packRoot -Directory |
        Where-Object {
            $_.Name -like "$tfmMajor.*" -and
            (Test-Path -LiteralPath (
                Join-Path $_.FullName "Sdk\WasiApp.targets"
            ) -PathType Leaf)
        } |
        Sort-Object {
            try {
                [version]$_.Name
            }
            catch {
                [version]"0.0"
            }
        } -Descending
    )

    if ($packs.Count -lt 1) {
        throw "DOTNET_WASI_PACK_FOR_TFM_NOT_FOUND=net$tfmMajor"
    }

    $pack = $packs[0]
    $targets = Join-Path $pack.FullName "Sdk\WasiApp.targets"
    $targetsText = Get-Content -LiteralPath $targets -Raw

    # This is the actual property used by Microsoft's WasiApp.targets.
    # It may include a Condition attribute, so do not require a bare tag.
    $matches = @(
        [regex]::Matches(
            $targetsText,
            '(?is)<_ExpectedWasiSdkVersion(?:\s+[^>]*)?>\s*' +
            '([0-9]+(?:\.[0-9]+)+)\s*</_ExpectedWasiSdkVersion>'
        )
    )

    $versions = @(
        $matches |
        ForEach-Object { $_.Groups[1].Value } |
        Sort-Object -Unique
    )

    if ($versions.Count -ne 1) {
        $versions | ForEach-Object {
            Write-Host "DOTNET_WASI_EXPECTED_SDK_VERSION_CANDIDATE=$_"
        }

        throw (
            "DOTNET_WASI_EXPECTED_SDK_VERSION_DISCOVERY_FAILED " +
            "pack=$($pack.Name) targets=$targets count=$($versions.Count)"
        )
    }

    return [pscustomobject]@{
        TargetFramework = "net$tfmMajor.0"
        PackVersion = $pack.Name
        PackRoot = $pack.FullName
        Targets = $targets
        RequiredWasiSdkVersion = $versions[0]
        AuthorityProperty = "_ExpectedWasiSdkVersion"
    }
}

function Get-WasiSdkVersionText {
    param([string]$Root)

    $versionFile = Join-Path $Root "VERSION"

    if (-not (Test-Path -LiteralPath $versionFile -PathType Leaf)) {
        return $null
    }

    $raw = Get-Content `
        -LiteralPath $versionFile `
        -Raw `
        -ErrorAction SilentlyContinue

    if ([string]::IsNullOrWhiteSpace([string]$raw)) {
        return $null
    }

    return ([string]$raw).Trim()
}

function Test-WasiSdkRoot {
    param(
        [string]$Root,
        [string]$RequiredVersion
    )

    if ([string]::IsNullOrWhiteSpace($Root)) {
        return $false
    }

    if (-not (Test-Path -LiteralPath $Root -PathType Container)) {
        return $false
    }

    $clang = Join-Path $Root "bin\clang.exe"
    $sysroot = Join-Path $Root "share\wasi-sysroot"

    if (
        -not (Test-Path -LiteralPath $clang -PathType Leaf) -or
        -not (Test-Path -LiteralPath $sysroot -PathType Container)
    ) {
        return $false
    }

    $versionText = Get-WasiSdkVersionText -Root $Root

    if ([string]::IsNullOrWhiteSpace([string]$versionText)) {
        return $false
    }

    # Match Microsoft's WasiApp.targets semantics: VERSION must start with the
    # expected wasi-sdk version.
    return $versionText.StartsWith(
        $RequiredVersion,
        [System.StringComparison]::Ordinal
    )
}

function Resolve-WasiSdkPath {
    param(
        [string]$Requested,
        [string]$RequiredVersion
    )

    $candidates = @()

    if ($Requested) {
        $candidates += $Requested
    }

    # Prefer the version-pinned side-by-side installation.
    $candidates += @(
        (Join-Path $env:LOCALAPPDATA (
            "Programs\wasi-sdk\" + $RequiredVersion
        ))
    )

    if ($env:WASI_SDK_PATH) {
        $candidates += $env:WASI_SDK_PATH
    }

    $candidates += @(
        (Join-Path $env:LOCALAPPDATA "Programs\wasi-sdk")
    )

    foreach ($candidate in @($candidates | Select-Object -Unique)) {
        if ([string]::IsNullOrWhiteSpace($candidate)) {
            continue
        }

        if (-not (Test-Path -LiteralPath $candidate -PathType Container)) {
            continue
        }

        $root = (Resolve-Path -LiteralPath $candidate).Path

        if (Test-WasiSdkRoot `
            -Root $root `
            -RequiredVersion $RequiredVersion) {
            return $root
        }

        $nested = @(
            Get-ChildItem `
                -LiteralPath $root `
                -Directory `
                -ErrorAction SilentlyContinue |
            Where-Object {
                Test-WasiSdkRoot `
                    -Root $_.FullName `
                    -RequiredVersion $RequiredVersion
            }
        )

        if ($nested.Count -eq 1) {
            return $nested[0].FullName
        }
    }

    throw "WASI_SDK_REQUIRED_VERSION_NOT_FOUND=$RequiredVersion"
}

function Require-Workload {
    param(
        [string]$Text,
        [string]$Name,
        [string]$PassMarker
    )

    if ($Text -notmatch "(?m)^\s*" + [regex]::Escape($Name) + "\s") {
        throw "DOTNET_WORKLOAD_MISSING=$Name"
    }

    Write-Host $PassMarker
}

function Require-Markers {
    param(
        [string]$Text,
        [string[]]$Markers,
        [string]$Code
    )

    foreach ($marker in $Markers) {
        if (-not $Text.Contains($marker)) {
            throw "$Code=$marker"
        }
        Write-Host "WASM_BATCH_WITNESS_PASS=$marker"
    }
}

function Write-TevDomDiagnostics {
    param(
        [string]$Dom,
        [string]$Name
    )

    Write-Host "----- TEV DOM DIAGNOSTICS: $Name -----"

    $htmlMatch = [regex]::Match(
        $Dom,
        "<html[^>]*>",
        [System.Text.RegularExpressions.RegexOptions]::IgnoreCase
    )
    if ($htmlMatch.Success) {
        Write-Host $htmlMatch.Value
    }

    $preMatch = [regex]::Match(
        $Dom,
        '<pre id="tev-gate6a-diagnostics"[^>]*>(.*?)</pre>',
        [System.Text.RegularExpressions.RegexOptions]::Singleline
    )
    if ($preMatch.Success) {
        $decoded = [System.Net.WebUtility]::HtmlDecode(
            $preMatch.Groups[1].Value
        )
        Write-Host $decoded
    }

    $gate6bMatch = [regex]::Match(
        $Dom,
        '<pre id="tev-log"[^>]*>(.*?)</pre>',
        [System.Text.RegularExpressions.RegexOptions]::Singleline
    )
    if ($gate6bMatch.Success) {
        $decoded6b = [System.Net.WebUtility]::HtmlDecode(
            $gate6bMatch.Groups[1].Value
        )
        Write-Host $decoded6b
    }
}

function Test-WasmMagic {
    param([string]$Path)

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "WASM_BINARY_MISSING=$Path"
    }

    $bytes = [System.IO.File]::ReadAllBytes($Path)
    if ($bytes.Length -lt 8) {
        throw "WASM_BINARY_TOO_SMALL=$Path"
    }

    if (
        $bytes[0] -ne 0x00 -or
        $bytes[1] -ne 0x61 -or
        $bytes[2] -ne 0x73 -or
        $bytes[3] -ne 0x6d
    ) {
        throw "WASM_MAGIC_INVALID=$Path"
    }
}

function Start-StaticServer {
    param(
        [string]$Root,
        [string]$RunRoot,
        [string]$Name,
        [string]$WitnessGate,
        [string]$WitnessToken
    )

    $portFile = Join-Path $RunRoot "$Name-port.txt"
    $witnessFile = Join-Path $RunRoot "$Name-witness.jsonl"
    $stdout = Join-Path $RunRoot "$Name-http.log"
    $stderr = Join-Path $RunRoot "$Name-http.err.log"

    Remove-Item -LiteralPath $portFile -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $witnessFile -Force -ErrorAction SilentlyContinue

    $python = (Get-Command python -ErrorAction Stop).Source
    $server = Start-Process `
        -FilePath $python `
        -ArgumentList @(
            (Join-Path $RepositoryRoot "tools\serve_wasm_static.py")
            "--root"
            $Root
            "--port-file"
            $portFile
            "--witness-file"
            $witnessFile
            "--witness-gate"
            $WitnessGate
            "--witness-token"
            $WitnessToken
        ) `
        -RedirectStandardOutput $stdout `
        -RedirectStandardError $stderr `
        -PassThru

    $deadline = (Get-Date).AddSeconds(15)
    $port = $null

    while ($null -eq $port) {
        $server.Refresh()

        if ($server.HasExited) {
            Write-Host "STATIC_SERVER_EXIT_CODE=$($server.ExitCode)"
            if (Test-Path -LiteralPath $stderr -PathType Leaf) {
                Write-Host "----- STATIC SERVER STDERR: $Name -----"
                Get-Content -LiteralPath $stderr -Tail 250 |
                    ForEach-Object { Write-Host $_ }
            }
            throw "STATIC_SERVER_EXITED=$Name"
        }

        if (Test-Path -LiteralPath $portFile -PathType Leaf) {
            $rawPort = Get-Content `
                -LiteralPath $portFile `
                -Raw `
                -ErrorAction SilentlyContinue

            if (-not [string]::IsNullOrWhiteSpace([string]$rawPort)) {
                $candidatePort = ([string]$rawPort).Trim()

                if ($candidatePort -match "^[0-9]+$") {
                    $port = $candidatePort
                    break
                }

                throw "STATIC_SERVER_PORT_INVALID=${Name}:$candidatePort"
            }

            Write-Host "STATIC_SERVER_PORT_FILE_EMPTY_RETRY=YES name=$Name"
        }

        if ((Get-Date) -gt $deadline) {
            throw "STATIC_SERVER_PORT_READY_TIMEOUT=$Name"
        }

        Start-Sleep -Milliseconds 100
    }

    Write-Host "STATIC_SERVER_PORT_READY=PASS name=$Name port=$port"

    $baseUrl = "http://127.0.0.1:$port"
    $healthUrl = $baseUrl + "/__tev_health"
    $healthDeadline = (Get-Date).AddSeconds(15)
    $healthReady = $false
    $lastHealthError = ""

    while (-not $healthReady) {
        $server.Refresh()

        if ($server.HasExited) {
            Write-Host "STATIC_SERVER_EXIT_CODE=$($server.ExitCode)"
            if (Test-Path -LiteralPath $stderr -PathType Leaf) {
                Write-Host "----- STATIC SERVER STDERR: $Name -----"
                Get-Content -LiteralPath $stderr -Tail 250 |
                    ForEach-Object { Write-Host $_ }
            }
            throw "STATIC_SERVER_EXITED_AFTER_PORT name=$Name"
        }

        try {
            $health = Invoke-WebRequest `
                -Uri $healthUrl `
                -Method Get `
                -TimeoutSec 2 `
                -ErrorAction Stop

            if ([int]$health.StatusCode -eq 204) {
                $healthReady = $true
                break
            }

            $lastHealthError =
                "unexpected_status=$([int]$health.StatusCode)"
        }
        catch {
            $lastHealthError = $_.Exception.Message
        }

        if ((Get-Date) -gt $healthDeadline) {
            if (Test-Path -LiteralPath $stderr -PathType Leaf) {
                Write-Host "----- STATIC SERVER STDERR: $Name -----"
                Get-Content -LiteralPath $stderr -Tail 250 |
                    ForEach-Object { Write-Host $_ }
            }

            throw (
                "STATIC_SERVER_HTTP_READY_TIMEOUT " +
                "name=$Name url=$healthUrl last_error=$lastHealthError"
            )
        }

        Start-Sleep -Milliseconds 100
    }

    Write-Host "STATIC_SERVER_PROCESS_ALIVE=PASS name=$Name"
    Write-Host "STATIC_SERVER_HTTP_READY=PASS name=$Name url=$baseUrl"

    return [pscustomobject]@{
        Process = $server
        Url = $baseUrl
        Stdout = $stdout
        Stderr = $stderr
        WitnessFile = $witnessFile
        WitnessGate = $WitnessGate
        WitnessToken = $WitnessToken
    }
}

function New-TevWitnessToken {
    $bytes = New-Object byte[] 16
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $rng.GetBytes($bytes)
    }
    finally {
        $rng.Dispose()
    }

    return (($bytes | ForEach-Object { $_.ToString("x2") }) -join "")
}

function Stop-HeadlessBrowser {
    param(
        [System.Diagnostics.Process]$Process
    )

    if ($null -eq $Process) {
        return
    }

    try {
        $Process.Refresh()
        if (-not $Process.HasExited) {
            $taskkill = Get-Command taskkill.exe -ErrorAction SilentlyContinue
            if ($null -ne $taskkill) {
                & $taskkill.Source /PID $Process.Id /T /F 2>$null | Out-Null
            }
            else {
                Stop-Process -Id $Process.Id -Force -ErrorAction SilentlyContinue
            }
        }
    }
    catch {
        Stop-Process -Id $Process.Id -Force -ErrorAction SilentlyContinue
    }
    finally {
        $Process.Dispose()
    }
}

function Wait-TevHttpWitness {
    param(
        [string]$WitnessFile,
        [string]$Gate,
        [string]$Token,
        [int]$BudgetMilliseconds,
        [System.Diagnostics.Process]$ServerProcess,
        [string]$Name
    )

    $deadline = (Get-Date).AddMilliseconds($BudgetMilliseconds)
    $launcherExitLogged = $false

    while ((Get-Date) -le $deadline) {
        if ($null -ne $ServerProcess) {
            $ServerProcess.Refresh()
            if ($ServerProcess.HasExited) {
                throw "HEADLESS_HTTP_WITNESS_SERVER_EXITED name=$Name gate=$Gate exit=$($ServerProcess.ExitCode)"
            }
        }

        if (Test-Path -LiteralPath $WitnessFile -PathType Leaf) {
            $lines = @(
                Get-Content -LiteralPath $WitnessFile -ErrorAction Stop |
                    Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
            )

            if ($lines.Count -gt 1) {
                throw "HEADLESS_HTTP_WITNESS_MULTIPLE_RECEIPTS name=$Name count=$($lines.Count)"
            }

            if ($lines.Count -eq 1) {
                $receipt = $lines[0] | ConvertFrom-Json
                if ([string]$receipt.schema -ne "TEV_SCRIPT_BROWSER_WITNESS_V1") {
                    throw "HEADLESS_HTTP_WITNESS_SCHEMA_MISMATCH name=$Name"
                }
                if ([string]$receipt.gate -ne $Gate) {
                    throw "HEADLESS_HTTP_WITNESS_GATE_MISMATCH name=$Name expected=$Gate observed=$($receipt.gate)"
                }
                if ([string]$receipt.token -ne $Token) {
                    throw "HEADLESS_HTTP_WITNESS_TOKEN_MISMATCH name=$Name"
                }

                $status = [string]$receipt.status
                if ($status -eq "FAIL") {
                    throw "HEADLESS_HTTP_WITNESS_FAIL name=$Name gate=$Gate detail=$($receipt.detail)"
                }
                if ($status -ne "PASS") {
                    throw "HEADLESS_HTTP_WITNESS_STATUS_INVALID name=$Name status=$status"
                }

                Write-Host (
                    "HEADLESS_HTTP_WITNESS=PASS " +
                    "name=$Name gate=$Gate detail=$($receipt.detail)"
                )
                return $receipt
            }
        }

        Start-Sleep -Milliseconds 100
    }

    throw "HEADLESS_HTTP_WITNESS_TIMEOUT name=$Name gate=$Gate budget_ms=$BudgetMilliseconds"
}

function Invoke-HeadlessHttpWitness {
    param(
        [string]$Browser,
        [string]$Root,
        [string]$Path,
        [string]$RunRoot,
        [string]$Name,
        [string]$Gate,
        [int]$BudgetMilliseconds,
        [switch]$RequireWebGL
    )

    $token = New-TevWitnessToken
    if ($token -notmatch "^[0-9a-f]{32}$") {
        throw "HEADLESS_HTTP_WITNESS_TOKEN_GENERATION_FAILED name=$Name"
    }

    Write-Host "HEADLESS_BROWSER_AUTHORITY=LOOPBACK_HTTP_WITNESS"
    Write-Host "HEADLESS_WAIT_MODE=REAL_TIME_HTTP_WITNESS_POLL"
    Write-Host "HEADLESS_WITNESS_NONCE_BITS=128"

    $server = Start-StaticServer `
        -Root $Root `
        -RunRoot $RunRoot `
        -Name $Name `
        -WitnessGate $Gate `
        -WitnessToken $token

    $profile = Join-Path $RunRoot "$Name-browser-profile"
    New-Item -ItemType Directory -Path $profile -Force | Out-Null

    $browserStdout = Join-Path $RunRoot "$Name-browser.out.txt"
    $browserStderr = Join-Path $RunRoot "$Name-browser.err.txt"

    $args = @(
        "--headless=new"
        "--no-first-run"
        "--no-default-browser-check"
        "--disable-background-timer-throttling"
        "--disable-backgrounding-occluded-windows"
        "--disable-renderer-backgrounding"
        "--window-size=1280,720"
        "--user-data-dir=$profile"
    )

    if ($RequireWebGL) {
        $args += @(
            "--use-gl=angle"
            "--use-angle=swiftshader"
            "--enable-unsafe-swiftshader"
            "--ignore-gpu-blocklist"
            "--enable-webgl"
        )

        Write-Host "HEADLESS_WEBGL_BACKEND=SWANGLE_SWIFTSHADER"
        Write-Host "HEADLESS_WEBGL_UNSAFE_SWIFTSHADER=EXPLICIT_LOCAL_TEST_OPT_IN"
    }

    $separator = "?"
    if ($Path.Contains("?")) {
        $separator = "&"
    }
    $url = (
        $server.Url +
        $Path +
        $separator +
        "tev_witness_token=" +
        [Uri]::EscapeDataString($token)
    )
    $args += $url

    Write-Host (
        "HEADLESS_BROWSER_LAUNCH_URL=PASS " +
        "name=$Name gate=$Gate token=REDACTED"
    )

    $process = $null
    try {
        $process = Start-Process `
            -FilePath $Browser `
            -ArgumentList $args `
            -RedirectStandardOutput $browserStdout `
            -RedirectStandardError $browserStderr `
            -PassThru

        $receipt = Wait-TevHttpWitness `
            -WitnessFile $server.WitnessFile `
            -Gate $Gate `
            -Token $token `
            -BudgetMilliseconds $BudgetMilliseconds `
            -ServerProcess $server.Process `
            -Name $Name

        return $receipt
    }
    catch {
        Write-BrowserDiagnostics `
            -RunRoot $RunRoot `
            -Name $Name `
            -ServerLog $server.Stdout `
            -ServerErrorLog $server.Stderr
        throw
    }
    finally {
        Stop-HeadlessBrowser -Process $process

        if (-not $server.Process.HasExited) {
            Stop-Process -Id $server.Process.Id -Force -ErrorAction SilentlyContinue
            $server.Process.WaitForExit()
        }
        $server.Process.Dispose()
    }
}

function Test-HttpWitnessServerContract {
    param(
        [string]$RunRoot
    )

    $root = Join-Path $RunRoot "http-witness-selftest-root"
    New-Item -ItemType Directory -Path $root -Force | Out-Null
    Set-Content -LiteralPath (Join-Path $root "index.html") -Value "ok" -Encoding ascii

    # Wrong nonce is ignored; first valid use persists; reuse is ignored.
    $gate = "witness-selftest-pass"
    $token = New-TevWitnessToken
    $wrong = New-TevWitnessToken
    $server = Start-StaticServer `
        -Root $root `
        -RunRoot $RunRoot `
        -Name "witness-selftest-pass" `
        -WitnessGate $gate `
        -WitnessToken $token
    try {
        [void](Invoke-WebRequest `
            -Uri ($server.Url + "/__tev_witness?gate=$gate&status=PASS&token=$wrong&detail=WRONG_NONCE") `
            -Method Get `
            -TimeoutSec 2 `
            -ErrorAction Stop)
        Start-Sleep -Milliseconds 150
        if (Test-Path -LiteralPath $server.WitnessFile -PathType Leaf) {
            if ((Get-Item -LiteralPath $server.WitnessFile).Length -gt 0) {
                throw "WASM_HTTP_WITNESS_WRONG_NONCE_WAS_PERSISTED"
            }
        }
        Write-Host "WASM_HTTP_WITNESS_WRONG_NONCE_IGNORED=PASS"

        [void](Invoke-WebRequest `
            -Uri ($server.Url + "/__tev_witness?gate=$gate&status=PASS&token=$token&detail=SELFTEST_PASS") `
            -Method Get `
            -TimeoutSec 2 `
            -ErrorAction Stop)

        $receipt = Wait-TevHttpWitness `
            -WitnessFile $server.WitnessFile `
            -Gate $gate `
            -Token $token `
            -BudgetMilliseconds 3000 `
            -ServerProcess $server.Process `
            -Name "witness-selftest-pass"
        if ([string]$receipt.detail -ne "SELFTEST_PASS") {
            throw "WASM_HTTP_WITNESS_SELFTEST_DETAIL_MISMATCH"
        }
        Write-Host "WASM_HTTP_WITNESS_FIRST_USE=PASS"

        [void](Invoke-WebRequest `
            -Uri ($server.Url + "/__tev_witness?gate=$gate&status=FAIL&token=$token&detail=REUSE") `
            -Method Get `
            -TimeoutSec 2 `
            -ErrorAction Stop)
        Start-Sleep -Milliseconds 150
        $lines = @(Get-Content -LiteralPath $server.WitnessFile)
        if ($lines.Count -ne 1) {
            throw "WASM_HTTP_WITNESS_REUSE_PERSISTED count=$($lines.Count)"
        }
        Write-Host "WASM_HTTP_WITNESS_NONCE_REUSE_IGNORED=PASS"
    }
    finally {
        if (-not $server.Process.HasExited) {
            Stop-Process -Id $server.Process.Id -Force -ErrorAction SilentlyContinue
            $server.Process.WaitForExit()
        }
        $server.Process.Dispose()
    }

    # Explicit FAIL is persisted and the authority reader aborts it.
    $failGate = "witness-selftest-fail"
    $failToken = New-TevWitnessToken
    $failServer = Start-StaticServer `
        -Root $root `
        -RunRoot $RunRoot `
        -Name "witness-selftest-fail" `
        -WitnessGate $failGate `
        -WitnessToken $failToken
    try {
        [void](Invoke-WebRequest `
            -Uri ($failServer.Url + "/__tev_witness?gate=$failGate&status=FAIL&token=$failToken&detail=EXPECTED_FAIL") `
            -Method Get `
            -TimeoutSec 2 `
            -ErrorAction Stop)
        try {
            [void](Wait-TevHttpWitness `
                -WitnessFile $failServer.WitnessFile `
                -Gate $failGate `
                -Token $failToken `
                -BudgetMilliseconds 3000 `
                -ServerProcess $failServer.Process `
                -Name "witness-selftest-fail")
            throw "WASM_HTTP_WITNESS_FAIL_DID_NOT_ABORT"
        }
        catch {
            if ($_.Exception.Message -notlike "HEADLESS_HTTP_WITNESS_FAIL*") {
                throw
            }
        }
        Write-Host "WASM_HTTP_WITNESS_EXPLICIT_FAIL_ABORT=PASS"
    }
    finally {
        if (-not $failServer.Process.HasExited) {
            Stop-Process -Id $failServer.Process.Id -Force -ErrorAction SilentlyContinue
            $failServer.Process.WaitForExit()
        }
        $failServer.Process.Dispose()
    }

    # Absence of a valid witness is a timeout, never an inferred PASS.
    $timeoutGate = "witness-selftest-timeout"
    $timeoutToken = New-TevWitnessToken
    $timeoutServer = Start-StaticServer `
        -Root $root `
        -RunRoot $RunRoot `
        -Name "witness-selftest-timeout" `
        -WitnessGate $timeoutGate `
        -WitnessToken $timeoutToken
    try {
        try {
            [void](Wait-TevHttpWitness `
                -WitnessFile $timeoutServer.WitnessFile `
                -Gate $timeoutGate `
                -Token $timeoutToken `
                -BudgetMilliseconds 350 `
                -ServerProcess $timeoutServer.Process `
                -Name "witness-selftest-timeout")
            throw "WASM_HTTP_WITNESS_ABSENCE_DID_NOT_TIMEOUT"
        }
        catch {
            if ($_.Exception.Message -notlike "HEADLESS_HTTP_WITNESS_TIMEOUT*") {
                throw
            }
        }
        Write-Host "WASM_HTTP_WITNESS_ABSENCE_TIMEOUT=PASS"
    }
    finally {
        if (-not $timeoutServer.Process.HasExited) {
            Stop-Process -Id $timeoutServer.Process.Id -Force -ErrorAction SilentlyContinue
            $timeoutServer.Process.WaitForExit()
        }
        $timeoutServer.Process.Dispose()
    }

    Write-Host "WASM_HTTP_WITNESS_SERVER_CONTRACT=PASS"
}

function Write-BrowserDiagnostics {
    param(
        [string]$RunRoot,
        [string]$Name,
        [string]$ServerLog,
        [string]$ServerErrorLog = ""
    )

    $stderr = Join-Path $RunRoot "$Name-browser.err.txt"

    if (Test-Path -LiteralPath $stderr -PathType Leaf) {
        Write-Host "----- BROWSER STDERR: $Name -----"
        Get-Content -LiteralPath $stderr -Tail 250 |
            ForEach-Object { Write-Host $_ }
    }

    if ($ServerLog -and
        (Test-Path -LiteralPath $ServerLog -PathType Leaf)) {
        Write-Host "----- HTTP LOG: $Name -----"
        Get-Content -LiteralPath $ServerLog -Tail 250 |
            ForEach-Object { Write-Host $_ }
    }

    if ($ServerErrorLog -and
        (Test-Path -LiteralPath $ServerErrorLog -PathType Leaf)) {
        Write-Host "----- HTTP STDERR: $Name -----"
        Get-Content -LiteralPath $ServerErrorLog -Tail 250 |
            ForEach-Object { Write-Host $_ }
    }
}

if (-not (Test-Path -LiteralPath (Join-Path $RepositoryRoot ".git") -PathType Container)) {
    throw "REPOSITORY_NOT_FOUND=$RepositoryRoot"
}

Set-Location $RepositoryRoot

if ($RequireClean) {
    Require-CleanGit -Root $RepositoryRoot
}

$head = (git rev-parse HEAD).Trim()
$tree = (git rev-parse "HEAD^{tree}").Trim()
$branch = (git branch --show-current).Trim()

$resolvedUnity = Resolve-UnityExe -Requested $UnityExe
$editorRoot = Split-Path -Parent (Split-Path -Parent $resolvedUnity)
$editorVersion = Split-Path -Leaf $editorRoot

if ($editorVersion -notlike "6000.3*") {
    throw "UNITY_VERSION_OUTSIDE_WASM_BOUNDARY=$editorVersion"
}

$webglSupport = Join-Path $editorRoot "Editor\Data\PlaybackEngines\WebGLSupport"
if (-not (Test-Path -LiteralPath $webglSupport -PathType Container)) {
    throw "UNITY_WEBGL_SUPPORT_MISSING=$webglSupport"
}
Write-Host "UNITY_WEBGL_SUPPORT=PASS"

$resolvedBrowser = Resolve-BrowserExe -Requested $BrowserExe
Write-Host "HEADLESS_BROWSER=PASS"
Write-Host "HEADLESS_BROWSER_EXE=$resolvedBrowser"

$workloads = @(dotnet workload list 2>&1)
if ($LASTEXITCODE -ne 0) {
    throw "DOTNET_WORKLOAD_LIST_FAILED"
}
$workloadText = $workloads -join "`n"

Require-Workload `
    -Text $workloadText `
    -Name "wasm-tools" `
    -PassMarker "WASM_TOOLS_WORKLOAD=PASS"

Require-Workload `
    -Text $workloadText `
    -Name "wasi-experimental" `
    -PassMarker "WASI_EXPERIMENTAL_WORKLOAD=PASS"

$wasiRequirement = Get-DotNetWasiSdkRequirement

Write-Host "DOTNET_WASI_TARGET_FRAMEWORK=$($wasiRequirement.TargetFramework)"
Write-Host "DOTNET_WASI_PACK_VERSION=$($wasiRequirement.PackVersion)"
Write-Host "DOTNET_WASI_TARGETS=$($wasiRequirement.Targets)"
Write-Host (
    "DOTNET_WASI_VERSION_AUTHORITY_PROPERTY=" +
    $wasiRequirement.AuthorityProperty
)
Write-Host (
    "DOTNET_WASI_REQUIRED_SDK_VERSION=" +
    $wasiRequirement.RequiredWasiSdkVersion
)

$resolvedWasiSdk = Resolve-WasiSdkPath `
    -Requested $WasiSdkPath `
    -RequiredVersion $wasiRequirement.RequiredWasiSdkVersion

if (-not (Test-WasiSdkRoot `
    -Root $resolvedWasiSdk `
    -RequiredVersion $wasiRequirement.RequiredWasiSdkVersion)) {
    throw (
        "WASI_SDK_VERSION_MISMATCH " +
        "required=$($wasiRequirement.RequiredWasiSdkVersion) " +
        "observed_root=$resolvedWasiSdk"
    )
}

$wasiClang = Join-Path $resolvedWasiSdk "bin\clang.exe"
$wasiSysroot = Join-Path $resolvedWasiSdk "share\wasi-sysroot"

$wasiClangVersion = @(& $wasiClang --version 2>&1)
if ($LASTEXITCODE -ne 0) {
    throw "WASI_SDK_CLANG_VERSION_FAILED"
}

if (-not (Test-Path -LiteralPath $wasiSysroot -PathType Container)) {
    throw "WASI_SDK_SYSROOT_MISSING=$wasiSysroot"
}

$env:WASI_SDK_PATH = $resolvedWasiSdk

Write-Host "WASI_SDK=PASS"
Write-Host "WASI_SDK_PATH=$resolvedWasiSdk"
Write-Host (
    "WASI_SDK_VERSION=" +
    $wasiRequirement.RequiredWasiSdkVersion
)
$wasiVersionText = Get-WasiSdkVersionText -Root $resolvedWasiSdk

Write-Host "WASI_SDK_VERSION_FILE=PASS"
Write-Host "WASI_SDK_VERSION_FILE_TEXT=$wasiVersionText"
Write-Host "WASI_SDK_VERSION_MATCH=PASS"
Write-Host "WASI_SDK_CLANG=$wasiClang"
Write-Host "WASI_SDK_SYSROOT=PASS"
Write-Host "WASI_SDK_CLANG_VERSION=$($wasiClangVersion[0])"

$wasmtimeCommand = Get-Command wasmtime -ErrorAction SilentlyContinue
if ($null -eq $wasmtimeCommand) {
    throw "WASMTIME_NOT_FOUND"
}
$wasmtimeExe = $wasmtimeCommand.Source
$wasmtimeVersion = @(& $wasmtimeExe --version 2>&1)
if ($LASTEXITCODE -ne 0) {
    throw "WASMTIME_VERSION_FAILED"
}
Write-Host "WASMTIME=PASS"
Write-Host "WASMTIME_VERSION=$($wasmtimeVersion -join ' ')"

if ($PreflightOnly) {
    Write-Host "WASM_BATCH_STATIC=DEFERRED_UNTIL_MATERIALIZATION"
    Write-Host "WASM_BATCH_PREFLIGHT=PASS"
    Write-Host "UNITY_EDITOR_VERSION=$editorVersion"
    Write-Host "WASM_BATCH_PREFLIGHT_ONLY=PASS"
    exit 0
}

$staticValidator = Join-Path $RepositoryRoot `
    "tools\validate_wasm_batch_6a_6c.py"

if (-not (Test-Path -LiteralPath $staticValidator -PathType Leaf)) {
    throw "WASM_BATCH_STATIC_VALIDATOR_MISSING=$staticValidator"
}

python $staticValidator
if ($LASTEXITCODE -ne 0) {
    throw "WASM_BATCH_STATIC_FAILED"
}

Write-Host "WASM_BATCH_STATIC=PASS"
Write-Host "WASM_BATCH_PREFLIGHT=PASS"
Write-Host "UNITY_EDITOR_VERSION=$editorVersion"

# R4 changes one logical Core source (TevScriptJson.cs) in both governed mirrors.
# Re-run the established three-runtime C# conformance before any WASM gate so
# canonical SHA-256 byte parity is proved rather than assumed from the base.
$csharpConformanceRunner = Join-Path $RepositoryRoot `
    "RUN_TEV_SCRIPT_CSHARP_CONFORMANCE_V1.ps1"
if (-not (Test-Path -LiteralPath $csharpConformanceRunner -PathType Leaf)) {
    throw "WASM_BATCH_CSHARP_CONFORMANCE_RUNNER_MISSING=$csharpConformanceRunner"
}

$csharpConformanceOutput = @(
    & pwsh -NoProfile -ExecutionPolicy Bypass `
        -File $csharpConformanceRunner `
        -RepositoryRoot $RepositoryRoot 2>&1
)
$csharpConformanceExit = $LASTEXITCODE
$csharpConformanceOutput | ForEach-Object { Write-Host $_ }
if ($csharpConformanceExit -ne 0) {
    throw "WASM_BATCH_CORE_SHA256_CONFORMANCE_FAILED exit=$csharpConformanceExit"
}
$csharpConformanceText = $csharpConformanceOutput -join "`n"
Require-Markers `
    -Text $csharpConformanceText `
    -Code "WASM_BATCH_CORE_SHA256_CONFORMANCE_WITNESS_MISSING" `
    -Markers @(
        "TEV_SCRIPT_THREE_RUNTIME_CONFORMANCE=PASS"
        "CSHARP_PYTHON_JAVASCRIPT_BYTE_PARITY=PASS"
        "CSHARP_CANONICAL_VECTORS=12_PASS"
    )
Write-Host "WASM_BATCH_CORE_SHA256_PORTABILITY_REGRESSION=PASS"
Write-Host "CORE_SHA256_PROVIDER=TEV_MANAGED_HOST_INDEPENDENT"

if ($head -ne "966f87c43a5a2c9ba5336ae3a313515832dd8498") {
    Write-Host "WASM_BATCH_BASE_HEAD_NOTE=$head"
}

$runRoot = Join-Path $env:LOCALAPPDATA `
    "TEV_SCRIPT_WASM_BATCH_6A_6C\$([Guid]::NewGuid().ToString('N'))"
New-Item -ItemType Directory -Path $runRoot -Force | Out-Null

Test-HttpWitnessServerContract -RunRoot $runRoot

# ------------------------------------------------------------------
# Gate 6A — Unity WebGL -> WebAssembly -> real browser.
# ------------------------------------------------------------------
$project6a = Join-Path $runRoot "gate6a-unity"
$build6a = Join-Path $project6a "WebBuild"
$buildLog6a = Join-Path $project6a "unity-web-build.log"

New-Item -ItemType Directory -Path (
    Join-Path $project6a "Assets\Gate6A\Runtime"
) -Force | Out-Null
New-Item -ItemType Directory -Path (
    Join-Path $project6a "Assets\Gate6A\Editor"
) -Force | Out-Null
New-Item -ItemType Directory -Path (
    Join-Path $project6a "Assets\Plugins\WebGL"
) -Force | Out-Null
New-Item -ItemType Directory -Path (
    Join-Path $project6a "Assets\Resources"
) -Force | Out-Null
New-Item -ItemType Directory -Path (
    Join-Path $project6a "Packages"
) -Force | Out-Null
New-Item -ItemType Directory -Path (
    Join-Path $project6a "ProjectSettings"
) -Force | Out-Null

$stagedPackage = Join-Path $project6a `
    "LocalPackages\com.marcbeacve.tev-script"
New-Item -ItemType Directory -Path (
    Split-Path -Parent $stagedPackage
) -Force | Out-Null
Copy-Item -LiteralPath (
    Join-Path $RepositoryRoot "unity\Package"
) -Destination $stagedPackage -Recurse -Force

$gate6aRoot = Join-Path $RepositoryRoot "unity\PlayerGates\Web"

Copy-Item -LiteralPath (
    Join-Path $gate6aRoot `
        "Runtime\Marcbeacve.TevScript.Gate6A.Web.asmdef"
) -Destination (
    Join-Path $project6a `
        "Assets\Gate6A\Runtime\Marcbeacve.TevScript.Gate6A.Web.asmdef"
) -Force
Copy-Item -LiteralPath (
    Join-Path $gate6aRoot "Runtime\TevScriptUnityWebGate.cs"
) -Destination (
    Join-Path $project6a "Assets\Gate6A\Runtime\TevScriptUnityWebGate.cs"
) -Force
Copy-Item -LiteralPath (
    Join-Path $gate6aRoot `
        "Editor\Marcbeacve.TevScript.Gate6A.Web.Editor.asmdef"
) -Destination (
    Join-Path $project6a `
        "Assets\Gate6A\Editor\Marcbeacve.TevScript.Gate6A.Web.Editor.asmdef"
) -Force
Copy-Item -LiteralPath (
    Join-Path $gate6aRoot "Editor\TevScriptUnityWebBuildGate.cs"
) -Destination (
    Join-Path $project6a `
        "Assets\Gate6A\Editor\TevScriptUnityWebBuildGate.cs"
) -Force
Copy-Item -LiteralPath (
    Join-Path $gate6aRoot "Plugins\WebGL\TevScriptGate6A.jslib"
) -Destination (
    Join-Path $project6a "Assets\Plugins\WebGL\TevScriptGate6A.jslib"
) -Force
Copy-Item -LiteralPath (
    Join-Path $RepositoryRoot "examples\Player.tevs.ir.json"
) -Destination (
    Join-Path $project6a "Assets\Resources\TevScriptGate6APlayer.json"
) -Force

$packageUri = (
    Resolve-Path -LiteralPath $stagedPackage
).Path.Replace("\", "/")

$manifest = [ordered]@{
    dependencies = [ordered]@{
        "com.marcbeacve.tev-script" = "file:$packageUri"
    }
}
$manifest | ConvertTo-Json -Depth 8 | Set-Content `
    -LiteralPath (Join-Path $project6a "Packages\manifest.json") `
    -Encoding utf8

"m_EditorVersion: $editorVersion`n" | Set-Content `
    -LiteralPath (Join-Path $project6a "ProjectSettings\ProjectVersion.txt") `
    -Encoding utf8

$oldGate6A = $env:TEV_SCRIPT_GATE6A_BUILD_DIR
$env:TEV_SCRIPT_GATE6A_BUILD_DIR = $build6a
try {
    $unityArgs = @(
        "-batchmode"
        "-nographics"
        "-quit"
        "-projectPath"
        ('"' + $project6a + '"')
        "-executeMethod"
        "Marcbeacve.TevScript.Gate6A.Web.Editor.TevScriptUnityWebBuildGate.Build"
        "-logFile"
        ('"' + $buildLog6a + '"')
    )

    $buildProcess = Start-Process `
        -FilePath $resolvedUnity `
        -ArgumentList $unityArgs `
        -Wait `
        -PassThru
    $buildExit = $buildProcess.ExitCode
}
finally {
    $env:TEV_SCRIPT_GATE6A_BUILD_DIR = $oldGate6A
}

if ($buildExit -ne 0) {
    if (Test-Path -LiteralPath $buildLog6a) {
        Get-Content -LiteralPath $buildLog6a -Tail 300 |
            ForEach-Object { Write-Host $_ }
    }
    throw "GATE6A_UNITY_WEB_BUILD_FAILED exit=$buildExit"
}

$buildText6a = Get-Content -LiteralPath $buildLog6a -Raw
Require-Markers `
    -Text $buildText6a `
    -Code "GATE6A_BUILD_WITNESS_MISSING" `
    -Markers @(
        "UNITY_GATE6A_BUILD_TARGET=WEBGL"
        "UNITY_GATE6A_BUILD_COMPRESSION=DISABLED"
        "UNITY_GATE6A_BUILD_RESULT=PASS"
    )

$index6a = Join-Path $build6a "index.html"
if (-not (Test-Path -LiteralPath $index6a -PathType Leaf)) {
    throw "GATE6A_INDEX_HTML_MISSING=$index6a"
}

$indexText6a = Get-Content -LiteralPath $index6a -Raw

if (-not $indexText6a.Contains("<body>")) {
    throw "GATE6A_INDEX_BODY_ANCHOR_MISSING"
}

$instrument6a = @'
<script id="tev-gate6a-harness">
(() => {
  const diag = document.createElement("pre");
  diag.id = "tev-gate6a-diagnostics";
  diag.style.display = "none";
  diag.textContent = "GATE6A_HARNESS=ACTIVE\n";
  document.body.appendChild(diag);
  document.documentElement.setAttribute(
    "data-tev-gate6a-harness",
    "ACTIVE");

  const witnessToken =
    new URLSearchParams(window.location.search)
      .get("tev_witness_token") || "";
  let released = false;
  let witnessSent = false;

  function append(kind, value) {
    const line = String(kind) + "=" + String(value);
    diag.textContent += line + "\n";

    if (diag.textContent.length > 24000) {
      diag.textContent =
        diag.textContent.slice(diag.textContent.length - 24000);
    }
  }

  function emitWitness(state, reason) {
    if (witnessSent) {
      return;
    }
    witnessSent = true;

    const query = new URLSearchParams({
      gate: "gate6a",
      status: String(state),
      token: witnessToken,
      detail: String(reason),
    });

    void fetch("/__tev_witness?" + query.toString(), {
      method: "GET",
      cache: "no-store",
      keepalive: true,
    }).catch((error) => {
      append("WITNESS_TRANSPORT_ERROR", error);
    });
  }

  function release(state, reason) {
    if (released) {
      return;
    }

    released = true;
    document.documentElement.setAttribute(
      "data-tev-gate6a-harness-result",
      String(state));
    document.documentElement.setAttribute(
      "data-tev-gate6a-harness-reason",
      String(reason));
    append("GATE6A_HARNESS_RELEASE", state + ":" + reason);
    emitWitness(state, reason);
  }

  window.__tevGate6ALog = append;
  window.__tevGate6AProgress = (progress) => {
    const value = Number(progress).toFixed(3);
    document.documentElement.setAttribute(
      "data-tev-unity-progress",
      value);
    append("UNITY_PROGRESS", value);
  };
  window.__tevGate6AResolved = () => {
    document.documentElement.setAttribute(
      "data-tev-unity-instance",
      "RESOLVED");
    append("CREATE_UNITY_INSTANCE", "RESOLVED");
  };
  window.__tevGate6AFail = (reason) => {
    document.documentElement.setAttribute(
      "data-tev-unity-instance",
      "REJECTED");
    append("CREATE_UNITY_INSTANCE", "REJECTED");
    append("CREATE_UNITY_ERROR", reason);
    release("FAIL", "CREATE_UNITY_INSTANCE");
  };

  const observer = new MutationObserver(() => {
    const state =
      document.documentElement.getAttribute("data-tev-gate6a");
    if (state === "PASS" || state === "FAIL") {
      append("TEV_GATE6A_JSLIB", state);
      release(state, "TEV_JSLIB");
    }
  });

  observer.observe(
    document.documentElement,
    {
      attributes: true,
      attributeFilter: ["data-tev-gate6a"]
    });

  window.alert = (message) => {
    append("WINDOW_ALERT", message);
    release("FAIL", "WINDOW_ALERT");
  };

  window.addEventListener("error", (event) => {
    append("WINDOW_ERROR", event.message || "unknown");
    if (event.filename) {
      append(
        "WINDOW_ERROR_LOCATION",
        event.filename + ":" + event.lineno + ":" + event.colno);
    }
    release("FAIL", "WINDOW_ERROR");
  });

  window.addEventListener("unhandledrejection", (event) => {
    append(
      "UNHANDLED_REJECTION",
      event.reason ? String(event.reason) : "unknown");
    release("FAIL", "UNHANDLED_REJECTION");
  });

  for (const level of ["log", "warn", "error"]) {
    const original = console[level].bind(console);
    console[level] = (...args) => {
      append(
        "CONSOLE_" + level.toUpperCase(),
        args.map(String).join(" "));
      original(...args);
    };
  }
})();
</script>
'@

$indexText6a = $indexText6a.Replace(
    "<body>",
    "<body>`n$instrument6a"
)

$progressAnchor =
    'createUnityInstance(canvas, config, (progress) => {'
if (-not $indexText6a.Contains($progressAnchor)) {
    throw "GATE6A_INDEX_PROGRESS_ANCHOR_MISSING"
}
$indexText6a = $indexText6a.Replace(
    $progressAnchor,
    $progressAnchor + "`n          window.__tevGate6AProgress(progress);"
)

$thenAnchor = '}).then((unityInstance) => {'
if (-not $indexText6a.Contains($thenAnchor)) {
    throw "GATE6A_INDEX_THEN_ANCHOR_MISSING"
}
$indexText6a = $indexText6a.Replace(
    $thenAnchor,
    $thenAnchor + "`n                window.__tevGate6AResolved();"
)

$catchAnchor = @'
              }).catch((message) => {
                alert(message);
              });
'@
$catchReplacement = @'
              }).catch((message) => {
                window.__tevGate6AFail(String(message));
              });
'@
if (-not $indexText6a.Contains($catchAnchor)) {
    throw "GATE6A_INDEX_CATCH_ANCHOR_MISSING"
}
$indexText6a = $indexText6a.Replace(
    $catchAnchor,
    $catchReplacement
)

$loaderOnloadAnchor = 'script.onload = () => {'
if (-not $indexText6a.Contains($loaderOnloadAnchor)) {
    throw "GATE6A_INDEX_LOADER_ONLOAD_ANCHOR_MISSING"
}
$indexText6a = $indexText6a.Replace(
    $loaderOnloadAnchor,
    'script.onerror = () => window.__tevGate6AFail("LOADER_SCRIPT_ERROR");' +
    "`n      " +
    $loaderOnloadAnchor
)

Set-Content `
    -LiteralPath $index6a `
    -Value $indexText6a `
    -Encoding utf8

Write-Host "GATE6A_BROWSER_INSTRUMENTATION=PASS"
Write-Host "GATE6A_HTTP_WITNESS_INSTRUMENTATION=PASS"

$wasm6a = @(
    Get-ChildItem -LiteralPath $build6a -Recurse -File -Filter "*.wasm"
)
if ($wasm6a.Count -lt 1) {
    throw "GATE6A_WASM_BINARY_NOT_FOUND"
}
$primaryWasm6a = $wasm6a |
    Sort-Object Length -Descending |
    Select-Object -First 1
Test-WasmMagic -Path $primaryWasm6a.FullName
$wasm6aSha = (
    Get-FileHash -LiteralPath $primaryWasm6a.FullName -Algorithm SHA256
).Hash.ToLowerInvariant()
Write-Host "GATE6A_WASM_BINARY=PASS"
Write-Host "GATE6A_WASM_SHA256=$wasm6aSha"

$probe6a = Join-Path $build6a "tev-gate6a-webgl2-probe.html"
@'
<!doctype html>
<html>
<head><meta charset="utf-8"><title>TEV Gate 6A WebGL2 Probe</title></head>
<body>
<pre id="probe">GATE6A_WEBGL2_PROBE=BOOT</pre>
<script>
(() => {
  const token =
    new URLSearchParams(window.location.search)
      .get("tev_witness_token") || "";
  const canvas = document.createElement("canvas");
  const gl = canvas.getContext("webgl2");
  const passed = !!gl;
  const status = passed ? "PASS" : "FAIL";
  const detail = passed ? "WEBGL2_CONTEXT_PASS" : "WEBGL2_CONTEXT_FAIL";

  document.documentElement.setAttribute("data-tev-webgl2", status);
  document.getElementById("probe").textContent =
    "GATE6A_WEBGL2_CONTEXT=" + status;
  document.title = "TEV_GATE6A_WEBGL2_" + status;

  const query = new URLSearchParams({
    gate: "gate6a-webgl2-probe",
    status,
    token,
    detail,
  });
  void fetch("/__tev_witness?" + query.toString(), {
    method: "GET",
    cache: "no-store",
    keepalive: true,
  });
})();
</script>
</body>
</html>
'@ | Set-Content -LiteralPath $probe6a -Encoding utf8

$webgl2Receipt = Invoke-HeadlessHttpWitness `
    -Browser $resolvedBrowser `
    -Root $build6a `
    -Path "/tev-gate6a-webgl2-probe.html" `
    -RunRoot $runRoot `
    -Name "gate6a-webgl2-probe" `
    -Gate "gate6a-webgl2-probe" `
    -BudgetMilliseconds 30000 `
    -RequireWebGL

if ([string]$webgl2Receipt.detail -ne "WEBGL2_CONTEXT_PASS") {
    throw "GATE6A_BROWSER_WEBGL2_WITNESS_DETAIL_INVALID=$($webgl2Receipt.detail)"
}
Write-Host "GATE6A_BROWSER_WEBGL2_CONTEXT=PASS"

$gate6aReceipt = Invoke-HeadlessHttpWitness `
    -Browser $resolvedBrowser `
    -Root $build6a `
    -Path "/index.html" `
    -RunRoot $runRoot `
    -Name "gate6a" `
    -Gate "gate6a" `
    -BudgetMilliseconds 190000 `
    -RequireWebGL

if ([string]$gate6aReceipt.detail -ne "TEV_JSLIB") {
    throw "GATE6A_BROWSER_HTTP_WITNESS_DETAIL_INVALID=$($gate6aReceipt.detail)"
}
Write-Host "GATE6A_BROWSER_HTTP_WITNESS=PASS"
# Historical marker retained for compatibility; external authority is HTTP.
Write-Host "GATE6A_BROWSER_DOM=PASS"
Write-Host "TEV_SCRIPT_UNITY_WEB_GATE_6A=PASS"

# ------------------------------------------------------------------
# Gate 6B — Pure TEV Core browser WASM AOT.
# ------------------------------------------------------------------
$project6b = Join-Path $RepositoryRoot `
    "runtimes\csharp\TevScript.BrowserWasmGate\TevScript.BrowserWasmGate.csproj"

$publish6b = Join-Path $runRoot "gate6b-publish"
New-Item -ItemType Directory -Path $publish6b -Force | Out-Null

dotnet publish $project6b `
    -c Release `
    --nologo `
    -p:PublishDir=$publish6b
if ($LASTEXITCODE -ne 0) {
    throw "GATE6B_BROWSER_WASM_PUBLISH_FAILED"
}
Write-Host "GATE6B_DOTNET_PUBLISH=PASS"
Write-Host "GATE6B_PUBLISH_DIR=$publish6b"

if (-not (Test-Path -LiteralPath $publish6b -PathType Container)) {
    throw "GATE6B_PUBLISH_DIR_MISSING=$publish6b"
}

$wwwroot6b = Join-Path $publish6b "wwwroot"

if (Test-Path -LiteralPath $wwwroot6b -PathType Container) {
    $webRoot6b = $wwwroot6b
    Write-Host "GATE6B_WEB_ROOT_KIND=WWWROOT"
}
else {
    $webRoot6b = $publish6b
    Write-Host "GATE6B_WEB_ROOT_KIND=PUBLISH_ROOT"
}

$index6b = Join-Path $webRoot6b "index.html"
$main6b = Join-Path $webRoot6b "main.mjs"
$framework6b = Join-Path $webRoot6b "_framework"

$dotnetJsCandidates6b = @(
    Get-ChildItem `
        -LiteralPath $framework6b `
        -File `
        -Filter "dotnet*.js" `
        -ErrorAction SilentlyContinue
)

$missing6b = @()

foreach ($required6b in @(
    $index6b
    $main6b
)) {
    if (-not (Test-Path -LiteralPath $required6b -PathType Leaf)) {
        $missing6b += $required6b
    }
}

if (-not (Test-Path -LiteralPath $framework6b -PathType Container)) {
    $missing6b += $framework6b
}

if ($dotnetJsCandidates6b.Count -lt 1) {
    $missing6b += (Join-Path $framework6b "dotnet*.js")
}

if ($missing6b.Count -ne 0) {
    Write-Host "----- GATE6B PUBLISH TREE -----"

    @(
        Get-ChildItem `
            -LiteralPath $publish6b `
            -Recurse `
            -File
    ) |
    ForEach-Object {
        $relative = [System.IO.Path]::GetRelativePath(
            $publish6b,
            $_.FullName
        ).Replace("\", "/")

        Write-Host (
            "GATE6B_PUBLISH_FILE=" +
            $relative +
            " bytes=" +
            $_.Length
        )
    }

    $missing6b | ForEach-Object {
        Write-Host "GATE6B_PUBLISH_MISSING=$_"
    }

    throw "GATE6B_PUBLISH_LAYOUT_INVALID"
}

$dotnetJs6b = $dotnetJsCandidates6b |
    Sort-Object Name |
    Select-Object -First 1

$dotnetJsRelative6b = [System.IO.Path]::GetRelativePath(
    $webRoot6b,
    $dotnetJs6b.FullName
).Replace("\", "/")

Write-Host "GATE6B_WEB_ROOT=$webRoot6b"
Write-Host "GATE6B_PUBLISH_LAYOUT=PASS"
Write-Host "GATE6B_DOTNET_JS=PASS"
Write-Host "GATE6B_DOTNET_JS_PATH=$dotnetJsRelative6b"
Write-Host "GATE6B_MAIN_MJS_PUBLISHED=PASS"

$wasm6b = @(
    Get-ChildItem `
        -LiteralPath $webRoot6b `
        -Recurse `
        -File `
        -Filter "*.wasm"
)
if ($wasm6b.Count -lt 1) {
    throw "GATE6B_WASM_BINARY_NOT_FOUND root=$publish6b"
}

$validWasm6b = @()
foreach ($candidate6b in $wasm6b) {
    try {
        Test-WasmMagic -Path $candidate6b.FullName
        $validWasm6b += $candidate6b
    }
    catch {
        Write-Host "GATE6B_NON_WASM_EXTENSION_FILE=$($candidate6b.FullName)"
    }
}

if ($validWasm6b.Count -lt 1) {
    throw "GATE6B_VALID_WASM_BINARY_NOT_FOUND root=$publish6b"
}

$primaryWasm6b = $validWasm6b |
    Sort-Object Length -Descending |
    Select-Object -First 1

$wasm6bSha = (
    Get-FileHash -LiteralPath $primaryWasm6b.FullName -Algorithm SHA256
).Hash.ToLowerInvariant()

$primaryWasm6bRelative = [System.IO.Path]::GetRelativePath(
    $publish6b,
    $primaryWasm6b.FullName
).Replace("\", "/")

Write-Host "GATE6B_WASM_BINARY=PASS"
Write-Host "GATE6B_WASM_COUNT=$($validWasm6b.Count)"
Write-Host "GATE6B_PRIMARY_WASM=$primaryWasm6bRelative"
Write-Host "GATE6B_WASM_SHA256=$wasm6bSha"

$mainText6b = Get-Content -LiteralPath $main6b -Raw
$expectedDotnetImport6b = "./_framework/dotnet.js"

if (-not $dotnetJsRelative6b.Equals(
    "_framework/dotnet.js",
    [System.StringComparison]::Ordinal
)) {
    if (-not $mainText6b.Contains($expectedDotnetImport6b)) {
        throw "GATE6B_MAIN_DOTNET_IMPORT_ANCHOR_MISSING"
    }

    $mainText6b = $mainText6b.Replace(
        $expectedDotnetImport6b,
        "./" + $dotnetJsRelative6b
    )

    Set-Content `
        -LiteralPath $main6b `
        -Value $mainText6b `
        -Encoding utf8

    Write-Host "GATE6B_DOTNET_JS_IMPORT_REBOUND=PASS"
}
else {
    Write-Host "GATE6B_DOTNET_JS_IMPORT_REBOUND=NOT_REQUIRED"
}

$gate6bReceipt = Invoke-HeadlessHttpWitness `
    -Browser $resolvedBrowser `
    -Root $webRoot6b `
    -Path "/index.html" `
    -RunRoot $runRoot `
    -Name "gate6b" `
    -Gate "gate6b" `
    -BudgetMilliseconds 190000

if ([string]$gate6bReceipt.detail -ne "TEV_CORE_BROWSER_WASM_PASS") {
    throw "GATE6B_BROWSER_HTTP_WITNESS_DETAIL_INVALID=$($gate6bReceipt.detail)"
}
Write-Host "GATE6B_BROWSER_HTTP_WITNESS=PASS"
# Historical marker retained for compatibility; external authority is HTTP.
Write-Host "GATE6B_BROWSER_DOM=PASS"
Write-Host "GATE6B_AOT=PASS_REQUESTED_AND_BROWSER_EXECUTED"
Write-Host "TEV_SCRIPT_PURE_CORE_BROWSER_WASM_GATE_6B=PASS"

# ------------------------------------------------------------------
# Gate 6C — Pure TEV Core WASI under Wasmtime.
# ------------------------------------------------------------------
$project6c = Join-Path $RepositoryRoot `
    "runtimes\csharp\TevScript.WasiGate\TevScript.WasiGate.csproj"

$publish6c = Join-Path $runRoot "gate6c-publish"
New-Item -ItemType Directory -Path $publish6c -Force | Out-Null

# The SDK-generated run-wasmtime.sh is written to $(WasmAppDir), whose
# default is the project's OutputPath/AppBundle, not a custom PublishDir.
# Record the publish boundary so a stale helper from an older build cannot
# satisfy this gate.
$publishStartedUtc6c = [DateTime]::UtcNow

dotnet publish $project6c `
    -c Release `
    --nologo `
    -p:PublishDir=$publish6c
if ($LASTEXITCODE -ne 0) {
    throw "GATE6C_WASI_PUBLISH_FAILED"
}
Write-Host "GATE6C_DOTNET_PUBLISH=PASS"
Write-Host "GATE6C_PUBLISH_DIR=$publish6c"

$wasm6cCandidates = @(
    Get-ChildItem `
        -LiteralPath $publish6c `
        -Recurse `
        -File `
        -Filter "*.wasm"
)
if ($wasm6cCandidates.Count -lt 1) {
    throw "GATE6C_WASI_BINARY_NOT_FOUND root=$publish6c"
}

$validWasm6c = @()
foreach ($candidate6c in $wasm6cCandidates) {
    try {
        Test-WasmMagic -Path $candidate6c.FullName
        $validWasm6c += $candidate6c
    }
    catch {
        Write-Host "GATE6C_NON_WASM_EXTENSION_FILE=$($candidate6c.FullName)"
    }
}

if ($validWasm6c.Count -lt 1) {
    throw "GATE6C_VALID_WASM_BINARY_NOT_FOUND root=$publish6c"
}

# This project is intentionally non-single-file. Microsoft's WASI SDK emits
# a generic dotnet.wasm host and passes the managed assembly name as argv[1].
$dotnetWasm6c = Join-Path $publish6c "dotnet.wasm"
if (-not (Test-Path -LiteralPath $dotnetWasm6c -PathType Leaf)) {
    Write-Host "----- GATE6C PUBLISH TREE -----"
    @(
        Get-ChildItem `
            -LiteralPath $publish6c `
            -Recurse `
            -File
    ) |
    ForEach-Object {
        $relative6c = [System.IO.Path]::GetRelativePath(
            $publish6c,
            $_.FullName
        ).Replace("\", "/")
        Write-Host (
            "GATE6C_PUBLISH_FILE=" +
            $relative6c +
            " bytes=" +
            $_.Length
        )
    }

    throw "GATE6C_DOTNET_HOST_WASM_MISSING=$dotnetWasm6c"
}

Test-WasmMagic -Path $dotnetWasm6c
$primaryWasm6c = Get-Item -LiteralPath $dotnetWasm6c

$wasm6cSha = (
    Get-FileHash -LiteralPath $primaryWasm6c.FullName -Algorithm SHA256
).Hash.ToLowerInvariant()

$primaryWasm6cRelative = [System.IO.Path]::GetRelativePath(
    $publish6c,
    $primaryWasm6c.FullName
).Replace("\", "/")

Write-Host "GATE6C_WASM_BINARY=PASS"
Write-Host "GATE6C_WASM_COUNT=$($validWasm6c.Count)"
Write-Host "GATE6C_PRIMARY_WASM=$primaryWasm6cRelative"
Write-Host "GATE6C_DOTNET_HOST_WASM=PASS"
Write-Host "GATE6C_WASM_SHA256=$wasm6cSha"

$assemblyName6c = [System.IO.Path]::GetFileNameWithoutExtension(
    $project6c
)

$dotnetRunContract6c = (
    "wasmtime run --dir . dotnet.wasm " +
    $assemblyName6c
)

$projectDir6c = Split-Path -Parent $project6c
$runScriptSearchRoot6c = Join-Path $projectDir6c "bin"
if (-not (Test-Path -LiteralPath $runScriptSearchRoot6c -PathType Container)) {
    throw "GATE6C_DOTNET_RUN_SCRIPT_SEARCH_ROOT_MISSING=$runScriptSearchRoot6c"
}

$runScriptCandidates6c = @(
    Get-ChildItem `
        -LiteralPath $runScriptSearchRoot6c `
        -Recurse `
        -File `
        -Filter "run-wasmtime.sh" `
        -ErrorAction SilentlyContinue
)

$freshThreshold6c = $publishStartedUtc6c.AddSeconds(-5)
$matchingRunScripts6c = @()
foreach ($candidateRunScript6c in $runScriptCandidates6c) {
    $candidateText6c = Get-Content `
        -LiteralPath $candidateRunScript6c.FullName `
        -Raw `
        -ErrorAction SilentlyContinue

    $candidateIsFresh6c = (
        $candidateRunScript6c.LastWriteTimeUtc -ge $freshThreshold6c
    )
    $candidateHasContract6c = (
        -not [string]::IsNullOrWhiteSpace([string]$candidateText6c) -and
        $candidateText6c.Contains($dotnetRunContract6c)
    )

    if ($candidateIsFresh6c -and $candidateHasContract6c) {
        $matchingRunScripts6c += $candidateRunScript6c
    }
    else {
        $candidateRelative6c = [System.IO.Path]::GetRelativePath(
            $projectDir6c,
            $candidateRunScript6c.FullName
        ).Replace("\", "/")
        Write-Host (
            "GATE6C_DOTNET_RUN_SCRIPT_CANDIDATE=" +
            $candidateRelative6c +
            " fresh=" +
            $candidateIsFresh6c +
            " contract=" +
            $candidateHasContract6c +
            " mtime_utc=" +
            $candidateRunScript6c.LastWriteTimeUtc.ToString("o")
        )
    }
}

if ($matchingRunScripts6c.Count -lt 1) {
    throw (
        "GATE6C_DOTNET_RUN_SCRIPT_FRESH_MATCH_MISSING " +
        "search_root=$runScriptSearchRoot6c " +
        "expected=$dotnetRunContract6c"
    )
}

$runScript6c = (
    $matchingRunScripts6c |
    Sort-Object LastWriteTimeUtc -Descending |
    Select-Object -First 1
).FullName
$runScriptText6c = Get-Content -LiteralPath $runScript6c -Raw

$runScriptParent6c = Split-Path -Parent $runScript6c
$runScriptParentName6c = Split-Path -Leaf $runScriptParent6c
if (-not $runScriptParentName6c.Equals(
        "AppBundle",
        [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "GATE6C_DOTNET_RUN_SCRIPT_NOT_APP_BUNDLE=$runScript6c"
}

if (-not $runScriptText6c.Contains($dotnetRunContract6c)) {
    Write-Host "----- DOTNET GENERATED run-wasmtime.sh -----"
    Write-Host $runScriptText6c
    throw (
        "GATE6C_DOTNET_RUN_CONTRACT_MISMATCH " +
        "expected=$dotnetRunContract6c"
    )
}

$runScriptRelative6c = [System.IO.Path]::GetRelativePath(
    $projectDir6c,
    $runScript6c
).Replace("\", "/")

Write-Host "GATE6C_DOTNET_RUN_SCRIPT=PASS"
Write-Host "GATE6C_DOTNET_RUN_SCRIPT_SOURCE=SDK_WASM_APP_DIR_PASS"
Write-Host "GATE6C_DOTNET_RUN_SCRIPT_PATH=$runScriptRelative6c"
Write-Host "GATE6C_DOTNET_RUN_CONTRACT=NON_SINGLE_FILE_PASS"
Write-Host "GATE6C_DOTNET_APP_ARG=$assemblyName6c"

# Wasmtime's wasi:http host implementation is opt-in. The .NET-generated
# component imports wasi:http/types@0.2.0 even though this TEV gate performs no
# network operation. Enable only the host interface required for linking.
$wasmtimeArgs6c = @(
    "run"
    "-S"
    "http"
    "--dir"
    "."
    "dotnet.wasm"
    $assemblyName6c
)

$wasmtimeStdout6c = Join-Path $runRoot "gate6c-wasmtime.out.txt"
$wasmtimeStderr6c = Join-Path $runRoot "gate6c-wasmtime.err.txt"

Write-Host "GATE6C_WASMTIME_WASI_HTTP=ENABLED_FOR_LINKAGE"
Write-Host "GATE6C_WASMTIME_DIR_PREOPEN=CONFIGURED_CURRENT_PUBLISH_DIR"
Write-Host "GATE6C_WASMTIME_WORKING_DIRECTORY=$publish6c"
Write-Host (
    "GATE6C_WASMTIME_COMMAND=wasmtime run -S http --dir . dotnet.wasm " +
    $assemblyName6c
)

$wasmtimeProcess6c = Start-Process `
    -FilePath $wasmtimeExe `
    -ArgumentList $wasmtimeArgs6c `
    -WorkingDirectory $publish6c `
    -RedirectStandardOutput $wasmtimeStdout6c `
    -RedirectStandardError $wasmtimeStderr6c `
    -Wait `
    -PassThru

$wasiStdout6c = @()
$wasiStderr6c = @()

if (Test-Path -LiteralPath $wasmtimeStdout6c -PathType Leaf) {
    $wasiStdout6c = @(
        Get-Content -LiteralPath $wasmtimeStdout6c
    )
}

if (Test-Path -LiteralPath $wasmtimeStderr6c -PathType Leaf) {
    $wasiStderr6c = @(
        Get-Content -LiteralPath $wasmtimeStderr6c
    )
}

$wasiStdout6c | ForEach-Object { Write-Host $_ }
$wasiStderr6c | ForEach-Object { Write-Host $_ }

$wasiExit = $wasmtimeProcess6c.ExitCode
if ($wasiExit -ne 0) {
    Write-Host "----- DOTNET GENERATED run-wasmtime.sh -----"
    Write-Host $runScriptText6c
    Write-Host "GATE6C_WASMTIME_VERSION=$($wasmtimeVersion -join ' ')"
    throw "GATE6C_WASMTIME_FAILED exit=$wasiExit"
}

$wasiOutput = @($wasiStdout6c + $wasiStderr6c)
$wasiText = $wasiOutput -join "`n"
Require-Markers `
    -Text $wasiText `
    -Code "GATE6C_WITNESS_MISSING" `
    -Markers @(
        "GATE6C_WASI_ACTIVE=PASS"
        "GATE6C_CORE_PARSE=PASS"
        "GATE6C_RUNTIME_STATE=PASS"
        "GATE6C_CANONICAL_JSON=PASS"
        "GATE6C_UNITY_DEPENDENCY=ABSENT_PASS"
        "GATE6C_BROWSER_DEPENDENCY=ABSENT_PASS"
        "TEV_SCRIPT_PURE_CORE_WASI_GATE_6C=PASS"
    )

Write-Host "GATE6C_WASMTIME_EXECUTION=PASS"

$evidenceDir = Join-Path $RepositoryRoot "receipts\wasm-batch-6a-6c"
New-Item -ItemType Directory -Path $evidenceDir -Force | Out-Null
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$evidence = Join-Path $evidenceDir "WASM_BATCH_$stamp.txt"

@(
    "TEV_SCRIPT_WASM_BATCH_6A_6C_EVIDENCE_V1"
    "BRANCH=$branch"
    "HEAD=$head"
    "TREE=$tree"
    "UNITY_EDITOR_VERSION=$editorVersion"
    "GATE6A=PASS_UNITY_WEB_BROWSER"
    "GATE6A_WASM_SHA256=$wasm6aSha"
    "GATE6B=PASS_PURE_CORE_BROWSER_WASM"
    "GATE6B_AOT=PASS_REQUESTED_AND_BROWSER_EXECUTED"
    "GATE6B_WASM_SHA256=$wasm6bSha"
    "GATE6C=PASS_PURE_CORE_WASI"
    "GATE6C_WASMTIME_VERSION=$($wasmtimeVersion -join ' ')"
    "GATE6C_DOTNET_RUN_CONTRACT=NON_SINGLE_FILE"
    "GATE6C_WASMTIME_WASI_HTTP=ENABLED_FOR_LINKAGE"
    "GATE6C_WASM_SHA256=$wasm6cSha"
    "GATE6D=NOT_IN_SCOPE"
    "CORE_PRODUCT_CHANGES=2_PHYSICAL_1_LOGICAL"
    "STABLE_RELEASE=NO"
) | Set-Content -LiteralPath $evidence -Encoding utf8

$evidenceSha = (
    Get-FileHash -LiteralPath $evidence -Algorithm SHA256
).Hash.ToLowerInvariant()

Write-Host ""
Write-Host "TEV_SCRIPT_WASM_BATCH_6A_6C=PASS"
Write-Host "BRANCH=$branch"
Write-Host "HEAD=$head"
Write-Host "TREE=$tree"
Write-Host "GATE6A=PASS_UNITY_WEB_REAL_BROWSER"
Write-Host "GATE6A_WASM_SHA256=$wasm6aSha"
Write-Host "GATE6B=PASS_PURE_CORE_BROWSER_WASM"
Write-Host "GATE6B_AOT=PASS_REQUESTED_AND_BROWSER_EXECUTED"
Write-Host "GATE6B_WASM_SHA256=$wasm6bSha"
Write-Host "GATE6C=PASS_PURE_CORE_WASI_WASMTIME"
Write-Host "GATE6C_DOTNET_RUN_CONTRACT=NON_SINGLE_FILE"
Write-Host "GATE6C_WASMTIME_WASI_HTTP=ENABLED_FOR_LINKAGE"
Write-Host "GATE6C_WASM_SHA256=$wasm6cSha"
Write-Host "GATE6D=NOT_IN_SCOPE"
Write-Host "CORE_PRODUCT_CHANGES=2_PHYSICAL_1_LOGICAL"
Write-Host "WASM_BATCH_EVIDENCE=$evidence"
Write-Host "WASM_BATCH_EVIDENCE_SHA256=$evidenceSha"
Write-Host "STABLE_RELEASE=NO"
Write-Host "GIT_STATUS=CANDIDATE_CHANGES_ALLOWED"
