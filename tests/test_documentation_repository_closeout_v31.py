from __future__ import annotations

import json
from pathlib import Path
import re

import tev_script
from tev_script.descriptor_v31 import v31_descriptor
from tev_script.runtime_v5_total import initial_total_core_checkpoint, run_total_core_quantum
from tev_script.source_total_core_v31 import compile_total_core_v31
from tools.validate_documentation_v31 import validate_documentation


ROOT = Path(__file__).resolve().parents[1]
_MANUAL = ROOT / "docs" / "manual"
_EXAMPLES = ROOT / "examples" / "docs" / "v31"
_NEGATIVE_BINDING = re.compile(
    r"<!--\s*tevdoc-source:\s*([^>]+?)\s*-->\s*"
    r"<!--\s*tevdoc-expect-diagnostic:\s*(TEVS_[A-Z0-9_]+)\s*-->",
    re.MULTILINE,
)
_MARKDOWN_LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
_CODE_FENCE = re.compile(r"```.*?```", re.DOTALL)


def test_real_repository_documentation_receipt_passes() -> None:
    receipt = validate_documentation(ROOT)
    assert receipt["status"] == "PASS", json.dumps(receipt, indent=2, sort_keys=True)


def test_final_navigation_and_diagnostic_pages_exist() -> None:
    required = (
        "docs/README.md",
        "docs/manual/documentation-policy.md",
        "docs/manual/cli-reference/README.md",
        "docs/manual/library-reference/README.md",
        "docs/manual/library-reference/advanced-embedding.md",
        "docs/manual/diagnostics/README.md",
        "docs/manual/diagnostics/current-inventory.md",
        "docs/manual/diagnostics/source.md",
        "docs/manual/diagnostics/program-ir.md",
        "docs/manual/diagnostics/runtime.md",
        "docs/manual/diagnostics/release-tooling.md",
        "docs/manual/versions/README.md",
        "docs/manual/versions/current.md",
        "docs/manual/versions/compatibility.md",
        "docs/manual/versions/version-domains.md",
        "docs/manual/versions/v1.md",
        "docs/manual/versions/v2.md",
        "docs/manual/versions/v3.md",
        "docs/manual/versions/v31.md",
        "docs/manual/versions/deprecations.md",
    )
    missing = [rel for rel in required if not (ROOT / rel).is_file()]
    assert missing == []


def test_advanced_embedding_documents_task_strategy_boundary() -> None:
    page = (_MANUAL / "library-reference" / "advanced-embedding.md").read_text(encoding="utf-8")
    assert "task_strategy" in page
    assert "TaskScopeExecutionStrategyV4" in page
    assert "run(tasks, evaluate_child)" in page
    assert "run_select" in page
    assert "run_select_cooperative" in page
    assert "no se exporta desde `tev_script.__all__`" in page
    assert "TaskScopeExecutionStrategyV4" not in tev_script.__all__

    current = (_MANUAL / "library-reference" / "current-total-core.md").read_text(encoding="utf-8")
    index = (_MANUAL / "library-reference" / "README.md").read_text(encoding="utf-8")
    assert "advanced-embedding.md" in current
    assert "advanced-embedding.md" in index


def test_validation_recipe_contains_every_repository_channel_command() -> None:
    policy = json.loads((ROOT / "REPOSITORY_CHANNEL.json").read_text(encoding="utf-8"))
    validation_text = (ROOT / "docs" / "VALIDATION.md").read_text(encoding="utf-8")
    missing: list[str] = []
    for rule in policy["validation"]["rules"]:
        for command in rule["commands"]:
            for token in command[1:]:
                if token not in validation_text:
                    missing.append(f"{rule['rule_id']}: {token}")
    assert missing == []


def test_internal_markdown_links_resolve_inside_repository() -> None:
    broken: list[str] = []
    escaped: list[str] = []
    pages = [ROOT / "docs" / "README.md", *sorted(_MANUAL.rglob("*.md"))]
    for page in pages:
        text = _CODE_FENCE.sub("", page.read_text(encoding="utf-8"))
        for raw_target in _MARKDOWN_LINK.findall(text):
            target = raw_target.strip()
            if target.startswith(("https://", "http://", "mailto:", "#")):
                continue
            path_text = target.split("#", 1)[0]
            if not path_text:
                continue
            resolved = (page.parent / path_text).resolve()
            try:
                resolved.relative_to(ROOT)
            except ValueError:
                escaped.append(f"{page.relative_to(ROOT).as_posix()} -> {target}")
                continue
            if not resolved.exists():
                broken.append(f"{page.relative_to(ROOT).as_posix()} -> {target}")
    assert escaped == []
    assert broken == []


def test_every_positive_documentation_case_executes_runtime() -> None:
    positives: list[str] = []
    negatives: list[str] = []
    for case_path in sorted(_EXAMPLES.rglob("case.json")):
        case = json.loads(case_path.read_text(encoding="utf-8"))
        rel = case_path.relative_to(ROOT).as_posix()
        if case["expected_status"] == "FAIL":
            negatives.append(rel)
            assert case["operation"] == "check"
            assert case["expected_returncode"] == 2
            assert isinstance(case["expected_diagnostic_code"], str)
            continue
        positives.append(rel)
        assert case["operation"] == "run", rel
        assert case["expected_returncode"] == 0, rel
        assert case["expected_status"] in {"HALTED", "SUSPENDED"}, rel
        assert case["expected_diagnostic_code"] is None, rel
    assert positives, "documentation must contain positive executable cases"
    assert negatives, "documentation must retain negative executable controls"


def test_capability_tutorial_binds_observation_and_final_state() -> None:
    case_dir = _EXAMPLES / "tutorial" / "07_capabilities_effects"
    case = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
    process_source = (case_dir / case["source"]).read_text(encoding="utf-8")
    unit_sources = {
        unit_id: (case_dir / rel).read_text(encoding="utf-8")
        for unit_id, rel in case["units"].items()
    }
    program = compile_total_core_v31(
        process_source,
        unit_sources=unit_sources,
        effect_inputs=case["effect_inputs"],
    )
    result = run_total_core_quantum(program, initial_total_core_checkpoint(program))
    assert result.status == "HALTED"
    bridges = [fact for fact in result.field.facts if fact.relation == "tev.tutorial.capability"]
    assert len(bridges) == 1
    payload = bridges[0].arguments[0]
    assert isinstance(payload, dict)
    final_state = {row["name"]: row["value"] for row in payload["final_state"]}
    assert final_state["count"] == {"$int": "13"}
    assert final_state["last"] == {"$int": "10"}
    assert payload["observation_calls"] == 1


def test_complete_application_binds_child_results_and_field_transition() -> None:
    case_dir = _EXAMPLES / "tutorial" / "15_complete_application"
    case = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
    process_source = (case_dir / case["source"]).read_text(encoding="utf-8")
    unit_sources = {
        unit_id: (case_dir / rel).read_text(encoding="utf-8")
        for unit_id, rel in case["units"].items()
    }
    program = compile_total_core_v31(
        process_source,
        unit_sources=unit_sources,
        effect_inputs=case["effect_inputs"],
    )
    result = run_total_core_quantum(program, initial_total_core_checkpoint(program))
    assert result.status == "HALTED"

    def one(relation: str):
        matches = [fact for fact in result.field.facts if fact.relation == relation]
        assert len(matches) == 1, relation
        return matches[0]

    assert not [fact for fact in result.field.facts if fact.relation == "app.pending"]
    assert one("app.complete").arguments == ("workflow",)

    calc_payload = one("tev.app.calc").arguments[0]
    rec_payload = one("tev.app.rec").arguments[0]
    assert isinstance(calc_payload, dict)
    assert isinstance(rec_payload, dict)
    assert calc_payload["result_encoded"] == {"$int": "5"}
    assert rec_payload["result_encoded"] == {"$int": "120"}


def test_displayed_negative_examples_match_their_canonical_case() -> None:
    observed = 0
    for page in sorted(_MANUAL.rglob("*.md")):
        text = page.read_text(encoding="utf-8")
        for match in _NEGATIVE_BINDING.finditer(text):
            observed += 1
            source_rel = match.group(1).strip()
            expected_code = match.group(2)
            source = ROOT / source_rel
            assert source.is_file(), f"missing negative source: {source_rel}"
            case_path = source.parent / "case.json"
            assert case_path.is_file(), f"missing case for negative source: {source_rel}"
            case = json.loads(case_path.read_text(encoding="utf-8"))
            assert case["expected_status"] == "FAIL"
            assert case["expected_returncode"] == 2
            assert case["expected_diagnostic_code"] == expected_code
    assert observed >= 1, "at least one displayed negative executable example is required"


def test_manual_has_no_stale_phase_placeholders() -> None:
    forbidden = (
        "se irán cerrando",
        "se ira cerrando",
        "se documentará en una fase",
        "se documentara en una fase",
        "se entrega en su fase dedicada",
        "placeholder documentation",
    )
    hits: list[str] = []
    for page in sorted(_MANUAL.rglob("*.md")):
        text = page.read_text(encoding="utf-8")
        lowered = text.lower()
        if re.search(r"(?im)^\s*(?:[-*]\s*)?(?:TODO|TBD)\b", text):
            hits.append(page.relative_to(ROOT).as_posix())
            continue
        if any(token in lowered for token in forbidden):
            hits.append(page.relative_to(ROOT).as_posix())
    assert hits == []


def test_host_support_matrix_does_not_overclaim_total_core_targets() -> None:
    descriptor = v31_descriptor()
    assert descriptor["runtime_targets"] == [
        "python_reference",
        "javascript_independent_required",
    ]
    matrix = (_MANUAL / "integrations" / "README.md").read_text(encoding="utf-8")

    def row(name: str) -> str:
        prefix = f"| {name} |"
        matches = [line for line in matrix.splitlines() if line.startswith(prefix)]
        assert len(matches) == 1, f"expected exactly one support row for {name!r}"
        return matches[0]

    python = row("Python")
    javascript = row("JavaScript")
    csharp = row("C#")
    unity = row("Unity")
    browser = row("Browser-WASM")
    wasi = row("WASI")

    assert "**CURRENT**" in python and "Total-Core" in python
    assert "**CURRENT / independent required target**" in javascript
    assert "**COMPATIBILITY**" in csharp and "no afirmar runtime V5" in csharp
    assert "**COMPATIBILITY host**" in unity and "no runtime V5 Total-Core certificado" in unity
    assert "**COMPATIBILITY gate**" in browser and "no V5 Total-Core browser certificado" in browser
    assert "**COMPATIBILITY gate**" in wasi and "no V5 Total-Core WASI certificado" in wasi
