from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import tomllib
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
BACKEND_SCHEMA = "TEV_SCRIPT_PYTHON_WHEEL_BACKEND_V1"


def _clean_environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    environment.update(
        {
            "PIP_CONFIG_FILE": os.devnull,
            "PIP_DISABLE_PIP_VERSION_CHECK": "1",
            "PIP_NO_INDEX": "1",
            "PYTHONHASHSEED": "0",
            "PYTHONNOUSERSITE": "1",
            "SOURCE_DATE_EPOCH": "1786380000",
        }
    )
    return environment


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _build(destination: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            ".",
            "--no-deps",
            "--no-build-isolation",
            "--wheel-dir",
            str(destination),
        ],
        cwd=ROOT,
        env=_clean_environment(),
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def _expected_wheel_name() -> str:
    document = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    project = document["project"]
    distribution = re.sub(r"[-_.]+", "_", str(project["name"])).strip("_")
    version = str(project["version"])
    return f"{distribution}-{version}-py3-none-any.whl"


class V1BuildSystemContractTests(unittest.TestCase):
    def test_build_backend_is_in_tree_and_dependency_free(self) -> None:
        document = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        build = document["build-system"]
        self.assertEqual(build["requires"], [])
        self.assertEqual(build["build-backend"], "tev_script_build_backend")
        self.assertEqual(build["backend-path"], ["tools"])
        self.assertEqual(document["project"].get("dependencies"), [])
        self.assertTrue((ROOT / "tools" / "tev_script_build_backend.py").is_file())

    def test_package_surface_is_python_only(self) -> None:
        unsupported = sorted(
            path.relative_to(ROOT).as_posix()
            for path in (ROOT / "tev_script").rglob("*")
            if path.is_file()
            and "__pycache__" not in path.parts
            and path.suffix not in {".py", ".pyc", ".pyo"}
        )
        self.assertEqual(unsupported, [])

    def test_clean_offline_pip_build_is_reproducible(self) -> None:
        with tempfile.TemporaryDirectory(prefix="tev-script-wheel-contract-") as temporary:
            root = Path(temporary)
            first_dir = root / "a"
            second_dir = root / "b"
            first_dir.mkdir()
            second_dir.mkdir()
            first = _build(first_dir)
            self.assertEqual(
                first.returncode,
                0,
                msg="first offline wheel build failed\nstdout="
                + first.stdout
                + "\nstderr="
                + first.stderr,
            )
            second = _build(second_dir)
            self.assertEqual(
                second.returncode,
                0,
                msg="second offline wheel build failed\nstdout="
                + second.stdout
                + "\nstderr="
                + second.stderr,
            )
            wheels_a = tuple(first_dir.glob("*.whl"))
            wheels_b = tuple(second_dir.glob("*.whl"))
            self.assertEqual(len(wheels_a), 1)
            self.assertEqual(len(wheels_b), 1)
            self.assertEqual(wheels_a[0].name, _expected_wheel_name())
            self.assertEqual(wheels_a[0].name, wheels_b[0].name)
            self.assertEqual(_sha256(wheels_a[0]), _sha256(wheels_b[0]))

            with zipfile.ZipFile(wheels_a[0], "r") as archive:
                names = tuple(archive.namelist())
                wheel_entry = next(name for name in names if name.endswith(".dist-info/WHEEL"))
                metadata_entry = next(name for name in names if name.endswith(".dist-info/METADATA"))
                record_entry = next(name for name in names if name.endswith(".dist-info/RECORD"))
                entry_points = next(
                    name for name in names if name.endswith(".dist-info/entry_points.txt")
                )
                wheel_text = archive.read(wheel_entry).decode("utf-8")
                metadata_text = archive.read(metadata_entry).decode("utf-8")
                record_text = archive.read(record_entry).decode("utf-8")
                entry_text = archive.read(entry_points).decode("utf-8")

            document = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
            version = str(document["project"]["version"])
            self.assertIn("Generator: " + BACKEND_SCHEMA, wheel_text)
            self.assertIn("Tag: py3-none-any", wheel_text)
            self.assertIn("Name: tev-script-portable-reference", metadata_text)
            self.assertIn("Version: " + version, metadata_text)
            self.assertIn("Requires-Python: >=3.11", metadata_text)
            self.assertIn(record_entry + ",,", record_text)
            self.assertIn("tev-script-v1 = tev_script.cli_v1:main", entry_text)


if __name__ == "__main__":
    unittest.main()
