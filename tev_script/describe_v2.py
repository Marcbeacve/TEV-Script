from __future__ import annotations

from .descriptor_v2 import v2_descriptor_json


def main() -> int:
    print(v2_descriptor_json())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
