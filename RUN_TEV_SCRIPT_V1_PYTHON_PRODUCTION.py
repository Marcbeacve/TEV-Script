from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import tomllib
import venv

ROOT = Path(__file__).resolve().parent
V0_2_ORACLE = "6e102f3cc3dcd131ae11e0cfc8bcfe64cccf87f5"
RECEIPT_SCHEMA = "TEV_SCRIPT_V1_PYTHON_PRODUCTION_RECEIPT_V1"
SOAK_EVENTS = 10_000


def run(
    arguments: list[str] | tuple[str, ...],
    *,
    cwd: Path = ROOT,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(arguments),
        cwd=cwd,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def fail(
    label: str,
    message: str,
    completed: subprocess.CompletedProcess[str] | None = None,
) -> None:
    print(f"{label}=FAIL {message}")
    if completed is not None:
        if completed.stdout:
            print(label + "_STDOUT=" + completed.stdout[-16000:].replace("\n", "\\n"))
        if completed.stderr:
            print(label + "_STDERR=" + completed.stderr[-16000:].replace("\n", "\\n"))
    print("TEV_SCRIPT_V1_PYTHON_PRODUCTION=FAIL")
    print("CERTIFY_FULL=NO")
    print("LANGUAGE_STABLE=NO")
    raise SystemExit(1)


def git_text(*arguments: str) -> str:
    completed = run(("git", *arguments))
    if completed.returncode != 0:
        fail("GIT_" + arguments[0].upper().replace("-", "_"), "COMMAND_FAILED", completed)
    return completed.stdout.strip()


def require_clean(stage: str) -> None:
    completed = run(("git", "status", "--porcelain=v1", "--untracked-files=all"))
    if completed.returncode != 0:
        fail("GIT_STATUS_" + stage, "COMMAND_FAILED", completed)
    if completed.stdout:
        fail("GIT_CLEAN_" + stage, "DIRTY=" + completed.stdout.replace("\n", "\\n"))
    print("GIT_CLEAN_" + stage + "=PASS")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def clean_environment(source_date_epoch: str) -> dict[str, str]:
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    environment.update(
        {
            "PIP_DISABLE_PIP_VERSION_CHECK": "1",
            "PIP_NO_INDEX": "1",
            "PYTHONHASHSEED": "0",
            "PYTHONNOUSERSITE": "1",
            "SOURCE_DATE_EPOCH": source_date_epoch,
        }
    )
    return environment


def archive_source(head: str, destination: Path) -> Path:
    destination.mkdir(parents=True, exist_ok=False)
    archive = destination.parent / (destination.name + ".tar")
    completed = run(
        ("git", "archive", "--format=tar", "--output", str(archive), head)
    )
    if completed.returncode != 0:
        fail("TEV_SCRIPT_V1_PYTHON_GIT_ARCHIVE", "COMMAND_FAILED", completed)
    with tarfile.open(archive, "r") as stream:
        stream.extractall(destination)
    archive.unlink()
    return destination


def build_wheel(source: Path, wheel_dir: Path, environment: dict[str, str]) -> Path:
    wheel_dir.mkdir(parents=True, exist_ok=False)
    completed = run(
        (
            sys.executable,
            "-m",
            "pip",
            "wheel",
            ".",
            "--no-deps",
            "--no-build-isolation",
            "--wheel-dir",
            str(wheel_dir),
        ),
        cwd=source,
        env=environment,
    )
    if completed.returncode != 0:
        fail("TEV_SCRIPT_V1_PYTHON_WHEEL_BUILD", "COMMAND_FAILED", completed)
    wheels = sorted(wheel_dir.glob("*.whl"))
    if len(wheels) != 1:
        fail(
            "TEV_SCRIPT_V1_PYTHON_WHEEL_BUILD",
            f"EXPECTED_ONE_WHEEL observed={len(wheels)}",
            completed,
        )
    return wheels[0]


def venv_python(root: Path) -> Path:
    return root / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def console_script(root: Path, name: str) -> Path:
    candidates = (
        root / "Scripts" / (name + ".exe"),
        root / "Scripts" / name,
        root / "bin" / name,
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    fail("TEV_SCRIPT_V1_PYTHON_CONSOLE_SCRIPT", f"MISSING={name}")
    raise AssertionError(name)


def require_success(
    label: str,
    completed: subprocess.CompletedProcess[str],
    witness: str | None = None,
) -> None:
    if completed.returncode != 0:
        fail(label, "COMMAND_FAILED", completed)
    if witness is not None and witness not in completed.stdout:
        fail(label, "MISSING_WITNESS=" + witness, completed)
    print(label + "=PASS")


def canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def main() -> int:
    print("TEV_SCRIPT_V1_PYTHON_PRODUCTION_GATE_SCHEMA=V1")
    print("V0_2_CERTIFIED_BASE=" + V0_2_ORACLE)
    if sys.version_info < (3, 11):
        fail(
            "TEV_SCRIPT_V1_PYTHON_VERSION",
            f"REQUIRES_3_11_OR_NEWER observed={sys.version.split()[0]}",
        )
    print("TEV_SCRIPT_V1_PYTHON_VERSION=PASS version=" + sys.version.split()[0])

    if shutil.which("git") is None:
        fail("TEV_SCRIPT_V1_PYTHON_TOOL_GIT", "MISSING")

    pip_check = run((sys.executable, "-m", "pip", "--version"))
    require_success("TEV_SCRIPT_V1_PYTHON_TOOL_PIP", pip_check)

    require_clean("BEFORE")
    head = git_text("rev-parse", "HEAD")
    tree = git_text("rev-parse", "HEAD^{tree}")
    branch = git_text("rev-parse", "--abbrev-ref", "HEAD")
    commit_epoch = git_text("show", "-s", "--format=%ct", "HEAD")

    ancestry = run(("git", "merge-base", "--is-ancestor", V0_2_ORACLE, "HEAD"))
    if ancestry.returncode != 0:
        fail("V0_2_ORACLE_ANCESTRY", "FAIL", ancestry)
    print("V0_2_ORACLE_ANCESTRY=PASS")

    governance = run(
        (sys.executable, str(ROOT / "tools" / "validate_v1_governance.py"))
    )
    require_success(
        "TEV_SCRIPT_V1_PYTHON_GOVERNANCE",
        governance,
        "TEV_SCRIPT_V1_GOVERNANCE=PASS",
    )

    frontend = run((sys.executable, str(ROOT / "RUN_TEV_SCRIPT_V1_FRONTEND_CLOSURE.py")))
    require_success(
        "TEV_SCRIPT_V1_PYTHON_FRONTEND_CLOSURE",
        frontend,
        "TEV_SCRIPT_V1_PYTHON_CLOSURE=PASS_CANDIDATE",
    )
    if "SKIPPED_" in frontend.stdout or "skipped=" in frontend.stdout.lower():
        fail("TEV_SCRIPT_V1_PYTHON_FRONTEND_CLOSURE", "TEST_SKIP_DETECTED", frontend)

    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    package_name = str(project["name"])
    package_version = str(project["version"])
    environment = clean_environment(commit_epoch)

    with tempfile.TemporaryDirectory(prefix="tev-script-v1-python-production-") as temporary:
        work = Path(temporary)
        source_a = archive_source(head, work / "source-a")
        source_b = archive_source(head, work / "source-b")
        wheel_a = build_wheel(source_a, work / "wheel-a", environment)
        wheel_b = build_wheel(source_b, work / "wheel-b", environment)
        wheel_a_hash = sha256(wheel_a)
        wheel_b_hash = sha256(wheel_b)
        if wheel_a.name != wheel_b.name or wheel_a_hash != wheel_b_hash:
            fail(
                "TEV_SCRIPT_V1_PYTHON_WHEEL_REPRODUCIBLE",
                f"A={wheel_a.name}:{wheel_a_hash} B={wheel_b.name}:{wheel_b_hash}",
            )
        print("TEV_SCRIPT_V1_PYTHON_WHEEL_BUILD=PASS")
        print("TEV_SCRIPT_V1_PYTHON_WHEEL_REPRODUCIBLE=PASS")
        print("TEV_SCRIPT_V1_PYTHON_WHEEL_SHA256=" + wheel_a_hash)

        venv_root = work / "venv"
        try:
            venv.EnvBuilder(with_pip=True, clear=True).create(venv_root)
        except Exception as exc:
            fail("TEV_SCRIPT_V1_PYTHON_VENV", type(exc).__name__ + ":" + str(exc))
        python = venv_python(venv_root)
        if not python.is_file():
            fail("TEV_SCRIPT_V1_PYTHON_VENV", "PYTHON_MISSING")
        print("TEV_SCRIPT_V1_PYTHON_VENV=PASS")

        install = run(
            (
                str(python),
                "-m",
                "pip",
                "install",
                "--no-index",
                "--no-deps",
                "--force-reinstall",
                str(wheel_a),
            ),
            cwd=work,
            env=environment,
        )
        require_success("TEV_SCRIPT_V1_PYTHON_ISOLATED_INSTALL", install)

        installed_version = run(
            (
                str(python),
                "-c",
                "import importlib.metadata; print(importlib.metadata.version('" + package_name + "'))",
            ),
            cwd=work,
            env=environment,
        )
        require_success("TEV_SCRIPT_V1_PYTHON_INSTALLED_METADATA", installed_version)
        if installed_version.stdout.strip() != package_version:
            fail(
                "TEV_SCRIPT_V1_PYTHON_INSTALLED_METADATA",
                f"VERSION expected={package_version} observed={installed_version.stdout.strip()}",
            )

        v1_cli = console_script(venv_root, "tev-script-v1")
        describe_cli = console_script(venv_root, "tev-script-v1-describe")
        console_script(venv_root, "tev-script-v1-ir")
        console_script(venv_root, "tev-script-v1-lsp")
        print("TEV_SCRIPT_V1_PYTHON_CONSOLE_SCRIPTS=PASS")

        descriptor_run = run((str(describe_cli),), cwd=work, env=environment)
        require_success("TEV_SCRIPT_V1_PYTHON_INSTALLED_DESCRIPTOR", descriptor_run)
        try:
            descriptor = json.loads(descriptor_run.stdout)
        except json.JSONDecodeError as exc:
            fail("TEV_SCRIPT_V1_PYTHON_INSTALLED_DESCRIPTOR", "INVALID_JSON=" + str(exc), descriptor_run)
        if descriptor.get("schema") != "TEV_SCRIPT_DESCRIPTOR_V3":
            fail("TEV_SCRIPT_V1_PYTHON_INSTALLED_DESCRIPTOR", "SCHEMA_MISMATCH", descriptor_run)
        if descriptor.get("stable") is not False:
            fail("TEV_SCRIPT_V1_PYTHON_INSTALLED_DESCRIPTOR", "UNAUTHORIZED_STABLE_CLAIM", descriptor_run)

        source = work / "production_smoke.tevs"
        source.write_text(
            'script ProductionSmoke version "1.0.0"; '
            'entity E { state x: Int = 0; on inc { x = x + 1; } }\n',
            encoding="utf-8",
        )
        ir_path = work / "production_smoke.ir.json"
        compile_run = run(
            (
                str(v1_cli),
                "compile",
                str(source),
                "--target",
                "irv3",
                "--output",
                str(ir_path),
            ),
            cwd=work,
            env=environment,
        )
        require_success("TEV_SCRIPT_V1_PYTHON_INSTALLED_COMPILE_IRV3", compile_run)
        try:
            compile_result = json.loads(compile_run.stdout)
        except json.JSONDecodeError as exc:
            fail("TEV_SCRIPT_V1_PYTHON_INSTALLED_COMPILE_IRV3", "INVALID_JSON=" + str(exc), compile_run)
        if compile_result.get("target_ir_schema") != "TEV_SCRIPT_PROGRAM_IR_V3":
            fail("TEV_SCRIPT_V1_PYTHON_INSTALLED_COMPILE_IRV3", "TARGET_SCHEMA_MISMATCH", compile_run)
        if not ir_path.is_file():
            fail("TEV_SCRIPT_V1_PYTHON_INSTALLED_COMPILE_IRV3", "IR_ARTIFACT_MISSING", compile_run)

        smoke_code = r'''
from pathlib import Path
import sys
from tev_script import PythonProgramArtifactV1, PythonRuntimeHostV1

artifact = PythonProgramArtifactV1.parse(Path(sys.argv[1]).read_text(encoding="utf-8"))
host = PythonRuntimeHostV1(artifact)
host.invoke("E", "inc")
if host.state("E")["x"] != 1:
    raise SystemExit("state_after_first_invoke")
checkpoint = host.capture_checkpoint_json()
host.invoke("E", "inc")
if host.state("E")["x"] != 2:
    raise SystemExit("state_after_second_invoke")
host.restore_checkpoint(checkpoint)
if host.state("E")["x"] != 1:
    raise SystemExit("state_after_restore")
host.invoke("E", "inc")
if host.state("E")["x"] != 2:
    raise SystemExit("state_after_restart_continuation")

soak_events = int(sys.argv[2])
soak = PythonRuntimeHostV1(artifact)
for _ in range(soak_events):
    soak.invoke("E", "inc")
if soak.state("E")["x"] != soak_events:
    raise SystemExit("soak_state_mismatch")

print("TEV_SCRIPT_V1_PYTHON_INSTALLED_RUNTIME_HOST=PASS")
print("TEV_SCRIPT_V1_PYTHON_INSTALLED_CHECKPOINT_RESTART=PASS")
print(f"TEV_SCRIPT_V1_PYTHON_SOAK_EVENTS={soak_events}")
'''
        smoke = run(
            (str(python), "-c", smoke_code, str(ir_path), str(SOAK_EVENTS)),
            cwd=work,
            env=environment,
        )
        require_success(
            "TEV_SCRIPT_V1_PYTHON_INSTALLED_RUNTIME",
            smoke,
            "TEV_SCRIPT_V1_PYTHON_INSTALLED_RUNTIME_HOST=PASS",
        )
        if "TEV_SCRIPT_V1_PYTHON_INSTALLED_CHECKPOINT_RESTART=PASS" not in smoke.stdout:
            fail(
                "TEV_SCRIPT_V1_PYTHON_INSTALLED_RUNTIME",
                "MISSING_CHECKPOINT_RESTART_WITNESS",
                smoke,
            )
        if f"TEV_SCRIPT_V1_PYTHON_SOAK_EVENTS={SOAK_EVENTS}" not in smoke.stdout:
            fail(
                "TEV_SCRIPT_V1_PYTHON_INSTALLED_RUNTIME",
                "MISSING_SOAK_WITNESS",
                smoke,
            )
        print("TEV_SCRIPT_V1_PYTHON_CHECKPOINT_RESTART=PASS")
        print("TEV_SCRIPT_V1_PYTHON_SOAK=PASS events=" + str(SOAK_EVENTS))

        require_clean("AFTER")
        head_after = git_text("rev-parse", "HEAD")
        tree_after = git_text("rev-parse", "HEAD^{tree}")
        if head_after != head or tree_after != tree:
            fail("GIT_IDENTITY_STABLE_DURING_PYTHON_PRODUCTION_GATE", "HEAD_OR_TREE_CHANGED")
        print("GIT_IDENTITY_STABLE_DURING_PYTHON_PRODUCTION_GATE=PASS")

        receipt_without_hash = {
            "schema": RECEIPT_SCHEMA,
            "branch": branch,
            "commit": head,
            "tree": tree,
            "v0_2_oracle": V0_2_ORACLE,
            "python_version": sys.version.split()[0],
            "package_name": package_name,
            "package_version": package_version,
            "wheel_filename": wheel_a.name,
            "wheel_sha256": wheel_a_hash,
            "v1_governance": "PASS",
            "frontend_closure": "PASS",
            "wheel_reproducible": True,
            "isolated_install": "PASS",
            "installed_console_scripts": "PASS",
            "installed_ir_v3_compile": "PASS",
            "installed_runtime_host": "PASS",
            "checkpoint_restart_continuation": "PASS",
            "soak_events": SOAK_EVENTS,
            "soak_result": "PASS",
            "certify_full": False,
            "language_stable": False,
        }
        receipt_hash = hashlib.sha256(
            canonical_json(receipt_without_hash).encode("utf-8")
        ).hexdigest()
        receipt = dict(receipt_without_hash)
        receipt["receipt_hash"] = receipt_hash
        print("TEV_SCRIPT_V1_PYTHON_PRODUCTION_RECEIPT_JSON=" + canonical_json(receipt))
        print("TEV_SCRIPT_V1_PYTHON_PRODUCTION_RECEIPT_SHA256=" + receipt_hash)

    print("TEV_SCRIPT_V1_PYTHON_PRODUCTION=PASS_CANDIDATE")
    print("CERTIFY_FULL=NO")
    print("LANGUAGE_STABLE=NO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
