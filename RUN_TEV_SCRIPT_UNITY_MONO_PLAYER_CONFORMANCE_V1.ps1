[CmdletBinding()]
param(
    [string]$RepositoryRoot = "C:\mio\TEV-Script",
    [string]$UnityExe = "",
    [switch]$RequireClean
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

    $preferred = "C:\Program Files\Unity\Hub\Editor\6000.3.10f1\Editor\Unity.exe"
    if (Test-Path -LiteralPath $preferred -PathType Leaf) { return $preferred }

    $hubRoot = "C:\Program Files\Unity\Hub\Editor"
    if (-not (Test-Path -LiteralPath $hubRoot -PathType Container)) {
        throw "UNITY_HUB_EDITOR_ROOT_NOT_FOUND"
    }
    $candidates = @(
        Get-ChildItem -LiteralPath $hubRoot -Directory |
        Where-Object { $_.Name -like "6000.3*" } |
        Sort-Object Name -Descending |
        ForEach-Object { Join-Path $_.FullName "Editor\Unity.exe" } |
        Where-Object { Test-Path -LiteralPath $_ -PathType Leaf }
    )
    if ($candidates.Count -lt 1) { throw "UNITY_6000_3_NOT_FOUND" }
    return $candidates[0]
}

function Wait-ProcessWithTimeout {
    param(
        [System.Diagnostics.Process]$Process,
        [int]$TimeoutMilliseconds,
        [string]$TimeoutCode
    )
    if ($null -eq $Process) { throw "PROCESS_HANDLE_MISSING" }
    $finished = $Process.WaitForExit($TimeoutMilliseconds)
    if (-not $finished) {
        try { taskkill /PID $Process.Id /T /F | Out-Null } catch {}
        throw "$TimeoutCode pid=$($Process.Id)"
    }
    return $Process.ExitCode
}

if (-not (Test-Path -LiteralPath (Join-Path $RepositoryRoot ".git") -PathType Container)) {
    throw "REPOSITORY_NOT_FOUND=$RepositoryRoot"
}
Set-Location $RepositoryRoot
if ($RequireClean) { Require-CleanGit -Root $RepositoryRoot }

$head = (git rev-parse HEAD).Trim()
$tree = (git rev-parse "HEAD^{tree}").Trim()
$branchLines = @(git branch --show-current)
if ($LASTEXITCODE -ne 0) { throw "GIT_IDENTITY_QUERY_FAILED" }
$branch = ($branchLines -join "").Trim()
if ([string]::IsNullOrWhiteSpace($branch)) { throw "GIT_BRANCH_EMPTY" }

python (Join-Path $RepositoryRoot "unity\VALIDATE_UNITY_PACKAGE.py")
if ($LASTEXITCODE -ne 0) { throw "UNITY_GATE1_STATIC_REGRESSION_FAILED" }
python (Join-Path $RepositoryRoot "unity\VALIDATE_UNITY_PLAYMODE_GATE2.py")
if ($LASTEXITCODE -ne 0) { throw "UNITY_GATE2_STATIC_REGRESSION_FAILED" }
python (Join-Path $RepositoryRoot "unity\VALIDATE_UNITY_MONO_PLAYER_GATE3.py")
if ($LASTEXITCODE -ne 0) { throw "UNITY_GATE3_STATIC_FAILED" }

$resolvedUnity = Resolve-UnityExe -Requested $UnityExe
$editorVersion = Split-Path -Leaf (Split-Path -Parent (Split-Path -Parent $resolvedUnity))
if ($editorVersion -notlike "6000.3*") {
    throw "UNITY_VERSION_OUTSIDE_GATE_BOUNDARY=$editorVersion"
}
Write-Host "UNITY_EXE=$resolvedUnity"
Write-Host "UNITY_EDITOR_VERSION=$editorVersion"

# Gate-2 is the certified lower-layer authority for the Unity runtime adapter.
# Re-run it from an isolated local clone of the exact certified commit so the
# Gate-3 harness cannot contaminate the PlayMode certification surface.
$gate2CertifiedHead = "c32f9305e61bd31321a654b3192c72fef28cd33e"
$gate2CloneParent = Join-Path $env:LOCALAPPDATA "TEV_SCRIPT_UNITY_GATE2_REGRESSION"
New-Item -ItemType Directory -Path $gate2CloneParent -Force | Out-Null
$gate2Clone = Join-Path $gate2CloneParent ([Guid]::NewGuid().ToString("N"))
try {
    git clone --quiet --no-hardlinks --no-checkout $RepositoryRoot $gate2Clone
    if ($LASTEXITCODE -ne 0) { throw "UNITY_GATE2_REGRESSION_CLONE_FAILED" }
    $gate2EphemeralBranch = "gate2-regression-" + [Guid]::NewGuid().ToString("N")
    git -C $gate2Clone switch --quiet -c $gate2EphemeralBranch $gate2CertifiedHead
    if ($LASTEXITCODE -ne 0) { throw "UNITY_GATE2_REGRESSION_CHECKOUT_FAILED" }
    $gate2Observed = (git -C $gate2Clone rev-parse HEAD).Trim()
    if ($gate2Observed -ne $gate2CertifiedHead) {
        throw "UNITY_GATE2_REGRESSION_HEAD_MISMATCH observed=$gate2Observed"
    }

    & pwsh -NoProfile -ExecutionPolicy Bypass `
        -File (Join-Path $gate2Clone "RUN_TEV_SCRIPT_UNITY_PLAYMODE_CONFORMANCE_V1.ps1") `
        -RepositoryRoot $gate2Clone `
        -UnityExe $resolvedUnity `
        -RequireClean
    if ($LASTEXITCODE -ne 0) { throw "UNITY_GATE2_REGRESSION_FAILED" }
}
finally {
    if (Test-Path -LiteralPath $gate2Clone) {
        Remove-Item -LiteralPath $gate2Clone -Recurse -Force -ErrorAction SilentlyContinue
    }
}
Write-Host "UNITY_GATE2_REGRESSION=PASS"
Write-Host "UNITY_GATE2_REGRESSION_ISOLATION=CERTIFIED_BASE_NAMED_BRANCH_CLONE"
Write-Host "UNITY_GATE2_REGRESSION_HEAD=$gate2CertifiedHead"

$packageRoot = Join-Path $RepositoryRoot "unity\Package"
$runtimeHarness = Join-Path $RepositoryRoot "unity\PlayerGates\Mono\TevScriptMonoPlayerGate.cs"
$runtimeHarnessAsmdef = Join-Path $RepositoryRoot "unity\PlayerGates\Mono\Marcbeacve.TevScript.Gate3.MonoPlayer.asmdef"
$buildHarness = Join-Path $RepositoryRoot "unity\PlayerGates\Mono\TevScriptMonoPlayerBuildGate.cs"
$canonicalPlayer = Join-Path $RepositoryRoot "examples\Player.tevs.ir.json"
foreach ($required in @($packageRoot, $runtimeHarness, $runtimeHarnessAsmdef, $buildHarness, $canonicalPlayer)) {
    if (-not (Test-Path -LiteralPath $required)) { throw "UNITY_GATE3_REQUIRED_PATH_MISSING=$required" }
}

$gateRoot = Join-Path $env:LOCALAPPDATA "TEV_SCRIPT_UNITY_MONO_PLAYER_GATE3"
New-Item -ItemType Directory -Path $gateRoot -Force | Out-Null
$projectRoot = Join-Path $gateRoot ([Guid]::NewGuid().ToString("N"))
$buildLog = Join-Path $projectRoot "unity-mono-build.log"
$playerLog = Join-Path $projectRoot "unity-mono-player.log"

New-Item -ItemType Directory -Path (Join-Path $projectRoot "Assets\Gate3") -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $projectRoot "Assets\Editor") -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $projectRoot "Assets\Resources") -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $projectRoot "Packages") -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $projectRoot "ProjectSettings") -Force | Out-Null

$localPackagesRoot = Join-Path $projectRoot "LocalPackages"
$stagedPackageRoot = Join-Path $localPackagesRoot "com.marcbeacve.tev-script"
New-Item -ItemType Directory -Path $localPackagesRoot -Force | Out-Null
Copy-Item -LiteralPath $packageRoot -Destination $stagedPackageRoot -Recurse -Force
Copy-Item -LiteralPath $runtimeHarness -Destination (Join-Path $projectRoot "Assets\Gate3\TevScriptMonoPlayerGate.cs") -Force
Copy-Item -LiteralPath $runtimeHarnessAsmdef -Destination (Join-Path $projectRoot "Assets\Gate3\Marcbeacve.TevScript.Gate3.MonoPlayer.asmdef") -Force
Copy-Item -LiteralPath $buildHarness -Destination (Join-Path $projectRoot "Assets\Editor\TevScriptMonoPlayerBuildGate.cs") -Force
Write-Host "UNITY_MONO_HARNESS_ASSEMBLY_REFERENCES=EXPLICIT_PASS"
Copy-Item -LiteralPath $canonicalPlayer -Destination (Join-Path $projectRoot "Assets\Resources\TevScriptGate3Player.json") -Force

$fixtureShaExpected = (Get-FileHash -LiteralPath $canonicalPlayer -Algorithm SHA256).Hash.ToLowerInvariant()
$fixtureShaStaged = (Get-FileHash -LiteralPath (Join-Path $projectRoot "Assets\Resources\TevScriptGate3Player.json") -Algorithm SHA256).Hash.ToLowerInvariant()
if ($fixtureShaExpected -ne $fixtureShaStaged) { throw "UNITY_GATE3_PLAYER_FIXTURE_DRIFT" }
Write-Host "UNITY_GATE3_PLAYER_FIXTURE_IDENTITY=PASS"

$packageUriPath = (Resolve-Path -LiteralPath $stagedPackageRoot).Path.Replace("\", "/")
$manifest = [ordered]@{
    dependencies = [ordered]@{
        "com.marcbeacve.tev-script" = "file:$packageUriPath"
    }
}
$manifest | ConvertTo-Json -Depth 8 | Set-Content `
    -LiteralPath (Join-Path $projectRoot "Packages\manifest.json") `
    -Encoding utf8
"m_EditorVersion: $editorVersion`n" | Set-Content `
    -LiteralPath (Join-Path $projectRoot "ProjectSettings\ProjectVersion.txt") `
    -Encoding utf8

$buildArgs = @(
    "-batchmode", "-nographics", "-quit",
    "-projectPath", ('"' + $projectRoot + '"'),
    "-buildTarget", "StandaloneWindows64",
    "-executeMethod", "TevScriptMonoPlayerBuildGate.Build",
    "-logFile", ('"' + $buildLog + '"')
)
$buildProcess = Start-Process -FilePath $resolvedUnity -ArgumentList $buildArgs -PassThru
$buildExit = Wait-ProcessWithTimeout -Process $buildProcess -TimeoutMilliseconds 420000 -TimeoutCode "UNITY_MONO_BUILD_TIMEOUT"
Write-Host "UNITY_MONO_BUILD_PROCESS_WAIT=PASS"
Write-Host "UNITY_MONO_BUILD_PROCESS_EXIT_CODE=$buildExit"

$evidenceDir = Join-Path $RepositoryRoot "receipts\unity-mono-player-gate3"
New-Item -ItemType Directory -Path $evidenceDir -Force | Out-Null
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$evidenceBuildLog = Join-Path $evidenceDir "UNITY_MONO_BUILD_$stamp.log"
$evidencePlayerLog = Join-Path $evidenceDir "UNITY_MONO_PLAYER_$stamp.log"
if (Test-Path -LiteralPath $buildLog -PathType Leaf) {
    Copy-Item -LiteralPath $buildLog -Destination $evidenceBuildLog -Force
}

if (-not (Test-Path -LiteralPath $buildLog -PathType Leaf)) {
    throw "UNITY_MONO_BUILD_LOG_MISSING exit=$buildExit temp_project=$projectRoot"
}
if ((Get-Item -LiteralPath $buildLog).Length -le 0) {
    throw "UNITY_MONO_BUILD_LOG_EMPTY exit=$buildExit temp_project=$projectRoot"
}
if ($buildExit -ne 0) {
    Get-Content -LiteralPath $buildLog -Tail 300 | ForEach-Object { Write-Host $_ }
    throw "UNITY_MONO_BUILD_FAILED exit=$buildExit temp_project=$projectRoot"
}

$buildText = Get-Content -LiteralPath $buildLog -Raw
foreach ($marker in @(
    "UNITY_MONO_PLAYER_BUILD_BACKEND=MONO",
    "UNITY_MONO_PLAYER_BUILD_TARGET=STANDALONE_WINDOWS64",
    "UNITY_MONO_PLAYER_BUILD_RESULT=PASS"
)) {
    if (-not $buildText.Contains($marker)) { throw "UNITY_MONO_BUILD_WITNESS_MISSING=$marker" }
    Write-Host "UNITY_MONO_BUILD_WITNESS_PASS=$marker"
}

$buildDir = Join-Path $projectRoot "Build"
$playerExe = Join-Path $buildDir "TEVScriptMonoGate.exe"
$monoDir = Join-Path $buildDir "MonoBleedingEdge"
$dataManaged = Join-Path $buildDir "TEVScriptMonoGate_Data\Managed"
$coreAssembly = Join-Path $dataManaged "Marcbeacve.TevScript.Core.dll"
$unityAssembly = Join-Path $dataManaged "Marcbeacve.TevScript.Unity.dll"
$gate3Assembly = Join-Path $dataManaged "Marcbeacve.TevScript.Gate3.MonoPlayer.dll"
$gameAssembly = Join-Path $buildDir "GameAssembly.dll"

foreach ($requiredFile in @($playerExe, $coreAssembly, $unityAssembly, $gate3Assembly)) {
    if (-not (Test-Path -LiteralPath $requiredFile -PathType Leaf)) {
        throw "UNITY_MONO_BUILD_ARTIFACT_MISSING=$requiredFile temp_project=$projectRoot"
    }
}
if (-not (Test-Path -LiteralPath $monoDir -PathType Container)) {
    throw "UNITY_MONO_RUNTIME_DIRECTORY_MISSING=$monoDir temp_project=$projectRoot"
}
if (Test-Path -LiteralPath $gameAssembly -PathType Leaf) {
    throw "UNITY_MONO_UNEXPECTED_IL2CPP_GAMEASSEMBLY=$gameAssembly"
}
Write-Host "UNITY_MONO_ARTIFACT_LAYOUT=PASS"
Write-Host "UNITY_MONO_MANAGED_CORE_ASSEMBLY=PASS"
Write-Host "UNITY_MONO_MANAGED_UNITY_ADAPTER_ASSEMBLY=PASS"
Write-Host "UNITY_MONO_MANAGED_GATE3_HARNESS_ASSEMBLY=PASS"
Write-Host "UNITY_MONO_HARNESS_ASSEMBLY_REFERENCES=EXPLICIT_PASS"
Write-Host "UNITY_MONO_GAMEASSEMBLY=ABSENT_PASS"

$exeSha = (Get-FileHash -LiteralPath $playerExe -Algorithm SHA256).Hash.ToLowerInvariant()
Write-Host "UNITY_MONO_PLAYER_EXE_SHA256=$exeSha"

$playerArgs = @(
    "-batchmode", "-nographics",
    "-logFile", ('"' + $playerLog + '"')
)
$playerProcess = Start-Process -FilePath $playerExe -ArgumentList $playerArgs -WorkingDirectory $buildDir -PassThru
$playerExit = Wait-ProcessWithTimeout -Process $playerProcess -TimeoutMilliseconds 90000 -TimeoutCode "UNITY_MONO_PLAYER_TIMEOUT"
Write-Host "UNITY_MONO_PLAYER_PROCESS_WAIT=PASS"
Write-Host "UNITY_MONO_PLAYER_PROCESS_EXIT_CODE=$playerExit"

if (Test-Path -LiteralPath $playerLog -PathType Leaf) {
    Copy-Item -LiteralPath $playerLog -Destination $evidencePlayerLog -Force
}
if (-not (Test-Path -LiteralPath $playerLog -PathType Leaf)) {
    throw "UNITY_MONO_PLAYER_LOG_MISSING exit=$playerExit temp_project=$projectRoot"
}
if ((Get-Item -LiteralPath $playerLog).Length -le 0) {
    throw "UNITY_MONO_PLAYER_LOG_EMPTY exit=$playerExit temp_project=$projectRoot"
}
if ($playerExit -ne 0) {
    Get-Content -LiteralPath $playerLog -Tail 300 | ForEach-Object { Write-Host $_ }
    throw "UNITY_MONO_PLAYER_EXECUTION_FAILED exit=$playerExit temp_project=$projectRoot"
}

$playerText = Get-Content -LiteralPath $playerLog -Raw
$requiredPlayerMarkers = @(
    "UNITY_MONO_PLAYER_ACTIVE=PASS",
    "UNITY_MONO_PLAYER_PLATFORM=WINDOWS_PLAYER_PASS",
    "UNITY_MONO_PLAYER_CORE_PARSE=PASS",
    "UNITY_MONO_PLAYER_CAPABILITY_INPUT_MOVE2D=PASS",
    "UNITY_MONO_PLAYER_CAPABILITY_MOTION_TRANSFORM2D=PASS",
    "UNITY_MONO_PLAYER_CAPABILITY_ANIMATION_PLAY=PASS",
    "UNITY_MONO_PLAYER_CAPABILITY_DEBUG_LOG=PASS",
    "UNITY_MONO_PLAYER_RUNTIME_STATE=PASS",
    "UNITY_MONO_PLAYER_CAPABILITY_TIME_DELTA=PASS",
    "UNITY_MONO_PLAYER_FLOAT_TO_RAT_EXACT=PASS",
    "UNITY_MONO_PLAYER_RAT_TO_FLOAT_BOUNDARY_WITNESS=PASS",
    "UNITY_MONO_PLAYER_TIME_DELTA_BOUNDARY_WITNESS=PASS",
    "UNITY_MONO_PLAYER_NONFINITE_FLOAT_FAIL_CLOSED=PASS",
    "UNITY_MONO_PLAYER_CAPABILITY_ABI=PASS",
    "UNITY_MONO_PLAYER_FLOAT_BOUNDARY=EXPLICIT_AUDITED_PASS",
    "UNITY_MONO_PLAYER_PROVIDER_AUTHORITY=EXPLICIT_PASS",
    "UNITY_INPUT_SYSTEM_DEVICE=NOT_PROBED",
    "UNITY_ANIMATOR_CONTROLLER=NOT_PROBED",
    "TEV_SCRIPT_UNITY_MONO_PLAYER_GATE_3=PASS",
    "UNITY_IL2CPP=NOT_PROBED"
)
foreach ($marker in $requiredPlayerMarkers) {
    if (-not $playerText.Contains($marker)) { throw "UNITY_MONO_PLAYER_WITNESS_MISSING=$marker" }
    Write-Host "UNITY_MONO_PLAYER_WITNESS_PASS=$marker"
}

$buildLogSha = (Get-FileHash -LiteralPath $evidenceBuildLog -Algorithm SHA256).Hash.ToLowerInvariant()
$playerLogSha = (Get-FileHash -LiteralPath $evidencePlayerLog -Algorithm SHA256).Hash.ToLowerInvariant()
Remove-Item -LiteralPath $projectRoot -Recurse -Force -ErrorAction SilentlyContinue

if ($RequireClean) { Require-CleanGit -Root $RepositoryRoot }

Write-Host ""
Write-Host "TEV_SCRIPT_UNITY_MONO_PLAYER_GATE_3=PASS"
Write-Host "BRANCH=$branch"
Write-Host "HEAD=$head"
Write-Host "TREE=$tree"
Write-Host "UNITY_EDITOR_VERSION=$editorVersion"
Write-Host "UNITY_MONO_PLAYER_BUILD=PASS"
Write-Host "UNITY_MONO_PLAYER_EXECUTION=PASS"
Write-Host "UNITY_MONO_PLAYER_BACKEND=MONO"
Write-Host "UNITY_MONO_PLAYER_CAPABILITY_ABI=PASS"
Write-Host "UNITY_MONO_PLAYER_FLOAT_BOUNDARY=EXPLICIT_AUDITED_PASS"
Write-Host "UNITY_MONO_PLAYER_PROVIDER_AUTHORITY=EXPLICIT_PASS"
Write-Host "UNITY_MONO_PLAYER_CORE=UNCHANGED_FROM_CERTIFIED_GATE2"
Write-Host "UNITY_MONO_PLAYER_HARNESS_ASSEMBLY=Marcbeacve.TevScript.Gate3.MonoPlayer"
Write-Host "UNITY_MONO_HARNESS_ASSEMBLY_REFERENCES=EXPLICIT_PASS"
Write-Host "UNITY_MONO_PLAYER_EXE_SHA256=$exeSha"
Write-Host "UNITY_MONO_BUILD_EVIDENCE=$evidenceBuildLog"
Write-Host "UNITY_MONO_BUILD_EVIDENCE_SHA256=$buildLogSha"
Write-Host "UNITY_MONO_PLAYER_EVIDENCE=$evidencePlayerLog"
Write-Host "UNITY_MONO_PLAYER_EVIDENCE_SHA256=$playerLogSha"
Write-Host "UNITY_INPUT_SYSTEM_DEVICE=NOT_PROBED"
Write-Host "UNITY_ANIMATOR_CONTROLLER=NOT_PROBED"
Write-Host "UNITY_IL2CPP=NOT_PROBED"
if ($RequireClean) { Write-Host "GIT_STATUS=CLEAN" } else { Write-Host "GIT_STATUS=CANDIDATE_CHANGES_ALLOWED" }
