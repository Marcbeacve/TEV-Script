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
    if ($LASTEXITCODE -ne 0) {
        throw "GIT_STATUS_QUERY_FAILED"
    }
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
    if (Test-Path -LiteralPath $preferred -PathType Leaf) {
        return $preferred
    }

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
    if ($candidates.Count -lt 1) {
        throw "UNITY_6000_3_NOT_FOUND"
    }
    return $candidates[0]
}

function Require-Markers {
    param(
        [string]$Text,
        [string[]]$Markers,
        [string]$Prefix
    )
    foreach ($marker in $Markers) {
        if (-not $Text.Contains($marker)) {
            throw "$Prefix=$marker"
        }
        Write-Host "GATE5B_WITNESS_PASS=$marker"
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
if ([string]::IsNullOrWhiteSpace($branch)) {
    throw "CURRENT_BRANCH_EMPTY"
}

python (Join-Path $RepositoryRoot "tools\validate_transactional_swap_gate5a.py")
if ($LASTEXITCODE -ne 0) {
    throw "GATE5B_GATE5A_STATIC_REGRESSION_FAILED"
}
python (Join-Path $RepositoryRoot "unity\VALIDATE_UNITY_IL2CPP_PLAYER_GATE4.py")
if ($LASTEXITCODE -ne 0) {
    throw "GATE5B_GATE4_STATIC_REGRESSION_FAILED"
}
python (Join-Path $RepositoryRoot "unity\VALIDATE_UNITY_IL2CPP_TRANSACTIONAL_SWAP_GATE5B.py")
if ($LASTEXITCODE -ne 0) {
    throw "GATE5B_STATIC_VALIDATION_FAILED"
}

$resolvedUnity = Resolve-UnityExe -Requested $UnityExe
$editorVersion = Split-Path -Leaf (
    Split-Path -Parent (
        Split-Path -Parent $resolvedUnity
    )
)
if ($editorVersion -notlike "6000.3*") {
    throw "UNITY_VERSION_OUTSIDE_GATE_BOUNDARY=$editorVersion"
}
Write-Host "UNITY_EXE=$resolvedUnity"
Write-Host "UNITY_EDITOR_VERSION=$editorVersion"

# ------------------------------------------------------------------
# Lower-layer regression 1: exact certified Gate-4 IL2CPP commit.
# ------------------------------------------------------------------
$gate4CertifiedHead = "39060bfc80bb0b7cc88515261d4f18d9c462a2b6"
$gate4CloneParent = Join-Path $env:LOCALAPPDATA `
    "TEV_SCRIPT_GATE5B_GATE4_REGRESSION"
New-Item -ItemType Directory -Path $gate4CloneParent -Force | Out-Null
$gate4Clone = Join-Path $gate4CloneParent ([Guid]::NewGuid().ToString("N"))

try {
    git clone --quiet --no-hardlinks --no-checkout $RepositoryRoot $gate4Clone
    if ($LASTEXITCODE -ne 0) {
        throw "GATE5B_GATE4_CLONE_FAILED"
    }

    $ephemeral = "gate5b-gate4-" + [Guid]::NewGuid().ToString("N")
    git -C $gate4Clone switch --quiet -c $ephemeral $gate4CertifiedHead
    if ($LASTEXITCODE -ne 0) {
        throw "GATE5B_GATE4_CHECKOUT_FAILED"
    }

    & pwsh -NoProfile -ExecutionPolicy Bypass `
        -File (Join-Path $gate4Clone "RUN_TEV_SCRIPT_UNITY_IL2CPP_PLAYER_CONFORMANCE_V1.ps1") `
        -RepositoryRoot $gate4Clone `
        -UnityExe $resolvedUnity `
        -RequireClean

    if ($LASTEXITCODE -ne 0) {
        throw "GATE5B_GATE4_REGRESSION_FAILED"
    }
}
finally {
    if (Test-Path -LiteralPath $gate4Clone) {
        Remove-Item -LiteralPath $gate4Clone -Recurse -Force -ErrorAction SilentlyContinue
    }
}
Write-Host "GATE5B_GATE4_REGRESSION=PASS"
Write-Host "GATE5B_GATE4_REGRESSION_HEAD=$gate4CertifiedHead"

# ------------------------------------------------------------------
# Lower-layer regression 2: exact certified Gate-5A commit.
# ------------------------------------------------------------------
$gate5aCertifiedHead = "50e920e4562358c28cb13ca7970599a15aa39408"
$gate5aCloneParent = Join-Path $env:LOCALAPPDATA `
    "TEV_SCRIPT_GATE5B_GATE5A_REGRESSION"
New-Item -ItemType Directory -Path $gate5aCloneParent -Force | Out-Null
$gate5aClone = Join-Path $gate5aCloneParent ([Guid]::NewGuid().ToString("N"))

try {
    git clone --quiet --no-hardlinks --no-checkout $RepositoryRoot $gate5aClone
    if ($LASTEXITCODE -ne 0) {
        throw "GATE5B_GATE5A_CLONE_FAILED"
    }

    $ephemeral = "gate5b-gate5a-" + [Guid]::NewGuid().ToString("N")
    git -C $gate5aClone switch --quiet -c $ephemeral $gate5aCertifiedHead
    if ($LASTEXITCODE -ne 0) {
        throw "GATE5B_GATE5A_CHECKOUT_FAILED"
    }

    Require-CleanGit -Root $gate5aClone

    & pwsh -NoProfile -ExecutionPolicy Bypass `
        -File (Join-Path $gate5aClone "RUN_TEV_SCRIPT_TRANSACTIONAL_SWAP_GATE5A_V1.ps1") `
        -RepositoryRoot $gate5aClone

    if ($LASTEXITCODE -ne 0) {
        throw "GATE5B_GATE5A_REGRESSION_FAILED"
    }

    Require-CleanGit -Root $gate5aClone
}
finally {
    if (Test-Path -LiteralPath $gate5aClone) {
        Remove-Item -LiteralPath $gate5aClone -Recurse -Force -ErrorAction SilentlyContinue
    }
}
Write-Host "GATE5B_GATE5A_REGRESSION=PASS"
Write-Host "GATE5B_GATE5A_REGRESSION_HEAD=$gate5aCertifiedHead"

# ------------------------------------------------------------------
# Generate Gate-5A fixtures, then upgrade GOOD to a behavior-changing
# Gate-5B candidate while preserving all Gate-5A compatibility contracts.
# ------------------------------------------------------------------
$gateRoot = Join-Path $env:LOCALAPPDATA `
    "TEV_SCRIPT_UNITY_IL2CPP_TRANSACTIONAL_SWAP_GATE5B"
New-Item -ItemType Directory -Path $gateRoot -Force | Out-Null
$projectRoot = Join-Path $gateRoot ([Guid]::NewGuid().ToString("N"))
$fixture5a = Join-Path $projectRoot "Gate5AFixtures"
$fixture5b = Join-Path $projectRoot "Gate5BFixtures"
$buildRoot = Join-Path $projectRoot "Build"
$playerExe = Join-Path $buildRoot "TEVScriptGate5B.exe"
$buildLog = Join-Path $projectRoot "unity-gate5b-build.log"
$playerLog = Join-Path $projectRoot "unity-gate5b-player.log"
$completed = $false

New-Item -ItemType Directory -Path $fixture5a -Force | Out-Null
New-Item -ItemType Directory -Path $fixture5b -Force | Out-Null
New-Item -ItemType Directory -Path $buildRoot -Force | Out-Null

$baseFixture = Join-Path $RepositoryRoot "examples\Player.tevs.ir.json"

$gen5aOutput = @(
    python (Join-Path $RepositoryRoot "tools\generate_transactional_swap_gate5a_fixtures.py") `
        --base $baseFixture `
        --out $fixture5a 2>&1
)
$gen5aExit = $LASTEXITCODE
$gen5aOutput | ForEach-Object { Write-Host $_ }
if ($gen5aExit -ne 0) {
    throw "GATE5B_GATE5A_FIXTURE_GENERATION_FAILED temp_project=$projectRoot"
}

$gen5bOutput = @(
    python (Join-Path $RepositoryRoot "tools\generate_transactional_swap_gate5b_fixtures.py") `
        --base $baseFixture `
        --gate5a-dir $fixture5a `
        --out $fixture5b 2>&1
)
$gen5bExit = $LASTEXITCODE
$gen5bOutput | ForEach-Object { Write-Host $_ }
if ($gen5bExit -ne 0) {
    throw "GATE5B_FIXTURE_GENERATION_FAILED temp_project=$projectRoot"
}

$gen5bText = $gen5bOutput -join "`n"
Require-Markers `
    -Text $gen5bText `
    -Prefix "GATE5B_FIXTURE_WITNESS_MISSING" `
    -Markers @(
        "GATE5B_BASE_HASH_RECONSTRUCTION=PASS"
        "GATE5B_GATE5A_GOOD_INPUT_VALID=PASS"
        "GATE5B_UPDATED_BEHAVIOR_IR=GENERATED"
        "GATE5B_STATE_REMOVAL_VALID_IR=GENERATED"
        "GATE5B_CAPABILITY_ESCALATION_VALID_IR=GENERATED"
        "GATE5B_PROGRAM_ID_NEGATIVE_VALID_IR=GENERATED"
    )

# ------------------------------------------------------------------
# Isolated Unity project.
# ------------------------------------------------------------------
New-Item -ItemType Directory -Path (
    Join-Path $projectRoot "Assets\Gate5B\Runtime"
) -Force | Out-Null
New-Item -ItemType Directory -Path (
    Join-Path $projectRoot "Assets\Gate5B\Editor"
) -Force | Out-Null
New-Item -ItemType Directory -Path (
    Join-Path $projectRoot "Assets\Resources"
) -Force | Out-Null
New-Item -ItemType Directory -Path (
    Join-Path $projectRoot "Packages"
) -Force | Out-Null
New-Item -ItemType Directory -Path (
    Join-Path $projectRoot "ProjectSettings"
) -Force | Out-Null

$packageRoot = Join-Path $RepositoryRoot "unity\Package"
$localPackagesRoot = Join-Path $projectRoot "LocalPackages"
$stagedPackageRoot = Join-Path $localPackagesRoot "com.marcbeacve.tev-script"
New-Item -ItemType Directory -Path $localPackagesRoot -Force | Out-Null
Copy-Item -LiteralPath $packageRoot -Destination $stagedPackageRoot -Recurse -Force

$gate5bRoot = Join-Path $RepositoryRoot `
    "unity\PlayerGates\IL2CPPTransactionalSwap"

Copy-Item `
    -LiteralPath (
        Join-Path $gate5bRoot `
            "Runtime\Marcbeacve.TevScript.Gate5B.Il2CppTransactionalSwap.asmdef"
    ) `
    -Destination (
        Join-Path $projectRoot `
            "Assets\Gate5B\Runtime\Marcbeacve.TevScript.Gate5B.Il2CppTransactionalSwap.asmdef"
    ) `
    -Force

Copy-Item `
    -LiteralPath (
        Join-Path $gate5bRoot `
            "Runtime\TevScriptIl2CppTransactionalSwapGate.cs"
    ) `
    -Destination (
        Join-Path $projectRoot `
            "Assets\Gate5B\Runtime\TevScriptIl2CppTransactionalSwapGate.cs"
    ) `
    -Force

Copy-Item `
    -LiteralPath (
        Join-Path $gate5bRoot `
            "Editor\Marcbeacve.TevScript.Gate5B.Il2CppTransactionalSwap.Editor.asmdef"
    ) `
    -Destination (
        Join-Path $projectRoot `
            "Assets\Gate5B\Editor\Marcbeacve.TevScript.Gate5B.Il2CppTransactionalSwap.Editor.asmdef"
    ) `
    -Force

Copy-Item `
    -LiteralPath (
        Join-Path $gate5bRoot `
            "Editor\TevScriptIl2CppTransactionalSwapBuildGate.cs"
    ) `
    -Destination (
        Join-Path $projectRoot `
            "Assets\Gate5B\Editor\TevScriptIl2CppTransactionalSwapBuildGate.cs"
    ) `
    -Force

$resources = @{
    "base.json" = "TevScriptGate5BBase.json"
    "candidate.good.json" = "TevScriptGate5BGood.json"
    "candidate.state_removed.json" = "TevScriptGate5BRemoved.json"
    "candidate.capability_escalated.json" = "TevScriptGate5BEscalated.json"
    "candidate.program_id_changed.json" = "TevScriptGate5BWrongProgram.json"
}

foreach ($name in $resources.Keys) {
    $source = Join-Path $fixture5b $name
    $destination = Join-Path (
        Join-Path $projectRoot "Assets\Resources"
    ) $resources[$name]

    Copy-Item -LiteralPath $source -Destination $destination -Force

    $a = (
        Get-FileHash -LiteralPath $source -Algorithm SHA256
    ).Hash.ToLowerInvariant()
    $b = (
        Get-FileHash -LiteralPath $destination -Algorithm SHA256
    ).Hash.ToLowerInvariant()

    if ($a -ne $b) {
        throw "GATE5B_RESOURCE_IDENTITY_FAILED=$name temp_project=$projectRoot"
    }
    Write-Host "GATE5B_RESOURCE_IDENTITY=PASS name=$name sha256=$b"
}

$packageUriPath = (
    Resolve-Path -LiteralPath $stagedPackageRoot
).Path.Replace("\", "/")

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

$oldBuildExe = $env:TEV_SCRIPT_GATE5B_BUILD_EXE
$env:TEV_SCRIPT_GATE5B_BUILD_EXE = $playerExe
try {
    $unityArgs = @(
        "-batchmode"
        "-nographics"
        "-quit"
        "-projectPath"
        ('"' + $projectRoot + '"')
        "-executeMethod"
        "Marcbeacve.TevScript.Gate5B.Il2CppTransactionalSwap.Editor.TevScriptIl2CppTransactionalSwapBuildGate.Build"
        "-logFile"
        ('"' + $buildLog + '"')
    )

    $buildProcess = Start-Process `
        -FilePath $resolvedUnity `
        -ArgumentList $unityArgs `
        -Wait `
        -PassThru
    $buildExit = $buildProcess.ExitCode
}
finally {
    $env:TEV_SCRIPT_GATE5B_BUILD_EXE = $oldBuildExe
}

Write-Host "GATE5B_BUILD_PROCESS_WAIT=PASS"
Write-Host "GATE5B_BUILD_PROCESS_EXIT_CODE=$buildExit"

if (-not (Test-Path -LiteralPath $buildLog -PathType Leaf)) {
    throw "GATE5B_BUILD_LOG_MISSING exit=$buildExit temp_project=$projectRoot"
}
if ($buildExit -ne 0) {
    Get-Content -LiteralPath $buildLog -Tail 300 |
        ForEach-Object { Write-Host $_ }
    throw "GATE5B_BUILD_FAILED exit=$buildExit temp_project=$projectRoot"
}

$buildText = Get-Content -LiteralPath $buildLog -Raw
Require-Markers `
    -Text $buildText `
    -Prefix "GATE5B_BUILD_WITNESS_MISSING" `
    -Markers @(
        "UNITY_GATE5B_IL2CPP_BUILD_BACKEND=IL2CPP"
        "UNITY_GATE5B_IL2CPP_BUILD_TARGET=STANDALONE_WINDOWS64"
        "UNITY_GATE5B_IL2CPP_BUILD_RESULT=PASS"
    )

if (-not (Test-Path -LiteralPath $playerExe -PathType Leaf)) {
    throw "GATE5B_PLAYER_EXE_MISSING"
}

$gameAssembly = Join-Path $buildRoot "GameAssembly.dll"
if (-not (Test-Path -LiteralPath $gameAssembly -PathType Leaf)) {
    throw "GATE5B_GAMEASSEMBLY_MISSING"
}
Write-Host "GATE5B_GAMEASSEMBLY=PASS"

$metadataCandidates = @(
    Get-ChildItem `
        -LiteralPath $buildRoot `
        -Recurse `
        -File `
        -Filter "global-metadata.dat" `
        -ErrorAction SilentlyContinue |
    Where-Object {
        $_.FullName -match "[\\/]il2cpp_data[\\/]Metadata[\\/]global-metadata\.dat$"
    }
)
if ($metadataCandidates.Count -ne 1) {
    throw "GATE5B_GLOBAL_METADATA_INVALID count=$($metadataCandidates.Count)"
}
Write-Host "GATE5B_GLOBAL_METADATA=PASS"

$monoDirs = @(
    Get-ChildItem `
        -LiteralPath $buildRoot `
        -Recurse `
        -Directory `
        -Filter "MonoBleedingEdge" `
        -ErrorAction SilentlyContinue
)
if ($monoDirs.Count -ne 0) {
    $monoDirs | ForEach-Object {
        Write-Host "UNEXPECTED_MONO_RUNTIME=$($_.FullName)"
    }
    throw "GATE5B_MONO_RUNTIME_PRESENT"
}
Write-Host "GATE5B_MONO_RUNTIME=ABSENT_PASS"

$exeSha = (
    Get-FileHash -LiteralPath $playerExe -Algorithm SHA256
).Hash.ToLowerInvariant()
$gameAssemblySha = (
    Get-FileHash -LiteralPath $gameAssembly -Algorithm SHA256
).Hash.ToLowerInvariant()
$metadataSha = (
    Get-FileHash -LiteralPath $metadataCandidates[0].FullName -Algorithm SHA256
).Hash.ToLowerInvariant()

Write-Host "GATE5B_PLAYER_EXE_SHA256=$exeSha"
Write-Host "GATE5B_GAMEASSEMBLY_SHA256=$gameAssemblySha"
Write-Host "GATE5B_GLOBAL_METADATA_SHA256=$metadataSha"

$playerArgs = @(
    "-batchmode"
    "-nographics"
    "-logFile"
    ('"' + $playerLog + '"')
)
$playerProcess = Start-Process `
    -FilePath $playerExe `
    -ArgumentList $playerArgs `
    -Wait `
    -PassThru
$playerExit = $playerProcess.ExitCode

Write-Host "GATE5B_PLAYER_PROCESS_WAIT=PASS"
Write-Host "GATE5B_PLAYER_PROCESS_EXIT_CODE=$playerExit"

if (-not (Test-Path -LiteralPath $playerLog -PathType Leaf)) {
    throw "GATE5B_PLAYER_LOG_MISSING exit=$playerExit temp_project=$projectRoot"
}
if ((Get-Item -LiteralPath $playerLog).Length -le 0) {
    throw "GATE5B_PLAYER_LOG_EMPTY exit=$playerExit temp_project=$projectRoot"
}
if ($playerExit -ne 0) {
    Get-Content -LiteralPath $playerLog -Tail 300 |
        ForEach-Object { Write-Host $_ }
    throw "GATE5B_PLAYER_EXECUTION_FAILED exit=$playerExit temp_project=$projectRoot"
}

$playerText = Get-Content -LiteralPath $playerLog -Raw
$requiredPlayerMarkers = @(
    "UNITY_GATE5B_IL2CPP_ACTIVE=PASS"
    "UNITY_GATE5B_IL2CPP_PLATFORM=WINDOWS_PLAYER_PASS"
    "UNITY_GATE5B_BASE_PARSE=PASS"
    "UNITY_GATE5B_BASE_BEHAVIOR=PASS"
    "UNITY_GATE5B_PREPARE_NON_AUTHORITATIVE=PASS"
    "UNITY_GATE5B_COMMIT_ATOMIC_REFERENCE_SWAP=PASS"
    "UNITY_GATE5B_EXISTING_STATE_MIGRATION=PASS"
    "UNITY_GATE5B_ADDITIVE_STATE_INITIALIZATION=PASS"
    "UNITY_GATE5B_UPDATED_BEHAVIOR_ACTIVE=PASS"
    "UNITY_GATE5B_PLAN_REUSE_FAIL_CLOSED=PASS"
    "UNITY_GATE5B_STATE_REMOVAL_VALID_IR_REACHES_HOST=PASS"
    "UNITY_GATE5B_STATE_REMOVAL_FAIL_CLOSED=PASS"
    "UNITY_GATE5B_CAPABILITY_CEILING_FAIL_CLOSED=PASS"
    "UNITY_GATE5B_PROGRAM_ID_CONTINUITY_FAIL_CLOSED=PASS"
    "UNITY_GATE5B_ROLLBACK_EXACT_RUNTIME_RESTORE=PASS"
    "UNITY_GATE5B_ROLLBACK_BEHAVIOR_RESTORED=PASS"
    "UNITY_GATE5B_STALE_PLAN_FAIL_CLOSED=PASS"
    "UNITY_GATE5B_TRANSACTION_BOUNDARY=PASS"
    "UNITY_GATE5B_DYNAMIC_CODE=ABSENT_PASS"
    "UNITY_GATE5B_NETWORK=NOT_IN_SCOPE"
    "UNITY_GATE5B_SIGNATURE_AUTHORITY=NOT_IN_SCOPE"
    "UNITY_GATE5B_WASM=NOT_IN_SCOPE"
    "TEV_SCRIPT_UNITY_IL2CPP_TRANSACTIONAL_SWAP_GATE_5B=PASS"
)
Require-Markers `
    -Text $playerText `
    -Prefix "GATE5B_PLAYER_WITNESS_MISSING" `
    -Markers $requiredPlayerMarkers

$buildLogSha = (
    Get-FileHash -LiteralPath $buildLog -Algorithm SHA256
).Hash.ToLowerInvariant()
$playerLogSha = (
    Get-FileHash -LiteralPath $playerLog -Algorithm SHA256
).Hash.ToLowerInvariant()

$evidenceDir = Join-Path $RepositoryRoot `
    "receipts\unity-il2cpp-transactional-swap-gate5b"
New-Item -ItemType Directory -Path $evidenceDir -Force | Out-Null
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"

$buildEvidence = Join-Path $evidenceDir "GATE5B_BUILD_$stamp.log"
$playerEvidence = Join-Path $evidenceDir "GATE5B_PLAYER_$stamp.log"
Copy-Item -LiteralPath $buildLog -Destination $buildEvidence -Force
Copy-Item -LiteralPath $playerLog -Destination $playerEvidence -Force

$buildEvidenceSha = (
    Get-FileHash -LiteralPath $buildEvidence -Algorithm SHA256
).Hash.ToLowerInvariant()
$playerEvidenceSha = (
    Get-FileHash -LiteralPath $playerEvidence -Algorithm SHA256
).Hash.ToLowerInvariant()

if ($buildEvidenceSha -ne $buildLogSha) {
    throw "GATE5B_BUILD_EVIDENCE_COPY_HASH_MISMATCH"
}
if ($playerEvidenceSha -ne $playerLogSha) {
    throw "GATE5B_PLAYER_EVIDENCE_COPY_HASH_MISMATCH"
}

$completed = $true

if ($completed -and (Test-Path -LiteralPath $projectRoot)) {
    Remove-Item -LiteralPath $projectRoot -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host ""
Write-Host "TEV_SCRIPT_UNITY_IL2CPP_TRANSACTIONAL_SWAP_GATE_5B=PASS"
Write-Host "BRANCH=$branch"
Write-Host "HEAD=$head"
Write-Host "TREE=$tree"
Write-Host "UNITY_EDITOR_VERSION=$editorVersion"
Write-Host "GATE5B_GATE4_REGRESSION=PASS"
Write-Host "GATE5B_GATE5A_REGRESSION=PASS"
Write-Host "GATE5B_IL2CPP_BUILD=PASS"
Write-Host "GATE5B_IL2CPP_EXECUTION=PASS"
Write-Host "GATE5B_BACKEND=IL2CPP"
Write-Host "GATE5B_AOT=PASS"
Write-Host "GATE5B_GAMEASSEMBLY=PASS"
Write-Host "GATE5B_GLOBAL_METADATA=PASS"
Write-Host "GATE5B_MONO_RUNTIME=ABSENT_PASS"
Write-Host "GATE5B_TRANSACTIONAL_SWAP=PASS_INSIDE_IL2CPP"
Write-Host "GATE5B_STATE_MIGRATION=EXACT_EXISTING_TYPES_PASS"
Write-Host "GATE5B_UPDATED_BEHAVIOR=PASS"
Write-Host "GATE5B_ADDITIVE_STATE=PASS"
Write-Host "GATE5B_CAPABILITY_CEILING=EXPLICIT_PASS"
Write-Host "GATE5B_ROLLBACK=EXACT_PREVIOUS_RUNTIME_PASS"
Write-Host "GATE5B_ROLLBACK_BEHAVIOR=RESTORED_PASS"
Write-Host "GATE5B_STALE_PLAN=FAIL_CLOSED_PASS"
Write-Host "GATE5B_DYNAMIC_CODE=ABSENT_PASS"
Write-Host "GATE5B_NETWORK=NOT_IN_SCOPE"
Write-Host "GATE5B_SIGNATURE_AUTHORITY=NOT_IN_SCOPE"
Write-Host "GATE5B_WASM=NOT_IN_SCOPE"
Write-Host "GATE5B_PLAYER_EXE_SHA256=$exeSha"
Write-Host "GATE5B_GAMEASSEMBLY_SHA256=$gameAssemblySha"
Write-Host "GATE5B_GLOBAL_METADATA_SHA256=$metadataSha"
Write-Host "GATE5B_BUILD_EVIDENCE=$buildEvidence"
Write-Host "GATE5B_BUILD_EVIDENCE_SHA256=$buildEvidenceSha"
Write-Host "GATE5B_PLAYER_EVIDENCE=$playerEvidence"
Write-Host "GATE5B_PLAYER_EVIDENCE_SHA256=$playerEvidenceSha"
Write-Host "GIT_STATUS=CANDIDATE_CHANGES_ALLOWED"
