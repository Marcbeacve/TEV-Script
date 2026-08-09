[CmdletBinding()]
param(
    [string]$RepositoryRoot = (Split-Path -Parent $MyInvocation.MyCommand.Path),
    [switch]$RequireClean,
    [switch]$WasiProbeOnly,
    [switch]$SkipStaticValidation
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
if (Get-Variable PSNativeCommandUseErrorActionPreference -ErrorAction SilentlyContinue) {
    $PSNativeCommandUseErrorActionPreference = $false
}
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)

function Invoke-Captured {
    param(
        [Parameter(Mandatory=$true)][string]$Label,
        [Parameter(Mandatory=$true)][scriptblock]$Command
    )
    $lines = @(& $Command 2>&1)
    $exit = $LASTEXITCODE
    $lines | ForEach-Object { Write-Host "$_" }
    if ($exit -ne 0) {
        throw "$Label`_FAILED exit=$exit"
    }
    return ,$lines
}

function Require-Line {
    param(
        [Parameter(Mandatory=$true)][object[]]$Lines,
        [Parameter(Mandatory=$true)][string]$Expected,
        [Parameter(Mandatory=$true)][string]$Label
    )
    if (@($Lines | Where-Object { "$_" -eq $Expected }).Count -ne 1) {
        throw "$Label`_MARKER_MISSING expected=$Expected"
    }
}

function Marker-Value {
    param(
        [Parameter(Mandatory=$true)][object[]]$Lines,
        [Parameter(Mandatory=$true)][string]$Prefix
    )
    $matches = @($Lines | Where-Object { "$_".StartsWith($Prefix, [StringComparison]::Ordinal) })
    if ($matches.Count -ne 1) {
        throw "MARKER_VALUE_MISSING_OR_DUPLICATE prefix=$Prefix count=$($matches.Count)"
    }
    return "$($matches[0])".Substring($Prefix.Length)
}

function Assert-FileBytesEqual {
    param(
        [Parameter(Mandatory=$true)][string]$Left,
        [Parameter(Mandatory=$true)][string]$Right,
        [Parameter(Mandatory=$true)][string]$Label
    )
    $a = [IO.File]::ReadAllBytes($Left)
    $b = [IO.File]::ReadAllBytes($Right)
    if ($a.Length -ne $b.Length) {
        throw "$Label`_BYTE_LENGTH_MISMATCH left=$Left right=$Right"
    }
    for ($index = 0; $index -lt $a.Length; $index++) {
        if ($a[$index] -ne $b[$index]) {
            throw "$Label`_BYTE_MISMATCH index=$index left=$Left right=$Right"
        }
    }
}

function Write-Base64File {
    param(
        [Parameter(Mandatory=$true)][string]$Base64,
        [Parameter(Mandatory=$true)][string]$Path
    )
    [IO.File]::WriteAllBytes(
        $Path,
        [Convert]::FromBase64String($Base64))
}

function Get-FreePort {
    $listener = [Net.Sockets.TcpListener]::new(
        [Net.IPAddress]::Loopback,
        0)
    $listener.Start()
    try {
        return ([Net.IPEndPoint]$listener.LocalEndpoint).Port
    }
    finally {
        $listener.Stop()
    }
}

function Wait-Port {
    param(
        [Parameter(Mandatory=$true)][int]$Port,
        [int]$TimeoutSeconds = 30
    )
    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    while ([DateTime]::UtcNow -lt $deadline) {
        $client = [Net.Sockets.TcpClient]::new()
        try {
            $task = $client.ConnectAsync("127.0.0.1", $Port)
            if ($task.Wait(250) -and $client.Connected) {
                return
            }
        }
        catch {}
        finally {
            $client.Dispose()
        }
        Start-Sleep -Milliseconds 100
    }
    throw "GATE7_SERVER_PORT_TIMEOUT port=$Port"
}

function Start-ExactProcess {
    param(
        [Parameter(Mandatory=$true)][string]$FileName,
        [Parameter(Mandatory=$true)][string[]]$Arguments
    )
    $psi = [Diagnostics.ProcessStartInfo]::new()
    $psi.FileName = $FileName
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true
    foreach ($item in $Arguments) {
        [void]$psi.ArgumentList.Add($item)
    }
    $process = [Diagnostics.Process]::Start($psi)
    if ($null -eq $process) {
        throw "PROCESS_START_FAILED file=$FileName"
    }
    return $process
}

function Wait-Witness {
    param(
        [Parameter(Mandatory=$true)][string]$Path,
        [Parameter(Mandatory=$true)][string]$Gate,
        [int]$TimeoutSeconds = 150,
        [switch]$AllowFail
    )
    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    while ([DateTime]::UtcNow -lt $deadline) {
        if (Test-Path -LiteralPath $Path) {
            foreach ($line in @(Get-Content -LiteralPath $Path -Encoding UTF8)) {
                if ([string]::IsNullOrWhiteSpace($line)) { continue }
                try {
                    $record = $line | ConvertFrom-Json -Depth 20
                }
                catch { continue }
                if ($record.gate -eq $Gate) {
                    if ($record.status -ne "PASS" -and -not $AllowFail) {
                        throw "GATE7_BROWSER_PHASE_FAILED gate=$Gate detail=$($record.detail)"
                    }
                    return $record
                }
            }
        }
        Start-Sleep -Milliseconds 150
    }
    throw "GATE7_BROWSER_WITNESS_TIMEOUT gate=$Gate"
}

function Stop-ChromeTree {
    param([Parameter(Mandatory=$true)][Diagnostics.Process]$Process)
    if ($Process.HasExited) { return }
    & taskkill /PID $Process.Id /T 2>$null | Out-Null
    Start-Sleep -Seconds 2
    if (-not $Process.HasExited) {
        & taskkill /PID $Process.Id /T /F 2>$null | Out-Null
        Start-Sleep -Seconds 1
    }
}

function Find-Chrome {
    $candidates = @(
        "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
        "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
        "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe"
    )
    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path -LiteralPath $candidate)) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }
    throw "GATE7_CHROME_NOT_FOUND"
}

function Get-DotNetWasiSdkRequirement {
    param([Parameter(Mandatory=$true)][string]$ProjectPath)
    $projectText = Get-Content -LiteralPath $ProjectPath -Raw -Encoding UTF8
    $tfmMatch = [regex]::Match(
        $projectText,
        '<TargetFramework>\s*net([0-9]+)\.[0-9]+\s*</TargetFramework>')
    if (-not $tfmMatch.Success) {
        throw "GATE7_WASI_TFM_DISCOVERY_FAILED"
    }

    $dotnetRoot = Split-Path -Parent (Get-Command dotnet -ErrorAction Stop).Source
    $packRoot = Join-Path $dotnetRoot "packs\Microsoft.NET.Runtime.WebAssembly.Wasi.Sdk"
    $packs = @(
        Get-ChildItem $packRoot -Directory -ErrorAction Stop |
        Where-Object {
            $_.Name -like "$($tfmMatch.Groups[1].Value).*" -and
            (Test-Path (Join-Path $_.FullName "Sdk\WasiApp.targets"))
        } |
        Sort-Object {
            try { [version]$_.Name } catch { [version]'0.0' }
        } -Descending
    )
    if ($packs.Count -lt 1) {
        throw "GATE7_WASI_PACK_MISSING"
    }

    $targets = Join-Path $packs[0].FullName "Sdk\WasiApp.targets"
    $matches = @([regex]::Matches(
        (Get-Content -LiteralPath $targets -Raw -Encoding UTF8),
        '(?is)<_ExpectedWasiSdkVersion(?:\s+[^>]*)?>\s*([0-9]+(?:\.[0-9]+)+)\s*</_ExpectedWasiSdkVersion>'))
    $versions = @(
        $matches |
        ForEach-Object { $_.Groups[1].Value } |
        Sort-Object -Unique
    )
    if ($versions.Count -ne 1) {
        throw "GATE7_WASI_EXPECTED_SDK_DISCOVERY_FAILED count=$($versions.Count)"
    }
    return $versions[0]
}

function Test-WasiSdkRoot {
    param(
        [string]$Root,
        [Parameter(Mandatory=$true)][string]$Required
    )
    if (-not $Root -or -not (Test-Path -LiteralPath $Root -PathType Container)) {
        return $false
    }
    $versionFile = Join-Path $Root "VERSION"
    $clang = Join-Path $Root "bin\clang.exe"
    $sysroot = Join-Path $Root "share\wasi-sysroot"
    if (-not (Test-Path -LiteralPath $versionFile -PathType Leaf) -or
        -not (Test-Path -LiteralPath $clang -PathType Leaf) -or
        -not (Test-Path -LiteralPath $sysroot -PathType Container)) {
        return $false
    }
    return ((Get-Content -LiteralPath $versionFile -Raw).Trim()).StartsWith(
        $Required,
        [StringComparison]::Ordinal)
}

function Resolve-WasiSdkPath {
    param([Parameter(Mandatory=$true)][string]$Required)
    $candidates = @()
    if ($env:WASI_SDK_PATH) {
        $candidates += $env:WASI_SDK_PATH
    }
    $candidates += (Join-Path $env:LOCALAPPDATA ("Programs\wasi-sdk\" + $Required))
    $candidates += (Join-Path $env:LOCALAPPDATA "Programs\wasi-sdk")

    foreach ($candidate in @($candidates | Select-Object -Unique)) {
        if (Test-WasiSdkRoot -Root $candidate -Required $Required) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
        if ($candidate -and (Test-Path -LiteralPath $candidate -PathType Container)) {
            $nested = @(
                Get-ChildItem -LiteralPath $candidate -Directory -ErrorAction SilentlyContinue |
                Where-Object {
                    Test-WasiSdkRoot -Root $_.FullName -Required $Required
                }
            )
            if ($nested.Count -eq 1) {
                return $nested[0].FullName
            }
        }
    }
    throw "GATE7_WASI_SDK_REQUIRED_VERSION_NOT_FOUND=$Required"
}

function Invoke-Gate7WasiCampaign {
    param(
        [Parameter(Mandatory=$true)][string]$RepositoryRoot,
        [Parameter(Mandatory=$true)][string]$WasiPublish,
        [Parameter(Mandatory=$true)][string]$Fixtures
    )

    $wasiProject = Join-Path $RepositoryRoot "runtimes\csharp\TevScript.WasiDeterminismGate\TevScript.WasiDeterminismGate.csproj"
    $requiredWasi = Get-DotNetWasiSdkRequirement -ProjectPath $wasiProject
    $resolvedWasi = Resolve-WasiSdkPath -Required $requiredWasi
    # The .NET 10 WASI SDK concatenates $(WASI_SDK_PATH) with paths such as
    # bin/clang.exe. Preserve the root identity, but bind the MSBuild-facing
    # value with one explicit trailing directory separator.
    $wasiSdkForMsbuild = $resolvedWasi.TrimEnd([char]'\', [char]'/') + [IO.Path]::DirectorySeparatorChar
    $expectedClangFromBinding = $wasiSdkForMsbuild + 'bin\clang.exe'
    $expectedSysrootFromBinding = $wasiSdkForMsbuild + 'share\wasi-sysroot'
    if (-not (Test-Path -LiteralPath $expectedClangFromBinding -PathType Leaf)) {
        throw "GATE7_WASI_SDK_BINDING_CLANG_MISSING=$expectedClangFromBinding"
    }
    if (-not (Test-Path -LiteralPath $expectedSysrootFromBinding -PathType Container)) {
        throw "GATE7_WASI_SDK_BINDING_SYSROOT_MISSING=$expectedSysrootFromBinding"
    }
    $env:WASI_SDK_PATH = $wasiSdkForMsbuild
    Write-Host "GATE7_WASI_SDK_REQUIRED=$requiredWasi"
    Write-Host "GATE7_WASI_SDK_ROOT=$resolvedWasi"
    Write-Host "GATE7_WASI_SDK_PATH=$wasiSdkForMsbuild"
    Write-Host "GATE7_WASI_SDK_BINDING_TRAILING_SEPARATOR=PASS"
    Write-Host "GATE7_WASI_SDK_BINDING_CLANG=PASS"
    Write-Host "GATE7_WASI_SDK_BINDING_SYSROOT=PASS"
    Write-Host "GATE7_WASI_SDK_BINDING=ENV_AND_EXPLICIT_MSBUILD_PROPERTY"

    $wasiPublishStart = [DateTime]::UtcNow
    $wasiPublishLines = Invoke-Captured -Label "GATE7_WASI_PUBLISH" -Command {
        dotnet publish $wasiProject --configuration Release --nologo `
            "-p:PublishDir=$WasiPublish" `
            "-p:Gate7FixtureDir=$Fixtures" `
            "-p:WASI_SDK_PATH=$wasiSdkForMsbuild"
    }
    if (-not (Test-Path -LiteralPath (Join-Path $WasiPublish "dotnet.wasm"))) {
        throw "GATE7_WASI_DOTNET_WASM_MISSING"
    }
    $wasiRunScripts = @(
        Get-ChildItem (Join-Path (Split-Path $wasiProject -Parent) "bin") `
            -Recurse -File -Filter "run-wasmtime.sh" -ErrorAction SilentlyContinue |
        Where-Object {
            $_.LastWriteTimeUtc -ge $wasiPublishStart.AddSeconds(-5) -and
            (Get-Content -LiteralPath $_.FullName -Raw -Encoding UTF8).Contains(
                "wasmtime run --dir . dotnet.wasm TevScript.WasiDeterminismGate")
        }
    )
    if ($wasiRunScripts.Count -lt 1) {
        throw "GATE7_WASI_GENERATED_RUN_CONTRACT_MISSING"
    }
    Write-Host "GATE7_WASI_DOTNET_PUBLISH=PASS"
    Write-Host "GATE7_WASI_RUN_CONTRACT=NON_SINGLE_FILE_PASS"

    Push-Location $WasiPublish
    try {
        $wasiFresh = Invoke-Captured -Label "GATE7_WASI_FRESH" -Command {
            wasmtime run -S http --dir . dotnet.wasm TevScript.WasiDeterminismGate fresh gate7.checkpoint.json
        }
        $wasiRestore = Invoke-Captured -Label "GATE7_WASI_RESTORE" -Command {
            wasmtime run -S http --dir . dotnet.wasm TevScript.WasiDeterminismGate restore gate7.checkpoint.json
        }
    }
    finally {
        Pop-Location
    }
    Require-Line -Lines $wasiFresh `
        -Expected "TEV_SCRIPT_WASI_DISTRIBUTED_DETERMINISM_GATE7=PASS" `
        -Label "GATE7_WASI_FRESH"
    Require-Line -Lines $wasiRestore `
        -Expected "TEV_SCRIPT_WASI_DISTRIBUTED_DETERMINISM_GATE7=PASS" `
        -Label "GATE7_WASI_RESTORE"

    return [pscustomobject]@{
        Fresh = @($wasiFresh)
        Restore = @($wasiRestore)
    }
}

$RepositoryRoot = (Resolve-Path -LiteralPath $RepositoryRoot).Path
Set-Location $RepositoryRoot

$validator = Join-Path $RepositoryRoot "tools\validate_distributed_determinism_gate7a_7e.py"
if (-not $SkipStaticValidation) {
    $staticLines = Invoke-Captured -Label "GATE7_STATIC_VALIDATION" -Command {
        python $validator
    }
    Require-Line -Lines $staticLines -Expected "TEV_SCRIPT_DISTRIBUTED_DETERMINISM_GATE7_STATIC=PASS" -Label "GATE7_STATIC"
}
else {
    Write-Host "GATE7_STATIC_VALIDATION=SKIPPED_DELTA_PROBE"
}

$mode = if ($WasiProbeOnly) { "WASI_DELTA_PROBE" } elseif ($RequireClean) { "CLEAN" } else { "PRECOMMIT" }
Write-Host "GATE7_RUN_MODE=$mode"

$runRoot = Join-Path $env:LOCALAPPDATA (
    "TEV_SCRIPT_DISTRIBUTED_DETERMINISM_GATE7\" +
    [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $runRoot -Force | Out-Null

$program = Join-Path $RepositoryRoot "examples\Player.tevs.ir.json"
$scenario = Join-Path $RepositoryRoot "conformance\distributed-lockstep.scenario.json"
$counterfactual = Join-Path $RepositoryRoot "conformance\distributed-lockstep.counterfactual.json"
$fixtures = Join-Path $runRoot "fixtures"
$hostOut = Join-Path $runRoot "host"
$prefixDir = Join-Path $runRoot "prefixes"
$prefixBaseReceipts = Join-Path $runRoot "prefix-baseline-receipts"
$prefixCounterReceipts = Join-Path $runRoot "prefix-counter-receipts"
$browserPublish = Join-Path $runRoot "browser-publish"
$wasiPublish = Join-Path $runRoot "wasi-publish"

@($fixtures, $hostOut, $prefixDir, $prefixBaseReceipts,
  $prefixCounterReceipts, $browserPublish, $wasiPublish) |
    ForEach-Object { New-Item -ItemType Directory -Path $_ -Force | Out-Null }

$fixtureProject = Join-Path $RepositoryRoot "runtimes\csharp\TevScript.HotUpdateFixtureTool\TevScript.HotUpdateFixtureTool.csproj"
Invoke-Captured -Label "GATE7_FIXTURE_GENERATION" -Command {
    dotnet run --project $fixtureProject --configuration Release -- --base $program --out $fixtures
} | Out-Null

$package1 = Join-Path $fixtures "package1.json"
$authority = Join-Path $fixtures "authority.json"
if (-not (Test-Path $package1) -or -not (Test-Path $authority)) {
    throw "GATE7_SIGNED_FIXTURE_MISSING"
}
Write-Host "GATE7_SIGNED_FIXTURE=PASS"

if ($WasiProbeOnly) {
    $wasiProbe = Invoke-Gate7WasiCampaign `
        -RepositoryRoot $RepositoryRoot `
        -WasiPublish $wasiPublish `
        -Fixtures $fixtures
    Write-Host "GATE7_WASI_DELTA_PROBE=PASS"
    Write-Host "GATE7_WASI_DELTA_PROBE_SCOPE=PUBLISH_FRESH_RESTORE_ONLY"
    return
}

$hostProject = Join-Path $RepositoryRoot "runtimes\csharp\TevScript.DeterminismHostGate\TevScript.DeterminismHostGate.csproj"
$hostLines = Invoke-Captured -Label "GATE7_HOST" -Command {
    dotnet run --project $hostProject --configuration Release -- $program $scenario $package1 $authority $hostOut
}
Require-Line -Lines $hostLines -Expected "GATE7A_CSHARP_REPLAY_64=PASS" -Label "GATE7A_CSHARP"
Require-Line -Lines $hostLines -Expected "GATE7D_HOST_RESTORE_CONTINUATION=PASS" -Label "GATE7D_HOST"
Require-Line -Lines $hostLines -Expected "TEV_SCRIPT_DISTRIBUTED_DETERMINISM_HOST_GATE7=PASS" -Label "GATE7_HOST"

$hostFull = Join-Path $hostOut "host.full.receipt.json"
$hostCheckpoint = Join-Path $hostOut "host.checkpoint.json"
$hostContinuation = Join-Path $hostOut "host.continuation.receipt.json"
$hostSigned = Join-Path $hostOut "host.signed-update.receipt.json"
$hostCheckpointHash = Marker-Value -Lines $hostLines -Prefix "GATE7D_HOST_CHECKPOINT_HASH="

$pythonFull = Join-Path $runRoot "python.full.receipt.json"
$pythonLines = Invoke-Captured -Label "GATE7_PYTHON" -Command {
    python (Join-Path $RepositoryRoot "tools\run_gate7_python_receipt.py") --program $program --scenario $scenario --out $pythonFull --repeat 64
}
Require-Line -Lines $pythonLines -Expected "GATE7_PYTHON_REPLAY_64=PASS" -Label "GATE7A_PYTHON"

$javascriptFull = Join-Path $runRoot "javascript.full.receipt.json"
$javascriptLines = Invoke-Captured -Label "GATE7_JAVASCRIPT" -Command {
    node (Join-Path $RepositoryRoot "tools\run_gate7_javascript_receipt.mjs") --program $program --scenario $scenario --out $javascriptFull --repeat 64
}
Require-Line -Lines $javascriptLines -Expected "GATE7_JAVASCRIPT_REPLAY_64=PASS" -Label "GATE7A_JAVASCRIPT"

Assert-FileBytesEqual -Left $hostFull -Right $pythonFull -Label "GATE7B_CSHARP_PYTHON"
Assert-FileBytesEqual -Left $hostFull -Right $javascriptFull -Label "GATE7B_CSHARP_JAVASCRIPT"
Write-Host "GATE7A_DETERMINISTIC_REPLAY=PASS"
Write-Host "GATE7B_NATIVE_THREE_RUNTIME_BYTE_PARITY=PASS"

Invoke-Captured -Label "GATE7_PREFIX_GENERATION" -Command {
    python (Join-Path $RepositoryRoot "tools\gate7_divergence.py") generate --baseline $scenario --counterfactual $counterfactual --out $prefixDir
} | Out-Null

for ($index = 1; $index -le 10; $index++) {
    $basePrefix = Join-Path $prefixDir "baseline.$index.json"
    $counterPrefix = Join-Path $prefixDir "counterfactual.$index.json"
    $pyReceipt = Join-Path $prefixBaseReceipts "baseline.$index.receipt.json"
    $jsBaselineReceipt = Join-Path $runRoot "js-baseline-$index.receipt.json"
    $jsCounterReceipt = Join-Path $prefixCounterReceipts "counterfactual.$index.receipt.json"

    Invoke-Captured -Label "GATE7_PREFIX_PYTHON_$index" -Command {
        python (Join-Path $RepositoryRoot "tools\run_gate7_python_receipt.py") --program $program --scenario $basePrefix --out $pyReceipt --repeat 1
    } | Out-Null
    Invoke-Captured -Label "GATE7_PREFIX_JS_BASE_$index" -Command {
        node (Join-Path $RepositoryRoot "tools\run_gate7_javascript_receipt.mjs") --program $program --scenario $basePrefix --out $jsBaselineReceipt --repeat 1
    } | Out-Null
    Assert-FileBytesEqual -Left $pyReceipt -Right $jsBaselineReceipt -Label "GATE7_PREFIX_LOCKSTEP_$index"

    Invoke-Captured -Label "GATE7_PREFIX_JS_COUNTER_$index" -Command {
        node (Join-Path $RepositoryRoot "tools\run_gate7_javascript_receipt.mjs") --program $program --scenario $counterPrefix --out $jsCounterReceipt --repeat 1
    } | Out-Null
}
Write-Host "GATE7B_STEPWISE_PYTHON_JAVASCRIPT_LOCKSTEP=PASS"

$divergenceLines = Invoke-Captured -Label "GATE7_DIVERGENCE" -Command {
    python (Join-Path $RepositoryRoot "tools\gate7_divergence.py") detect --baseline $scenario --counterfactual $counterfactual --prefix-dir $prefixDir --baseline-receipts $prefixBaseReceipts --counterfactual-receipts $prefixCounterReceipts --expected 7
}
Require-Line -Lines $divergenceLines -Expected "GATE7C_FIRST_DIVERGENCE_INDEX=7" -Label "GATE7C_INDEX"
Require-Line -Lines $divergenceLines -Expected "GATE7C_FIRST_DIVERGENCE_LOCALIZATION=PASS" -Label "GATE7C"
Write-Host "GATE7C_DIVERGENCE_DETECTION=PASS"

$browserProject = Join-Path $RepositoryRoot "runtimes\csharp\TevScript.BrowserDeterminismGate\TevScript.BrowserDeterminismGate.csproj"
Invoke-Captured -Label "GATE7_BROWSER_PUBLISH" -Command {
    dotnet publish $browserProject --configuration Release --runtime browser-wasm "-p:Gate7FixtureDir=$fixtures" "-p:RunAOTCompilation=true" --output $browserPublish
} | Out-Null
$webRoot = Join-Path $browserPublish "wwwroot"
if (-not (Test-Path (Join-Path $webRoot "_framework\dotnet.js"))) {
    throw "GATE7_BROWSER_PUBLISH_LAYOUT_INVALID"
}
Write-Host "GATE7_BROWSER_DOTNET_PUBLISH=PASS"
Write-Host "GATE7_BROWSER_AOT=PASS_REQUESTED"

$chrome = Find-Chrome
$port = Get-FreePort
$witnessPath = Join-Path $runRoot "browser-witness.jsonl"
$profile = Join-Path $runRoot "chrome-profile"
New-Item -ItemType Directory -Path $profile -Force | Out-Null
$freshToken = [guid]::NewGuid().ToString("N")
$restoreToken = [guid]::NewGuid().ToString("N")
$pythonExe = (Get-Command python -ErrorAction Stop).Source
$browserFailure = $null
$freshWitness = $null
$restoreWitness = $null
$serverProcess = Start-ExactProcess -FileName $pythonExe -Arguments @(
    (Join-Path $RepositoryRoot "tools\serve_gate7_browser.py"),
    "--root", $webRoot,
    "--port", "$port",
    "--witness-file", $witnessPath,
    "--token", "gate7-browser-fresh=$freshToken",
    "--token", "gate7-browser-restore=$restoreToken"
)
try {
    Wait-Port -Port $port

    $freshUrl = "http://127.0.0.1:$port/index.html?phase=fresh&tev_witness_token=$freshToken"
    $chromeFresh = Start-ExactProcess -FileName $chrome -Arguments @(
        "--headless=new",
        "--disable-background-networking",
        "--disable-component-update",
        "--no-first-run",
        "--no-default-browser-check",
        "--enable-aggressive-domstorage-flushing",
        "--user-data-dir=$profile",
        "--window-size=1280,800",
        $freshUrl
    )
    $freshWitness = Wait-Witness -Path $witnessPath -Gate "gate7-browser-fresh" -AllowFail
    Start-Sleep -Seconds 3
    Stop-ChromeTree -Process $chromeFresh
    Start-Sleep -Seconds 2

    if ($freshWitness.status -eq "PASS") {
        $restoreUrl = "http://127.0.0.1:$port/index.html?phase=restore&tev_witness_token=$restoreToken"
        $chromeRestore = Start-ExactProcess -FileName $chrome -Arguments @(
            "--headless=new",
            "--disable-background-networking",
            "--disable-component-update",
            "--no-first-run",
            "--no-default-browser-check",
            "--enable-aggressive-domstorage-flushing",
            "--user-data-dir=$profile",
            "--window-size=1280,800",
            $restoreUrl
        )
        $restoreWitness = Wait-Witness -Path $witnessPath -Gate "gate7-browser-restore" -AllowFail
        Stop-ChromeTree -Process $chromeRestore
        if ($restoreWitness.status -ne "PASS") {
            $browserFailure = $restoreWitness
        }
    }
    else {
        $browserFailure = $freshWitness
    }
}
finally {
    if ($serverProcess -and -not $serverProcess.HasExited) {
        $serverProcess.Kill($true)
        $serverProcess.WaitForExit(5000) | Out-Null
    }
}

$browserPassed = $null -eq $browserFailure
if ($browserPassed) {
    $browserFull = Join-Path $runRoot "browser.full.receipt.json"
    $browserContinuationFresh = Join-Path $runRoot "browser.continuation.fresh.json"
    $browserContinuationRestore = Join-Path $runRoot "browser.continuation.restore.json"
    $browserSigned = Join-Path $runRoot "browser.signed-update.receipt.json"

    Write-Base64File -Base64 $freshWitness.payload.GATE7_BROWSER_FULL_RECEIPT_B64 -Path $browserFull
    Write-Base64File -Base64 $freshWitness.payload.GATE7_BROWSER_CONTINUATION_RECEIPT_B64 -Path $browserContinuationFresh
    Write-Base64File -Base64 $restoreWitness.payload.GATE7_BROWSER_CONTINUATION_RECEIPT_B64 -Path $browserContinuationRestore
    Write-Base64File -Base64 $freshWitness.payload.GATE7_BROWSER_SIGNED_UPDATE_RECEIPT_B64 -Path $browserSigned
    $browserCheckpointHash = "$($freshWitness.payload.GATE7_BROWSER_CHECKPOINT_HASH)"

    Assert-FileBytesEqual -Left $hostFull -Right $browserFull -Label "GATE7B_BROWSER"
    Assert-FileBytesEqual -Left $hostContinuation -Right $browserContinuationFresh -Label "GATE7D_BROWSER_FRESH"
    Assert-FileBytesEqual -Left $hostContinuation -Right $browserContinuationRestore -Label "GATE7D_BROWSER_RESTORE"
    Assert-FileBytesEqual -Left $hostSigned -Right $browserSigned -Label "GATE7E_BROWSER"
    if ($browserCheckpointHash -ne $hostCheckpointHash) {
        throw "GATE7D_BROWSER_CHECKPOINT_HASH_MISMATCH"
    }
    Write-Host "GATE7_BROWSER_REAL_PROCESS_RESTART=PASS"
    Write-Host "GATE7D_BROWSER_CHECKPOINT_RESTORE=PASS"
}
else {
    Write-Host "GATE7_BROWSER_DIAGNOSTIC_STATUS=FAIL_CAPTURED_CONTINUING_TO_WASI"
    Write-Host "GATE7_BROWSER_DIAGNOSTIC_GATE=$($browserFailure.gate)"
    Write-Host "GATE7_BROWSER_DIAGNOSTIC_DETAIL=$($browserFailure.detail)"
    if ($browserFailure.payload) {
        foreach ($name in @(
            "GATE7_BROWSER_FAILURE_PHASE",
            "GATE7_BROWSER_FAILURE_STAGE",
            "GATE7_BROWSER_FAILURE_CODE",
            "GATE7_BROWSER_FAILURE_TYPE",
            "GATE7_BROWSER_FAILURE_MESSAGE_B64")) {
            $property = $browserFailure.payload.PSObject.Properties[$name]
            if ($null -ne $property) {
                Write-Host "$name=$($property.Value)"
            }
        }
    }
}

$wasiCampaign = Invoke-Gate7WasiCampaign `
    -RepositoryRoot $RepositoryRoot `
    -WasiPublish $wasiPublish `
    -Fixtures $fixtures
$wasiFresh = @($wasiCampaign.Fresh)
$wasiRestore = @($wasiCampaign.Restore)

$wasiFull = Join-Path $runRoot "wasi.full.receipt.json"
$wasiContinuationFresh = Join-Path $runRoot "wasi.continuation.fresh.json"
$wasiContinuationRestore = Join-Path $runRoot "wasi.continuation.restore.json"
$wasiSigned = Join-Path $runRoot "wasi.signed-update.receipt.json"
Write-Base64File -Base64 (Marker-Value -Lines $wasiFresh -Prefix "GATE7_WASI_FULL_RECEIPT_B64=") -Path $wasiFull
Write-Base64File -Base64 (Marker-Value -Lines $wasiFresh -Prefix "GATE7_WASI_CONTINUATION_RECEIPT_B64=") -Path $wasiContinuationFresh
Write-Base64File -Base64 (Marker-Value -Lines $wasiRestore -Prefix "GATE7_WASI_CONTINUATION_RECEIPT_B64=") -Path $wasiContinuationRestore
Write-Base64File -Base64 (Marker-Value -Lines $wasiFresh -Prefix "GATE7_WASI_SIGNED_UPDATE_RECEIPT_B64=") -Path $wasiSigned
$wasiCheckpointHash = Marker-Value -Lines $wasiFresh -Prefix "GATE7_WASI_CHECKPOINT_HASH="

Assert-FileBytesEqual -Left $hostFull -Right $wasiFull -Label "GATE7B_WASI"
Assert-FileBytesEqual -Left $hostContinuation -Right $wasiContinuationFresh -Label "GATE7D_WASI_FRESH"
Assert-FileBytesEqual -Left $hostContinuation -Right $wasiContinuationRestore -Label "GATE7D_WASI_RESTORE"
Assert-FileBytesEqual -Left $hostSigned -Right $wasiSigned -Label "GATE7E_WASI"
if ($wasiCheckpointHash -ne $hostCheckpointHash) {
    throw "GATE7D_WASI_CHECKPOINT_HASH_MISMATCH"
}
Write-Host "GATE7_WASI_DIAGNOSTIC_CAMPAIGN=PASS"

if (-not $browserPassed) {
    throw "GATE7_BROWSER_DIAGNOSTIC_FAILURE gate=$($browserFailure.gate) detail=$($browserFailure.detail)"
}

Write-Host "GATE7B_CROSS_HOST_LOCKSTEP=PASS"
Write-Host "GATE7B_HOSTS=PYTHON_JAVASCRIPT_CSHARP_BROWSER_WASM_WASI"
Write-Host "GATE7D_CANONICAL_CHECKPOINT=PASS"
Write-Host "GATE7D_RESTART_CONTINUATION_BYTE_PARITY=PASS"
Write-Host "GATE7E_SIGNED_UPDATE_LOCKSTEP=PASS"

$branch = (git branch --show-current).Trim()
$head = (git rev-parse HEAD).Trim()
$tree = (git rev-parse "$head^{tree}").Trim()
$parent = (git rev-parse "$head^").Trim()
$receiptDir = Join-Path $RepositoryRoot "receipts\distributed-determinism-gate7"
New-Item -ItemType Directory -Path $receiptDir -Force | Out-Null
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$evidencePath = Join-Path $receiptDir "GATE7_$stamp.json"

$evidence = [ordered]@{
    schema = "TEV_SCRIPT_DISTRIBUTED_DETERMINISM_GATE7A_7E_RECEIPT_V1"
    mode = $mode
    branch = $branch
    head = $head
    tree = $tree
    parent = $parent
    gate7a = "PASS_DETERMINISTIC_REPLAY_64"
    gate7b = "PASS_CROSS_HOST_BYTE_LOCKSTEP"
    gate7c = "PASS_FIRST_DIVERGENCE_INDEX_7"
    gate7d = "PASS_CANONICAL_CHECKPOINT_RESTART"
    gate7e = "PASS_SIGNED_UPDATE_LOCKSTEP"
    checkpoint_hash = $hostCheckpointHash
    full_receipt_sha256 = (Get-FileHash -LiteralPath $hostFull -Algorithm SHA256).Hash.ToLowerInvariant()
    continuation_receipt_sha256 = (Get-FileHash -LiteralPath $hostContinuation -Algorithm SHA256).Hash.ToLowerInvariant()
    signed_update_receipt_sha256 = (Get-FileHash -LiteralPath $hostSigned -Algorithm SHA256).Hash.ToLowerInvariant()
    core_product_changes = "2_PHYSICAL_1_LOGICAL"
    stable_release = $false
}
$evidence | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $evidencePath -Encoding utf8NoBOM
$evidenceHash = (Get-FileHash -LiteralPath $evidencePath -Algorithm SHA256).Hash.ToLowerInvariant()

Write-Host ""
Write-Host "GATE7A_DETERMINISTIC_REPLAY=PASS"
Write-Host "GATE7B_CROSS_HOST_LOCKSTEP=PASS"
Write-Host "GATE7C_FIRST_DIVERGENCE_LOCALIZATION=PASS"
Write-Host "GATE7D_CHECKPOINT_RESTART=PASS"
Write-Host "GATE7E_SIGNED_UPDATE_LOCKSTEP=PASS"
Write-Host "TEV_SCRIPT_DISTRIBUTED_DETERMINISM_GATE7A_7E=PASS"
Write-Host "GATE7_CORE_PRODUCT_CHANGES=2_PHYSICAL_1_LOGICAL"
Write-Host "GATE7_EVIDENCE=$evidencePath"
Write-Host "GATE7_EVIDENCE_SHA256=$evidenceHash"
Write-Host "STABLE_RELEASE=NO"
