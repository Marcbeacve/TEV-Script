from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from tools import validate_ir_v3_browser_wasm as browser_gate


class BrowserProfileCleanupTests(unittest.TestCase):
    def test_windows_cleanup_has_outer_timeout_and_exact_profile_environment(self) -> None:
        completed = subprocess.CompletedProcess(["powershell.exe"], 0, "", "")
        with tempfile.TemporaryDirectory() as raw:
            profile = Path(raw) / "profile"
            with (
                patch.object(browser_gate.os, "name", "nt"),
                patch.object(browser_gate, "_stop_process"),
                patch.object(browser_gate.subprocess, "run", return_value=completed) as run,
            ):
                browser_gate._stop_browser_process(None, profile)
        _args, kwargs = run.call_args
        self.assertEqual(kwargs["timeout"], 35)
        self.assertEqual(
            kwargs["env"]["TEV_BROWSER_PROFILE_CLEANUP"],
            str(profile.resolve()),
        )
        command = _args[0]
        self.assertIn("$_.CommandLine.Contains($needle)", command[-1])

    def test_windows_cleanup_nonzero_exit_fails_closed_with_diagnostics(self) -> None:
        completed = subprocess.CompletedProcess(
            ["powershell.exe"],
            1,
            "cleanup-out",
            "cleanup-err",
        )
        with tempfile.TemporaryDirectory() as raw:
            profile = Path(raw) / "profile"
            with (
                patch.object(browser_gate.os, "name", "nt"),
                patch.object(browser_gate, "_stop_process"),
                patch.object(browser_gate.subprocess, "run", return_value=completed),
            ):
                with self.assertRaisesRegex(RuntimeError, "cleanup-out.*cleanup-err"):
                    browser_gate._stop_browser_process(None, profile)

    def test_windows_cleanup_timeout_is_a_gate_failure(self) -> None:
        expired = subprocess.TimeoutExpired(["powershell.exe"], 35, output="late-out", stderr="late-err")
        with tempfile.TemporaryDirectory() as raw:
            profile = Path(raw) / "profile"
            with (
                patch.object(browser_gate.os, "name", "nt"),
                patch.object(browser_gate, "_stop_process"),
                patch.object(browser_gate.subprocess, "run", side_effect=expired),
            ):
                with self.assertRaisesRegex(RuntimeError, "timed out.*late-out.*late-err"):
                    browser_gate._stop_browser_process(None, profile)

    def test_windows_cim_enumeration_failure_is_a_gate_failure(self) -> None:
        def simulate_cim_failure(
            arguments: list[str],
            **_kwargs: object,
        ) -> subprocess.CompletedProcess[str]:
            command = arguments[-1]
            terminating = (
                "$ErrorActionPreference='Stop'" in command
                and "Get-CimInstance Win32_Process -ErrorAction Stop" in command
            )
            return subprocess.CompletedProcess(
                arguments,
                1 if terminating else 0,
                "",
                "simulated CIM enumeration failure" if terminating else "",
            )

        with tempfile.TemporaryDirectory() as raw:
            profile = Path(raw) / "profile"
            with (
                patch.object(browser_gate.os, "name", "nt"),
                patch.object(browser_gate, "_stop_process"),
                patch.object(browser_gate.subprocess, "run", side_effect=simulate_cim_failure),
            ):
                with self.assertRaisesRegex(RuntimeError, "simulated CIM enumeration failure"):
                    browser_gate._stop_browser_process(None, profile)

    def test_hung_taskkill_is_bounded_and_continues_to_profile_fallback(self) -> None:
        process = MagicMock()
        process.pid = 4242
        process.poll.return_value = None
        process.wait.side_effect = subprocess.TimeoutExpired(["browser.exe"], 5)
        calls: list[tuple[list[str], dict[str, object]]] = []

        def simulate_hung_taskkill(
            arguments: list[str],
            **kwargs: object,
        ) -> subprocess.CompletedProcess[str]:
            calls.append((arguments, kwargs))
            if arguments[0] == "taskkill":
                raise subprocess.TimeoutExpired(arguments, kwargs.get("timeout", 0))
            return subprocess.CompletedProcess(arguments, 0, "", "")

        with tempfile.TemporaryDirectory() as raw:
            profile = Path(raw) / "profile"
            with (
                patch.object(browser_gate.os, "name", "nt"),
                patch.object(browser_gate.subprocess, "run", side_effect=simulate_hung_taskkill),
            ):
                try:
                    browser_gate._stop_browser_process(process, profile)
                except subprocess.TimeoutExpired as error:
                    self.fail(f"hung taskkill escaped instead of continuing to fallback: {error}")

        self.assertEqual([call[0][0] for call in calls], ["taskkill", "powershell.exe"])
        self.assertEqual(calls[0][1]["timeout"], 5)


if __name__ == "__main__":
    unittest.main()
