from __future__ import annotations

import json
from pathlib import Path

from tools.validate_documentation_v31 import validate_documentation


def _write_foundation(root: Path) -> None:
    (root / "tev_script").mkdir(parents=True, exist_ok=True)
    (root / "spec").mkdir(parents=True, exist_ok=True)
    (root / "docs" / "manual" / "tutorial").mkdir(parents=True, exist_ok=True)
    (root / "examples" / "docs" / "v31" / "tutorial" / "01_exact").mkdir(
        parents=True,
        exist_ok=True,
    )
    (root / "tev_script" / "version.py").write_text(
        'PACKAGE_VERSION = "3.1.2"\n'
        'CURRENT_LANGUAGE_VERSION = "3.1.0"\n'
        'CURRENT_PROFILE = "total_core"\n'
        'PUBLISHED_PREDECESSOR_PACKAGE_VERSION = "3.1.1"\n'
        'ARCHIVED_V31_PACKAGE_VERSION = "3.1.0"\n',
        encoding="utf-8",
    )
    (root / "spec" / "TEV_SCRIPT_3_1_PLATFORM.md").write_text(
        "package_version = 3.1.2\n"
        "language_version = 3.1.0\n"
        "current_profile = total_core\n"
        "published_predecessor_package = 3.1.1\n",
        encoding="utf-8",
    )
    (root / "spec" / "TEV_SCRIPT_VERSION_MATRIX.json").write_text(
        json.dumps(
            {
                "schema": "TEV_SCRIPT_VERSION_MATRIX_V1",
                "current_language": "3.1.0",
                "domains": {
                    "package": [
                        {"version": "3.1.2", "status": "current"},
                        {
                            "version": "3.1.1",
                            "status": "compatible",
                            "note": "published immutable immediate predecessor v3.1.1",
                        },
                        {
                            "version": "3.1.0",
                            "status": "compatible",
                            "note": "published immutable predecessor v3.1.0",
                        },
                    ]
                },
            }
        ),
        encoding="utf-8",
    )
    (root / "docs" / "manual" / "README.md").write_text("# Manual\n", encoding="utf-8")
    (root / "docs" / "manual" / "DOCUMENTATION_COVERAGE_V1.json").write_text(
        json.dumps(
            {
                "schema": "TEV_SCRIPT_DOCUMENTATION_COVERAGE_V1",
                "package_version": "3.1.2",
                "language_version": "3.1.0",
                "profile": "total_core",
                "phase": "TEST",
                "domains": {
                    "language_constructs": [],
                    "cli_surface": [],
                    "python_api": [],
                    "source_profiles": [],
                    "ir_runtime_profiles": [],
                    "diagnostics": [],
                    "integrations": [],
                    "version_domains": [],
                },
            }
        ),
        encoding="utf-8",
    )


def _source_path(root: Path) -> Path:
    return root / "examples" / "docs" / "v31" / "tutorial" / "01_exact" / "main.tevs"


def _page_path(root: Path) -> Path:
    return root / "docs" / "manual" / "tutorial" / "exact.md"


def test_exact_bound_tevs_fence_passes(tmp_path: Path) -> None:
    _write_foundation(tmp_path)
    source = 'process Exact version "3.1.0";\nentry Start;\n'
    _source_path(tmp_path).write_text(source, encoding="utf-8")
    _page_path(tmp_path).write_text(
        "# Exact\n\n"
        "<!-- tevdoc-source: examples/docs/v31/tutorial/01_exact/main.tevs -->\n"
        "```tevs\n"
        + source
        + "```\n",
        encoding="utf-8",
    )
    assert validate_documentation(tmp_path)["checks"]["SOURCE_BINDINGS"] == {
        "status": "PASS",
        "binding_count": 1,
    }


def test_source_directive_inside_non_tevs_fence_is_documentation_not_binding(tmp_path: Path) -> None:
    _write_foundation(tmp_path)
    _page_path(tmp_path).write_text(
        "# Policy example\n\n"
        "```text\n"
        "<!-- tevdoc-source: examples/docs/v31/tutorial/01_exact/main.tevs -->\n"
        "```\n",
        encoding="utf-8",
    )
    assert validate_documentation(tmp_path)["checks"]["SOURCE_BINDINGS"] == {
        "status": "PASS",
        "binding_count": 0,
    }


def test_source_fence_drift_fails_closed(tmp_path: Path) -> None:
    _write_foundation(tmp_path)
    _source_path(tmp_path).write_text("entry Start;\n", encoding="utf-8")
    _page_path(tmp_path).write_text(
        "<!-- tevdoc-source: examples/docs/v31/tutorial/01_exact/main.tevs -->\n"
        "```tevs\nentry Other;\n```\n",
        encoding="utf-8",
    )
    check = validate_documentation(tmp_path)["checks"]["SOURCE_BINDINGS"]
    assert check["status"] == "FAIL"
    assert check["reason"] == "INVALID_SOURCE_BINDINGS"
    assert "source fence drift" in check["error"]


def test_missing_bound_source_fails_closed(tmp_path: Path) -> None:
    _write_foundation(tmp_path)
    _page_path(tmp_path).write_text(
        "<!-- tevdoc-source: examples/docs/v31/tutorial/01_exact/main.tevs -->\n"
        "```tevs\nentry Start;\n```\n",
        encoding="utf-8",
    )
    check = validate_documentation(tmp_path)["checks"]["SOURCE_BINDINGS"]
    assert check["status"] == "FAIL"
    assert "bound source missing" in check["error"]


def test_unbound_tevs_fence_fails_closed(tmp_path: Path) -> None:
    _write_foundation(tmp_path)
    _page_path(tmp_path).write_text(
        "# Unbound\n\n```tevs\nentry Start;\n```\n",
        encoding="utf-8",
    )
    check = validate_documentation(tmp_path)["checks"]["SOURCE_BINDINGS"]
    assert check["status"] == "FAIL"
    assert "unbound tevs fence" in check["error"]


def test_two_source_directives_cannot_bind_one_fence(tmp_path: Path) -> None:
    _write_foundation(tmp_path)
    _source_path(tmp_path).write_text("entry Start;\n", encoding="utf-8")
    _page_path(tmp_path).write_text(
        "<!-- tevdoc-source: examples/docs/v31/tutorial/01_exact/main.tevs -->\n"
        "<!-- tevdoc-source: examples/docs/v31/tutorial/01_exact/main.tevs -->\n"
        "```tevs\nentry Start;\n```\n",
        encoding="utf-8",
    )
    check = validate_documentation(tmp_path)["checks"]["SOURCE_BINDINGS"]
    assert check["status"] == "FAIL"
    assert "multiple source directives" in check["error"]
