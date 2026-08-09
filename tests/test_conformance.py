from __future__ import annotations

import json
import shutil
import tempfile
import subprocess
import unittest
from argparse import Namespace
from unittest.mock import patch
from pathlib import Path

from tev_script import compile_path
from tev_script.cli import _compile, _conformance
from tev_script.canonical import canonical_json
from tev_script.conformance import run_conformance

ROOT = Path(__file__).resolve().parents[1]
VECTORS = (
    ("player", "Player.tevs"),
    ("matrix", "ConformanceMatrix.tevs"),
    ("player-idle", "Player.tevs"),
    ("event-chain", "EventChain.tevs"),
)


class ConformanceTests(unittest.TestCase):
    def test_python_matches_all_expected_receipts(self) -> None:
        for vector_id, source_name in VECTORS:
            with self.subTest(vector=vector_id):
                ir = compile_path(ROOT / "examples" / source_name).ir
                scenario = json.loads(
                    (ROOT / "conformance" / f"{vector_id}.scenario.json").read_text(encoding="utf-8")
                )
                expected = (
                    ROOT / "conformance" / f"{vector_id}.expected.json"
                ).read_text(encoding="utf-8")
                actual = canonical_json(run_conformance(ir, scenario)) + "\n"
                self.assertEqual(actual, expected)

    @unittest.skipUnless(shutil.which("node"), "Node.js unavailable")
    def test_node_matches_all_expected_receipts(self) -> None:
        for vector_id, _ in VECTORS:
            with self.subTest(vector=vector_id):
                completed = subprocess.run(
                    (
                        "node",
                        str(ROOT / "javascript" / "src" / "run-conformance.mjs"),
                        str(ROOT / "conformance" / f"{vector_id}.scenario.json"),
                    ),
                    check=False,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                )
                self.assertEqual(completed.returncode, 0, completed.stderr)
                expected = (
                    ROOT / "conformance" / f"{vector_id}.expected.json"
                ).read_text(encoding="utf-8")
                self.assertEqual(completed.stdout, expected)


    def test_cli_file_outputs_bypass_platform_newline_translation(self) -> None:
        def windows_like_write_text(path: Path, data: str, *args: object, **kwargs: object) -> int:
            encoded = data.replace("\n", "\r\n").encode("utf-8")
            path.write_bytes(encoded)
            return len(data)

        with tempfile.TemporaryDirectory() as temporary:
            output_root = Path(temporary)
            compiled = output_root / "Player.ir.json"
            receipt = output_root / "player.receipt.json"
            with patch.object(Path, "write_text", windows_like_write_text):
                self.assertEqual(
                    _compile(Namespace(source=ROOT / "examples" / "Player.tevs", output=compiled)),
                    0,
                )
                self.assertEqual(
                    _conformance(
                        Namespace(
                            source=ROOT / "examples" / "Player.tevs",
                            scenario=ROOT / "conformance" / "player.scenario.json",
                            output=receipt,
                        )
                    ),
                    0,
                )
            for path in (compiled, receipt):
                payload = path.read_bytes()
                self.assertTrue(payload.endswith(b"\n"))
                self.assertNotIn(b"\r\n", payload)

    def test_javascript_distribution_fixtures_match_authority(self) -> None:
        fixture_root = ROOT / "javascript" / "fixtures"
        pairs = tuple(
            (authoritative, fixture_root / authoritative.relative_to(ROOT))
            for authoritative in (
                ROOT / "examples" / "Player.tevs.ir.json",
                ROOT / "examples" / "ConformanceMatrix.tevs.ir.json",
                ROOT / "examples" / "EventChain.tevs.ir.json",
                ROOT / "conformance" / "player.scenario.json",
                ROOT / "conformance" / "player.expected.json",
                ROOT / "conformance" / "matrix.scenario.json",
                ROOT / "conformance" / "matrix.expected.json",
                ROOT / "conformance" / "player-idle.scenario.json",
                ROOT / "conformance" / "player-idle.expected.json",
                ROOT / "conformance" / "event-chain.scenario.json",
                ROOT / "conformance" / "event-chain.expected.json",
                ROOT / "conformance" / "canonical.vectors.json",
            )
        )
        for authoritative, fixture in pairs:
            with self.subTest(fixture=fixture.name):
                self.assertEqual(fixture.read_bytes(), authoritative.read_bytes())


if __name__ == "__main__":
    unittest.main()
