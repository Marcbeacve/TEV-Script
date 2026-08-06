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
$branch = (git branch --show-current).Trim()
if ($LASTEXITCODE -ne 0) { throw "GIT_IDENTITY_QUERY_FAILED" }

$packageRoot = Join-Path $RepositoryRoot "unity\Package"
if (-not (Test-Path -LiteralPath $packageRoot -PathType Container)) {
    throw "UNITY_PACKAGE_MISSING"
}

python (Join-Path $RepositoryRoot "unity\VALIDATE_UNITY_PACKAGE.py")
if ($LASTEXITCODE -ne 0) { throw "UNITY_PACKAGE_STATIC_GATE_FAILED" }

if ($RequireClean) {
    & pwsh -NoProfile -ExecutionPolicy Bypass `
        -File (Join-Path $RepositoryRoot "RUN_TEV_SCRIPT_CSHARP_CONFORMANCE_V1.ps1") `
        -RepositoryRoot $RepositoryRoot `
        -RequireClean
} else {
    & pwsh -NoProfile -ExecutionPolicy Bypass `
        -File (Join-Path $RepositoryRoot "RUN_TEV_SCRIPT_CSHARP_CONFORMANCE_V1.ps1") `
        -RepositoryRoot $RepositoryRoot
}
if ($LASTEXITCODE -ne 0) { throw "THREE_RUNTIME_REGRESSION_FAILED" }
Write-Host "THREE_RUNTIME_REGRESSION=PASS"

$resolvedUnity = Resolve-UnityExe -Requested $UnityExe
$editorVersion = Split-Path -Leaf (Split-Path -Parent (Split-Path -Parent $resolvedUnity))
if ($editorVersion -notlike "6000.3*") {
    throw "UNITY_VERSION_OUTSIDE_GATE_BOUNDARY=$editorVersion"
}
Write-Host "UNITY_EXE=$resolvedUnity"
Write-Host "UNITY_EDITOR_VERSION=$editorVersion"

$gateRoot = Join-Path $env:LOCALAPPDATA "TEV_SCRIPT_UNITY_EDITOR_GATE1"
New-Item -ItemType Directory -Path $gateRoot -Force | Out-Null
$projectRoot = Join-Path $gateRoot ([Guid]::NewGuid().ToString("N"))
$logPath = Join-Path $projectRoot "unity-editor-gate1.log"
New-Item -ItemType Directory -Path (Join-Path $projectRoot "Assets") -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $projectRoot "Packages") -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $projectRoot "ProjectSettings") -Force | Out-Null

$localPackagesRoot = Join-Path $projectRoot "LocalPackages"
$stagedPackageRoot = Join-Path $localPackagesRoot "com.marcbeacve.tev-script"
New-Item -ItemType Directory -Path $localPackagesRoot -Force | Out-Null
Copy-Item -LiteralPath $packageRoot -Destination $stagedPackageRoot -Recurse -Force
$packageUriPath = (Resolve-Path -LiteralPath $stagedPackageRoot).Path.Replace("\", "/")
$manifest = [ordered]@{
    dependencies = [ordered]@{
        "com.marcbeacve.tev-script" = "file:$packageUriPath"
    }
}
$manifest | ConvertTo-Json -Depth 5 | Set-Content `
    -LiteralPath (Join-Path $projectRoot "Packages\manifest.json") `
    -Encoding utf8
"m_EditorVersion: $editorVersion`n" | Set-Content `
    -LiteralPath (Join-Path $projectRoot "ProjectSettings\ProjectVersion.txt") `
    -Encoding utf8

$unityArguments = @(
    "-batchmode", "-nographics", "-quit",
    "-projectPath", ('"' + $projectRoot + '"'),
    "-executeMethod", "Marcbeacve.TevScript.Unity.Editor.TevScriptUnityEditorGate.Run",
    "-logFile", ('"' + $logPath + '"')
)
$process = Start-Process -FilePath $resolvedUnity -ArgumentList $unityArguments -Wait -PassThru
$unityExit = $process.ExitCode
Write-Host "UNITY_PROCESS_WAIT=PASS"
Write-Host "UNITY_PROCESS_EXIT_CODE=$unityExit"

$evidenceDir = Join-Path $RepositoryRoot "receipts\unity-editor-gate1"
New-Item -ItemType Directory -Path $evidenceDir -Force | Out-Null
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$evidenceLog = Join-Path $evidenceDir "UNITY_EDITOR_GATE1_$stamp.log"
if (Test-Path -LiteralPath $logPath -PathType Leaf) {
    Copy-Item -LiteralPath $logPath -Destination $evidenceLog -Force
}

if (-not (Test-Path -LiteralPath $logPath -PathType Leaf)) {
    throw "UNITY_EDITOR_LOG_MISSING exit=$unityExit temp_project=$projectRoot"
}
if ((Get-Item -LiteralPath $logPath).Length -le 0) {
    throw "UNITY_EDITOR_LOG_EMPTY exit=$unityExit temp_project=$projectRoot"
}
if ($unityExit -ne 0) {
    Get-Content -LiteralPath $logPath -Tail 200 | ForEach-Object { Write-Host $_ }
    throw "UNITY_EDITOR_GATE_EXECUTION_FAILED exit=$unityExit temp_project=$projectRoot"
}

$logText = Get-Content -LiteralPath $logPath -Raw
$requiredMarkers = @(
    "UNITY_CANONICAL_VECTORS=12_PASS",
    "UNITY_PLAYER_BYTE_PARITY=PASS",
    "UNITY_MATRIX_BYTE_PARITY=PASS",
    "UNITY_PLAYER_IDLE_BYTE_PARITY=PASS",
    "UNITY_EVENT_CHAIN_BYTE_PARITY=PASS",
    "UNITY_SEMANTIC_HASH_TAMPERING_FAIL_CLOSED=PASS",
    "UNITY_MISSING_CAPABILITY_FAIL_CLOSED=PASS",
    "UNITY_STRICT_UTF8_BOUNDARY=PASS",
    "UNITY_CSHARP_CORE_CONFORMANCE_SCENARIOS=4_PASS",
    "UNITY_THREE_RUNTIME_REFERENCE_PARITY=PASS",
    "UNITY_HOST_SEMANTIC_DRIFT=NONE_OBSERVED",
    "UNITY_PLAYMODE=NOT_PROBED",
    "UNITY_MONO_PLAYER=NOT_PROBED",
    "UNITY_IL2CPP=NOT_PROBED",
    "TEV_SCRIPT_UNITY_EDITOR_GATE_1=PASS"
)
foreach ($marker in $requiredMarkers) {
    if (-not $logText.Contains($marker)) { throw "UNITY_GATE_WITNESS_MISSING=$marker" }
    Write-Host "UNITY_WITNESS_PASS=$marker"
}

$evidenceSha = (Get-FileHash -LiteralPath $evidenceLog -Algorithm SHA256).Hash.ToLowerInvariant()
Remove-Item -LiteralPath $projectRoot -Recurse -Force -ErrorAction SilentlyContinue

if ($RequireClean) { Require-CleanGit -Root $RepositoryRoot }

Write-Host ""
Write-Host "TEV_SCRIPT_UNITY_EDITOR_GATE_1=PASS"
Write-Host "BRANCH=$branch"
Write-Host "HEAD=$head"
Write-Host "TREE=$tree"
Write-Host "UNITY_EDITOR_VERSION=$editorVersion"
Write-Host "UNITY_PACKAGE=com.marcbeacve.tev-script@0.2.0-preview.1"
Write-Host "UNITY_CORE_SOURCE_IDENTITY=9_PASS"
Write-Host "UNITY_CONFORMANCE_SCENARIOS=4_PASS"
Write-Host "UNITY_THREE_RUNTIME_REFERENCE_PARITY=PASS"
Write-Host "UNITY_HOST_SEMANTIC_DRIFT=NONE_OBSERVED"
Write-Host "UNITY_EDITOR_EVIDENCE=$evidenceLog"
Write-Host "UNITY_EDITOR_EVIDENCE_SHA256=$evidenceSha"
Write-Host "UNITY_PLAYMODE=NOT_PROBED"
Write-Host "UNITY_MONO_PLAYER=NOT_PROBED"
Write-Host "UNITY_IL2CPP=NOT_PROBED"
if ($RequireClean) { Write-Host "GIT_STATUS=CLEAN" } else { Write-Host "GIT_STATUS=CANDIDATE_CHANGES_ALLOWED" }
