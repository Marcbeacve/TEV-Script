from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import tempfile
import tomllib
import unittest
import zipfile


ROOT = Path(__file__).resolve().parents[1]
PACKAGING_ROOT = ROOT / "packaging/v31"
PYPROJECT = PACKAGING_ROOT / "pyproject.toml"
BACKEND = PACKAGING_ROOT / "tools/tev_script_build_backend_v31.py"
EXPECTED_WHEEL = "tev_script_portable_reference-3.1.0-py3-none-any.whl"


class V31PackagingTests(unittest.TestCase):
    def _document(self) -> dict:
        return tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))

    def _project(self) -> dict:
        return self._document()["project"]

    def _backend(self):
        spec = importlib.util.spec_from_file_location(
            "tev_script_build_backend_v31_test",
            BACKEND,
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_v31_has_dedicated_zero_dependency_packaging_authority(self) -> None:
        document = self._document()
        build = document["build-system"]
        self.assertEqual(build["requires"], [])
        self.assertEqual(build["build-backend"], "tev_script_build_backend_v31")
        self.assertEqual(build["backend-path"], ["tools"])

        project = document["project"]
        self.assertEqual(project["name"], "tev-script-portable-reference")
        self.assertEqual(project["version"], "3.1.0")
        self.assertEqual(project["requires-python"], ">=3.11")
        self.assertEqual(project["dependencies"], [])

    def test_v31_entrypoints_preserve_predecessors_and_add_total_core(self) -> None:
        scripts = self._project()["scripts"]
        expected = {
            "tev-script": "tev_script.cli:main",
            "tev-script-v1": "tev_script.cli_v1:main",
            "tev-script-v1-describe": "tev_script.describe_v1:main",
            "tev-script-v1-ir": "tev_script.runtime_cli_v3:main",
            "tev-script-v1-lsp": "tev_script.lsp_v1:main",
            "tev-script-v2": "tev_script.cli_v2:main",
            "tev-script-v2-describe": "tev_script.describe_v2:main",
            "tev-script-v3": "tev_script.cli_v3:main",
            "tev-script-v3-describe": "tev_script.describe_v3:main",
            "tev-script-v31": "tev_script.cli_v31:main",
            "tev-script-v31-describe": "tev_script.describe_v31:main",
        }
        self.assertEqual(scripts, expected)

    def test_backend_identity_and_no_runtime_build_dependencies(self) -> None:
        backend = self._backend()
        self.assertEqual(backend.BACKEND_SCHEMA, "TEV_SCRIPT_PYTHON_WHEEL_BACKEND_V31")
        self.assertEqual(backend.WHEEL_TAG, "py3-none-any")
        self.assertEqual(backend.get_requires_for_build_wheel(), [])

    def test_source_date_epoch_is_mandatory(self) -> None:
        backend = self._backend()
        old = os.environ.pop("SOURCE_DATE_EPOCH", None)
        try:
            with tempfile.TemporaryDirectory() as target:
                with self.assertRaisesRegex(RuntimeError, "SOURCE_DATE_EPOCH required"):
                    backend.build_wheel(target)
        finally:
            if old is not None:
                os.environ["SOURCE_DATE_EPOCH"] = old

    def test_wheel_build_is_byte_reproducible_and_exactly_named(self) -> None:
        backend = self._backend()
        old = os.environ.get("SOURCE_DATE_EPOCH")
        os.environ["SOURCE_DATE_EPOCH"] = "1700000000"
        try:
            with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
                name1 = backend.build_wheel(first)
                name2 = backend.build_wheel(second)
                self.assertEqual(name1, EXPECTED_WHEEL)
                self.assertEqual(name1, name2)
                left = (Path(first) / name1).read_bytes()
                right = (Path(second) / name2).read_bytes()
                self.assertEqual(left, right)
        finally:
            if old is None:
                os.environ.pop("SOURCE_DATE_EPOCH", None)
            else:
                os.environ["SOURCE_DATE_EPOCH"] = old

    def test_wheel_contains_v31_python_surface_and_predecessor_entrypoints(self) -> None:
        backend = self._backend()
        old = os.environ.get("SOURCE_DATE_EPOCH")
        os.environ["SOURCE_DATE_EPOCH"] = "1700000000"
        try:
            with tempfile.TemporaryDirectory() as target:
                name = backend.build_wheel(target)
                with zipfile.ZipFile(Path(target) / name) as wheel:
                    names = set(wheel.namelist())
                    for required in (
                        "tev_script/program_ir_v5_total.py",
                        "tev_script/runtime_v5_total.py",
                        "tev_script/source_total_core_v31.py",
                        "tev_script/cli_v31.py",
                        "tev_script/descriptor_v31.py",
                        "tev_script/describe_v31.py",
                        "tev_script/cli_v3.py",
                        "tev_script/cli_v2.py",
                        "tev_script/cli_v1.py",
                    ):
                        self.assertIn(required, names)

                    package_entries = [
                        item
                        for item in names
                        if item.startswith("tev_script/") and not item.endswith("/")
                    ]
                    self.assertTrue(package_entries)
                    self.assertTrue(all(item.endswith(".py") for item in package_entries))
                    self.assertFalse(any("__pycache__" in item for item in names))
                    self.assertFalse(any(item.endswith((".pyc", ".pyo")) for item in names))
                    self.assertFalse(any(item.startswith("runtime_js_v31/") for item in names))

                    metadata_name = next(
                        item for item in names if item.endswith(".dist-info/METADATA")
                    )
                    metadata = wheel.read(metadata_name).decode("utf-8")
                    self.assertIn("Name: tev-script-portable-reference\n", metadata)
                    self.assertIn("Version: 3.1.0\n", metadata)
                    self.assertIn("Requires-Python: >=3.11\n", metadata)
                    self.assertNotIn("Requires-Dist:", metadata)

                    entry_name = next(
                        item for item in names if item.endswith(".dist-info/entry_points.txt")
                    )
                    entries = wheel.read(entry_name).decode("utf-8")
                    self.assertIn("tev-script-v31 = tev_script.cli_v31:main", entries)
                    self.assertIn(
                        "tev-script-v31-describe = tev_script.describe_v31:main",
                        entries,
                    )
                    self.assertIn("tev-script-v3 = tev_script.cli_v3:main", entries)
                    self.assertIn("tev-script-v2 = tev_script.cli_v2:main", entries)
        finally:
            if old is None:
                os.environ.pop("SOURCE_DATE_EPOCH", None)
            else:
                os.environ["SOURCE_DATE_EPOCH"] = old

    def test_zip_members_share_source_date_epoch_timestamp(self) -> None:
        backend = self._backend()
        old = os.environ.get("SOURCE_DATE_EPOCH")
        os.environ["SOURCE_DATE_EPOCH"] = "1700000000"
        try:
            with tempfile.TemporaryDirectory() as target:
                name = backend.build_wheel(target)
                with zipfile.ZipFile(Path(target) / name) as wheel:
                    timestamps = {item.date_time for item in wheel.infolist()}
                self.assertEqual(len(timestamps), 1)
        finally:
            if old is None:
                os.environ.pop("SOURCE_DATE_EPOCH", None)
            else:
                os.environ["SOURCE_DATE_EPOCH"] = old


if __name__ == "__main__":
    unittest.main()
