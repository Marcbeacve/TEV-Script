from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

MODULES = (
    "tev_script/semantic_activation_v0.py",
    "tev_script/semantic_execution_observation_v0.py",
    "tev_script/semantic_grounded_discovery_v0.py",
)
TESTS = (
    "tests/test_realization_activation_v0.py",
    "tests/test_realization_execution_observation_v0.py",
    "tests/test_execution_grounded_discovery_v0.py",
)
ALLOWED_ABSOLUTE_IMPORTS = frozenset({"__future__", "dataclasses", "re", "typing"})
FORBIDDEN_IMPORTS = frozenset({"os", "platform", "subprocess", "socket", "psutil", "torch", "cpuinfo"})
FORBIDDEN_TOKENS = ("nvidia", "cuda", "rocm", "tevprover", "ia_tev", "ia-tev")


def fail(detail: str) -> int:
    print("REALIZATION_ACTION_LOOP_AUTHORITY=FAIL")
    print("REALIZATION_ACTION_LOOP_AUTHORITY_DETAIL=" + detail)
    return 1


def validate_module(path_text: str) -> tuple[bool, str]:
    path = ROOT / path_text
    if not path.is_file():
        return False, f"missing module {path_text}"
    source = path.read_text(encoding="utf-8")
    lowered = source.lower()
    for token in FORBIDDEN_TOKENS:
        if token in lowered:
            return False, f"forbidden implementation authority token {token!r} in {path_text}"
    tree = ast.parse(source, filename=path_text)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".", 1)[0]
                if root in FORBIDDEN_IMPORTS:
                    return False, f"host introspection import {alias.name!r} in {path_text}"
                if root not in ALLOWED_ABSOLUTE_IMPORTS:
                    return False, f"unapproved absolute import {alias.name!r} in {path_text}"
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            root = (node.module or "").split(".", 1)[0]
            if root in FORBIDDEN_IMPORTS:
                return False, f"host introspection import {node.module!r} in {path_text}"
            if root not in ALLOWED_ABSOLUTE_IMPORTS:
                return False, f"unapproved absolute import {node.module!r} in {path_text}"
    return True, ""


def main() -> int:
    for path_text in (*MODULES, *TESTS):
        if not (ROOT / path_text).is_file():
            return fail(f"missing action-loop path {path_text}")
    print("ACTION_LOOP_REQUIRED_PATHS=PASS")

    for module in MODULES:
        ok, detail = validate_module(module)
        if not ok:
            return fail(detail)
    print("ACTION_LOOP_NO_HOST_OR_VENDOR_AUTHORITY=PASS")

    activation = (ROOT / MODULES[0]).read_text(encoding="utf-8")
    observation = (ROOT / MODULES[1]).read_text(encoding="utf-8")
    grounded = (ROOT / MODULES[2]).read_text(encoding="utf-8")

    required_activation = (
        "realization_receipt_hash",
        "placement_evaluation_hash",
        "runtime_state_evaluation_hash",
        "execution_context_hash",
    )
    if any(token not in activation for token in required_activation):
        return fail("activation is not bound to realization/placement/runtime/context")
    print("ACTION_LOOP_ACTIVATION_BINDING=PASS")

    required_observation = (
        "activation_receipt_hash",
        "execution_context_hash",
        "causal_result_field_hash",
        "causal_residual_field_hash",
        "observed_history_hash",
        "is_residual_field",
    )
    if any(token not in observation for token in required_observation):
        return fail("execution observation binding surface incomplete")
    print("ACTION_LOOP_CAUSAL_WORLD_OBSERVATION_BINDING=PASS")

    required_grounding = (
        "epistemic_cycle_hash",
        "activation_receipt_hash",
        "execution_observation_receipt_hash",
        "grounded.observed_history_mismatch",
        "grounded.activation_realization_receipt_mismatch",
    )
    if any(token not in grounded for token in required_grounding):
        return fail("grounded discovery chain incomplete")
    print("ACTION_LOOP_DISCOVERY_GROUNDED_IN_EXECUTION=PASS")

    if "CommitResultV1" in observation or "COMMITTED" in observation or "ABORTED" in observation:
        return fail("R0 execution observation must not redefine causal result status semantics")
    print("ACTION_LOOP_CAUSAL_STATUS_AUTHORITY_NOT_REDEFINED=PASS")

    print("REALIZATION_ACTION_LOOP_AUTHORITY=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
