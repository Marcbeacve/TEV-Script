from __future__ import annotations
import json
from .descriptor_v3 import v3_descriptor

def main(argv: list[str] | None = None) -> int:
    if argv not in (None, []):
        raise SystemExit("tev-script-v3-describe accepts no arguments")
    print(json.dumps(v3_descriptor(), sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
