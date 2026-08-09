from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def generate(baseline: Path, counterfactual: Path, out: Path) -> None:
    base = json.loads(baseline.read_text(encoding="utf-8"))
    counter = json.loads(counterfactual.read_text(encoding="utf-8"))
    if len(base["invocations"]) != len(counter["invocations"]):
        raise RuntimeError("GATE7_PREFIX_INVOCATION_COUNT_MISMATCH")
    out.mkdir(parents=True, exist_ok=True)
    for index in range(1, len(base["invocations"]) + 1):
        b = dict(base)
        c = dict(counter)
        b["invocations"] = base["invocations"][:index]
        c["invocations"] = counter["invocations"][:index]
        (out / f"baseline.{index}.json").write_text(
            json.dumps(b, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        (out / f"counterfactual.{index}.json").write_text(
            json.dumps(c, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(f"GATE7_PREFIX_SCENARIOS={len(base['invocations'])}_PASS")


def detect(
    baseline: Path,
    counterfactual: Path,
    prefix_dir: Path,
    baseline_receipts: Path,
    counter_receipts: Path,
    expected: int,
) -> None:
    base = json.loads(baseline.read_text(encoding="utf-8"))
    counter = json.loads(counterfactual.read_text(encoding="utf-8"))

    first_input = None
    for index, (left, right) in enumerate(
        zip(base["invocations"], counter["invocations"]), start=1
    ):
        if canonical_bytes(left) != canonical_bytes(right):
            first_input = index
            break

    first_receipt = None
    reconverged = False
    for index in range(1, len(base["invocations"]) + 1):
        left = (baseline_receipts / f"baseline.{index}.receipt.json").read_bytes()
        right = (counter_receipts / f"counterfactual.{index}.receipt.json").read_bytes()
        if left != right and first_receipt is None:
            first_receipt = index
        if first_receipt is not None and index > first_receipt and left == right:
            reconverged = True

    if first_input != expected:
        raise RuntimeError(
            f"GATE7_INPUT_DIVERGENCE_MISMATCH expected={expected} observed={first_input}"
        )
    if first_receipt != expected:
        raise RuntimeError(
            f"GATE7_RECEIPT_DIVERGENCE_MISMATCH expected={expected} observed={first_receipt}"
        )

    witness = {
        "schema": "TEV_SCRIPT_GATE7_DIVERGENCE_WITNESS_V1",
        "first_input_divergence": first_input,
        "first_receipt_divergence": first_receipt,
        "eventual_reconvergence_observed": reconverged,
        "baseline_scenario_sha256": hashlib.sha256(
            baseline.read_bytes()
        ).hexdigest(),
        "counterfactual_scenario_sha256": hashlib.sha256(
            counterfactual.read_bytes()
        ).hexdigest(),
    }
    (prefix_dir / "divergence-witness.json").write_text(
        json.dumps(witness, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    print(f"GATE7C_FIRST_DIVERGENCE_INDEX={expected}")
    print("GATE7C_PRE_DIVERGENCE_PREFIX_PARITY=PASS")
    print("GATE7C_FIRST_DIVERGENCE_LOCALIZATION=PASS")
    if reconverged:
        print("GATE7C_EVENTUAL_RECONVERGENCE=OBSERVED")


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("generate")
    gen.add_argument("--baseline", required=True)
    gen.add_argument("--counterfactual", required=True)
    gen.add_argument("--out", required=True)

    det = sub.add_parser("detect")
    det.add_argument("--baseline", required=True)
    det.add_argument("--counterfactual", required=True)
    det.add_argument("--prefix-dir", required=True)
    det.add_argument("--baseline-receipts", required=True)
    det.add_argument("--counterfactual-receipts", required=True)
    det.add_argument("--expected", type=int, required=True)

    args = parser.parse_args()
    if args.command == "generate":
        generate(Path(args.baseline), Path(args.counterfactual), Path(args.out))
    else:
        detect(
            Path(args.baseline),
            Path(args.counterfactual),
            Path(args.prefix_dir),
            Path(args.baseline_receipts),
            Path(args.counterfactual_receipts),
            args.expected,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
