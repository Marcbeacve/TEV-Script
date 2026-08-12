from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API_PATH = ROOT / "tev_script/system_api_v0.py"
COVERAGE_PATH = ROOT / "spec/TEV_SCRIPT_AXIOM_COVERAGE_V0.json"
ALLOWED_LAYERS = {f"L{index}" for index in range(9)}


def _literal_assignment(module: ast.Module, name: str):
    for node in module.body:
        if isinstance(node, ast.Assign):
            if any(
                isinstance(target, ast.Name) and target.id == name
                for target in node.targets
            ):
                return ast.literal_eval(node.value)
    raise KeyError(name)


def _covered_ids(
    rows: object,
    *,
    expected_kind: str,
    failures: list[str],
) -> set[str]:
    if not isinstance(rows, dict):
        failures.append(f"coverage:{expected_kind}:not_mapping")
        return set()
    observed: set[str] = set()
    for layer, values in rows.items():
        if layer not in ALLOWED_LAYERS:
            failures.append(f"coverage:{expected_kind}:unknown_layer:{layer}")
            continue
        if not isinstance(values, list) or not values:
            failures.append(f"coverage:{expected_kind}:empty_layer:{layer}")
            continue
        for value in values:
            if not isinstance(value, str) or not value:
                failures.append(
                    f"coverage:{expected_kind}:invalid_identifier:{layer}"
                )
                continue
            observed.add(value)
    return observed


def validate() -> tuple[str, ...]:
    failures: list[str] = []

    if not API_PATH.is_file():
        return ("system_api:missing",)
    if not COVERAGE_PATH.is_file():
        return ("coverage:missing",)

    api_ast = ast.parse(API_PATH.read_text(encoding="utf-8"))
    try:
        causal_registry = _literal_assignment(
            api_ast, "SYSTEM_CAUSAL_MODULE_PATHS_V0"
        )
        semantic_registry = _literal_assignment(
            api_ast, "SYSTEM_SUBSYSTEM_MODULE_PATHS_V0"
        )
        system_surfaces = _literal_assignment(
            api_ast, "_SYSTEM_SURFACES_V0"
        )
    except (KeyError, ValueError, SyntaxError) as exc:
        return ("system_api:literal_registry_parse:" + type(exc).__name__,)

    try:
        coverage = json.loads(COVERAGE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return ("coverage:invalid_json",)

    if coverage.get("schema") != "TEV_SCRIPT_AXIOM_COVERAGE_V0":
        failures.append("coverage:schema")
    if coverage.get("status") != "AXIOMATIC_CANDIDATE":
        failures.append("coverage:status")
    if coverage.get("primitive_families") != ["Field", "Transformation"]:
        failures.append("coverage:primitive_families")
    if set(coverage.get("allowed_layers", [])) != ALLOWED_LAYERS:
        failures.append("coverage:allowed_layers")

    covered_surfaces = _covered_ids(
        coverage.get("system_surface_layers"),
        expected_kind="system_surfaces",
        failures=failures,
    )
    covered_causal = _covered_ids(
        coverage.get("causal_module_layers"),
        expected_kind="causal_modules",
        failures=failures,
    )
    covered_semantic = _covered_ids(
        coverage.get("semantic_module_layers"),
        expected_kind="semantic_modules",
        failures=failures,
    )

    expected_surfaces = set(system_surfaces)
    expected_causal = set(causal_registry)
    expected_semantic = set(semantic_registry)

    if covered_surfaces != expected_surfaces:
        failures.append(
            "coverage:system_surface_set:"
            + "missing="
            + ",".join(sorted(expected_surfaces - covered_surfaces))
            + ":extra="
            + ",".join(sorted(covered_surfaces - expected_surfaces))
        )
    if covered_causal != expected_causal:
        failures.append(
            "coverage:causal_set:"
            + "missing="
            + ",".join(sorted(expected_causal - covered_causal))
            + ":extra="
            + ",".join(sorted(covered_causal - expected_causal))
        )
    if covered_semantic != expected_semantic:
        failures.append(
            "coverage:semantic_set:"
            + "missing="
            + ",".join(sorted(expected_semantic - covered_semantic))
            + ":extra="
            + ",".join(sorted(covered_semantic - expected_semantic))
        )

    for module_id, module_path in {
        **causal_registry,
        **semantic_registry,
    }.items():
        if not isinstance(module_path, str):
            failures.append(f"registry:path_type:{module_id}")
            continue
        relative = module_path.replace(".", "/") + ".py"
        if not (ROOT / relative).is_file():
            failures.append(f"registry:source_missing:{module_id}:{relative}")

    closure = coverage.get("closure")
    if not isinstance(closure, dict):
        failures.append("coverage:closure")
    else:
        required_true = {
            "system_surface_union_must_equal_system_api_surface_set",
            "causal_module_union_must_equal_system_api_registry",
            "semantic_module_union_must_equal_system_api_registry",
        }
        required_false = {
            "uncovered_module_is_pass",
            "unknown_module_is_pass",
            "unknown_layer_is_pass",
        }
        for key in required_true:
            if closure.get(key) is not True:
                failures.append("coverage:closure_true:" + key)
        for key in required_false:
            if closure.get(key) is not False:
                failures.append("coverage:closure_false:" + key)

    manifest_path = ROOT / "spec/TEV_SCRIPT_AXIOM_OBLIGATIONS_V0.json"
    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            failures.append("manifest:invalid_json")
            manifest = {}
        if manifest.get("coverage_ledger") != (
            "spec/TEV_SCRIPT_AXIOM_COVERAGE_V0.json"
        ):
            failures.append("manifest:coverage_ledger")
        promotion = manifest.get("promotion")
        if not isinstance(promotion, dict) or promotion.get(
            "requires_closed_module_axiom_coverage"
        ) is not True:
            failures.append("manifest:coverage_promotion_gate")
    else:
        failures.append("manifest:missing")

    for relative in (
        "CANONICAL_INDEX.json",
        "spec/TEV_SCRIPT_SYSTEM_CANONICAL_INDEX_V0.json",
    ):
        path = ROOT / relative
        if path.is_file() and (
            "TEV_SCRIPT_AXIOM_COVERAGE_V0"
            in path.read_text(encoding="utf-8")
        ):
            failures.append("authority:premature_coverage_binding:" + relative)

    return tuple(sorted(set(failures)))


def main() -> int:
    failures = validate()
    if failures:
        for failure in failures:
            print("TEV_SCRIPT_AXIOM_COVERAGE_V0=FAIL:" + failure)
        return 1
    print("TEV_SCRIPT_AXIOM_COVERAGE_V0=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
