from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class WasiAuthorityBoundaryTests(unittest.TestCase):
    def test_wasi_process_linkage_does_not_surface_network_api_in_v3_source(self) -> None:
        roots = (
            ROOT / "runtimes" / "csharp" / "TevScript.Core",
            ROOT / "runtimes" / "csharp" / "TevScript.V3WasiGate",
            ROOT / "runtimes" / "csharp" / "TevScript.V3WasiSignedUpdateGate",
        )
        sources = [path for root in roots for path in root.glob("*.cs")]
        self.assertGreater(len(sources), 0)
        combined = "\n".join(path.read_text(encoding="utf-8") for path in sources)

        for forbidden in (
            "System.Net",
            "HttpClient",
            "HttpRequestMessage",
            "WebRequest",
            "TcpClient",
            "UdpClient",
            "System.Net.Sockets",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, combined)

    def test_wasmtime_http_switch_is_host_linkage_not_tev_capability(self) -> None:
        normal_tool = (ROOT / "tools" / "validate_ir_v3_wasi.py").read_text(encoding="utf-8")
        signed_tool = (ROOT / "tools" / "validate_ir_v3_wasi_signed_update.py").read_text(encoding="utf-8")
        normal_gate = (ROOT / "runtimes" / "csharp" / "TevScript.V3WasiGate" / "Program.cs").read_text(encoding="utf-8")
        signed_gate = (ROOT / "runtimes" / "csharp" / "TevScript.V3WasiSignedUpdateGate" / "Program.cs").read_text(encoding="utf-8")

        self.assertIn('"-S",', normal_tool)
        self.assertIn('"http",', normal_tool)
        self.assertIn('"-S",', signed_tool)
        self.assertIn('"http",', signed_tool)

        self.assertNotIn("http", normal_gate.lower())
        self.assertNotIn("http", signed_gate.lower())
        self.assertNotIn("capability http", normal_gate.lower())
        self.assertNotIn("capability http", signed_gate.lower())


if __name__ == "__main__":
    unittest.main()
