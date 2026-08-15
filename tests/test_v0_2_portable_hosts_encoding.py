from __future__ import annotations

import sys
import unittest

import tools.validate_v0_2_portable_hosts as portable_hosts


class V02PortableHostsEncodingTests(unittest.TestCase):
    def test_subprocess_output_with_non_utf8_bytes_is_captured_without_decoder_failure(self) -> None:
        completed = portable_hosts.run(
            [
                sys.executable,
                "-c",
                "import sys; sys.stdout.buffer.write(b'\\xe1\\n')",
            ]
        )

        self.assertEqual(completed.returncode, 0)
        self.assertIn("\ufffd", completed.stdout)


if __name__ == "__main__":
    unittest.main()
