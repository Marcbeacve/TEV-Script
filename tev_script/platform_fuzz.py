from __future__ import annotations

import copy
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import random
import shutil
import subprocess
from typing import Callable

from .version import CURRENT_LANGUAGE_VERSION

CaseExecutor = Callable[[Path, dict[str, object], str], dict[str, object]]
ToolResolver = Callable[[str], str | None]

CASE_KIND_ORDER = (
    "control_flow",
    "branch_apply",
    "invoke_pure",
    "invoke_recursive",
    "invoke_effects",
    "proof_apply",
)
REQUIRED_CASE_KINDS = frozenset(CASE_KIND_ORDER)


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def _digest(seed: int, index: int, label: str) -> str:
    return hashlib.sha256(
        f"tevscript-fuzz:{seed}:{index}:{label}".encode("utf-8")
    ).hexdigest()


def _process_header(
    program_id: str,
    authority: str,
    quantum_steps: int,
) -> list[str]:
    return [
        f'process {program_id} version "{CURRENT_LANGUAGE_VERSION}"',
        f"authority {authority}",
        f"quantum_steps {quantum_steps}",
    ]


def _render(statements: list[str]) -> str:
    return ";\n".join(statements) + ";\n"


def _signed_int_expression(name: str, delta: int) -> str:
    if delta >= 0:
        return f"{name}+{delta}"
    return f"{name}-{abs(delta)}"


def generate_cases(seed: int, count: int) -> tuple[dict[str, object], ...]:
    if not isinstance(seed, int) or isinstance(seed, bool):
        raise ValueError("seed must be an integer")
    if (
        not isinstance(count, int)
        or isinstance(count, bool)
        or count < 1
        or count > 10_000
    ):
        raise ValueError("count must be between 1 and 10000")

    rng = random.Random(seed)
    cases: list[dict[str, object]] = []
    for index in range(count):
        case_kind = CASE_KIND_ORDER[index % len(CASE_KIND_ORDER)]
        quantum_steps = rng.randint(1, 8)
        epochs = rng.randint(1, 3)
        authority = _digest(seed, index, "authority")
        program_id = f"Fuzz_{seed}_{index}"
        unit_sources: dict[str, str] = {}
        extra: dict[str, object] = {}

        if case_kind == "control_flow":
            labels = rng.randint(1, 6)
            statements = _process_header(program_id, authority, quantum_steps)
            statements.append("field actual = []")
            for label in range(labels):
                if rng.random() < 0.28:
                    body = "halt"
                else:
                    body = f"jump L{rng.randrange(labels)}"
                statements.append(f"label L{label} = {body}")
            statements.append("entry L0")
            source = _render(statements)

        elif case_kind == "branch_apply":
            quantum_steps = max(3, quantum_steps)
            before_value = rng.randint(-50, 50)
            after_value = before_value + rng.randint(1, 7)
            effect_hash = _digest(seed, index, "effect")
            resource_hash = _digest(seed, index, "resource")
            statements = _process_header(program_id, authority, quantum_steps)
            statements.extend(
                [
                    f"fact before = fuzz.state [{before_value}]",
                    f"fact after = fuzz.state [{after_value}]",
                    "field actual = [before]",
                    (
                        f"transform advance effects {effect_hash} resources "
                        f"{resource_hash} remove [before] add [after]"
                    ),
                    "label L0 = branch_fact before L1 L2",
                    "label L1 = apply advance L2",
                    "label L2 = halt",
                    "entry L0",
                ]
            )
            source = _render(statements)

        elif case_kind == "invoke_pure":
            quantum_steps = max(2, quantum_steps)
            value = rng.randint(-30, 30)
            delta = rng.randint(-9, 9)
            unit_sources["Calc"] = (
                'script Calc version "2.0.0"; '
                f"fn shift(x:Int)->Int={_signed_int_expression('x', delta)}; "
                f"entry main:Int=shift({value});"
            )
            statements = _process_header(program_id, authority, quantum_steps)
            statements.extend(
                [
                    "unit Calc profile pure",
                    "field actual = []",
                    "label L0 = invoke_v4 Calc result fuzz.total.result L1",
                    "label L1 = halt",
                    "entry L0",
                ]
            )
            source = _render(statements)

        elif case_kind == "invoke_recursive":
            quantum_steps = max(2, quantum_steps)
            value = rng.randint(0, 5)
            unit_sources["Rec"] = (
                'script Rec version "2.0.0"; '
                "recursive fn factorial(n:Int)->Int decreases n max_depth 8 = "
                "if n==0 then 1 else n*self(n-1); "
                f"entry main:Int=factorial({value});"
            )
            statements = _process_header(program_id, authority, quantum_steps)
            statements.extend(
                [
                    "unit Rec profile recursive",
                    "field actual = []",
                    "label L0 = invoke_v4 Rec result fuzz.total.result L1",
                    "label L1 = halt",
                    "entry L0",
                ]
            )
            source = _render(statements)

        elif case_kind == "invoke_effects":
            quantum_steps = max(2, quantum_steps)
            effect_return = rng.randint(-20, 20)
            unit_sources["Effects"] = (
                'script Effects version "2.0.0"; '
                "state count:Int=0; "
                "capability observation sensor.read(Int)->Int; "
                "action tick() { observe sample=sensor.read(count); set count=sample; } "
                "entry main=tick();"
            )
            statements = _process_header(program_id, authority, quantum_steps)
            statements.extend(
                [
                    "unit Effects profile effects",
                    "field actual = []",
                    "label L0 = invoke_v4 Effects result fuzz.total.result L1",
                    "label L1 = halt",
                    "entry L0",
                ]
            )
            source = _render(statements)
            extra["effect_return"] = effect_return

        else:  # proof_apply
            quantum_steps = max(2, quantum_steps)
            proof_value = rng.randint(-100, 100)
            statements = _process_header(program_id, authority, quantum_steps)
            statements.extend(
                [
                    f"fact admitted = fuzz.proof [{proof_value}]",
                    "field actual = []",
                    "label L0 = halt",
                    "entry L0",
                ]
            )
            source = _render(statements)
            extra.update(
                {
                    "proof_value": proof_value,
                    "proof_requirement_hash": _digest(seed, index, "requirement"),
                    "verification_receipt_hash": _digest(seed, index, "verification"),
                    "verifier_identity_hash": _digest(seed, index, "verifier"),
                    "effect_set_hash": _digest(seed, index, "proof-effect"),
                    "resource_vector_hash": _digest(seed, index, "proof-resource"),
                }
            )

        cases.append(
            {
                "case_id": f"fuzz-{index:04d}",
                "case_kind": case_kind,
                "source": source,
                "unit_sources": unit_sources,
                "quantum_steps": quantum_steps,
                "epochs": epochs,
                **extra,
            }
        )
    return tuple(cases)


def _build_case_program(case: dict[str, object]):
    from .canonical import canonical_hash
    from .omega_semantic_basis_v1 import (
        field_fact,
        field_transformation,
        semantic_field,
    )
    from .program_ir_v5_total import (
        TotalCoreInstructionV1,
        TotalCoreProgramV1,
        VerifiedProofAdmissionV1,
    )
    from .source_effect_program_v2 import compile_effect_program_v2
    from .source_total_core_v31 import compile_total_core_v31

    case_kind = str(case["case_kind"])
    if case_kind == "proof_apply":
        requirement = str(case["proof_requirement_hash"])
        authority = _extract_authority(str(case["source"]))
        fact = field_fact("fuzz.proof.admitted", (case["proof_value"],))
        transformation = field_transformation(
            transformation_id=f"{case['case_id']}.proof",
            add_facts=(fact,),
            effect_set_hash=str(case["effect_set_hash"]),
            resource_vector_hash=str(case["resource_vector_hash"]),
            proof_requirement_hashes=(requirement,),
        )
        admission = VerifiedProofAdmissionV1.build(
            requirement_hash=requirement,
            verification_receipt_hash=str(case["verification_receipt_hash"]),
            verifier_identity_hash=str(case["verifier_identity_hash"]),
            authority_hash=authority,
        )
        return TotalCoreProgramV1.build(
            program_id=str(case["case_id"]),
            source_semantic_hash=canonical_hash(
                {
                    "schema": "TEV_SCRIPT_PLATFORM_FUZZ_DIRECT_PROOF_V1",
                    "case": case,
                }
            ),
            initial_field=semantic_field((), profile="actual"),
            transformations=(transformation,),
            v4_units=(),
            proof_admissions=(admission,),
            instructions=(
                TotalCoreInstructionV1.apply(
                    transformation.transformation_hash,
                    next_pc=1,
                ),
                TotalCoreInstructionV1.halt(),
            ),
            entry_pc=0,
            quantum_step_limit=int(case["quantum_steps"]),
            authority_hash=authority,
        )

    unit_sources_raw = case.get("unit_sources", {})
    if not isinstance(unit_sources_raw, dict) or any(
        not isinstance(name, str) or not isinstance(source, str)
        for name, source in unit_sources_raw.items()
    ):
        raise ValueError("invalid fuzz unit_sources")
    unit_sources = dict(unit_sources_raw)

    effect_inputs = None
    if case_kind == "invoke_effects":
        effect_source = unit_sources["Effects"]
        compiled = compile_effect_program_v2(effect_source)
        contract = compiled.capabilities.require("sensor.read")
        effect_inputs = {
            "Effects": {
                "scenario": {
                    "capability_table_hash": compiled.capabilities.table_hash,
                    "capabilities": [
                        {
                            "capability_id": "sensor.read",
                            "contract_hash": contract.contract_hash,
                            "calls": [
                                {
                                    "arguments": [{"$int": "0"}],
                                    "return": {"$int": str(case["effect_return"])},
                                }
                            ],
                        }
                    ],
                }
            }
        }

    return compile_total_core_v31(
        str(case["source"]),
        unit_sources=unit_sources,
        effect_inputs=effect_inputs,
    )


def _extract_authority(source: str) -> str:
    for statement in source.replace("\n", " ").split(";"):
        value = statement.strip()
        if value.startswith("authority "):
            authority = value.split(None, 1)[1]
            if len(authority) == 64 and all(ch in "0123456789abcdef" for ch in authority):
                return authority
    raise ValueError("fuzz source authority missing")


def _default_case_executor(
    root: Path,
    case: dict[str, object],
    node_executable: str,
) -> dict[str, object]:
    from .canonical import canonical_json
    from .program_ir_v5_total import (
        total_core_program_to_mapping,
        validate_total_core_program,
    )
    from .runtime_v5_total import initial_total_core_checkpoint, run_total_core_quantum

    runtime = root / "runtime_js_v31" / "runtime_v5_total.mjs"
    try:
        program = _build_case_program(case)
        initial = initial_total_core_checkpoint(program)
        checkpoint = initial
        for epoch in range(int(case["epochs"])):
            python_result = run_total_core_quantum(program, checkpoint)
            payload = canonical_json(
                {
                    "program": total_core_program_to_mapping(program),
                    "checkpoint": asdict(checkpoint),
                }
            )
            completed = subprocess.run(
                (node_executable, str(runtime)),
                input=payload,
                text=True,
                capture_output=True,
                cwd=root,
                timeout=30,
                check=False,
            )
            expected = canonical_json(asdict(python_result)) + "\n"
            if completed.returncode != 0:
                return {
                    "status": "FAIL",
                    "reason": "JAVASCRIPT_RUNTIME_ERROR",
                    "epoch": epoch,
                }
            if completed.stdout != expected:
                return {
                    "status": "FAIL",
                    "reason": "CANONICAL_RUNTIME_DIVERGENCE",
                    "epoch": epoch,
                }
            checkpoint = python_result.next_checkpoint
            if checkpoint.halted:
                break

        tampered = copy.deepcopy(total_core_program_to_mapping(program))
        tampered["program_hash"] = "0" * 64
        python_rejected = False
        try:
            validate_total_core_program(tampered)
        except Exception:
            python_rejected = True
        if not python_rejected:
            return {"status": "FAIL", "reason": "PYTHON_TAMPER_ACCEPTED"}
        completed = subprocess.run(
            (node_executable, str(runtime)),
            input=canonical_json(
                {"program": tampered, "checkpoint": asdict(initial)}
            ),
            text=True,
            capture_output=True,
            cwd=root,
            timeout=30,
            check=False,
        )
        if completed.returncode == 0:
            return {"status": "FAIL", "reason": "JAVASCRIPT_TAMPER_ACCEPTED"}
        return {"status": "PASS"}
    except Exception as error:
        return {
            "status": "FAIL",
            "reason": "FUZZ_EXECUTION_ERROR",
            "error_type": type(error).__name__,
        }


def run_differential_fuzz(
    root: Path | str,
    *,
    seed: int,
    count: int,
    node_executable: str = "node",
    tool_resolver: ToolResolver | None = None,
    case_executor: CaseExecutor | None = None,
) -> dict[str, object]:
    root = Path(root)
    resolve = shutil.which if tool_resolver is None else tool_resolver
    cases = generate_cases(seed, count)
    corpus = [dict(case) for case in cases]
    corpus_sha256 = hashlib.sha256(_canonical_json_bytes(corpus)).hexdigest()
    case_kind_counts = {
        kind: sum(1 for case in cases if case["case_kind"] == kind)
        for kind in CASE_KIND_ORDER
    }
    missing_case_kinds = sorted(
        kind for kind, observed in case_kind_counts.items() if observed == 0
    )
    if missing_case_kinds:
        return {
            "schema": "TEV_SCRIPT_PLATFORM_DIFFERENTIAL_FUZZ_V2",
            "status": "HOLD",
            "seed": seed,
            "case_count": count,
            "corpus_sha256": corpus_sha256,
            "case_kind_counts": case_kind_counts,
            "missing_case_kinds": missing_case_kinds,
            "first_divergence": None,
            "reason": "INSUFFICIENT_CASE_KIND_COVERAGE",
        }
    if resolve(node_executable) is None:
        return {
            "schema": "TEV_SCRIPT_PLATFORM_DIFFERENTIAL_FUZZ_V2",
            "status": "HOLD",
            "seed": seed,
            "case_count": count,
            "corpus_sha256": corpus_sha256,
            "case_kind_counts": case_kind_counts,
            "missing_case_kinds": [],
            "first_divergence": None,
            "reason": "NODE_UNAVAILABLE",
        }
    execute = _default_case_executor if case_executor is None else case_executor
    outcomes: list[dict[str, object]] = []
    first: dict[str, object] | None = None
    for case in cases:
        try:
            result = dict(execute(root, case, node_executable))
        except Exception as error:
            result = {
                "status": "FAIL",
                "reason": "CASE_EXECUTOR_EXCEPTION",
                "error_type": type(error).__name__,
            }
        status = result.get("status")
        if status not in {"PASS", "FAIL"}:
            result = {"status": "FAIL", "reason": "INVALID_CASE_EXECUTOR_RESULT"}
            status = "FAIL"
        outcome = {
            "case_id": case["case_id"],
            "case_kind": case["case_kind"],
            **result,
        }
        outcomes.append(outcome)
        if status == "FAIL" and first is None:
            first = {**outcome, "source": case["source"]}
    status = "FAIL" if first is not None else "PASS"
    body = {
        "schema": "TEV_SCRIPT_PLATFORM_DIFFERENTIAL_FUZZ_V2",
        "status": status,
        "seed": seed,
        "case_count": count,
        "corpus_sha256": corpus_sha256,
        "case_kind_counts": case_kind_counts,
        "missing_case_kinds": [],
        "outcomes": outcomes,
        "first_divergence": first,
    }
    return {
        **body,
        "receipt_sha256": hashlib.sha256(_canonical_json_bytes(body)).hexdigest(),
    }


__all__ = [
    "CASE_KIND_ORDER",
    "REQUIRED_CASE_KINDS",
    "generate_cases",
    "run_differential_fuzz",
]
