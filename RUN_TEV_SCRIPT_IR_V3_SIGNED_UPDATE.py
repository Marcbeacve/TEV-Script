from __future__ import annotations

import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
root_text = str(ROOT)
if root_text not in sys.path:
    sys.path.insert(0, root_text)
existing = os.environ.get("PYTHONPATH")
os.environ["PYTHONPATH"] = root_text if not existing else root_text + os.pathsep + existing

from tools.validate_ir_v3_signed_update import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
