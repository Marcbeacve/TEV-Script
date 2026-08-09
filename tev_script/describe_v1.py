from __future__ import annotations

from .descriptor_v1 import v1_descriptor_json


def main() -> int:
    print(v1_descriptor_json())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
