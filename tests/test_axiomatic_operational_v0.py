from __future__ import annotations

from tools.validate_axiomatic_operational_v0 import validate


def test_axiomatic_operational_v0() -> None:
    assert validate() == ()
