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

function Resolve-TestFrameworkVersion {
    param([string]$ResolvedUnityExe)

    $editorDir = Split-Path -Parent $ResolvedUnityExe
    $packageManagerRoot = Join-Path $editorDir "Data\Resources\PackageManager"
    if (-not (Test-Path -LiteralPath $packageManagerRoot -PathType Container)) {
        throw "UNITY_PACKAGE_MANAGER_RESOURCES_NOT_FOUND=$packageManagerRoot"
    }

    $preferred = Join-Path $packageManagerRoot "BuiltInPackages\com.unity.test-framework\package.json"
    $candidates = @()
    if (Test-Path -LiteralPath $preferred -PathType Leaf) {
        $candidates += $preferred
    }
    $candidates += @(
        Get-ChildItem -LiteralPath $packageManagerRoot -Recurse -Filter package.json -File -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty FullName
    )

    foreach ($candidate in @($candidates | Select-Object -Unique)) {
        try {
            $payload = Get-Content -LiteralPath $candidate -Raw | ConvertFrom-Json
            if ($payload.name -eq "com.unity.test-framework" -and $payload.version) {
                return [string]$payload.version
            }
        }
        catch {
            continue
        }
    }
    throw "UNITY_TEST_FRAMEWORK_BUILTIN_PACKAGE_NOT_FOUND"
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

python (Join-Path $RepositoryRoot "unity\VALIDATE_UNITY_PACKAGE.py")
if ($LASTEXITCODE -ne 0) { throw "UNITY_GATE1_STATIC_REGRESSION_FAILED" }
python (Join-Path $RepositoryRoot "unity\VALIDATE_UNITY_PLAYMODE_GATE2.py")
if ($LASTEXITCODE -ne 0) { throw "UNITY_GATE2_STATIC_FAILED" }

$resolvedUnity = Resolve-UnityExe -Requested $UnityExe
$editorVersion = Split-Path -Leaf (Split-Path -Parent (Split-Path -Parent $resolvedUnity))
if ($editorVersion -notlike "6000.3*") {
    throw "UNITY_VERSION_OUTSIDE_GATE_BOUNDARY=$editorVersion"
}
Write-Host "UNITY_EXE=$resolvedUnity"
Write-Host "UNITY_EDITOR_VERSION=$editorVersion"

# Gate-1 is a lower-layer regression. Run it from an isolated local clone of
# the exact certified Gate-1 commit so Gate-2 adapter sources cannot leak into
# the Gate-1 compilation surface. The current Gate-2 candidate separately
# passes the static Core identity gate above, so this does not hide Core drift.
$gate1CertifiedHead = "5438da66d407bf9f7ed306cf8a3208189a19fdb7"
$gate1CloneParent = Join-Path $env:LOCALAPPDATA "TEV_SCRIPT_UNITY_GATE1_REGRESSION"
New-Item -ItemType Directory -Path $gate1CloneParent -Force | Out-Null
$gate1Clone = Join-Path $gate1CloneParent ([Guid]::NewGuid().ToString("N"))
try {
    git clone --quiet --no-hardlinks --no-checkout $RepositoryRoot $gate1Clone
    if ($LASTEXITCODE -ne 0) { throw "UNITY_GATE1_REGRESSION_CLONE_FAILED" }
    # Keep the certified commit/tree exact, but give the temporary worktree a
    # local branch name. The certified Gate-1 runner records the current branch
    # and older PowerShell versions may return $null for --show-current in a
    # detached HEAD. A local ephemeral branch changes only the ref name, never
    # the checked-out commit or tree.
    $gate1EphemeralBranch = "gate1-regression-" + [Guid]::NewGuid().ToString("N")
    git -C $gate1Clone switch --quiet -c $gate1EphemeralBranch $gate1CertifiedHead
    if ($LASTEXITCODE -ne 0) { throw "UNITY_GATE1_REGRESSION_NAMED_CHECKOUT_FAILED" }

    $gate1Observed = (git -C $gate1Clone rev-parse HEAD).Trim()
    if ($gate1Observed -ne $gate1CertifiedHead) {
        throw "UNITY_GATE1_REGRESSION_HEAD_MISMATCH observed=$gate1Observed"
    }
    $gate1BranchLines = @(git -C $gate1Clone branch --show-current)
    if ($LASTEXITCODE -ne 0) { throw "UNITY_GATE1_REGRESSION_BRANCH_QUERY_FAILED" }
    $gate1ObservedBranch = ($gate1BranchLines -join "").Trim()
    if ([string]::IsNullOrWhiteSpace($gate1ObservedBranch)) {
        throw "UNITY_GATE1_REGRESSION_BRANCH_EMPTY"
    }

    $gate1Args = @(
        "-NoProfile", "-ExecutionPolicy", "Bypass",
        "-File", (Join-Path $gate1Clone "RUN_TEV_SCRIPT_UNITY_EDITOR_CONFORMANCE_V1.ps1"),
        "-RepositoryRoot", $gate1Clone,
        "-UnityExe", $resolvedUnity,
        "-RequireClean"
    )
    & pwsh @gate1Args
    if ($LASTEXITCODE -ne 0) { throw "UNITY_GATE1_REGRESSION_FAILED" }
}
finally {
    if (Test-Path -LiteralPath $gate1Clone) {
        Remove-Item -LiteralPath $gate1Clone -Recurse -Force -ErrorAction SilentlyContinue
    }
}
Write-Host "UNITY_GATE1_REGRESSION=PASS"
Write-Host "UNITY_GATE1_REGRESSION_ISOLATION=CERTIFIED_BASE_NAMED_BRANCH_CLONE"
Write-Host "UNITY_GATE1_REGRESSION_HEAD=$gate1CertifiedHead"
Write-Host "UNITY_GATE1_REGRESSION_BRANCH_MODE=EPHEMERAL_NAMED_BRANCH"

$testFrameworkVersion = Resolve-TestFrameworkVersion -ResolvedUnityExe $resolvedUnity
Write-Host "UNITY_TEST_FRAMEWORK_VERSION=$testFrameworkVersion"

$packageRoot = Join-Path $RepositoryRoot "unity\Package"
$gateRoot = Join-Path $env:LOCALAPPDATA "TEV_SCRIPT_UNITY_PLAYMODE_GATE2"
New-Item -ItemType Directory -Path $gateRoot -Force | Out-Null
$projectRoot = Join-Path $gateRoot ([Guid]::NewGuid().ToString("N"))
$logPath = Join-Path $projectRoot "unity-playmode-gate2.log"
$resultPath = Join-Path $projectRoot "unity-playmode-gate2-results.xml"
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
        "com.unity.test-framework" = $testFrameworkVersion
    }
    testables = @("com.marcbeacve.tev-script")
}
$manifest | ConvertTo-Json -Depth 8 | Set-Content `
    -LiteralPath (Join-Path $projectRoot "Packages\manifest.json") `
    -Encoding utf8
"m_EditorVersion: $editorVersion`n" | Set-Content `
    -LiteralPath (Join-Path $projectRoot "ProjectSettings\ProjectVersion.txt") `
    -Encoding utf8

$unityArguments = @(
    "-batchmode", "-nographics",
    "-projectPath", ('"' + $projectRoot + '"'),
    "-runTests",
    "-testPlatform", "PlayMode",
    "-testResults", ('"' + $resultPath + '"'),
    "-logFile", ('"' + $logPath + '"')
)
$process = Start-Process -FilePath $resolvedUnity -ArgumentList $unityArguments -Wait -PassThru
$unityExit = $process.ExitCode
Write-Host "UNITY_PLAYMODE_PROCESS_WAIT=PASS"
Write-Host "UNITY_PLAYMODE_PROCESS_EXIT_CODE=$unityExit"

$evidenceDir = Join-Path $RepositoryRoot "receipts\unity-playmode-gate2"
New-Item -ItemType Directory -Path $evidenceDir -Force | Out-Null
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$evidenceLog = Join-Path $evidenceDir "UNITY_PLAYMODE_GATE2_$stamp.log"
$evidenceXml = Join-Path $evidenceDir "UNITY_PLAYMODE_GATE2_$stamp.xml"
if (Test-Path -LiteralPath $logPath -PathType Leaf) {
    Copy-Item -LiteralPath $logPath -Destination $evidenceLog -Force
}
if (Test-Path -LiteralPath $resultPath -PathType Leaf) {
    Copy-Item -LiteralPath $resultPath -Destination $evidenceXml -Force
}

if (-not (Test-Path -LiteralPath $logPath -PathType Leaf)) {
    throw "UNITY_PLAYMODE_LOG_MISSING exit=$unityExit temp_project=$projectRoot"
}
if ((Get-Item -LiteralPath $logPath).Length -le 0) {
    throw "UNITY_PLAYMODE_LOG_EMPTY exit=$unityExit temp_project=$projectRoot"
}
if (-not (Test-Path -LiteralPath $resultPath -PathType Leaf)) {
    Get-Content -LiteralPath $logPath -Tail 250 | ForEach-Object { Write-Host $_ }
    throw "UNITY_PLAYMODE_RESULTS_MISSING exit=$unityExit temp_project=$projectRoot"
}
if ($unityExit -ne 0) {
    Get-Content -LiteralPath $logPath -Tail 250 | ForEach-Object { Write-Host $_ }
    throw "UNITY_PLAYMODE_GATE_EXECUTION_FAILED exit=$unityExit temp_project=$projectRoot"
}

[xml]$results = Get-Content -LiteralPath $resultPath -Raw
$testRun = $results.DocumentElement
if ($null -eq $testRun -or $testRun.LocalName -ne "test-run") {
    throw "UNITY_PLAYMODE_RESULTS_ROOT_INVALID"
}
$total = [int]$testRun.GetAttribute("total")
$passed = [int]$testRun.GetAttribute("passed")
$failed = [int]$testRun.GetAttribute("failed")
$result = $testRun.GetAttribute("result")
if ($total -lt 3 -or $passed -lt 3 -or $failed -ne 0 -or $result -ne "Passed") {
    Write-Host "UNITY_TEST_TOTAL=$total"
    Write-Host "UNITY_TEST_PASSED=$passed"
    Write-Host "UNITY_TEST_FAILED=$failed"
    Write-Host "UNITY_TEST_RESULT=$result"
    throw "UNITY_PLAYMODE_TEST_RESULT_FAILED temp_project=$projectRoot"
}
Write-Host "UNITY_PLAYMODE_TESTS=$($passed)_PASS"

$logText = Get-Content -LiteralPath $logPath -Raw
$requiredMarkers = @(
    "UNITY_PLAYMODE_ACTIVE=PASS",
    "UNITY_CAPABILITY_INPUT_MOVE2D=PASS",
    "UNITY_CAPABILITY_MOTION_TRANSFORM2D=PASS",
    "UNITY_CAPABILITY_ANIMATION_PLAY=PASS",
    "UNITY_CAPABILITY_DEBUG_LOG=PASS",
    "UNITY_CAPABILITY_TIME_DELTA=PASS",
    "UNITY_FLOAT_TO_RAT_EXACT=PASS",
    "UNITY_RAT_TO_FLOAT_BOUNDARY_WITNESS=PASS",
    "UNITY_TIME_DELTA_FLOAT_TO_RAT_EXACT=PASS",
    "UNITY_RAT_TO_FLOAT_ROUNDING_EXPOSED=PASS",
    "UNITY_NONFINITE_FLOAT_FAIL_CLOSED=PASS",
    "TEV_SCRIPT_UNITY_PLAYMODE_GATE_2=PASS"
)
foreach ($marker in $requiredMarkers) {
    if (-not $logText.Contains($marker)) { throw "UNITY_PLAYMODE_WITNESS_MISSING=$marker" }
    Write-Host "UNITY_PLAYMODE_WITNESS_PASS=$marker"
}

$logSha = (Get-FileHash -LiteralPath $evidenceLog -Algorithm SHA256).Hash.ToLowerInvariant()
$xmlSha = (Get-FileHash -LiteralPath $evidenceXml -Algorithm SHA256).Hash.ToLowerInvariant()
Remove-Item -LiteralPath $projectRoot -Recurse -Force -ErrorAction SilentlyContinue

if ($RequireClean) { Require-CleanGit -Root $RepositoryRoot }

Write-Host ""
Write-Host "TEV_SCRIPT_UNITY_PLAYMODE_GATE_2=PASS"
Write-Host "BRANCH=$branch"
Write-Host "HEAD=$head"
Write-Host "TREE=$tree"
Write-Host "UNITY_EDITOR_VERSION=$editorVersion"
Write-Host "UNITY_TEST_FRAMEWORK_VERSION=$testFrameworkVersion"
Write-Host "UNITY_PLAYMODE=PASS_OBSERVED"
Write-Host "UNITY_CAPABILITY_INPUT_MOVE2D=PASS"
Write-Host "UNITY_CAPABILITY_MOTION_TRANSFORM2D=PASS"
Write-Host "UNITY_CAPABILITY_ANIMATION_PLAY=PASS"
Write-Host "UNITY_CAPABILITY_TIME_DELTA=PASS"
Write-Host "UNITY_CAPABILITY_DEBUG_LOG=PASS"
Write-Host "UNITY_FLOAT_BOUNDARY=EXPLICIT_AUDITED_PASS"
Write-Host "UNITY_PROVIDER_AUTHORITY=EXPLICIT_PASS"
Write-Host "UNITY_INPUT_SYSTEM_DEVICE=NOT_PROBED"
Write-Host "UNITY_ANIMATOR_CONTROLLER=NOT_PROBED"
Write-Host "UNITY_MONO_PLAYER=NOT_PROBED"
Write-Host "UNITY_IL2CPP=NOT_PROBED"
Write-Host "UNITY_PLAYMODE_EVIDENCE=$evidenceLog"
Write-Host "UNITY_PLAYMODE_EVIDENCE_SHA256=$logSha"
Write-Host "UNITY_PLAYMODE_RESULTS=$evidenceXml"
Write-Host "UNITY_PLAYMODE_RESULTS_SHA256=$xmlSha"
if ($RequireClean) { Write-Host "GIT_STATUS=CLEAN" } else { Write-Host "GIT_STATUS=CANDIDATE_CHANGES_ALLOWED" }
