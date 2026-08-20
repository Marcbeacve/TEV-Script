from __future__ import annotations

from pathlib import Path

import RUN_PORTABLE_CONFORMANCE as portable


ROOT = Path(__file__).resolve().parents[1]


def test_python_receipt_bytes_match_authoritative_player_vector_without_generic_cli() -> None:
    observed = portable.python_receipt_bytes(
        ROOT / "examples" / "Player.tevs",
        ROOT / "conformance" / "player.scenario.json",
    )
    expected = (ROOT / "conformance" / "player.expected.json").read_bytes()
    assert observed == expected
