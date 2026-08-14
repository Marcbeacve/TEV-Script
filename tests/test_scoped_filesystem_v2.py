from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from tev_script.diagnostics import TevScriptError
from tev_script import scoped_filesystem_v2 as scoped_filesystem
from tev_script.scoped_filesystem_v2 import (
    _consume_bounded_v2,
    open_scoped_root_v2,
    read_scoped_file_v2,
    replace_scoped_file_v2,
)


class ScopedFilesystemV2Tests(unittest.TestCase):
    def test_unavailable_secure_backend_fails_closed_without_path_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            with patch.object(scoped_filesystem, "_SECURE_BACKEND_AVAILABLE", False):
                with self.assertRaises(TevScriptError) as caught:
                    open_scoped_root_v2(raw)
            self.assertEqual(caught.exception.diagnostic.code, "TEVS_SCOPED_FS_UNSUPPORTED")

    def test_rejects_ambiguous_or_escaping_relative_paths_before_access(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw) / "root"
            root.mkdir()
            with open_scoped_root_v2(root) as scope:
                invalid = (
                    "",
                    ".",
                    "..",
                    "../outside.txt",
                    "/absolute.txt",
                    "a/./b.txt",
                    "a/../b.txt",
                    "name. ",
                    "stream:secret",
                    "NUL.txt",
                    "embedded\x00nul",
                )
                for value in invalid:
                    with self.subTest(value=value):
                        with self.assertRaises(TevScriptError) as caught:
                            read_scoped_file_v2(scope, value, maximum_bytes=16)
                        self.assertEqual(caught.exception.diagnostic.code, "TEVS_SCOPED_FS_PATH")

    def test_windows_unicode_name_lengths_fail_closed_before_ntcreatefile(self) -> None:
        accepted = "a" * 32_766
        rejected = "a" * 32_767

        self.assertEqual(scoped_filesystem._parse_relative(accepted), ((accepted,), accepted))
        with self.assertRaises(TevScriptError) as caught:
            scoped_filesystem._parse_relative(rejected)
        self.assertEqual(caught.exception.diagnostic.code, "TEVS_SCOPED_FS_PATH")

        if os.name == "nt":
            with patch.object(scoped_filesystem, "_NtCreateFile") as nt_create_file:
                with self.assertRaises(TevScriptError) as caught:
                    scoped_filesystem._win_open_relative(
                        0,
                        rejected,
                        desired_access=0,
                        create_disposition=0,
                        create_options=0,
                    )
            self.assertEqual(caught.exception.diagnostic.code, "TEVS_SCOPED_FS_PATH")
            nt_create_file.assert_not_called()

    def test_windows_unicode_name_surrogate_fails_closed_before_ntcreatefile(self) -> None:
        rejected = "\ud800"

        with self.assertRaises(TevScriptError) as caught:
            scoped_filesystem._parse_relative(rejected)
        self.assertEqual(caught.exception.diagnostic.code, "TEVS_SCOPED_FS_PATH")

        if os.name == "nt":
            with patch.object(scoped_filesystem, "_NtCreateFile") as nt_create_file:
                with self.assertRaises(TevScriptError) as caught:
                    scoped_filesystem._win_open_relative(
                        0,
                        rejected,
                        desired_access=0,
                        create_disposition=0,
                        create_options=0,
                    )
            self.assertEqual(caught.exception.diagnostic.code, "TEVS_SCOPED_FS_PATH")
            nt_create_file.assert_not_called()

    def test_scope_pins_root_object_across_path_replacement_for_read(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            parent = Path(raw)
            root = parent / "root"
            moved = parent / "root-original"
            root.mkdir()
            (root / "value.txt").write_text("authorized", encoding="utf-8")

            with open_scoped_root_v2(root) as scope:
                root.rename(moved)
                root.mkdir()
                (root / "value.txt").write_text("replacement", encoding="utf-8")
                observed = read_scoped_file_v2(scope, "value.txt", maximum_bytes=64)

            self.assertEqual(observed.data, b"authorized")
            self.assertEqual((root / "value.txt").read_bytes(), b"replacement")

    def test_scope_pins_root_object_across_path_replacement_for_replace(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            parent = Path(raw)
            root = parent / "root"
            moved = parent / "root-original"
            root.mkdir()
            (root / "value.txt").write_text("old", encoding="utf-8")

            with open_scoped_root_v2(root) as scope:
                root.rename(moved)
                root.mkdir()
                (root / "value.txt").write_text("outside-sentinel", encoding="utf-8")
                if os.name == "nt":
                    result = replace_scoped_file_v2(scope, "value.txt", b"new")
                else:
                    with self.assertRaises(TevScriptError) as caught:
                        replace_scoped_file_v2(scope, "value.txt", b"new")
                    self.assertEqual(caught.exception.diagnostic.code, "TEVS_SCOPED_FS_UNSUPPORTED")
                    result = None

            if os.name == "nt":
                self.assertIsNotNone(result)
                self.assertTrue(result.replaced)
                self.assertEqual((moved / "value.txt").read_bytes(), b"new")
            else:
                self.assertIsNone(result)
                self.assertEqual((moved / "value.txt").read_bytes(), b"old")
            self.assertEqual((root / "value.txt").read_bytes(), b"outside-sentinel")

    def test_posix_temporary_source_substitution_never_returns_success_receipt(self) -> None:
        intended = b"verified-content"
        attacker = b"attacker-content"
        model = {"target": b"old-content"}

        def substitute_source_and_replace(*_args: object, **_kwargs: object) -> None:
            model["target"] = attacker

        with (
            patch.object(scoped_filesystem.os, "name", "posix"),
            patch.object(scoped_filesystem.os, "O_NOFOLLOW", 0, create=True),
            patch.object(scoped_filesystem, "_require_scope", return_value=object()),
            patch.object(scoped_filesystem, "_posix_open_parent", return_value=101),
            patch.object(scoped_filesystem, "_posix_existing_bytes", return_value=None),
            patch.object(scoped_filesystem.secrets, "token_hex", return_value="race"),
            patch.object(scoped_filesystem.os, "open", return_value=202),
            patch.object(scoped_filesystem, "_posix_write_all"),
            patch.object(scoped_filesystem.os, "fsync"),
            patch.object(scoped_filesystem.os, "lseek"),
            patch.object(scoped_filesystem, "_consume_bounded_v2", return_value=intended),
            patch.object(scoped_filesystem.os, "replace", side_effect=substitute_source_and_replace),
            patch.object(scoped_filesystem.os, "unlink"),
            patch.object(scoped_filesystem.os, "close"),
        ):
            receipt = None
            try:
                receipt = replace_scoped_file_v2(object(), "target.bin", intended)
            except TevScriptError as error:
                self.assertEqual(error.diagnostic.code, "TEVS_SCOPED_FS_UNSUPPORTED")

        self.assertFalse(receipt is not None and model["target"] == attacker)
        self.assertEqual(model["target"], b"old-content")

    def test_posix_failure_cleanup_preserves_substituted_temporary_entry(self) -> None:
        model = {"substituted_entry_exists": True}

        def fail_replacement(*_args: object, **_kwargs: object) -> None:
            raise OSError("simulated destination failure after source substitution")

        def unlink_substituted_entry(*_args: object, **_kwargs: object) -> None:
            model["substituted_entry_exists"] = False

        with (
            patch.object(scoped_filesystem.os, "O_NOFOLLOW", 0, create=True),
            patch.object(scoped_filesystem, "_posix_open_parent", return_value=101),
            patch.object(scoped_filesystem, "_posix_existing_bytes", return_value=None),
            patch.object(scoped_filesystem.secrets, "token_hex", return_value="race"),
            patch.object(scoped_filesystem.os, "open", return_value=202),
            patch.object(scoped_filesystem, "_posix_write_all"),
            patch.object(scoped_filesystem.os, "fsync"),
            patch.object(scoped_filesystem.os, "lseek"),
            patch.object(scoped_filesystem, "_consume_bounded_v2", return_value=b"verified-content"),
            patch.object(scoped_filesystem.os, "replace", side_effect=fail_replacement),
            patch.object(scoped_filesystem.os, "unlink", side_effect=unlink_substituted_entry),
            patch.object(scoped_filesystem.os, "close"),
        ):
            with self.assertRaises(TevScriptError):
                scoped_filesystem._posix_replace(object(), ("target.bin",), "target.bin", b"verified-content")

        self.assertTrue(model["substituted_entry_exists"])

    def test_parent_link_or_junction_escape_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            parent = Path(raw)
            root = parent / "root"
            outside = parent / "outside"
            link = root / "escape"
            root.mkdir()
            outside.mkdir()
            (outside / "secret.txt").write_text("outside", encoding="utf-8")
            self._create_directory_link(link, outside)
            try:
                with open_scoped_root_v2(root) as scope:
                    with self.assertRaises(TevScriptError) as caught:
                        read_scoped_file_v2(scope, "escape/secret.txt", maximum_bytes=64)
                    self.assertEqual(caught.exception.diagnostic.code, "TEVS_SCOPED_FS_ESCAPE")
            finally:
                self._remove_directory_link(link)

    def test_parent_swap_to_junction_after_scope_open_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            parent = Path(raw)
            root = parent / "root"
            original = root / "parent-original"
            selected = root / "selected"
            outside = parent / "outside"
            root.mkdir()
            selected.mkdir()
            outside.mkdir()
            (selected / "value.txt").write_text("authorized", encoding="utf-8")
            (outside / "value.txt").write_text("outside-sentinel", encoding="utf-8")
            with open_scoped_root_v2(root) as scope:
                selected.rename(original)
                self._create_directory_link(selected, outside)
                try:
                    with self.assertRaises(TevScriptError) as caught:
                        read_scoped_file_v2(scope, "selected/value.txt", maximum_bytes=64)
                    self.assertEqual(caught.exception.diagnostic.code, "TEVS_SCOPED_FS_ESCAPE")
                finally:
                    self._remove_directory_link(selected)
            self.assertEqual((outside / "value.txt").read_bytes(), b"outside-sentinel")

    def test_bounded_consumer_never_requests_or_retains_more_than_limit_plus_one(self) -> None:
        payload = memoryview(b"x" * 4096)
        offset = 0
        requests: list[int] = []

        def read_chunk(maximum: int) -> bytes:
            nonlocal offset
            requests.append(maximum)
            self.assertLessEqual(maximum, 1025 - offset)
            size = min(maximum, 113, len(payload) - offset)
            chunk = bytes(payload[offset : offset + size])
            offset += size
            return chunk

        with self.assertRaises(TevScriptError) as caught:
            _consume_bounded_v2(read_chunk, 1024)
        self.assertEqual(caught.exception.diagnostic.code, "TEVS_SCOPED_FS_BUDGET")
        self.assertEqual(offset, 1025)

    def test_bounded_consumer_accepts_short_stream_and_hashes_exact_bytes(self) -> None:
        chunks = iter((b"abc", b"def", b""))
        data = _consume_bounded_v2(lambda _maximum: next(chunks), 6)
        self.assertEqual(data, b"abcdef")

    def test_posix_fifo_fails_closed_without_blocking_read_or_replace(self) -> None:
        if os.name == "nt":
            import inspect

            self.assertIn("O_NONBLOCK", inspect.getsource(scoped_filesystem._posix_open_file))
            self.assertIn("O_NONBLOCK", inspect.getsource(scoped_filesystem._posix_existing_bytes))
            return
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            os.mkfifo(root / "pipe")
            program = """
import sys
from tev_script.diagnostics import TevScriptError
from tev_script.scoped_filesystem_v2 import open_scoped_root_v2, read_scoped_file_v2, replace_scoped_file_v2
with open_scoped_root_v2(sys.argv[1]) as scope:
    for operation, expected_code in (
        (lambda: read_scoped_file_v2(scope, "pipe", maximum_bytes=16), "TEVS_SCOPED_FS_KIND"),
        (lambda: replace_scoped_file_v2(scope, "pipe", b"value"), "TEVS_SCOPED_FS_UNSUPPORTED"),
    ):
        try:
            operation()
        except TevScriptError as error:
            assert error.diagnostic.code == expected_code, error.diagnostic.code
        else:
            raise AssertionError("FIFO must fail closed")
"""
            completed = subprocess.run(
                [sys.executable, "-c", program, str(root)],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)

    @staticmethod
    def _create_directory_link(link: Path, target: Path) -> None:
        if os.name == "nt":
            completed = subprocess.run(
                ["cmd.exe", "/d", "/c", "mklink", "/J", str(link), str(target)],
                capture_output=True,
                text=True,
                check=False,
            )
            if completed.returncode != 0 or not link.exists():
                raise AssertionError(
                    "Windows junction creation is required by the V2 safety gate: "
                    + completed.stdout
                    + completed.stderr
                )
            return
        link.symlink_to(target, target_is_directory=True)

    @staticmethod
    def _remove_directory_link(link: Path) -> None:
        if not os.path.lexists(link):
            return
        if os.name == "nt":
            os.rmdir(link)
        else:
            link.unlink()


if __name__ == "__main__":
    unittest.main()
