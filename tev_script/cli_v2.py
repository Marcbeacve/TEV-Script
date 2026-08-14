from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Any, Mapping

from .diagnostics import TevScriptError
from .json_io import load_strict_json
from .program_ir_v4_effect_commands import PROGRAM_IR_V4_EFFECTS_R2_SCHEMA
from .program_ir_v4 import (
    PROGRAM_IR_V4_PURE_SCHEMA,
    PROGRAM_IR_V4_RECURSIVE_SCHEMA,
    PROGRAM_IR_V4_EFFECTS_SCHEMA,
    canonical_program_ir_v4_bytes,
    export_program_ir_v4_pure,
    export_program_ir_v4_recursive,
    run_program_ir_v4,
    validate_program_ir_v4,
)

LANGUAGE_VERSION_V2 = "2.0.0"
ARTIFACT_COMMIT_POLICY_V2 = "ATOMIC_SINGLE_PATH_REPLACE_V1"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tev-script-v2",
        description="TEV Script V2 compiler and standalone Program IR V4 runtime.",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    descriptor = commands.add_parser("descriptor", help="report V2 language/runtime surface")
    descriptor.set_defaults(handler=_descriptor)

    check = commands.add_parser("check", help="parse/type-check/compile source through portable Program IR V4")
    check.add_argument("source", type=Path)
    check.set_defaults(handler=_check)

    compile_command = commands.add_parser("compile", help="compile V2 source to canonical Program IR V4 JSON")
    compile_command.add_argument("source", type=Path)
    compile_command.add_argument("--output", "-o", type=Path, required=True)
    compile_command.set_defaults(handler=_compile)

    signed_remote_verify = commands.add_parser("verify-signed-remote-module-manifest", help="verify an Ed25519-signed remote module manifest against an external public-key pin")
    signed_remote_verify.add_argument("signed_manifest", type=Path)
    signed_remote_verify.add_argument("--expected-public-key-sha256", required=True)
    signed_remote_verify.set_defaults(handler=_verify_signed_remote_module_manifest)

    signed_remote_acquire = commands.add_parser("acquire-signed-remote-modules", help="verify manifest authenticity and acquire its HTTPS modules in one build-time step")
    signed_remote_acquire.add_argument("signed_manifest", type=Path)
    signed_remote_acquire.add_argument("--expected-public-key-sha256", required=True)
    signed_remote_acquire.add_argument("--output", "-o", type=Path, required=True)
    signed_remote_acquire.set_defaults(handler=_acquire_signed_remote_modules)

    signed_remote_extract = commands.add_parser("extract-signed-remote-module-bundle", help="reverify signed acquisition offline and extract its portable module bundle")
    signed_remote_extract.add_argument("acquisition", type=Path)
    signed_remote_extract.add_argument("--expected-public-key-sha256", required=True)
    signed_remote_extract.add_argument("--expected-transport-descriptor-hash")
    signed_remote_extract.add_argument("--output", "-o", type=Path, required=True)
    signed_remote_extract.set_defaults(handler=_extract_signed_remote_module_bundle)

    remote_module_check = commands.add_parser("check-remote-module-manifest", help="validate a content-pinned remote module manifest without network access")
    remote_module_check.add_argument("manifest", type=Path)
    remote_module_check.set_defaults(handler=_check_remote_module_manifest)

    remote_module_acquire = commands.add_parser("acquire-remote-modules", help="acquire HTTPS modules at build time into one content-addressed result artifact")
    remote_module_acquire.add_argument("manifest", type=Path)
    remote_module_acquire.add_argument("--output", "-o", type=Path, required=True)
    remote_module_acquire.set_defaults(handler=_acquire_remote_modules)

    remote_module_extract = commands.add_parser("extract-remote-module-bundle", help="validate remote acquisition evidence offline and extract its portable module bundle")
    remote_module_extract.add_argument("acquisition", type=Path)
    remote_module_extract.add_argument("--output", "-o", type=Path, required=True)
    remote_module_extract.add_argument("--expected-transport-descriptor-hash")
    remote_module_extract.add_argument("--expected-manifest-hash")
    remote_module_extract.set_defaults(handler=_extract_remote_module_bundle)

    module_bundle = commands.add_parser("bundle-modules", help="acquire local pure-module sources into a content-addressed portable bundle")
    module_bundle.add_argument("--module", action="append", dest="modules", type=Path, required=True, help="module source file; repeat for dependencies")
    module_bundle.add_argument("--output", "-o", type=Path, required=True)
    module_bundle.set_defaults(handler=_bundle_modules)

    module_check = commands.add_parser("check-modules", help="link a V2 program against a portable module bundle and validate Program IR closure")
    module_check.add_argument("source", type=Path)
    module_check.add_argument("--bundle", type=Path, required=True)
    module_check.set_defaults(handler=_check_modules)

    module_compile = commands.add_parser("compile-modules", help="link a V2 program against a portable module bundle and emit standalone Program IR")
    module_compile.add_argument("source", type=Path)
    module_compile.add_argument("--bundle", type=Path, required=True)
    module_compile.add_argument("--output", "-o", type=Path, required=True)
    module_compile.set_defaults(handler=_compile_modules)

    effects_check = commands.add_parser("check-effects", help="parse/type-check Effects V2 source and close state/capability/action semantics")
    effects_check.add_argument("source", type=Path)
    effects_check.set_defaults(handler=_check_effects)

    effects_scenario = commands.add_parser("scenario-effects", help="write a contract-bound empty scenario skeleton for Effects V2 source")
    effects_scenario.add_argument("source", type=Path)
    effects_scenario.add_argument("--output", "-o", type=Path, required=True)
    effects_scenario.set_defaults(handler=_scenario_effects)

    effects_compile = commands.add_parser("compile-effects", help="compile Effects V2 source + scenario to portable Program IR V4")
    effects_compile.add_argument("source", type=Path)
    effects_compile.add_argument("--scenario", type=Path, required=True)
    effects_compile.add_argument("--output", "-o", type=Path, required=True)
    effects_compile.set_defaults(handler=_compile_effects)

    file_observation_request = commands.add_parser("request-file-observations", help="build a contract-bound file.read acquisition request; does not read the host")
    file_observation_request.add_argument("source", type=Path)
    file_observation_request.add_argument("--path", action="append", dest="paths", required=True, help="relative file.read path; repeat for multiple calls")
    file_observation_request.add_argument("--output", "-o", type=Path, required=True)
    file_observation_request.set_defaults(handler=_request_file_observations)

    file_observation_acquire = commands.add_parser("acquire-file-observations", help="acquire scoped file.read evidence and derive a replayable Effects scenario")
    file_observation_acquire.add_argument("source", type=Path)
    file_observation_acquire.add_argument("--request", type=Path, required=True)
    file_observation_acquire.add_argument("--root", type=Path, required=True)
    file_observation_acquire.add_argument(
        "--read-workers",
        type=int,
        metavar="N",
        help="physically acquire independent file.read calls with 1..64 worker threads; operational only",
    )
    file_observation_acquire.add_argument("--scenario-output", type=Path, required=True)
    file_observation_acquire.add_argument("--evidence-output", type=Path, required=True)
    file_observation_acquire.set_defaults(handler=_acquire_file_observations)

    effects_r2_check = commands.add_parser("check-effects-r2", help="parse/type-check physical-effect R2 source without touching a provider")
    effects_r2_check.add_argument("source", type=Path)
    effects_r2_check.set_defaults(handler=_check_effects_r2)

    effects_r2_scenario = commands.add_parser("scenario-effects-r2", help="write observation scenario skeleton for Effects R2 source")
    effects_r2_scenario.add_argument("source", type=Path)
    effects_r2_scenario.add_argument("--output", "-o", type=Path, required=True)
    effects_r2_scenario.set_defaults(handler=_scenario_effects_r2)

    effects_r2_compile = commands.add_parser("compile-effects-r2", help="compile Effects R2 source + observation scenario to portable Program IR")
    effects_r2_compile.add_argument("source", type=Path)
    effects_r2_compile.add_argument("--scenario", type=Path, required=True)
    effects_r2_compile.add_argument("--output", "-o", type=Path, required=True)
    effects_r2_compile.set_defaults(handler=_compile_effects_r2)

    effects_r2_plan = commands.add_parser("plan-effects-r2", help="plan physical effect intents from Program IR without committing them")
    effects_r2_plan.add_argument("program_ir", type=Path)
    effects_r2_plan.add_argument("--output", "-o", type=Path, required=True, help="portable plan/outbox artifact")
    effects_r2_plan.add_argument("--receipt", type=Path, help="optional plan receipt JSON")
    effects_r2_plan.add_argument("--expected-program-ir-hash")
    effects_r2_plan.add_argument("--expected-source-semantic-hash")
    effects_r2_plan.set_defaults(handler=_plan_effects_r2)

    authorize_file = commands.add_parser("authorize-file-effects-r2", help="authorize one planned file.replace batch for one exact filesystem root; does not commit it")
    authorize_file.add_argument("plan", type=Path)
    authorize_file.add_argument("--root", type=Path, required=True)
    authorize_file.add_argument("--output", "-o", type=Path, required=True, help="authority grant artifact")
    authorize_file.add_argument("--descriptor-output", type=Path, required=True, help="provider descriptor artifact")
    authorize_file.set_defaults(handler=_authorize_file_effects_r2)

    commit_file = commands.add_parser("commit-file-effects-r2", help="explicitly commit one authorized file.replace batch and finalize its proposed state")
    commit_file.add_argument("plan", type=Path)
    commit_file.add_argument("--grant", type=Path, required=True)
    commit_file.add_argument("--root", type=Path, required=True)
    commit_file.add_argument("--ledger", type=Path, required=True)
    commit_file.add_argument("--output", "-o", type=Path, required=True, help="command commit receipt artifact")
    commit_file.add_argument("--finalized", type=Path, required=True, help="finalized state transition artifact")
    commit_file.set_defaults(handler=_commit_file_effects_r2)

    run = commands.add_parser("run", help="validate and execute standalone Program IR V4 JSON")
    run.add_argument("program_ir", type=Path)
    run.add_argument("--output", "-o", type=Path)
    run.add_argument("--expected-program-ir-hash")
    run.add_argument("--expected-source-semantic-hash")
    run.add_argument(
        "--task-workers",
        type=int,
        metavar="N",
        help="physically execute Pure TASK_SCOPE children with 1..64 worker threads; operational only",
    )
    run.set_defaults(handler=_run)
    return parser


def _descriptor(_arguments: argparse.Namespace) -> int:
    print(_canonical_json({
        "schema": "TEV_SCRIPT_V2_DESCRIPTOR_V1",
        "language_version": LANGUAGE_VERSION_V2,
        "source_extension": ".tevs",
        "program_ir_schemas": [PROGRAM_IR_V4_PURE_SCHEMA, PROGRAM_IR_V4_RECURSIVE_SCHEMA, PROGRAM_IR_V4_EFFECTS_SCHEMA, PROGRAM_IR_V4_EFFECTS_R2_SCHEMA],
        "commands": ["check", "compile", "verify-signed-remote-module-manifest", "acquire-signed-remote-modules", "extract-signed-remote-module-bundle", "check-remote-module-manifest", "acquire-remote-modules", "extract-remote-module-bundle", "bundle-modules", "check-modules", "compile-modules", "check-effects", "scenario-effects", "compile-effects", "request-file-observations", "acquire-file-observations", "check-effects-r2", "scenario-effects-r2", "compile-effects-r2", "plan-effects-r2", "authorize-file-effects-r2", "commit-file-effects-r2", "run"],
        "runtime_requires_source_compiler": False,
        "boundaries": {
            "dynamic_code": False,
            "unbounded_loops": False,
            "uncontracted_recursion": False,
            "implicit_host_io": False,
            "runtime_source_compilation": False,
            "physical_effect_commit": "explicit_grant_only",
            "file_provider_batch": "single_file_replace_v1",
        },
    }))
    return 0


def _check(arguments: argparse.Namespace) -> int:
    compiled, ir = _compile_source(arguments.source)
    validation = validate_program_ir_v4(ir)
    print(_canonical_json({
        "schema": "TEV_SCRIPT_V2_CHECK_RESULT_V1",
        "status": "PASS_CANDIDATE",
        "source": arguments.source.as_posix(),
        "program_id": compiled.program_id,
        "language_version": compiled.language_version,
        "source_semantic_hash": compiled.semantic_hash,
        "entry_name": compiled.entry.name,
        "entry_profile": compiled.entry.function_kind,
        "program_ir_schema": validation.schema,
        "program_ir_hash": validation.program_ir_hash,
        "type_table_hash": validation.type_table_hash,
        "stable_release": False,
    }))
    return 0


def _compile(arguments: argparse.Namespace) -> int:
    compiled, ir = _compile_source(arguments.source)
    data = canonical_program_ir_v4_bytes(ir) + b"\n"
    _atomic_write(arguments.output, data)
    print(_canonical_json({
        "schema": "TEV_SCRIPT_V2_COMPILE_RESULT_V1",
        "status": "PASS_CANDIDATE",
        "source": arguments.source.as_posix(),
        "output": arguments.output.as_posix(),
        "program_id": compiled.program_id,
        "source_semantic_hash": compiled.semantic_hash,
        "entry_profile": compiled.entry.function_kind,
        "program_ir_schema": ir["schema"],
        "program_ir_hash": ir["program_ir_hash"],
        "artifact_commit": ARTIFACT_COMMIT_POLICY_V2,
        "stable_release": False,
    }))
    return 0



def _verify_signed_remote_module_manifest(arguments: argparse.Namespace) -> int:
    from .signed_remote_module_manifest_v2 import verify_signed_remote_module_manifest_v2
    raw = load_strict_json(arguments.signed_manifest)
    if not isinstance(raw, Mapping):
        raise TevScriptError("TEVS_V2_CLI_SIGNED_REMOTE_MODULE", "signed remote module manifest root must be an object")
    verified = verify_signed_remote_module_manifest_v2(raw, expected_public_key_sha256=arguments.expected_public_key_sha256)
    receipt = verified["verification"]
    print(_canonical_json({
        "schema": "TEV_SCRIPT_V2_SIGNED_REMOTE_MODULE_VERIFY_RESULT_V1",
        "status": "PASS",
        "signed_manifest": arguments.signed_manifest.as_posix(),
        "manifest_hash": receipt["manifest_hash"],
        "key_id": receipt["key_id"],
        "public_key_sha256": receipt["public_key_sha256"],
        "signature_sha256": receipt["signature_sha256"],
        "verification_hash": receipt["verification_hash"],
        "network_accessed": False,
        "runtime_network_acquisition": False,
    }))
    return 0


def _acquire_signed_remote_modules(arguments: argparse.Namespace) -> int:
    from .remote_module_acquisition_v2 import UrllibHttpsModuleTransportV2
    from .signed_remote_module_manifest_v2 import acquire_signed_remote_module_bundle_v2
    raw = load_strict_json(arguments.signed_manifest)
    if not isinstance(raw, Mapping):
        raise TevScriptError("TEVS_V2_CLI_SIGNED_REMOTE_MODULE", "signed remote module manifest root must be an object")
    transport = UrllibHttpsModuleTransportV2()
    result = acquire_signed_remote_module_bundle_v2(
        raw,
        expected_public_key_sha256=arguments.expected_public_key_sha256,
        transport=transport,
    )
    _atomic_write(arguments.output, (_canonical_json(result) + "\n").encode("utf-8"))
    verification = result["verification"]
    acquisition = result["acquisition"]
    print(_canonical_json({
        "schema": "TEV_SCRIPT_V2_SIGNED_REMOTE_MODULE_ACQUIRE_RESULT_V1",
        "status": "PASS",
        "signed_manifest": arguments.signed_manifest.as_posix(),
        "output": arguments.output.as_posix(),
        "signed_result_hash": result["signed_result_hash"],
        "manifest_hash": verification["manifest_hash"],
        "public_key_sha256": verification["public_key_sha256"],
        "verification_hash": verification["verification_hash"],
        "transport_descriptor_hash": acquisition["evidence"]["transport"]["descriptor_hash"],
        "evidence_hash": acquisition["evidence"]["evidence_hash"],
        "module_bundle_hash": acquisition["bundle"]["bundle_hash"],
        "module_lock_hash": acquisition["bundle"]["lock"]["lock_hash"],
        "network_accessed": True,
        "runtime_network_acquisition": False,
        "artifact_commit": ARTIFACT_COMMIT_POLICY_V2,
    }))
    return 0


def _extract_signed_remote_module_bundle(arguments: argparse.Namespace) -> int:
    from .signed_remote_module_manifest_v2 import validate_signed_remote_module_acquisition_result_v2
    raw = load_strict_json(arguments.acquisition)
    if not isinstance(raw, Mapping):
        raise TevScriptError("TEVS_V2_CLI_SIGNED_REMOTE_MODULE", "signed remote module acquisition root must be an object")
    result = validate_signed_remote_module_acquisition_result_v2(
        raw,
        expected_public_key_sha256=arguments.expected_public_key_sha256,
        expected_transport_descriptor_hash=arguments.expected_transport_descriptor_hash,
    )
    bundle = result["acquisition"]["bundle"]
    _atomic_write(arguments.output, (_canonical_json(bundle) + "\n").encode("utf-8"))
    print(_canonical_json({
        "schema": "TEV_SCRIPT_V2_SIGNED_REMOTE_MODULE_BUNDLE_EXTRACT_RESULT_V1",
        "status": "PASS",
        "acquisition": arguments.acquisition.as_posix(),
        "output": arguments.output.as_posix(),
        "signed_result_hash": result["signed_result_hash"],
        "manifest_hash": result["verification"]["manifest_hash"],
        "public_key_sha256": result["verification"]["public_key_sha256"],
        "verification_hash": result["verification"]["verification_hash"],
        "module_bundle_hash": bundle["bundle_hash"],
        "module_lock_hash": bundle["lock"]["lock_hash"],
        "network_accessed": False,
        "runtime_network_acquisition": False,
        "artifact_commit": ARTIFACT_COMMIT_POLICY_V2,
    }))
    return 0


def _check_remote_module_manifest(arguments: argparse.Namespace) -> int:
    from .remote_module_acquisition_v2 import validate_remote_module_manifest_v2
    raw = load_strict_json(arguments.manifest)
    if not isinstance(raw, Mapping):
        raise TevScriptError("TEVS_V2_CLI_REMOTE_MODULE_MANIFEST", "remote module manifest root must be an object")
    manifest = validate_remote_module_manifest_v2(raw)
    print(_canonical_json({
        "schema": "TEV_SCRIPT_V2_REMOTE_MODULE_MANIFEST_CHECK_RESULT_V1",
        "status": "PASS_CANDIDATE",
        "manifest": arguments.manifest.as_posix(),
        "manifest_hash": manifest["manifest_hash"],
        "module_count": len(manifest["entries"]),
        "module_ids": [item["module_id"] for item in manifest["entries"]],
        "network_accessed": False,
        "runtime_network_acquisition": False,
    }))
    return 0


def _acquire_remote_modules(arguments: argparse.Namespace) -> int:
    from .remote_module_acquisition_v2 import UrllibHttpsModuleTransportV2, acquire_remote_module_bundle_v2
    raw = load_strict_json(arguments.manifest)
    if not isinstance(raw, Mapping):
        raise TevScriptError("TEVS_V2_CLI_REMOTE_MODULE_MANIFEST", "remote module manifest root must be an object")
    transport = UrllibHttpsModuleTransportV2()
    result = acquire_remote_module_bundle_v2(raw, transport)
    _atomic_write(arguments.output, (_canonical_json(result) + "\n").encode("utf-8"))
    print(_canonical_json({
        "schema": "TEV_SCRIPT_V2_REMOTE_MODULE_ACQUISITION_RESULT_V1",
        "status": "PASS",
        "manifest": arguments.manifest.as_posix(),
        "output": arguments.output.as_posix(),
        "manifest_hash": result["manifest"]["manifest_hash"],
        "transport_descriptor_hash": result["evidence"]["transport"]["descriptor_hash"],
        "evidence_hash": result["evidence"]["evidence_hash"],
        "module_bundle_hash": result["bundle"]["bundle_hash"],
        "module_lock_hash": result["bundle"]["lock"]["lock_hash"],
        "module_count": len(result["bundle"]["modules"]),
        "network_accessed": True,
        "runtime_network_acquisition": False,
        "artifact_commit": ARTIFACT_COMMIT_POLICY_V2,
    }))
    return 0


def _extract_remote_module_bundle(arguments: argparse.Namespace) -> int:
    from .remote_module_acquisition_v2 import validate_remote_module_acquisition_result_v2
    raw = load_strict_json(arguments.acquisition)
    if not isinstance(raw, Mapping):
        raise TevScriptError("TEVS_V2_CLI_REMOTE_MODULE_ACQUISITION", "remote module acquisition root must be an object")
    result = validate_remote_module_acquisition_result_v2(
        raw,
        expected_transport_descriptor_hash=arguments.expected_transport_descriptor_hash,
        expected_manifest_hash=arguments.expected_manifest_hash,
    )
    bundle = result["bundle"]
    _atomic_write(arguments.output, (_canonical_json(bundle) + "\n").encode("utf-8"))
    print(_canonical_json({
        "schema": "TEV_SCRIPT_V2_REMOTE_MODULE_BUNDLE_EXTRACT_RESULT_V1",
        "status": "PASS",
        "acquisition": arguments.acquisition.as_posix(),
        "output": arguments.output.as_posix(),
        "result_hash": result["result_hash"],
        "manifest_hash": result["manifest"]["manifest_hash"],
        "evidence_hash": result["evidence"]["evidence_hash"],
        "transport_descriptor_hash": result["evidence"]["transport"]["descriptor_hash"],
        "module_bundle_hash": bundle["bundle_hash"],
        "module_lock_hash": bundle["lock"]["lock_hash"],
        "network_accessed": False,
        "runtime_network_acquisition": False,
        "artifact_commit": ARTIFACT_COMMIT_POLICY_V2,
    }))
    return 0


def _bundle_modules(arguments: argparse.Namespace) -> int:
    from .module_linker_v2 import build_module_bundle_v2, parse_pure_module_v2
    sources: dict[str, str] = {}
    source_files: list[str] = []
    for path in arguments.modules:
        text = path.read_text(encoding="utf-8")
        module = parse_pure_module_v2(text)
        if module.module_id in sources:
            raise TevScriptError("TEVS_V2_CLI_MODULE_DUPLICATE", f"duplicate acquired module id {module.module_id!r}")
        sources[module.module_id] = text
        source_files.append(path.as_posix())
    bundle = build_module_bundle_v2(sources)
    _atomic_write(arguments.output, (_canonical_json(bundle) + "\n").encode("utf-8"))
    print(_canonical_json({
        "schema": "TEV_SCRIPT_V2_MODULE_BUNDLE_RESULT_V1",
        "status": "PASS_CANDIDATE",
        "output": arguments.output.as_posix(),
        "module_count": len(bundle["modules"]),
        "module_ids": [item["module_id"] for item in bundle["modules"]],
        "bundle_hash": bundle["bundle_hash"],
        "lock_hash": bundle["lock"]["lock_hash"],
        "source_files": source_files,
        "runtime_module_acquisition": False,
        "network_acquisition": False,
        "artifact_commit": ARTIFACT_COMMIT_POLICY_V2,
    }))
    return 0


def _check_modules(arguments: argparse.Namespace) -> int:
    linked, ir, bundle = _compile_module_source(arguments.source, arguments.bundle)
    validation = validate_program_ir_v4(ir)
    print(_canonical_json({
        "schema": "TEV_SCRIPT_V2_MODULE_CHECK_RESULT_V1",
        "status": "PASS_CANDIDATE",
        "source": arguments.source.as_posix(),
        "bundle": arguments.bundle.as_posix(),
        "program_id": linked.compiled.program_id,
        "source_semantic_hash": linked.compiled.semantic_hash,
        "entry_profile": linked.compiled.entry.function_kind,
        "dependency_lock_hash": linked.dependency_lock_hash,
        "module_lock_hash": linked.module_lock_hash,
        "module_bundle_hash": bundle["bundle_hash"],
        "link_receipt_hash": linked.link_receipt_hash,
        "program_ir_schema": validation.schema,
        "program_ir_hash": validation.program_ir_hash,
        "runtime_module_acquisition": False,
        "runtime_requires_source_compiler": False,
    }))
    return 0


def _compile_modules(arguments: argparse.Namespace) -> int:
    linked, ir, bundle = _compile_module_source(arguments.source, arguments.bundle)
    data = canonical_program_ir_v4_bytes(ir) + b"\n"
    _atomic_write(arguments.output, data)
    print(_canonical_json({
        "schema": "TEV_SCRIPT_V2_MODULE_COMPILE_RESULT_V1",
        "status": "PASS_CANDIDATE",
        "source": arguments.source.as_posix(),
        "bundle": arguments.bundle.as_posix(),
        "output": arguments.output.as_posix(),
        "program_id": linked.compiled.program_id,
        "source_semantic_hash": linked.compiled.semantic_hash,
        "entry_profile": linked.compiled.entry.function_kind,
        "dependency_lock_hash": linked.dependency_lock_hash,
        "module_lock_hash": linked.module_lock_hash,
        "module_bundle_hash": bundle["bundle_hash"],
        "link_receipt_hash": linked.link_receipt_hash,
        "program_ir_schema": ir["schema"],
        "program_ir_hash": ir["program_ir_hash"],
        "runtime_module_acquisition": False,
        "artifact_commit": ARTIFACT_COMMIT_POLICY_V2,
    }))
    return 0


def _check_effects(arguments: argparse.Namespace) -> int:
    from .source_effect_program_v2 import compile_effect_program_v2
    source = arguments.source.read_text(encoding="utf-8")
    compiled = compile_effect_program_v2(source)
    print(_canonical_json({
        "schema": "TEV_SCRIPT_V2_EFFECTS_CHECK_RESULT_V1",
        "status": "PASS_CANDIDATE",
        "source": arguments.source.as_posix(),
        "program_id": compiled.program_id,
        "language_version": compiled.language_version,
        "source_semantic_hash": compiled.semantic_hash,
        "state_schema_hash": compiled.state_schema_hash,
        "initial_state_hash": compiled.initial_state_hash,
        "capability_table_hash": compiled.capability_table_hash,
        "actions": [{"name": name, "action_hash": action_hash} for name, action_hash in compiled.action_hashes],
        "entry_name": compiled.entry.name,
        "entry_action": compiled.entry.action_name,
        "entry_hash": compiled.entry.entry_hash,
        "stable_release": False,
    }))
    return 0


def _scenario_effects(arguments: argparse.Namespace) -> int:
    from .source_effect_program_v2 import compile_effect_program_v2, effect_scenario_skeleton_v2
    compiled = compile_effect_program_v2(arguments.source.read_text(encoding="utf-8"))
    skeleton = effect_scenario_skeleton_v2(compiled)
    _atomic_write(arguments.output, (_canonical_json(skeleton) + "\n").encode("utf-8"))
    print(_canonical_json({
        "schema": "TEV_SCRIPT_V2_EFFECTS_SCENARIO_RESULT_V1",
        "status": "PASS_CANDIDATE",
        "source": arguments.source.as_posix(),
        "output": arguments.output.as_posix(),
        "source_semantic_hash": compiled.semantic_hash,
        "capability_table_hash": compiled.capability_table_hash,
        "capability_count": len(compiled.capabilities.contracts),
        "artifact_commit": ARTIFACT_COMMIT_POLICY_V2,
    }))
    return 0


def _compile_effects(arguments: argparse.Namespace) -> int:
    from .source_effect_program_v2 import build_effect_program_ir_v4, compile_effect_program_v2
    compiled = compile_effect_program_v2(arguments.source.read_text(encoding="utf-8"))
    scenario = load_strict_json(arguments.scenario)
    if not isinstance(scenario, Mapping):
        raise TevScriptError("TEVS_V2_CLI_EFFECTS_SCENARIO", "effects scenario root must be an object")
    ir = build_effect_program_ir_v4(compiled, scenario)
    validation = validate_program_ir_v4(ir)
    _atomic_write(arguments.output, canonical_program_ir_v4_bytes(ir) + b"\n")
    print(_canonical_json({
        "schema": "TEV_SCRIPT_V2_EFFECTS_COMPILE_RESULT_V1",
        "status": "PASS_CANDIDATE",
        "source": arguments.source.as_posix(),
        "scenario": arguments.scenario.as_posix(),
        "output": arguments.output.as_posix(),
        "program_id": compiled.program_id,
        "source_semantic_hash": compiled.semantic_hash,
        "entry_profile": "effects",
        "program_ir_schema": validation.schema,
        "program_ir_hash": validation.program_ir_hash,
        "state_schema_hash": validation.state_schema_hash,
        "capability_table_hash": validation.capability_table_hash,
        "action_hash": validation.action_hash,
        "scenario_hash": validation.scenario_hash,
        "artifact_commit": ARTIFACT_COMMIT_POLICY_V2,
        "stable_release": False,
    }))
    return 0


def _request_file_observations(arguments: argparse.Namespace) -> int:
    from .file_observation_acquisition_v2 import build_file_read_acquisition_request_v2
    compiled = _compile_effect_source_for_observation_acquisition(arguments.source)
    request = build_file_read_acquisition_request_v2(compiled.capabilities, arguments.paths)
    _atomic_write(arguments.output, (_canonical_json(request) + "\n").encode("utf-8"))
    print(_canonical_json({
        "schema": "TEV_SCRIPT_V2_FILE_OBSERVATION_REQUEST_RESULT_V1",
        "status": "PASS_CANDIDATE",
        "source": arguments.source.as_posix(),
        "output": arguments.output.as_posix(),
        "source_semantic_hash": compiled.semantic_hash,
        "capability_table_hash": compiled.capability_table_hash,
        "request_hash": request["request_hash"],
        "call_count": len(request["calls"]),
        "host_observations_acquired": False,
        "artifact_commit": ARTIFACT_COMMIT_POLICY_V2,
    }))
    return 0


def _acquire_file_observations(arguments: argparse.Namespace) -> int:
    from .file_observation_acquisition_v2 import (
        acquire_file_read_observations_v2,
        scenario_from_file_read_evidence_v2,
    )
    from .ir_v4_effects import build_effect_scenario_v4
    compiled = _compile_effect_source_for_observation_acquisition(arguments.source)
    request = load_strict_json(arguments.request)
    if not isinstance(request, Mapping):
        raise TevScriptError("TEVS_V2_CLI_FILE_OBSERVATION_REQUEST", "file observation request root must be an object")
    execution_strategy = None
    acquisition_scheduler_descriptor = None
    if arguments.read_workers is not None:
        from .file_observation_scheduler_v2 import BoundedThreadFileReadAcquisitionStrategyV2

        execution_strategy = BoundedThreadFileReadAcquisitionStrategyV2(arguments.read_workers)
        acquisition_scheduler_descriptor = execution_strategy.descriptor()
    evidence = acquire_file_read_observations_v2(
        request,
        compiled.capabilities,
        arguments.root,
        execution_strategy=execution_strategy,
    )
    scenario = scenario_from_file_read_evidence_v2(evidence, compiled.capabilities)
    validated_scenario = build_effect_scenario_v4(scenario, compiled.types.table, compiled.capabilities)
    _atomic_write(arguments.evidence_output, (_canonical_json(evidence) + "\n").encode("utf-8"))
    _atomic_write(arguments.scenario_output, (_canonical_json(scenario) + "\n").encode("utf-8"))
    summary = {
        "schema": "TEV_SCRIPT_V2_FILE_OBSERVATION_ACQUISITION_RESULT_V1",
        "status": "PASS",
        "source": arguments.source.as_posix(),
        "request": arguments.request.as_posix(),
        "scenario_output": arguments.scenario_output.as_posix(),
        "evidence_output": arguments.evidence_output.as_posix(),
        "source_semantic_hash": compiled.semantic_hash,
        "capability_table_hash": compiled.capability_table_hash,
        "scenario_hash": validated_scenario.scenario_hash,
        "evidence_hash": evidence["evidence_hash"],
        "provider_descriptor_hash": evidence["provider"]["descriptor_hash"],
        "authority_scope_hash": evidence["authority_scope_hash"],
        "call_count": len(evidence["calls"]),
        "host_observations_acquired": True,
        "physical_effects_committed": False,
        "state_finalized": False,
        "artifact_commit": ARTIFACT_COMMIT_POLICY_V2,
    }
    if acquisition_scheduler_descriptor is not None:
        summary["acquisition_scheduler"] = acquisition_scheduler_descriptor
    print(_canonical_json(summary))
    return 0


def _check_effects_r2(arguments: argparse.Namespace) -> int:
    from .source_effect_program_v2 import compile_effect_command_program_v2
    compiled = compile_effect_command_program_v2(arguments.source.read_text(encoding="utf-8"))
    print(_canonical_json({
        "schema": "TEV_SCRIPT_V2_EFFECTS_R2_CHECK_RESULT_V1",
        "status": "PASS_CANDIDATE",
        "source": arguments.source.as_posix(),
        "program_id": compiled.program_id,
        "language_version": compiled.language_version,
        "source_semantic_hash": compiled.semantic_hash,
        "state_schema_hash": compiled.state_schema_hash,
        "initial_state_hash": compiled.initial_state_hash,
        "capability_table_hash": compiled.capability_table_hash,
        "command_table_hash": compiled.command_table_hash,
        "actions": [{"name": name, "action_hash": action_hash} for name, action_hash in compiled.action_hashes],
        "entry_name": compiled.entry.name,
        "entry_action": compiled.entry.action_name,
        "entry_hash": compiled.entry.entry_hash,
        "physical_effects_committed": False,
        "stable_release": False,
    }))
    return 0


def _scenario_effects_r2(arguments: argparse.Namespace) -> int:
    from .source_effect_program_v2 import compile_effect_command_program_v2, effect_scenario_skeleton_v2
    compiled = compile_effect_command_program_v2(arguments.source.read_text(encoding="utf-8"))
    skeleton = effect_scenario_skeleton_v2(compiled)
    _atomic_write(arguments.output, (_canonical_json(skeleton) + "\n").encode("utf-8"))
    print(_canonical_json({
        "schema": "TEV_SCRIPT_V2_EFFECTS_R2_SCENARIO_RESULT_V1",
        "status": "PASS_CANDIDATE",
        "source": arguments.source.as_posix(),
        "output": arguments.output.as_posix(),
        "source_semantic_hash": compiled.semantic_hash,
        "capability_table_hash": compiled.capability_table_hash,
        "command_table_hash": compiled.command_table_hash,
        "physical_effects_committed": False,
        "artifact_commit": ARTIFACT_COMMIT_POLICY_V2,
    }))
    return 0


def _compile_effects_r2(arguments: argparse.Namespace) -> int:
    from .program_ir_v4_effect_commands import canonical_program_ir_v4_effects_r2_bytes, validate_program_ir_v4_effects_r2
    from .source_effect_program_v2 import build_effect_command_program_ir_v4, compile_effect_command_program_v2
    compiled = compile_effect_command_program_v2(arguments.source.read_text(encoding="utf-8"))
    scenario = load_strict_json(arguments.scenario)
    if not isinstance(scenario, Mapping):
        raise TevScriptError("TEVS_V2_CLI_EFFECTS_R2_SCENARIO", "Effects R2 scenario root must be an object")
    ir = build_effect_command_program_ir_v4(compiled, scenario)
    validation = validate_program_ir_v4_effects_r2(ir)
    _atomic_write(arguments.output, canonical_program_ir_v4_effects_r2_bytes(ir) + b"\n")
    print(_canonical_json({
        "schema": "TEV_SCRIPT_V2_EFFECTS_R2_COMPILE_RESULT_V1",
        "status": "PASS_CANDIDATE",
        "source": arguments.source.as_posix(),
        "scenario": arguments.scenario.as_posix(),
        "output": arguments.output.as_posix(),
        "program_id": compiled.program_id,
        "source_semantic_hash": compiled.semantic_hash,
        "program_ir_schema": validation.schema,
        "program_ir_hash": validation.program_ir_hash,
        "state_schema_hash": validation.state_schema_hash,
        "capability_table_hash": validation.capability_table_hash,
        "command_table_hash": validation.command_table_hash,
        "action_hash": validation.action_hash,
        "scenario_hash": validation.scenario_hash,
        "physical_effects_committed": False,
        "artifact_commit": ARTIFACT_COMMIT_POLICY_V2,
        "stable_release": False,
    }))
    return 0


def _plan_effects_r2(arguments: argparse.Namespace) -> int:
    from .program_ir_v4_effect_commands import plan_program_ir_v4_effects_r2
    raw = load_strict_json(arguments.program_ir)
    if not isinstance(raw, Mapping):
        raise TevScriptError("TEVS_V2_CLI_EFFECTS_R2_PROGRAM_IR", "Effects R2 Program IR root must be an object")
    result = plan_program_ir_v4_effects_r2(
        raw,
        expected_program_ir_hash=arguments.expected_program_ir_hash,
        expected_source_semantic_hash=arguments.expected_source_semantic_hash,
    )
    _atomic_write(arguments.output, (_canonical_json(result.plan_artifact) + "\n").encode("utf-8"))
    receipt_payload = asdict(result.receipt)
    if arguments.receipt is not None:
        _atomic_write(arguments.receipt, (_canonical_json(receipt_payload) + "\n").encode("utf-8"))
    print(_canonical_json({
        "schema": "TEV_SCRIPT_V2_EFFECTS_R2_PLAN_RESULT_V1",
        "status": result.receipt.status,
        "program_ir": arguments.program_ir.as_posix(),
        "output": arguments.output.as_posix(),
        "receipt_output": arguments.receipt.as_posix() if arguments.receipt is not None else None,
        "program_ir_hash": result.receipt.program_ir_hash,
        "source_semantic_hash": result.receipt.source_semantic_hash,
        "planning_receipt_hash": result.receipt.planning_receipt_hash,
        "command_batch_hash": result.receipt.command_batch_hash,
        "proposed_final_state_hash": result.receipt.proposed_final_state_hash,
        "plan_artifact_hash": result.receipt.plan_artifact_hash,
        "physical_effects_committed": False,
        "state_finalized": False,
        "artifact_commit": ARTIFACT_COMMIT_POLICY_V2,
    }))
    return 0


def _authorize_file_effects_r2(arguments: argparse.Namespace) -> int:
    from .file_effect_provider_v2 import AtomicFileReplaceProviderV2, FILE_REPLACE_COMMAND_ID_V2
    from .ir_v4_effect_commands import (
        build_effect_authority_grant_v4,
        effect_authority_grant_to_dict_v4,
        effect_provider_descriptor_to_dict_v4,
        load_planned_effect_transition_v4,
    )
    raw = load_strict_json(arguments.plan)
    if not isinstance(raw, Mapping):
        raise TevScriptError("TEVS_V2_CLI_FILE_PLAN", "file authorization plan root must be an object")
    planned = load_planned_effect_transition_v4(raw)
    if len(planned.command_batch.intents) != 1:
        raise TevScriptError("TEVS_V2_CLI_FILE_BATCH", "file provider R2 authorizes exactly one file.replace intent per batch")
    intent = planned.command_batch.intents[0]
    if intent.command_id != FILE_REPLACE_COMMAND_ID_V2:
        raise TevScriptError("TEVS_V2_CLI_FILE_COMMAND", f"file provider cannot authorize command {intent.command_id!r}")
    provider = AtomicFileReplaceProviderV2(arguments.root, contract_hash=intent.contract_hash)
    grant = build_effect_authority_grant_v4(
        provider.descriptor,
        planned.command_batch,
        allowed_contract_hashes=[intent.contract_hash],
        authority_scope_hash=provider.scope.scope_hash,
    )
    descriptor_wire = effect_provider_descriptor_to_dict_v4(provider.descriptor)
    grant_wire = effect_authority_grant_to_dict_v4(grant)
    _atomic_write(arguments.descriptor_output, (_canonical_json(descriptor_wire) + "\n").encode("utf-8"))
    _atomic_write(arguments.output, (_canonical_json(grant_wire) + "\n").encode("utf-8"))
    print(_canonical_json({
        "schema": "TEV_SCRIPT_V2_FILE_EFFECT_AUTHORIZATION_RESULT_V1",
        "status": "AUTHORIZED_NOT_COMMITTED",
        "plan": arguments.plan.as_posix(),
        "root": provider.scope.root,
        "authority_scope_hash": provider.scope.scope_hash,
        "provider_descriptor_hash": provider.descriptor.descriptor_hash,
        "batch_hash": planned.command_batch.batch_hash,
        "intent_hash": intent.intent_hash,
        "contract_hash": intent.contract_hash,
        "grant_hash": grant.grant_hash,
        "grant_output": arguments.output.as_posix(),
        "descriptor_output": arguments.descriptor_output.as_posix(),
        "physical_effects_committed": False,
        "state_finalized": False,
        "artifact_commit": ARTIFACT_COMMIT_POLICY_V2,
    }))
    return 0


def _commit_file_effects_r2(arguments: argparse.Namespace) -> int:
    from .effect_commit_ledger_v2 import JsonEffectCommitLedgerV4
    from .file_effect_provider_v2 import AtomicFileReplaceProviderV2, FILE_REPLACE_COMMAND_ID_V2
    from .ir_v4_effect_commands import (
        commit_effect_command_batch_v4,
        effect_command_commit_receipt_to_dict_v4,
        finalized_effect_transition_to_dict_v4,
        finalize_effect_transition_v4,
        load_effect_authority_grant_v4,
        load_planned_effect_transition_v4,
    )
    raw_plan = load_strict_json(arguments.plan)
    raw_grant = load_strict_json(arguments.grant)
    if not isinstance(raw_plan, Mapping) or not isinstance(raw_grant, Mapping):
        raise TevScriptError("TEVS_V2_CLI_FILE_ARTIFACT", "file commit plan/grant roots must be objects")
    planned = load_planned_effect_transition_v4(raw_plan)
    grant = load_effect_authority_grant_v4(raw_grant)
    if len(planned.command_batch.intents) != 1:
        raise TevScriptError("TEVS_V2_CLI_FILE_BATCH", "file provider R2 commits exactly one file.replace intent per batch")
    intent = planned.command_batch.intents[0]
    if intent.command_id != FILE_REPLACE_COMMAND_ID_V2:
        raise TevScriptError("TEVS_V2_CLI_FILE_COMMAND", f"file provider cannot commit command {intent.command_id!r}")
    provider = AtomicFileReplaceProviderV2(arguments.root, contract_hash=intent.contract_hash)
    # Reject a root/provider mismatch before invoking the physical provider.
    if grant.batch_hash != planned.command_batch.batch_hash:
        raise TevScriptError("TEVS_V2_CLI_FILE_GRANT_BATCH", "authority grant is bound to a different batch")
    if grant.provider_descriptor_hash != provider.descriptor.descriptor_hash:
        raise TevScriptError("TEVS_V2_CLI_FILE_GRANT_PROVIDER", "authority grant is bound to a different file provider implementation")
    if grant.authority_scope_hash != provider.scope.scope_hash:
        raise TevScriptError("TEVS_V2_CLI_FILE_GRANT_SCOPE", "authority grant is bound to a different filesystem root")
    ledger = JsonEffectCommitLedgerV4(arguments.ledger)
    commit = commit_effect_command_batch_v4(planned.command_batch, provider, grant, ledger)
    commit_wire = effect_command_commit_receipt_to_dict_v4(commit)
    _atomic_write(arguments.output, (_canonical_json(commit_wire) + "\n").encode("utf-8"))
    if commit.status != "PASS":
        print(_canonical_json({
            "schema": "TEV_SCRIPT_V2_FILE_EFFECT_COMMIT_RESULT_V1",
            "status": "FAIL_NOT_FINALIZED",
            "batch_hash": planned.command_batch.batch_hash,
            "commit_receipt_hash": commit.receipt_hash,
            "commit_output": arguments.output.as_posix(),
            "ledger": arguments.ledger.as_posix(),
            "physical_effects_committed": False,
            "state_finalized": False,
        }))
        return 3
    finalized = finalize_effect_transition_v4(planned, commit)
    finalized_wire = finalized_effect_transition_to_dict_v4(finalized)
    _atomic_write(arguments.finalized, (_canonical_json(finalized_wire) + "\n").encode("utf-8"))
    print(_canonical_json({
        "schema": "TEV_SCRIPT_V2_FILE_EFFECT_COMMIT_RESULT_V1",
        "status": "PASS_FINALIZED",
        "plan": arguments.plan.as_posix(),
        "grant": arguments.grant.as_posix(),
        "root": provider.scope.root,
        "authority_scope_hash": provider.scope.scope_hash,
        "provider_descriptor_hash": provider.descriptor.descriptor_hash,
        "authority_grant_hash": grant.grant_hash,
        "batch_hash": planned.command_batch.batch_hash,
        "commit_receipt_hash": commit.receipt_hash,
        "provider_effect_receipt_hashes": [item.provider_effect_receipt_hash for item in commit.intent_receipts],
        "finalized_receipt_hash": finalized.receipt_hash,
        "final_state_hash": finalized.final_state_hash,
        "ledger": arguments.ledger.as_posix(),
        "ledger_hash": ledger.ledger_hash,
        "ledger_entries": ledger.entry_count,
        "provider_invocations": provider.commit_calls,
        "commit_output": arguments.output.as_posix(),
        "finalized_output": arguments.finalized.as_posix(),
        "physical_effects_committed": True,
        "state_finalized": True,
        "artifact_commit": ARTIFACT_COMMIT_POLICY_V2,
    }))
    return 0

def _run(arguments: argparse.Namespace) -> int:
    raw = load_strict_json(arguments.program_ir)
    if not isinstance(raw, Mapping):
        raise TevScriptError("TEVS_V2_CLI_PROGRAM_IR", "Program IR root must be an object")
    if raw.get("schema") == PROGRAM_IR_V4_EFFECTS_R2_SCHEMA:
        raise TevScriptError(
            "TEVS_V2_CLI_R2_PLAN_REQUIRED",
            "Effects R2 Program IR contains physical effect intents; use plan-effects-r2. run never commits or finalizes R2 effects.",
        )
    task_strategy = None
    task_scheduler_descriptor = None
    if arguments.task_workers is not None:
        # Lazy import keeps the default runtime free of thread-pool machinery.
        from .task_scheduler_v2 import BoundedThreadTaskStrategyV2

        task_strategy = BoundedThreadTaskStrategyV2(arguments.task_workers)
        task_scheduler_descriptor = task_strategy.descriptor()
    receipt = run_program_ir_v4(
        raw,
        expected_program_ir_hash=arguments.expected_program_ir_hash,
        expected_source_semantic_hash=arguments.expected_source_semantic_hash,
        task_strategy=task_strategy,
    )
    payload = asdict(receipt)
    output = (_canonical_json(payload) + "\n").encode("utf-8")
    if arguments.output is None:
        sys.stdout.buffer.write(output)
    else:
        _atomic_write(arguments.output, output)
        summary = {
            "schema": "TEV_SCRIPT_V2_RUN_RESULT_V1",
            "status": "PASS",
            "program_ir": arguments.program_ir.as_posix(),
            "output": arguments.output.as_posix(),
            "program_ir_hash": receipt.program_ir_hash,
            "source_semantic_hash": receipt.source_semantic_hash,
            "receipt_hash": receipt.receipt_hash,
            "artifact_commit": ARTIFACT_COMMIT_POLICY_V2,
        }
        if task_scheduler_descriptor is not None:
            summary["task_scheduler"] = task_scheduler_descriptor
        if hasattr(receipt, "result_type"):
            summary["profile"] = "recursive" if raw.get("profile") == "recursive" else "pure"
            summary["result_type"] = receipt.result_type
            summary["result_hash"] = receipt.result_hash
        else:
            summary["profile"] = "effects"
            summary["final_state_hash"] = receipt.final_state_hash
            summary["transition_receipt_hash"] = receipt.transition_receipt_hash
            summary["observation_calls"] = receipt.observation_calls
        print(_canonical_json(summary))
    return 0


def _compile_effect_source_for_observation_acquisition(path: Path):
    from .source_effect_program_v2 import compile_effect_command_program_v2, compile_effect_program_v2
    source = path.read_text(encoding="utf-8")
    try:
        return compile_effect_program_v2(source)
    except TevScriptError as error:
        if error.diagnostic.code != "TEVS_V2_EFFECT_R2_REQUIRED":
            raise
    return compile_effect_command_program_v2(source)


def _compile_module_source(source_path: Path, bundle_path: Path):
    from .module_linker_v2 import compile_program_from_module_bundle_v2, validate_module_bundle_v2
    source = source_path.read_text(encoding="utf-8")
    raw = load_strict_json(bundle_path)
    if not isinstance(raw, Mapping):
        raise TevScriptError("TEVS_V2_CLI_MODULE_BUNDLE", "module bundle root must be an object")
    bundle = validate_module_bundle_v2(raw)
    linked = compile_program_from_module_bundle_v2(source, bundle)
    compiled = linked.compiled
    if compiled.entry.function_kind == "pure":
        ir = export_program_ir_v4_pure(compiled)
    elif compiled.entry.function_kind == "recursive":
        ir = export_program_ir_v4_recursive(compiled)
    else:
        raise TevScriptError("TEVS_V2_CLI_MODULE_PROFILE", f"unsupported module-linked entry profile {compiled.entry.function_kind!r}")
    return linked, ir, bundle


def _compile_source(path: Path):
    from .source_program_v2 import compile_program_v2
    source = path.read_text(encoding="utf-8")
    compiled = compile_program_v2(source)
    if compiled.entry.function_kind == "pure":
        ir = export_program_ir_v4_pure(compiled)
    elif compiled.entry.function_kind == "recursive":
        ir = export_program_ir_v4_recursive(compiled)
    else:
        raise TevScriptError("TEVS_V2_CLI_PROFILE", f"unsupported V2 entry profile {compiled.entry.function_kind!r}")
    return compiled, ir


def _atomic_write(path: Path, data: bytes) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def main(argv: list[str] | None = None) -> int:
    try:
        arguments = build_parser().parse_args(argv)
        return int(arguments.handler(arguments))
    except TevScriptError as error:
        print(_canonical_json({
            "schema": "TEV_SCRIPT_V2_DIAGNOSTIC_V1",
            "status": "FAIL",
            "diagnostic": error.diagnostic.to_dict(),
        }), file=sys.stderr)
        return 2
    except (OSError, UnicodeError, ValueError) as error:
        print(_canonical_json({
            "schema": "TEV_SCRIPT_V2_HOST_IO_ERROR_V1",
            "status": "FAIL",
            "error": type(error).__name__,
            "message": str(error),
        }), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
