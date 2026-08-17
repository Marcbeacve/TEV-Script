from __future__ import annotations

from tev_script.platform_fuzz import generate_cases


def test_negative_pure_delta_is_rendered_as_canonical_subtraction() -> None:
    cases = generate_cases(2, 3)
    pure = cases[2]
    assert pure["case_kind"] == "invoke_pure"
    source = pure["unit_sources"]["Calc"]
    assert "+-" not in source
    assert "x-4" in source
