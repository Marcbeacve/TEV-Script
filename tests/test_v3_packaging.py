from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import tempfile
import tomllib
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]


class V3PackagingTests(unittest.TestCase):
    def _project(self):
        return tomllib.loads((ROOT / "packaging/v3/pyproject.toml").read_text(encoding="utf-8"))["project"]

    def _backend(self):
        path = ROOT / "packaging/v3/tools/tev_script_build_backend_v3.py"
        spec = importlib.util.spec_from_file_location("tev_script_build_backend_v3_test", path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        return module

    def test_v3_project_is_3_0_zero_dependency_and_preserves_compat_entrypoints(self) -> None:
        project = self._project()
        self.assertEqual(project["name"], "tev-script-portable-reference")
        self.assertEqual(project["version"], "3.0.0")
        self.assertEqual(project["dependencies"], [])
        scripts = project["scripts"]
        self.assertEqual(scripts["tev-script-v3"], "tev_script.cli_v3:main")
        self.assertEqual(scripts["tev-script-v3-describe"], "tev_script.describe_v3:main")
        self.assertEqual(scripts["tev-script-v2"], "tev_script.cli_v2:main")
        self.assertEqual(scripts["tev-script-v1"], "tev_script.cli_v1:main")

    def test_v3_wheel_build_is_byte_reproducible_and_contains_v3_surface(self) -> None:
        backend = self._backend()
        old = os.environ.get("SOURCE_DATE_EPOCH")
        os.environ["SOURCE_DATE_EPOCH"] = "1700000000"
        try:
            with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
                name1 = backend.build_wheel(first); name2 = backend.build_wheel(second)
                self.assertEqual(name1, name2)
                left = (Path(first) / name1).read_bytes(); right = (Path(second) / name2).read_bytes()
                self.assertEqual(left, right)
                self.assertIn("-3.0.0-py3-none-any.whl", name1)
                with zipfile.ZipFile(Path(first) / name1) as wheel:
                    names = set(wheel.namelist())
                    self.assertIn("tev_script/cli_v3.py", names)
                    self.assertIn("tev_script/descriptor_v3.py", names)
                    metadata_name = next(name for name in names if name.endswith(".dist-info/METADATA"))
                    metadata = wheel.read(metadata_name).decode("utf-8")
                    self.assertIn("Version: 3.0.0\n", metadata)
                    entry_name = next(name for name in names if name.endswith(".dist-info/entry_points.txt"))
                    entries = wheel.read(entry_name).decode("utf-8")
                    self.assertIn("tev-script-v3 = tev_script.cli_v3:main", entries)
                    self.assertIn("tev-script-v2 = tev_script.cli_v2:main", entries)
        finally:
            if old is None: os.environ.pop("SOURCE_DATE_EPOCH", None)
            else: os.environ["SOURCE_DATE_EPOCH"] = old


if __name__ == "__main__":
    unittest.main()
