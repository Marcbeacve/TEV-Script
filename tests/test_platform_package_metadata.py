from __future__ import annotations

from pathlib import Path
import tomllib

from tools.tev_script_build_backend import _metadata_bytes, _project_metadata

ROOT = Path(__file__).resolve().parents[1]


def test_current_project_declares_markdown_readme() -> None:
    with (ROOT / "pyproject.toml").open("rb") as stream:
        project = tomllib.load(stream)["project"]
    assert project["readme"] == {
        "file": "README.md",
        "content-type": "text/markdown",
    }


def test_reproducible_backend_emits_long_description_metadata() -> None:
    metadata = _metadata_bytes(_project_metadata(ROOT), ROOT).decode("utf-8")
    assert "Description-Content-Type: text/markdown\n" in metadata
    assert "\n\n# TEV Script — current platform\n" in metadata
    assert "Current platform-completion candidate" in metadata
