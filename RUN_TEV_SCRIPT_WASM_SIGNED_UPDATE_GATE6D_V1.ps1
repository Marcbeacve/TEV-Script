[CmdletBinding()]
param(
    [string]$RepositoryRoot = (Split-Path -Parent $MyInvocation.MyCommand.Path),
    [string]$BrowserExe = "",
    [string]$WasiSdkPath = "",
    [switch]$RequireClean
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
if (Get-Variable PSNativeCommandUseErrorActionPreference -ErrorAction SilentlyContinue) {
    $PSNativeCommandUseErrorActionPreference = $false
}

$ExpectedBase = "3d0390d0071204410544a3989391283fd0b66bfa"
$ExpectedBranch = "agent/tev-script-wasm-signed-update-gate6d-v1"
$RepositoryRoot = (Resolve-Path -LiteralPath $RepositoryRoot).Path
Set-Location $RepositoryRoot

function Resolve-BrowserExe {
    param([string]$Requested)
    if ($Requested) {
        if (-not (Test-Path -LiteralPath $Requested -PathType Leaf)) { throw "BROWSER_EXE_NOT_FOUND=$Requested" }
        return (Resolve-Path -LiteralPath $Requested).Path
    }
    foreach ($candidate in @(
        "$env:ProgramFiles(x86)\Microsoft\Edge\Application\msedge.exe",
        "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe",
        "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
        "$env:ProgramFiles(x86)\Google\Chrome\Application\chrome.exe")) {
        if ($candidate -and (Test-Path -LiteralPath $candidate -PathType Leaf)) { return (Resolve-Path $candidate).Path }
    }
    throw "CHROMIUM_BROWSER_NOT_FOUND"
}

function New-WitnessToken {
    $bytes = New-Object byte[] 16
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
    return (($bytes | ForEach-Object { $_.ToString("x2") }) -join "")
}

function Stop-BrowserTree {
    param([System.Diagnostics.Process]$Process)
    if ($null -eq $Process) { return }
    try {
        $Process.Refresh()
        if (-not $Process.HasExited) {
            # Give Chromium a normal shutdown path first so persistent DOM
            # Storage can flush its pending commit queue. /F is fallback only.
            & taskkill.exe /PID $Process.Id /T 2>$null | Out-Null
            $deadline=(Get-Date).AddSeconds(12)
            while((Get-Date)-lt $deadline){
                Start-Sleep -Milliseconds 100
                $Process.Refresh()
                if($Process.HasExited){break}
            }
            if(-not $Process.HasExited){
                Write-Host "GATE6D_BROWSER_GRACEFUL_SHUTDOWN=FALLBACK_FORCE"
                & taskkill.exe /PID $Process.Id /T /F 2>$null | Out-Null
            } else {
                Write-Host "GATE6D_BROWSER_GRACEFUL_SHUTDOWN=PASS"
            }
        }
    } catch { Stop-Process -Id $Process.Id -Force -ErrorAction SilentlyContinue }
    finally { $Process.Dispose() }
}

function Require-Markers {
    param([object[]]$Lines,[string[]]$Markers,[string]$Label)
    foreach ($marker in $Markers) {
        if (@($Lines | Where-Object { [string]$_ -eq $marker }).Count -ne 1) {
            throw "$Label`_MARKER_MISSING=$marker"
        }
    }
}

function Get-DotNetWasiSdkRequirement {
    $gateProject = Join-Path $RepositoryRoot "runtimes\csharp\TevScript.WasiUpdateGate\TevScript.WasiUpdateGate.csproj"
    $projectText = Get-Content -LiteralPath $gateProject -Raw
    $tfmMatch = [regex]::Match($projectText,'<TargetFramework>\s*net([0-9]+)\.[0-9]+\s*</TargetFramework>')
    if (-not $tfmMatch.Success) { throw "GATE6D_WASI_TFM_DISCOVERY_FAILED" }
    $dotnetRoot = Split-Path -Parent (Get-Command dotnet -ErrorAction Stop).Source
    $packRoot = Join-Path $dotnetRoot "packs\Microsoft.NET.Runtime.WebAssembly.Wasi.Sdk"
    $packs = @(Get-ChildItem $packRoot -Directory | Where-Object { $_.Name -like "$($tfmMatch.Groups[1].Value).*" -and (Test-Path (Join-Path $_.FullName "Sdk\WasiApp.targets")) } | Sort-Object { try {[version]$_.Name}catch{[version]'0.0'} } -Descending)
    if ($packs.Count -lt 1) { throw "GATE6D_WASI_PACK_MISSING" }
    $targets = Join-Path $packs[0].FullName "Sdk\WasiApp.targets"
    $matches = @([regex]::Matches((Get-Content $targets -Raw),'(?is)<_ExpectedWasiSdkVersion(?:\s+[^>]*)?>\s*([0-9]+(?:\.[0-9]+)+)\s*</_ExpectedWasiSdkVersion>'))
    $versions = @($matches | ForEach-Object {$_.Groups[1].Value} | Sort-Object -Unique)
    if ($versions.Count -ne 1) { throw "GATE6D_WASI_EXPECTED_SDK_DISCOVERY_FAILED count=$($versions.Count)" }
    return $versions[0]
}

function Test-WasiSdkRoot {
    param([string]$Root,[string]$Required)
    if (-not $Root -or -not (Test-Path $Root -PathType Container)) { return $false }
    $versionFile=Join-Path $Root "VERSION"; $clang=Join-Path $Root "bin\clang.exe"; $sysroot=Join-Path $Root "share\wasi-sysroot"
    if (-not (Test-Path $versionFile) -or -not (Test-Path $clang) -or -not (Test-Path $sysroot -PathType Container)) { return $false }
    return ((Get-Content $versionFile -Raw).Trim()).StartsWith($Required,[StringComparison]::Ordinal)
}

function Resolve-WasiSdkPath {
    param([string]$Requested,[string]$Required)
    $candidates=@()
    if($Requested){$candidates+=$Requested}
    $candidates+=(Join-Path $env:LOCALAPPDATA ("Programs\wasi-sdk\"+$Required))
    if($env:WASI_SDK_PATH){$candidates+=$env:WASI_SDK_PATH}
    $candidates+=(Join-Path $env:LOCALAPPDATA "Programs\wasi-sdk")
    foreach($candidate in @($candidates|Select-Object -Unique)){
        if(Test-WasiSdkRoot $candidate $Required){return (Resolve-Path $candidate).Path}
        if($candidate -and (Test-Path $candidate -PathType Container)){
            $nested=@(Get-ChildItem $candidate -Directory -ErrorAction SilentlyContinue|Where-Object{Test-WasiSdkRoot $_.FullName $Required})
            if($nested.Count -eq 1){return $nested[0].FullName}
        }
    }
    throw "GATE6D_WASI_SDK_REQUIRED_VERSION_NOT_FOUND=$Required"
}

function Wait-ServerReady {
    param([System.Diagnostics.Process]$Process,[string]$PortFile,[string]$Stderr)
    $deadline=(Get-Date).AddSeconds(20)
    while((Get-Date)-lt $deadline){
        $Process.Refresh(); if($Process.HasExited){if(Test-Path $Stderr){Get-Content $Stderr -Tail 100|ForEach-Object{Write-Host $_}};throw "GATE6D_SERVER_EXITED"}
        if(Test-Path $PortFile){$raw=(Get-Content $PortFile -Raw).Trim();if($raw -match '^\d+$'){return $raw}}
        Start-Sleep -Milliseconds 100
    }
    throw "GATE6D_SERVER_PORT_TIMEOUT"
}

function Wait-Witness {
    param([string]$File,[int]$Sequence,[string]$Gate,[string]$Token,[System.Diagnostics.Process]$Server)
    $deadline=(Get-Date).AddSeconds(190)
    while((Get-Date)-lt $deadline){
        $Server.Refresh(); if($Server.HasExited){throw "GATE6D_WITNESS_SERVER_EXITED"}
        if(Test-Path $File){
            $lines=@(Get-Content $File|Where-Object{-not [string]::IsNullOrWhiteSpace($_)})
            if($lines.Count -ge $Sequence){
                $receipt=$lines[$Sequence-1]|ConvertFrom-Json
                if([string]$receipt.schema -ne 'TEV_SCRIPT_GATE6D_BROWSER_WITNESS_V1' -or [int]$receipt.sequence -ne $Sequence -or [string]$receipt.gate -ne $Gate -or [string]$receipt.token -ne $Token){throw "GATE6D_WITNESS_BINDING_MISMATCH sequence=$Sequence"}
                if([string]$receipt.status -ne 'PASS'){throw "GATE6D_BROWSER_PHASE_FAILED gate=$Gate detail=$($receipt.detail)"}
                Write-Host "GATE6D_BROWSER_HTTP_WITNESS=PASS sequence=$Sequence gate=$Gate detail=$($receipt.detail)"
                return $receipt
            }
        }
        Start-Sleep -Milliseconds 100
    }
    throw "GATE6D_BROWSER_WITNESS_TIMEOUT gate=$Gate"
}

$branch=(git branch --show-current).Trim(); $head=(git rev-parse HEAD).Trim(); $tree=(git rev-parse 'HEAD^{tree}').Trim()
$parent=""
if($head -ne $ExpectedBase){
    $parent=(git rev-parse HEAD^).Trim()
    if($LASTEXITCODE -ne 0){throw "GATE6D_PARENT_QUERY_FAILED"}
}
if($branch -ne $ExpectedBranch){throw "GATE6D_BRANCH_MISMATCH expected=$ExpectedBranch observed=$branch"}
if($head -eq $ExpectedBase){
    if($RequireClean){throw "GATE6D_REQUIRE_CLEAN_REQUIRES_COMMITTED_CANDIDATE"}
} elseif($parent -eq $ExpectedBase) {
    if(-not $RequireClean){throw "GATE6D_COMMITTED_CANDIDATE_REQUIRES_REQUIRE_CLEAN"}
    Write-Host "GATE6D_CLEAN_COMMIT_ADMISSION=PASS"
} else {
    throw "GATE6D_HEAD_LINEAGE_MISMATCH base=$ExpectedBase head=$head parent=$parent"
}
if($RequireClean -and @(git status --porcelain=v1 --untracked-files=all).Count -ne 0){throw "GATE6D_REQUIRE_CLEAN_FAILED"}

python .\tools\validate_wasm_signed_update_gate6d.py --repo-root $RepositoryRoot
if($LASTEXITCODE -ne 0){throw "GATE6D_STATIC_VALIDATION_FAILED"}
Write-Host "GATE6D_CORE_PRODUCT_CHANGES=0"
Write-Host "GATE6D_UPDATE_PRODUCT_CHANGES=2_PHYSICAL_1_LOGICAL"

$resolvedBrowser=Resolve-BrowserExe $BrowserExe
$wasmtime=(Get-Command wasmtime -ErrorAction Stop).Source
$wasmtimeVersion=@(& $wasmtime --version 2>&1); if($LASTEXITCODE -ne 0){throw "GATE6D_WASMTIME_VERSION_FAILED"}
$workloads=@(dotnet workload list 2>&1); if($LASTEXITCODE -ne 0){throw "GATE6D_DOTNET_WORKLOAD_QUERY_FAILED"}
if(($workloads -join "`n") -notmatch '(?m)^\s*wasm-tools\s'){throw "GATE6D_DOTNET_WORKLOAD_MISSING=wasm-tools"}
if(($workloads -join "`n") -notmatch '(?m)^\s*wasi-experimental\s'){throw "GATE6D_DOTNET_WORKLOAD_MISSING=wasi-experimental"}
$requiredWasi=Get-DotNetWasiSdkRequirement
$resolvedWasi=Resolve-WasiSdkPath $WasiSdkPath $requiredWasi
$env:WASI_SDK_PATH=$resolvedWasi
Write-Host "GATE6D_BROWSER_EXE=$resolvedBrowser"
Write-Host "GATE6D_WASMTIME_VERSION=$($wasmtimeVersion -join ' ')"
Write-Host "GATE6D_WASI_SDK_REQUIRED=$requiredWasi"
Write-Host "GATE6D_WASI_SDK_PATH=$resolvedWasi"

$runRoot=Join-Path $env:LOCALAPPDATA ("TEV_SCRIPT_WASM_GATE6D\"+[guid]::NewGuid().ToString('N'))
$fixtures=Join-Path $runRoot "fixtures"; New-Item $fixtures -ItemType Directory -Force|Out-Null
$base=Join-Path $RepositoryRoot "examples\Player.tevs.ir.json"
$fixtureProject=Join-Path $RepositoryRoot "runtimes\csharp\TevScript.HotUpdateFixtureTool\TevScript.HotUpdateFixtureTool.csproj"
dotnet run --project $fixtureProject -c Release -- --base $base --out $fixtures
if($LASTEXITCODE -ne 0){throw "GATE6D_FIXTURE_GENERATION_FAILED"}
Write-Host "GATE6D_FIXTURE_AUTHORITY=EXISTING_GATE5C_FIXTURE_TOOL_PASS"

# Regression: the previously certified desktop provider and 5C/5D authority remain intact.
$regStore=Join-Path $runRoot "gate5d-regression.json"
$regProject=Join-Path $RepositoryRoot "runtimes\csharp\TevScript.HotUpdateBatchGate\TevScript.HotUpdateBatchGate.csproj"
$regOutput=@(dotnet run --project $regProject -c Release -- --base $base --fixtures $fixtures --store $regStore 2>&1)
$regExit=$LASTEXITCODE; $regOutput|ForEach-Object{Write-Host $_}
if($regExit -ne 0 -or @($regOutput|Where-Object{"$_" -eq 'TEV_SCRIPT_HOT_UPDATE_BATCH_GATE_5C_5D=PASS'}).Count -ne 1){throw "GATE6D_GATE5C_5D_REGRESSION_FAILED"}
Write-Host "GATE6D_GATE5C_5D_REGRESSION=PASS"

# Browser-WASM signed update gate.
$browserProject=Join-Path $RepositoryRoot "runtimes\csharp\TevScript.BrowserWasmUpdateGate\TevScript.BrowserWasmUpdateGate.csproj"
$browserPublish=Join-Path $runRoot "browser-publish"; New-Item $browserPublish -ItemType Directory -Force|Out-Null
dotnet publish $browserProject -c Release --nologo "-p:PublishDir=$browserPublish" "-p:TevGate6DFixtureDir=$fixtures"
if($LASTEXITCODE -ne 0){throw "GATE6D_BROWSER_PUBLISH_FAILED"}
$www=Join-Path $browserPublish "wwwroot"; $webRoot=if(Test-Path $www -PathType Container){$www}else{$browserPublish}
$main=Join-Path $webRoot "main.mjs"; $index=Join-Path $webRoot "index.html"; $framework=Join-Path $webRoot "_framework"
if(-not (Test-Path $main) -or -not (Test-Path $index) -or -not (Test-Path $framework -PathType Container)){throw "GATE6D_BROWSER_PUBLISH_LAYOUT_INVALID"}
$dotnetJs=@(Get-ChildItem $framework -File -Filter 'dotnet*.js')|Sort-Object Name|Select-Object -First 1
if($null -eq $dotnetJs){throw "GATE6D_BROWSER_DOTNET_JS_MISSING"}
$relative=[IO.Path]::GetRelativePath($webRoot,$dotnetJs.FullName).Replace('\','/')
if($relative -ne '_framework/dotnet.js'){
    $text=Get-Content $main -Raw; if(-not $text.Contains('./_framework/dotnet.js')){throw "GATE6D_BROWSER_IMPORT_ANCHOR_MISSING"}
    Set-Content $main ($text.Replace('./_framework/dotnet.js','./'+$relative)) -Encoding utf8
}
$wasms=@(Get-ChildItem $webRoot -Recurse -File -Filter '*.wasm'); if($wasms.Count -lt 1){throw "GATE6D_BROWSER_WASM_MISSING"}
Write-Host "GATE6D_BROWSER_DOTNET_PUBLISH=PASS"
Write-Host "GATE6D_BROWSER_AOT=REQUESTED"

$token1=New-WitnessToken; $token2=New-WitnessToken; if($token1 -eq $token2){throw "GATE6D_NONCE_COLLISION"}
$plan=Join-Path $runRoot 'browser-plan.json'; @(@{gate='gate6d-browser-fresh';token=$token1},@{gate='gate6d-browser-restore';token=$token2})|ConvertTo-Json -Compress|Set-Content $plan -Encoding utf8
$portFile=Join-Path $runRoot 'browser-port.txt'; $witnessFile=Join-Path $runRoot 'browser-witness.jsonl'; $serverOut=Join-Path $runRoot 'browser-server.out'; $serverErr=Join-Path $runRoot 'browser-server.err'
$server=Start-Process (Get-Command python).Source -ArgumentList @((Join-Path $RepositoryRoot 'tools\serve_gate6d_browser.py'),'--root',$webRoot,'--port-file',$portFile,'--witness-file',$witnessFile,'--plan-file',$plan) -RedirectStandardOutput $serverOut -RedirectStandardError $serverErr -PassThru
$port=Wait-ServerReady $server $portFile $serverErr; $baseUrl="http://127.0.0.1:$port"
$profile=Join-Path $runRoot 'browser-profile'; New-Item $profile -ItemType Directory -Force|Out-Null
try {
    foreach($phaseInfo in @(@{phase='fresh';token=$token1;seq=1},@{phase='restore';token=$token2;seq=2})){
        $phase=$phaseInfo.phase; $token=$phaseInfo.token; $seq=[int]$phaseInfo.seq
        $bout=Join-Path $runRoot "browser-$phase.out"; $berr=Join-Path $runRoot "browser-$phase.err"
        $url="$baseUrl/index.html?phase=$phase&tev_witness_token=$token"
        $browser=Start-Process $resolvedBrowser -ArgumentList @('--headless=new','--no-first-run','--no-default-browser-check','--disable-background-timer-throttling','--disable-backgrounding-occluded-windows','--disable-renderer-backgrounding','--enable-aggressive-domstorage-flushing','--window-size=1280,720',"--user-data-dir=$profile",$url) -RedirectStandardOutput $bout -RedirectStandardError $berr -PassThru
        try {
            [void](Wait-Witness $witnessFile $seq ("gate6d-browser-"+$phase) $token $server)
            if($phase -eq 'fresh'){
                # localStorage.setItem is synchronous at the JS surface, but
                # its disk-backed commit is browser-managed. Keep the first
                # process alive long enough for the aggressive flush policy
                # before exercising a true process restart.
                Write-Host "GATE6D_BROWSER_STORAGE_FLUSH_POLICY=AGGRESSIVE_DOMSTORAGE"
                Start-Sleep -Seconds 5
            } else {
                Start-Sleep -Milliseconds 800
            }
        } finally {
            Stop-BrowserTree $browser
            Start-Sleep -Milliseconds 1200
        }
    }
} finally {
    if(-not $server.HasExited){Stop-Process $server.Id -Force -ErrorAction SilentlyContinue;$server.WaitForExit()};$server.Dispose()
}
$receipts=@(Get-Content $witnessFile|ForEach-Object{$_|ConvertFrom-Json})
if($receipts.Count -ne 2){throw "GATE6D_BROWSER_RECEIPT_COUNT_MISMATCH=$($receipts.Count)"}
foreach($r in $receipts){if([string]$r.detail -notmatch '^SIGNED_UPDATE_(FRESH|RESTORE)_WEBCRYPTO_PASS$'){throw "GATE6D_BROWSER_DETAIL_INVALID=$($r.detail)"}}
Write-Host "GATE6D_BROWSER_WEBCRYPTO_ORACLE=PASS"
Write-Host "GATE6D_BROWSER_LOCALSTORAGE_RESTART_RESTORE=PASS"
Write-Host "TEV_SCRIPT_BROWSER_WASM_SIGNED_UPDATE_GATE_6D=PASS"

# WASI signed update gate, two real Wasmtime processes sharing the durable store.
$wasiProject=Join-Path $RepositoryRoot "runtimes\csharp\TevScript.WasiUpdateGate\TevScript.WasiUpdateGate.csproj"
$wasiPublish=Join-Path $runRoot 'wasi-publish'; New-Item $wasiPublish -ItemType Directory -Force|Out-Null
$publishStart=[DateTime]::UtcNow
dotnet publish $wasiProject -c Release --nologo "-p:PublishDir=$wasiPublish" "-p:TevGate6DFixtureDir=$fixtures"
if($LASTEXITCODE -ne 0){throw "GATE6D_WASI_PUBLISH_FAILED"}
$dotnetWasm=Join-Path $wasiPublish 'dotnet.wasm'; if(-not (Test-Path $dotnetWasm)){throw "GATE6D_WASI_DOTNET_WASM_MISSING"}
$runScripts=@(Get-ChildItem (Join-Path (Split-Path $wasiProject -Parent) 'bin') -Recurse -File -Filter 'run-wasmtime.sh' -ErrorAction SilentlyContinue|Where-Object{$_.LastWriteTimeUtc -ge $publishStart.AddSeconds(-5) -and (Get-Content $_.FullName -Raw).Contains('wasmtime run --dir . dotnet.wasm TevScript.WasiUpdateGate')})
if($runScripts.Count -lt 1){throw "GATE6D_WASI_GENERATED_RUN_CONTRACT_MISSING"}
Write-Host "GATE6D_WASI_DOTNET_PUBLISH=PASS"
Write-Host "GATE6D_WASI_RUN_CONTRACT=NON_SINGLE_FILE_PASS"

$allWasi=@()
foreach($phase in @('fresh','restore')){
    $out=Join-Path $runRoot "wasi-$phase.out"; $err=Join-Path $runRoot "wasi-$phase.err"
    $proc=Start-Process $wasmtime -ArgumentList @('run','-S','http','--dir','.','dotnet.wasm','TevScript.WasiUpdateGate',$phase) -WorkingDirectory $wasiPublish -RedirectStandardOutput $out -RedirectStandardError $err -Wait -PassThru
    $lines=@();if(Test-Path $out){$lines+=@(Get-Content $out)};if(Test-Path $err){$lines+=@(Get-Content $err)};$lines|ForEach-Object{Write-Host $_}
    if($proc.ExitCode -ne 0){throw "GATE6D_WASMTIME_PHASE_FAILED phase=$phase exit=$($proc.ExitCode)"}
    Require-Markers $lines @('GATE6D_WASI_MANAGED_ES256=PASS','GATE6D_WASI_UPDATE_AUTHORITY=SAME_TEV_AUTHORITY_PASS','TEV_SCRIPT_WASI_SIGNED_UPDATE_GATE_6D=PASS') ("GATE6D_WASI_"+$phase.ToUpperInvariant())
    $allWasi+=$lines
}
Require-Markers $allWasi @('GATE6D_WASI_DURABLE_PHASE1=PASS','GATE6D_WASI_DURABLE_RESTORE=PASS','GATE6D_WASI_REPLAY_AFTER_RESTORE_FAIL_CLOSED=PASS','GATE6D_WASI_EPOCH_ADVANCE=PASS') 'GATE6D_WASI_CAMPAIGN'
Write-Host "GATE6D_WASI_TWO_PROCESS_RESTORE=PASS"
Write-Host "TEV_SCRIPT_WASI_SIGNED_UPDATE_GATE_6D=PASS"

$evidenceDir=Join-Path $RepositoryRoot 'receipts\wasm-gate6d'; New-Item $evidenceDir -ItemType Directory -Force|Out-Null
$stamp=Get-Date -Format 'yyyyMMdd_HHmmss'; $evidence=Join-Path $evidenceDir "WASM_GATE6D_$stamp.txt"
@(
    "TEV_SCRIPT_WASM_SIGNED_UPDATE_GATE_6D=PASS",
    "BASE_HEAD=$ExpectedBase",
    "HEAD=$head",
    "TREE=$tree",
    "PARENT=$parent",
    "BRANCH=$ExpectedBranch",
    "GATE6D_CORE_PRODUCT_CHANGES=0",
    "GATE6D_UPDATE_PRODUCT_CHANGES=2_PHYSICAL_1_LOGICAL",
    "GATE6D_MANAGED_ES256_DIFFERENTIAL=PASS_PREPACKAGE_600_CASES",
    "GATE6D_BROWSER=PASS_REAL_BROWSER_TWO_PHASE_LOCALSTORAGE",
    "GATE6D_BROWSER_WEBCRYPTO_ORACLE=PASS",
    "GATE6D_WASI=PASS_WASMTIME_TWO_PROCESS_FILE_STORE",
    "GATE6D_GATE5C_5D_REGRESSION=PASS",
    "GATE6D_PRIVATE_KEY_PRODUCT=ABSENT_PASS",
    "GATE6E_OR_DISTRIBUTED_DETERMINISM=NOT_IN_SCOPE",
    "STABLE_RELEASE=NO") | Set-Content $evidence -Encoding utf8
$evidenceSha=(Get-FileHash $evidence -Algorithm SHA256).Hash.ToLowerInvariant()
Write-Host ""
Write-Host "TEV_SCRIPT_WASM_SIGNED_UPDATE_GATE_6D=PASS"
Write-Host "GATE6D_BROWSER=PASS"
Write-Host "GATE6D_WASI=PASS"
Write-Host "GATE6D_CORE_PRODUCT_CHANGES=0"
Write-Host "GATE6D_UPDATE_PRODUCT_CHANGES=2_PHYSICAL_1_LOGICAL"
Write-Host "GATE6D_EVIDENCE=$evidence"
Write-Host "GATE6D_EVIDENCE_SHA256=$evidenceSha"
Write-Host "COMMIT=NOT_CREATED"
Write-Host "REMOTE_PUSH=NOT_PERFORMED"
Write-Host "PR1=NOT_MODIFIED"
Write-Host "MERGE=NOT_PERFORMED"
