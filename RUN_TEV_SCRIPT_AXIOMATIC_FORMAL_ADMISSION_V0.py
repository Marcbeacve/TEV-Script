from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import tempfile

from tools.validate_axiomatic_formal_evidence_v0 import validate_evidence_dir

ROOT = Path(__file__).resolve().parent


def _git(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return completed.stdout.strip()


def _identity() -> tuple[str, str, str]:
    if _git("status", "--porcelain"):
        raise RuntimeError("axiomatic formal admission requires a clean checkout")
    branch = _git("branch", "--show-current")
    if not branch:
        raise RuntimeError("axiomatic formal admission requires a named branch")
    return branch, _git("rev-parse", "HEAD"), _git("rev-parse", "HEAD^{tree}")


def _outside_repo(path: Path) -> None:
    resolved = path.resolve()
    try:
        resolved.relative_to(ROOT.resolve())
    except ValueError:
        return
    raise RuntimeError("axiomatic formal receipt output must be outside repository")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", required=True)
    parser.add_argument("--receipt-out", required=True)
    args = parser.parse_args()

    evidence_dir = Path(args.evidence_dir).expanduser().resolve()
    receipt_out = Path(args.receipt_out).expanduser().resolve()
    _outside_repo(receipt_out)
    if receipt_out.exists():
        raise RuntimeError("axiomatic formal receipt output must not already exist")
    if not evidence_dir.is_dir():
        raise RuntimeError("axiomatic formal evidence directory missing")

    branch, head, tree = _identity()
    failures, receipt = validate_evidence_dir(
        evidence_dir,
        root=ROOT,
        branch=branch,
        head=head,
        tree=tree,
    )
    if failures or receipt is None:
        for failure in failures:
            print("TEV_SCRIPT_AXIOMATIC_FORMAL_ADMISSION_V0=FAIL:" + failure)
        return 1

    receipt_out.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        receipt.to_object(),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ) + "\n"
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="\n",
        dir=receipt_out.parent,
        delete=False,
    ) as handle:
        handle.write(payload)
        temp = Path(handle.name)
    temp.replace(receipt_out)

    print("AXIOMATIC_SOURCE_BRANCH=" + branch)
    print("AXIOMATIC_SOURCE_HEAD=" + head)
    print("AXIOMATIC_SOURCE_TREE=" + tree)
    print("AXIOMATIC_FORMAL_RECEIPT=" + str(receipt_out))
    print("AXIOMATIC_FORMAL_RECEIPT_HASH=" + receipt.receipt_hash)
    print("TEV_SCRIPT_AXIOMATIC_FORMAL_ADMISSION_V0=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
