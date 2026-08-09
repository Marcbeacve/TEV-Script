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
if ([string]::IsNullOrWhiteSpace($branch)) {
    throw "CURRENT_BRANCH_EMPTY"
}

python (Join-Path $RepositoryRoot "unity\VALIDATE_UNITY_PACKAGE.py")
if ($LASTEXITCODE -ne 0) { throw "UNITY_GATE1_STATIC_REGRESSION_FAILED" }
python (Join-Path $RepositoryRoot "unity\VALIDATE_UNITY_PLAYMODE_GATE2.py")
if ($LASTEXITCODE -ne 0) { throw "UNITY_GATE2_STATIC_REGRESSION_FAILED" }
python (Join-Path $RepositoryRoot "unity\VALIDATE_UNITY_MONO_PLAYER_GATE3.py")
if ($LASTEXITCODE -ne 0) { throw "UNITY_GATE3_STATIC_REGRESSION_FAILED" }
python (Join-Path $RepositoryRoot "unity\VALIDATE_UNITY_IL2CPP_PLAYER_GATE4.py")
if ($LASTEXITCODE -ne 0) { throw "UNITY_GATE4_STATIC_FAILED" }

$resolvedUnity = Resolve-UnityExe -Requested $UnityExe
$editorVersion = Split-Path -Leaf (Split-Path -Parent (Split-Path -Parent $resolvedUnity))
if ($editorVersion -notlike "6000.3*") {
    throw "UNITY_VERSION_OUTSIDE_GATE_BOUNDARY=$editorVersion"
}
Write-Host "UNITY_EXE=$resolvedUnity"
Write-Host "UNITY_EDITOR_VERSION=$editorVersion"

# Lower-layer regression: exact certified Gate-3 commit in an isolated named branch.
$gate3CertifiedHead = "79fe95c8847f1d41be18b55d2e386919ffe57e56"
$gate3CloneParent = Join-Path $env:LOCALAPPDATA "TEV_SCRIPT_UNITY_GATE3_REGRESSION"
New-Item -ItemType Directory -Path $gate3CloneParent -Force | Out-Null
$gate3Clone = Join-Path $gate3CloneParent ([Guid]::NewGuid().ToString("N"))
try {
    git clone --quiet --no-hardlinks --no-checkout $RepositoryRoot $gate3Clone
    if ($LASTEXITCODE -ne 0) { throw "UNITY_GATE3_REGRESSION_CLONE_FAILED" }

    $ephemeral = "gate3-regression-" + [Guid]::NewGuid().ToString("N")
    git -C $gate3Clone switch --quiet -c $ephemeral $gate3CertifiedHead
    if ($LASTEXITCODE -ne 0) { throw "UNITY_GATE3_REGRESSION_CHECKOUT_FAILED" }

    $observed = (git -C $gate3Clone rev-parse HEAD).Trim()
    if ($observed -ne $gate3CertifiedHead) {
        throw "UNITY_GATE3_REGRESSION_HEAD_MISMATCH observed=$observed"
    }

    & pwsh -NoProfile -ExecutionPolicy Bypass `
        -File (Join-Path $gate3Clone "RUN_TEV_SCRIPT_UNITY_MONO_PLAYER_CONFORMANCE_V1.ps1") `
        -RepositoryRoot $gate3Clone `
        -UnityExe $resolvedUnity `
        -RequireClean
    if ($LASTEXITCODE -ne 0) { throw "UNITY_GATE3_REGRESSION_FAILED" }
}
finally {
    if (Test-Path -LiteralPath $gate3Clone) {
        Remove-Item -LiteralPath $gate3Clone -Recurse -Force -ErrorAction SilentlyContinue
    }
}
Write-Host "UNITY_GATE3_REGRESSION=PASS"
Write-Host "UNITY_GATE3_REGRESSION_ISOLATION=CERTIFIED_BASE_NAMED_BRANCH_CLONE"
Write-Host "UNITY_GATE3_REGRESSION_HEAD=$gate3CertifiedHead"

$packageRoot = Join-Path $RepositoryRoot "unity\Package"
$gate4Root = Join-Path $RepositoryRoot "unity\PlayerGates\IL2CPP"
$canonicalPlayer = Join-Path $RepositoryRoot "examples\Player.tevs.ir.json"

$gateRoot = Join-Path $env:LOCALAPPDATA "TEV_SCRIPT_UNITY_IL2CPP_PLAYER_GATE4"
New-Item -ItemType Directory -Path $gateRoot -Force | Out-Null
$projectRoot = Join-Path $gateRoot ([Guid]::NewGuid().ToString("N"))
$buildRoot = Join-Path $projectRoot "Build"
$playerExe = Join-Path $buildRoot "TEVScriptIl2CppGate.exe"
$buildLog = Join-Path $projectRoot "unity-il2cpp-build.log"
$playerLog = Join-Path $projectRoot "unity-il2cpp-player.log"

New-Item -ItemType Directory -Path (Join-Path $projectRoot "Assets\Gate4\Runtime") -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $projectRoot "Assets\Gate4\Editor") -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $projectRoot "Assets\Resources") -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $projectRoot "Packages") -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $projectRoot "ProjectSettings") -Force | Out-Null
New-Item -ItemType Directory -Path $buildRoot -Force | Out-Null

$localPackagesRoot = Join-Path $projectRoot "LocalPackages"
$stagedPackageRoot = Join-Path $localPackagesRoot "com.marcbeacve.tev-script"
New-Item -ItemType Directory -Path $localPackagesRoot -Force | Out-Null
Copy-Item -LiteralPath $packageRoot -Destination $stagedPackageRoot -Recurse -Force

Copy-Item -LiteralPath (Join-Path $gate4Root "Runtime\Marcbeacve.TevScript.Gate4.Il2CppPlayer.asmdef") `
    -Destination (Join-Path $projectRoot "Assets\Gate4\Runtime\Marcbeacve.TevScript.Gate4.Il2CppPlayer.asmdef") -Force
Copy-Item -LiteralPath (Join-Path $gate4Root "Runtime\TevScriptIl2CppPlayerGate.cs") `
    -Destination (Join-Path $projectRoot "Assets\Gate4\Runtime\TevScriptIl2CppPlayerGate.cs") -Force
Copy-Item -LiteralPath (Join-Path $gate4Root "Editor\Marcbeacve.TevScript.Gate4.Il2CppPlayer.Editor.asmdef") `
    -Destination (Join-Path $projectRoot "Assets\Gate4\Editor\Marcbeacve.TevScript.Gate4.Il2CppPlayer.Editor.asmdef") -Force
Copy-Item -LiteralPath (Join-Path $gate4Root "Editor\TevScriptIl2CppPlayerBuildGate.cs") `
    -Destination (Join-Path $projectRoot "Assets\Gate4\Editor\TevScriptIl2CppPlayerBuildGate.cs") -Force
Copy-Item -LiteralPath $canonicalPlayer `
    -Destination (Join-Path $projectRoot "Assets\Resources\TevScriptGate4Player.json") -Force

$fixtureOriginalSha = (Get-FileHash -LiteralPath $canonicalPlayer -Algorithm SHA256).Hash.ToLowerInvariant()
$fixtureStagedSha = (Get-FileHash -LiteralPath (Join-Path $projectRoot "Assets\Resources\TevScriptGate4Player.json") -Algorithm SHA256).Hash.ToLowerInvariant()
if ($fixtureOriginalSha -ne $fixtureStagedSha) {
    throw "UNITY_GATE4_PLAYER_FIXTURE_IDENTITY_FAILED"
}
Write-Host "UNITY_GATE4_PLAYER_FIXTURE_IDENTITY=PASS"

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

$oldBuildExe = $env:TEV_SCRIPT_GATE4_BUILD_EXE
$env:TEV_SCRIPT_GATE4_BUILD_EXE = $playerExe
try {
    $unityArgs = @(
        "-batchmode", "-nographics", "-quit",
        "-projectPath", ('"' + $projectRoot + '"'),
        "-executeMethod",
        "Marcbeacve.TevScript.Gate4.Il2CppPlayer.Editor.TevScriptIl2CppPlayerBuildGate.Build",
        "-logFile", ('"' + $buildLog + '"')
    )
    $buildProcess = Start-Process -FilePath $resolvedUnity -ArgumentList $unityArgs -Wait -PassThru
    $buildExit = $buildProcess.ExitCode
}
finally {
    $env:TEV_SCRIPT_GATE4_BUILD_EXE = $oldBuildExe
}

Write-Host "UNITY_IL2CPP_BUILD_PROCESS_WAIT=PASS"
Write-Host "UNITY_IL2CPP_BUILD_PROCESS_EXIT_CODE=$buildExit"

if (-not (Test-Path -LiteralPath $buildLog -PathType Leaf)) {
    throw "UNITY_IL2CPP_BUILD_LOG_MISSING exit=$buildExit temp_project=$projectRoot"
}
if ($buildExit -ne 0) {
    Get-Content -LiteralPath $buildLog -Tail 300 | ForEach-Object { Write-Host $_ }
    throw "UNITY_IL2CPP_BUILD_FAILED exit=$buildExit temp_project=$projectRoot"
}

$buildText = Get-Content -LiteralPath $buildLog -Raw
foreach ($marker in @(
    "UNITY_IL2CPP_PLAYER_BUILD_BACKEND=IL2CPP",
    "UNITY_IL2CPP_PLAYER_BUILD_TARGET=STANDALONE_WINDOWS64",
    "UNITY_IL2CPP_PLAYER_BUILD_RESULT=PASS"
)) {
    if (-not $buildText.Contains($marker)) {
        throw "UNITY_IL2CPP_BUILD_WITNESS_MISSING=$marker"
    }
    Write-Host "UNITY_IL2CPP_BUILD_WITNESS_PASS=$marker"
}

if (-not (Test-Path -LiteralPath $playerExe -PathType Leaf)) {
    throw "UNITY_IL2CPP_PLAYER_EXE_MISSING"
}

$gameAssembly = Join-Path $buildRoot "GameAssembly.dll"
if (-not (Test-Path -LiteralPath $gameAssembly -PathType Leaf)) {
    throw "UNITY_IL2CPP_GAMEASSEMBLY_MISSING"
}
Write-Host "UNITY_IL2CPP_GAMEASSEMBLY=PASS"

$metadataCandidates = @(
    Get-ChildItem -LiteralPath $buildRoot -Recurse -File -Filter "global-metadata.dat" -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -match "[\\/]il2cpp_data[\\/]Metadata[\\/]global-metadata\.dat$" }
)
if ($metadataCandidates.Count -ne 1) {
    throw "UNITY_IL2CPP_GLOBAL_METADATA_INVALID count=$($metadataCandidates.Count)"
}
Write-Host "UNITY_IL2CPP_GLOBAL_METADATA=PASS"

$monoDirs = @(
    Get-ChildItem -LiteralPath $buildRoot -Recurse -Directory -Filter "MonoBleedingEdge" -ErrorAction SilentlyContinue
)
if ($monoDirs.Count -ne 0) {
    $monoDirs | ForEach-Object { Write-Host "UNEXPECTED_MONO_RUNTIME=$($_.FullName)" }
    throw "UNITY_IL2CPP_MONO_RUNTIME_PRESENT"
}
Write-Host "UNITY_IL2CPP_MONO_RUNTIME=ABSENT_PASS"

$exeSha = (Get-FileHash -LiteralPath $playerExe -Algorithm SHA256).Hash.ToLowerInvariant()
$gameAssemblySha = (Get-FileHash -LiteralPath $gameAssembly -Algorithm SHA256).Hash.ToLowerInvariant()
$metadataSha = (Get-FileHash -LiteralPath $metadataCandidates[0].FullName -Algorithm SHA256).Hash.ToLowerInvariant()
Write-Host "UNITY_IL2CPP_PLAYER_EXE_SHA256=$exeSha"
Write-Host "UNITY_IL2CPP_GAMEASSEMBLY_SHA256=$gameAssemblySha"
Write-Host "UNITY_IL2CPP_GLOBAL_METADATA_SHA256=$metadataSha"

$playerArgs = @(
    "-batchmode", "-nographics",
    "-logFile", ('"' + $playerLog + '"')
)
$playerProcess = Start-Process -FilePath $playerExe -ArgumentList $playerArgs -Wait -PassThru
$playerExit = $playerProcess.ExitCode
Write-Host "UNITY_IL2CPP_PLAYER_PROCESS_WAIT=PASS"
Write-Host "UNITY_IL2CPP_PLAYER_PROCESS_EXIT_CODE=$playerExit"

if (-not (Test-Path -LiteralPath $playerLog -PathType Leaf)) {
    throw "UNITY_IL2CPP_PLAYER_LOG_MISSING exit=$playerExit temp_project=$projectRoot"
}
if ((Get-Item -LiteralPath $playerLog).Length -le 0) {
    throw "UNITY_IL2CPP_PLAYER_LOG_EMPTY exit=$playerExit temp_project=$projectRoot"
}
if ($playerExit -ne 0) {
    Get-Content -LiteralPath $playerLog -Tail 300 | ForEach-Object { Write-Host $_ }
    throw "UNITY_IL2CPP_PLAYER_EXECUTION_FAILED exit=$playerExit temp_project=$projectRoot"
}

$playerText = Get-Content -LiteralPath $playerLog -Raw
$requiredPlayerMarkers = @(
    "UNITY_IL2CPP_PLAYER_ACTIVE=PASS",
    "UNITY_IL2CPP_PLAYER_PLATFORM=WINDOWS_PLAYER_PASS",
    "UNITY_IL2CPP_PLAYER_CORE_PARSE=PASS",
    "UNITY_IL2CPP_PLAYER_CAPABILITY_INPUT_MOVE2D=PASS",
    "UNITY_IL2CPP_PLAYER_CAPABILITY_MOTION_TRANSFORM2D=PASS",
    "UNITY_IL2CPP_PLAYER_CAPABILITY_ANIMATION_PLAY=PASS",
    "UNITY_IL2CPP_PLAYER_CAPABILITY_DEBUG_LOG=PASS",
    "UNITY_IL2CPP_PLAYER_RUNTIME_STATE=PASS",
    "UNITY_IL2CPP_PLAYER_CAPABILITY_TIME_DELTA=PASS",
    "UNITY_IL2CPP_PLAYER_FLOAT_TO_RAT_EXACT=PASS",
    "UNITY_IL2CPP_PLAYER_RAT_TO_FLOAT_BOUNDARY_WITNESS=PASS",
    "UNITY_IL2CPP_PLAYER_TIME_DELTA_BOUNDARY_WITNESS=PASS",
    "UNITY_IL2CPP_PLAYER_RAT_TO_FLOAT_ROUNDING_EXPOSED=PASS",
    "UNITY_IL2CPP_PLAYER_NONFINITE_FLOAT_FAIL_CLOSED=PASS",
    "UNITY_IL2CPP_PLAYER_CAPABILITY_ABI=PASS",
    "UNITY_IL2CPP_PLAYER_FLOAT_BOUNDARY=EXPLICIT_AUDITED_PASS",
    "UNITY_IL2CPP_PLAYER_PROVIDER_AUTHORITY=EXPLICIT_PASS",
    "UNITY_INPUT_SYSTEM_DEVICE=NOT_PROBED",
    "UNITY_ANIMATOR_CONTROLLER=NOT_PROBED",
    "TEV_SCRIPT_UNITY_IL2CPP_PLAYER_GATE_4=PASS"
)
foreach ($marker in $requiredPlayerMarkers) {
    if (-not $playerText.Contains($marker)) {
        throw "UNITY_IL2CPP_PLAYER_WITNESS_MISSING=$marker"
    }
    Write-Host "UNITY_IL2CPP_PLAYER_WITNESS_PASS=$marker"
}

$evidenceDir = Join-Path $RepositoryRoot "receipts\unity-il2cpp-player-gate4"
New-Item -ItemType Directory -Path $evidenceDir -Force | Out-Null
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$buildEvidence = Join-Path $evidenceDir "UNITY_IL2CPP_BUILD_$stamp.log"
$playerEvidence = Join-Path $evidenceDir "UNITY_IL2CPP_PLAYER_$stamp.log"
Copy-Item -LiteralPath $buildLog -Destination $buildEvidence -Force
Copy-Item -LiteralPath $playerLog -Destination $playerEvidence -Force

$buildEvidenceSha = (Get-FileHash -LiteralPath $buildEvidence -Algorithm SHA256).Hash.ToLowerInvariant()
$playerEvidenceSha = (Get-FileHash -LiteralPath $playerEvidence -Algorithm SHA256).Hash.ToLowerInvariant()

if ($RequireClean) { Require-CleanGit -Root $RepositoryRoot }

Remove-Item -LiteralPath $projectRoot -Recurse -Force -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "TEV_SCRIPT_UNITY_IL2CPP_PLAYER_GATE_4=PASS"
Write-Host "BRANCH=$branch"
Write-Host "HEAD=$head"
Write-Host "TREE=$tree"
Write-Host "UNITY_EDITOR_VERSION=$editorVersion"
Write-Host "UNITY_IL2CPP_PLAYER_BUILD=PASS"
Write-Host "UNITY_IL2CPP_PLAYER_EXECUTION=PASS"
Write-Host "UNITY_IL2CPP_PLAYER_BACKEND=IL2CPP"
Write-Host "UNITY_IL2CPP_PLAYER_AOT=PASS"
Write-Host "UNITY_IL2CPP_GAMEASSEMBLY=PASS"
Write-Host "UNITY_IL2CPP_GLOBAL_METADATA=PASS"
Write-Host "UNITY_IL2CPP_MONO_RUNTIME=ABSENT_PASS"
Write-Host "UNITY_IL2CPP_PLAYER_CAPABILITY_ABI=PASS"
Write-Host "UNITY_IL2CPP_PLAYER_FLOAT_BOUNDARY=EXPLICIT_AUDITED_PASS"
Write-Host "UNITY_IL2CPP_PLAYER_PROVIDER_AUTHORITY=EXPLICIT_PASS"
Write-Host "UNITY_IL2CPP_PLAYER_CORE=UNCHANGED_FROM_CERTIFIED_GATE3"
Write-Host "UNITY_IL2CPP_PLAYER_HARNESS_ASSEMBLY=Marcbeacve.TevScript.Gate4.Il2CppPlayer"
Write-Host "UNITY_IL2CPP_PLAYER_EXE_SHA256=$exeSha"
Write-Host "UNITY_IL2CPP_GAMEASSEMBLY_SHA256=$gameAssemblySha"
Write-Host "UNITY_IL2CPP_GLOBAL_METADATA_SHA256=$metadataSha"
Write-Host "UNITY_IL2CPP_BUILD_EVIDENCE=$buildEvidence"
Write-Host "UNITY_IL2CPP_BUILD_EVIDENCE_SHA256=$buildEvidenceSha"
Write-Host "UNITY_IL2CPP_PLAYER_EVIDENCE=$playerEvidence"
Write-Host "UNITY_IL2CPP_PLAYER_EVIDENCE_SHA256=$playerEvidenceSha"
Write-Host "UNITY_INPUT_SYSTEM_DEVICE=NOT_PROBED"
Write-Host "UNITY_ANIMATOR_CONTROLLER=NOT_PROBED"
if ($RequireClean) { Write-Host "GIT_STATUS=CLEAN" } else { Write-Host "GIT_STATUS=CANDIDATE_CHANGES_ALLOWED" }
