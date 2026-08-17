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


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


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
        labels = rng.randint(1, 6)
        quantum_steps = rng.randint(1, 8)
        epochs = rng.randint(1, 3)
        authority = hashlib.sha256(
            f"tevscript-fuzz:{seed}:{index}:authority".encode("utf-8")
        ).hexdigest()
        statements = [
            f'process Fuzz_{seed}_{index} version "{CURRENT_LANGUAGE_VERSION}"',
            f"authority {authority}",
            f"quantum_steps {quantum_steps}",
            "field actual = []",
        ]
        for label in range(labels):
            if rng.random() < 0.28:
                body = "halt"
            else:
                target = rng.randrange(labels)
                body = f"jump L{target}"
            statements.append(f"label L{label} = {body}")
        statements.append("entry L0")
        source = ";\n".join(statements) + ";\n"
        cases.append(
            {
                "case_id": f"fuzz-{index:04d}",
                "source": source,
                "quantum_steps": quantum_steps,
                "epochs": epochs,
            }
        )
    return tuple(cases)


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
    from .source_total_core_v31 import compile_total_core_v31

    runtime = root / "runtime_js_v31" / "runtime_v5_total.mjs"
    try:
        program = compile_total_core_v31(str(case["source"]), unit_sources={})
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
    corpus = [
        {
            "case_id": case["case_id"],
            "source": case["source"],
            "epochs": case["epochs"],
        }
        for case in cases
    ]
    corpus_sha256 = hashlib.sha256(_canonical_json_bytes(corpus)).hexdigest()
    if resolve(node_executable) is None:
        return {
            "schema": "TEV_SCRIPT_PLATFORM_DIFFERENTIAL_FUZZ_V1",
            "status": "HOLD",
            "seed": seed,
            "case_count": count,
            "corpus_sha256": corpus_sha256,
            "first_divergence": None,
            "reason": "NODE_UNAVAILABLE",
        }
    execute = _default_case_executor if case_executor is None else case_executor
    outcomes: list[dict[str, object]] = []
    first: dict[str, object] | None = None
    for case in cases:
        result = dict(execute(root, case, node_executable))
        status = result.get("status")
        if status not in {"PASS", "FAIL"}:
            result = {"status": "FAIL", "reason": "INVALID_CASE_EXECUTOR_RESULT"}
            status = "FAIL"
        outcome = {"case_id": case["case_id"], **result}
        outcomes.append(outcome)
        if status == "FAIL" and first is None:
            first = {**outcome, "source": case["source"]}
    status = "FAIL" if first is not None else "PASS"
    body = {
        "schema": "TEV_SCRIPT_PLATFORM_DIFFERENTIAL_FUZZ_V1",
        "status": status,
        "seed": seed,
        "case_count": count,
        "corpus_sha256": corpus_sha256,
        "outcomes": outcomes,
        "first_divergence": first,
    }
    return {
        **body,
        "receipt_sha256": hashlib.sha256(_canonical_json_bytes(body)).hexdigest(),
    }


__all__ = ["generate_cases", "run_differential_fuzz"]
