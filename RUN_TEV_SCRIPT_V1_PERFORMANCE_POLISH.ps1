[CmdletBinding()]
param(
    [ValidateSet("experiment", "promotion")]
    [string]$Profile = "experiment",

    [string]$Python = "",
    [string]$OptimizerOracle = "",

    [int]$Events = 200000,
    [int]$RichEvents = 50000,
    [int]$CapabilityEvents = 100000,
    [int]$Rounds = 7,
    [int]$Warmup = 5000,

    [string]$Log = ""
)

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot

function Resolve-Python {
    param([string]$Requested)

    if ($Requested) {
        if (-not (Test-Path $Requested)) {
            throw "Requested Python does not exist: $Requested"
        }
        return (Resolve-Path $Requested).Path
    }

    if ($env:TEV_SCRIPT_PYTHON -and (Test-Path $env:TEV_SCRIPT_PYTHON)) {
        return (Resolve-Path $env:TEV_SCRIPT_PYTHON).Path
    }

    $ProjectVenv = Join-Path $Root ".venv\Scripts\python.exe"
    if (Test-Path $ProjectVenv) {
        return (Resolve-Path $ProjectVenv).Path
    }

    $KnownGlobalVenv = "C:\TEV\venvs\tev-script-v1-global\Scripts\python.exe"
    if (Test-Path $KnownGlobalVenv) {
        return (Resolve-Path $KnownGlobalVenv).Path
    }

    $Command = Get-Command python -ErrorAction SilentlyContinue
    if ($null -ne $Command) {
        return $Command.Source
    }

    throw "Python not found. Pass -Python or set TEV_SCRIPT_PYTHON."
}


$PythonExe = Resolve-Python $Python

if (-not $Log) {
    $EvidenceRoot = "C:\TEV\evidence"
    if (-not (Test-Path $EvidenceRoot)) {
        New-Item -ItemType Directory -Force -Path $EvidenceRoot | Out-Null
    }
    $Log = Join-Path $EvidenceRoot "TEV_SCRIPT_V1_PERFORMANCE_POLISH.log"
}

$Head = (& git -C $Root rev-parse HEAD).Trim()
$Tree = (& git -C $Root rev-parse "HEAD^{tree}").Trim()
$Dirty = & git -C $Root status --porcelain=v1 --untracked-files=all

"PERFORMANCE_POLISH_ROOT=$Root"
"PERFORMANCE_POLISH_HEAD=$Head"
"PERFORMANCE_POLISH_TREE=$Tree"
"PERFORMANCE_POLISH_PYTHON=$PythonExe"
if ($OptimizerOracle) {
    "PERFORMANCE_POLISH_OPTIMIZER_ORACLE=$OptimizerOracle"
} else {
    "PERFORMANCE_POLISH_OPTIMIZER_ORACLE=LOCAL_DEFAULT"
}

if ($Dirty) {
    throw "Performance-polish worktree must be clean before benchmarking."
}

$Arguments = @(
    (Join-Path $Root "RUN_TEV_SCRIPT_V1_PERFORMANCE_POLISH.py"),
    "--profile", $Profile,
    "--events", "$Events",
    "--rich-events", "$RichEvents",
    "--capability-events", "$CapabilityEvents",
    "--rounds", "$Rounds",
    "--warmup", "$Warmup"
)

if ($OptimizerOracle) {
    $Arguments += @("--optimizer-oracle", $OptimizerOracle)
}

"PERFORMANCE_POLISH_LOG=$Log"
"PERFORMANCE_POLISH_BEGIN"

# Every Python process in this campaign must import the source tree under test,
# not a potentially stale tev_script installed in the selected venv. Child
# subprocesses inherit this exact worktree binding. Restore the user's previous
# PYTHONPATH afterwards even when the gate fails.
$PreviousPythonPath = $env:PYTHONPATH
if ($PreviousPythonPath) {
    $env:PYTHONPATH = "$Root;$PreviousPythonPath"
} else {
    $env:PYTHONPATH = $Root
}
"PERFORMANCE_POLISH_PYTHONPATH_ROOT=$Root"

$Code = 1
try {
    & $PythonExe @Arguments 2>&1 | Tee-Object -FilePath $Log
    $Code = $LASTEXITCODE
}
finally {
    if ($null -eq $PreviousPythonPath) {
        Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
    } else {
        $env:PYTHONPATH = $PreviousPythonPath
    }
}

"PERFORMANCE_POLISH_END"
"PERFORMANCE_POLISH_EXIT_CODE=$Code"

if ($Code -eq 0) {
    "PERFORMANCE_POLISH_RESULT=PASS"
} elseif ($Code -eq 2) {
    "PERFORMANCE_POLISH_RESULT=HOLD_PERFORMANCE_TARGET_NOT_MET"
} else {
    "PERFORMANCE_POLISH_RESULT=FAIL"
}

# Deliberately do not `exit`: an interactive PowerShell session must remain
# open even when the experiment fails or is held by a performance threshold.
$global:LASTEXITCODE = $Code
