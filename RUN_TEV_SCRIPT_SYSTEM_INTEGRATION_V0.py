from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import tomllib
import venv
import zipfile

ROOT = Path(__file__).resolve().parent
FOCAL = ROOT / "tests" / "run_system_integration_v0_focal.py"
SYSTEM_INDEX = ROOT / "spec" / "TEV_SCRIPT_SYSTEM_CANONICAL_INDEX_V0.json"
SYSTEM_SPEC = ROOT / "spec" / "TEV_SCRIPT_SYSTEM_INTEGRATION_V0.md"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(command: list[str], *, cwd: Path = ROOT, env: dict[str, str] | None = None, capture: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        check=False,
        capture_output=capture,
    )


def git_text(*args: str) -> str:
    completed = run(["git", *args], capture=True)
    if completed.returncode:
        raise RuntimeError("git command failed: " + " ".join(args) + ":" + completed.stderr.strip())
    return completed.stdout.strip()


def require_clean_checkout() -> tuple[str, str, str, str]:
    status = git_text("status", "--porcelain")
    if status:
        raise RuntimeError("system integration artifact requires clean checkout")
    branch = git_text("branch", "--show-current")
    head = git_text("rev-parse", "HEAD")
    tree = git_text("rev-parse", "HEAD^{tree}")
    epoch = git_text("show", "-s", "--format=%ct", "HEAD")
    if not branch:
        raise RuntimeError("system integration artifact requires a named branch")
    if not epoch.isdigit():
        raise RuntimeError("invalid git commit epoch")
    return branch, head, tree, epoch


def load_project_metadata() -> dict[str, object]:
    document = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    project = document.get("project")
    if not isinstance(project, dict):
        raise RuntimeError("pyproject project table missing")
    if project.get("dependencies", []) != []:
        raise RuntimeError("system integration artifact requires zero runtime dependencies")
    return project


def venv_python(directory: Path) -> Path:
    if os.name == "nt":
        return directory / "Scripts" / "python.exe"
    return directory / "bin" / "python"


def source_python_module_paths() -> tuple[str, ...]:
    package_root = ROOT / "tev_script"
    modules = tuple(
        sorted(
            path.relative_to(ROOT).as_posix()
            for path in package_root.rglob("*.py")
            if path.is_file() and "__pycache__" not in path.parts
        )
    )
    if not modules:
        raise RuntimeError("TEV Script Python package closure is empty")
    return modules


def wheel_python_module_paths(path: Path) -> tuple[str, ...]:
    with zipfile.ZipFile(path, "r") as archive:
        return tuple(
            sorted(
                name
                for name in archive.namelist()
                if name.startswith("tev_script/") and name.endswith(".py")
            )
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Build and verify an exact TEV Script complete-system integration artifact.")
    parser.add_argument("--artifact-out-dir", required=True)
    args = parser.parse_args()

    try:
        if not FOCAL.is_file() or not SYSTEM_INDEX.is_file() or not SYSTEM_SPEC.is_file():
            raise RuntimeError("system integration authority files missing")

        out_dir = Path(args.artifact_out_dir).expanduser().resolve()
        root_resolved = ROOT.resolve()
        if out_dir == root_resolved or root_resolved in out_dir.parents:
            raise RuntimeError("artifact output directory must be outside repository")
        out_dir.mkdir(parents=True, exist_ok=True)
        if any(out_dir.iterdir()):
            raise RuntimeError("artifact output directory must be empty")

        branch, head, tree, epoch = require_clean_checkout()
        project = load_project_metadata()
        source_python_modules = source_python_module_paths()

        print("SYSTEM_SOURCE_CLEAN=PASS")
        print("SYSTEM_SOURCE_BRANCH=" + branch)
        print("SYSTEM_SOURCE_HEAD=" + head)
        print("SYSTEM_SOURCE_TREE=" + tree)

        focal = run([sys.executable, str(FOCAL)])
        if focal.returncode:
            raise RuntimeError("system focal gate failed")
        print("SYSTEM_SOURCE_FOCAL=PASS")

        from tev_script.canonical import canonical_hash, canonical_json  # noqa: PLC0415
        from tev_script.system_api_v0 import (  # noqa: PLC0415
            SYSTEM_API_CONTRACT_HASH_V0,
            SYSTEM_CANONICAL_INDEX_SCHEMA_V0,
            SYSTEM_CAUSAL_MODULE_PATHS_V0,
            SYSTEM_SUBSYSTEM_MODULE_PATHS_V0,
            V1_LANGUAGE_VERSION,
            build_system_integration_receipt_v0,
            system_api_contract_object_v0,
            verify_system_integration_receipt_v0,
        )
        from tools.tev_script_build_backend import build_wheel  # noqa: PLC0415

        system_contract = system_api_contract_object_v0()
        system_index = json.loads(SYSTEM_INDEX.read_text(encoding="utf-8"))
        if system_index.get("schema") != SYSTEM_CANONICAL_INDEX_SCHEMA_V0:
            raise RuntimeError("system canonical index schema mismatch")
        if system_index.get("language_version") != V1_LANGUAGE_VERSION:
            raise RuntimeError("system canonical index language version mismatch")
        if canonical_hash(system_contract) != SYSTEM_API_CONTRACT_HASH_V0:
            raise RuntimeError("system api contract hash mismatch")
        if not SYSTEM_CAUSAL_MODULE_PATHS_V0:
            raise RuntimeError("complete causal subsystem registry is empty")
        if not SYSTEM_SUBSYSTEM_MODULE_PATHS_V0:
            raise RuntimeError("complete semantic subsystem registry is empty")
        stable_public_api = tuple(system_contract["surfaces"]["stable_public_api"])
        if not stable_public_api:
            raise RuntimeError("stable public API surface is empty")
        print("SYSTEM_API_CONTRACT_HASH=PASS")
        print("SYSTEM_SOURCE_STABLE_PUBLIC_API=PASS")
        print("SYSTEM_SOURCE_COMPLETE_CAUSAL_REGISTRY=PASS")
        print("SYSTEM_SOURCE_COMPLETE_SEMANTIC_REGISTRY=PASS")

        with tempfile.TemporaryDirectory(prefix="tev-script-system-") as temporary:
            temp = Path(temporary)
            build_a = temp / "build-a"
            build_b = temp / "build-b"
            build_a.mkdir()
            build_b.mkdir()

            previous_epoch = os.environ.get("SOURCE_DATE_EPOCH")
            os.environ["SOURCE_DATE_EPOCH"] = epoch
            try:
                wheel_a_name = build_wheel(str(build_a))
                wheel_b_name = build_wheel(str(build_b))
            finally:
                if previous_epoch is None:
                    os.environ.pop("SOURCE_DATE_EPOCH", None)
                else:
                    os.environ["SOURCE_DATE_EPOCH"] = previous_epoch

            if wheel_a_name != wheel_b_name:
                raise RuntimeError("deterministic wheel filename mismatch")
            wheel_a = build_a / wheel_a_name
            wheel_b = build_b / wheel_b_name
            wheel_a_sha = sha256_file(wheel_a)
            wheel_b_sha = sha256_file(wheel_b)
            if wheel_a_sha != wheel_b_sha or wheel_a.read_bytes() != wheel_b.read_bytes():
                raise RuntimeError("independent system wheel builds are not byte-identical")
            print("SYSTEM_WHEEL_DETERMINISTIC_BYTES=PASS")

            wheel_python_modules = wheel_python_module_paths(wheel_a)
            if wheel_python_modules != source_python_modules:
                missing = sorted(set(source_python_modules) - set(wheel_python_modules))
                extra = sorted(set(wheel_python_modules) - set(source_python_modules))
                raise RuntimeError(
                    "system wheel Python module closure mismatch missing="
                    + repr(missing)
                    + " extra="
                    + repr(extra)
                )
            print("SYSTEM_WHEEL_COMPLETE_PYTHON_MODULE_CLOSURE=PASS")

            env_dir = temp / "installed-env"
            venv.EnvBuilder(with_pip=True, clear=True).create(env_dir)
            python_executable = venv_python(env_dir)
            install = run(
                [str(python_executable), "-m", "pip", "install", "--no-index", "--no-deps", str(wheel_a)],
                cwd=temp,
                capture=True,
            )
            if install.returncode:
                raise RuntimeError("installed wheel failed: " + install.stderr.strip())

            smoke_code = (
                "import json; import tev_script; import tev_script.system_api_v0 as api; "
                "required=('compile_v1_sources_to_ir_v3','verify_ir_v3_lowering_receipt','ScriptRuntimeV3',"
                "'PythonRuntimeHostV1','admit_realization','resolve_realization_selection','HostExecutionAdmissionV1',"
                "'evaluate_execution_activation','evaluate_execution_observation',"
                "'verify_system_integration_receipt_v0','load_system_causal_subsystem_v0','load_system_subsystem_v0'); "
                "assert all(hasattr(api,n) for n in required); "
                "root_api=tuple(tev_script.__all__); "
                "assert tuple(api.system_api_contract_object_v0()['surfaces']['stable_public_api'])==root_api; "
                "assert all(hasattr(api,n) and getattr(api,n) is getattr(tev_script,n) for n in root_api); "
                "assert all(api.load_system_causal_subsystem_v0(n).__name__==api.SYSTEM_CAUSAL_MODULE_PATHS_V0[n] "
                "for n in api.SYSTEM_CAUSAL_MODULE_PATHS_V0); "
                "assert all(api.load_system_subsystem_v0(n).__name__==api.SYSTEM_SUBSYSTEM_MODULE_PATHS_V0[n] "
                "for n in api.SYSTEM_SUBSYSTEM_MODULE_PATHS_V0); "
                "print(json.dumps({'language_version':api.V1_LANGUAGE_VERSION,"
                "'contract_hash':api.SYSTEM_API_CONTRACT_HASH_V0,'exports':len(api.SYSTEM_API_EXPORTS_V0),"
                "'stable_public_api':len(root_api),"
                "'causal_subsystems':len(api.SYSTEM_CAUSAL_MODULE_PATHS_V0),"
                "'semantic_subsystems':len(api.SYSTEM_SUBSYSTEM_MODULE_PATHS_V0)},sort_keys=True))"
            )
            smoke = run([str(python_executable), "-I", "-c", smoke_code], cwd=temp, capture=True)
            if smoke.returncode:
                raise RuntimeError("installed system api smoke failed: " + smoke.stderr.strip())
            installed = json.loads(smoke.stdout.strip().splitlines()[-1])
            if installed.get("language_version") != V1_LANGUAGE_VERSION:
                raise RuntimeError("installed system language version mismatch")
            if installed.get("contract_hash") != SYSTEM_API_CONTRACT_HASH_V0:
                raise RuntimeError("installed system api contract hash mismatch")
            if int(installed.get("exports", 0)) <= 0:
                raise RuntimeError("installed system api export surface empty")
            if int(installed.get("stable_public_api", 0)) != len(stable_public_api):
                raise RuntimeError("installed stable public API cardinality mismatch")
            if int(installed.get("causal_subsystems", 0)) != len(SYSTEM_CAUSAL_MODULE_PATHS_V0):
                raise RuntimeError("installed causal subsystem registry cardinality mismatch")
            if int(installed.get("semantic_subsystems", 0)) != len(SYSTEM_SUBSYSTEM_MODULE_PATHS_V0):
                raise RuntimeError("installed semantic subsystem registry cardinality mismatch")
            print("SYSTEM_INSTALLED_WHEEL_IMPORT=PASS")
            print("SYSTEM_INSTALLED_API_IDENTITY=PASS")
            print("SYSTEM_INSTALLED_STABLE_PUBLIC_API=PASS")
            print("SYSTEM_INSTALLED_COMPLETE_CAUSAL_REGISTRY=PASS")
            print("SYSTEM_INSTALLED_COMPLETE_SEMANTIC_REGISTRY=PASS")

            receipt_record = build_system_integration_receipt_v0(
                branch=branch,
                head=head,
                tree=tree,
                source_date_epoch=epoch,
                language_version=V1_LANGUAGE_VERSION,
                system_api_contract_hash=SYSTEM_API_CONTRACT_HASH_V0,
                system_canonical_index_schema=SYSTEM_CANONICAL_INDEX_SCHEMA_V0,
                system_canonical_index_file_sha256=sha256_file(SYSTEM_INDEX),
                system_integration_spec_sha256=sha256_file(SYSTEM_SPEC),
                distribution_name=str(project.get("name")),
                distribution_version=str(project.get("version")),
                wheel_name=wheel_a.name,
                wheel_sha256=wheel_a_sha,
            )
            verify_system_integration_receipt_v0(
                receipt_record.to_object(),
                expected_language_version=V1_LANGUAGE_VERSION,
                expected_system_api_contract_hash=SYSTEM_API_CONTRACT_HASH_V0,
                expected_distribution_artifact_sha256=wheel_a_sha,
                expected_source_head=head,
                expected_source_tree=tree,
            )

            staged_receipt = temp / "TEV_SCRIPT_SYSTEM_INTEGRATION_V0.receipt.json"
            staged_receipt.write_bytes(canonical_json(receipt_record.to_object()).encode("utf-8") + b"\n")

            receipt_smoke_code = (
                "import json,sys; import tev_script.system_api_v0 as api; "
                "doc=json.load(open(sys.argv[1],encoding='utf-8')); "
                "r=api.verify_system_integration_receipt_v0(doc,"
                "expected_language_version=api.V1_LANGUAGE_VERSION,"
                "expected_system_api_contract_hash=api.SYSTEM_API_CONTRACT_HASH_V0,"
                "expected_distribution_artifact_sha256=sys.argv[2],"
                "expected_source_head=sys.argv[3],expected_source_tree=sys.argv[4]); "
                "print(r.receipt_hash)"
            )
            receipt_smoke = run(
                [
                    str(python_executable),
                    "-I",
                    "-c",
                    receipt_smoke_code,
                    str(staged_receipt),
                    wheel_a_sha,
                    head,
                    tree,
                ],
                cwd=temp,
                capture=True,
            )
            if receipt_smoke.returncode:
                raise RuntimeError("installed receipt verifier failed: " + receipt_smoke.stderr.strip())
            if receipt_smoke.stdout.strip().splitlines()[-1] != receipt_record.receipt_hash:
                raise RuntimeError("installed receipt verifier identity mismatch")
            print("SYSTEM_INSTALLED_RECEIPT_VERIFIER=PASS")

            target_wheel = out_dir / wheel_a.name
            shutil.copyfile(wheel_a, target_wheel)
            target_wheel_sha = sha256_file(target_wheel)
            if target_wheel_sha != wheel_a_sha:
                raise RuntimeError("copied wheel hash mismatch")

            receipt_path = out_dir / staged_receipt.name
            shutil.copyfile(staged_receipt, receipt_path)
            receipt_file_sha = sha256_file(receipt_path)
            if receipt_file_sha != sha256_file(staged_receipt):
                raise RuntimeError("copied integration receipt hash mismatch")

        print("SYSTEM_ARTIFACT_RECEIPT_LAST=PASS")
        print("SYSTEM_DISTRIBUTION_WHEEL=" + target_wheel.name)
        print("SYSTEM_DISTRIBUTION_WHEEL_SHA256=" + target_wheel_sha)
        print("SYSTEM_API_CONTRACT_HASH_V0=" + SYSTEM_API_CONTRACT_HASH_V0)
        print("SYSTEM_INTEGRATION_RECEIPT_SHA256=" + receipt_record.receipt_hash)
        print("SYSTEM_INTEGRATION_RECEIPT_FILE_SHA256=" + receipt_file_sha)
        print("CERTIFY_FULL=DEFERRED_BY_DESIGN")
        print("UNITY_VALIDATION=DEFERRED_BY_PRIORITY")
        print("TEV_SCRIPT_SYSTEM_INTEGRATION_ARTIFACT=PASS")
        return 0
    except Exception as error:
        print("TEV_SCRIPT_SYSTEM_INTEGRATION_ARTIFACT=FAIL")
        print("TEV_SCRIPT_SYSTEM_INTEGRATION_ARTIFACT_DETAIL=" + str(error))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
