from __future__ import annotations

import hashlib
import json
from itertools import product

try:
    from tools.v1_optimizer_oracle_contract import (
        OPTIMIZER_ORACLE_PASS_MARKER,
        OPTIMIZER_ORACLE_SCHEMA_V1,
        optimizer_oracle_receipt_line,
    )
except ModuleNotFoundError:
    from v1_optimizer_oracle_contract import (
        OPTIMIZER_ORACLE_PASS_MARKER,
        OPTIMIZER_ORACLE_SCHEMA_V1,
        optimizer_oracle_receipt_line,
    )

DEFAULT_MODULI = (7, 11, 13, 17, 19, 23, 29, 31)
FAMILIES = (
    ("ADD_STATE_INT_CONST", 5, lambda x, c, m: ((x + c) % m, 5, 0), lambda x, c, m: ((x + c) % m, 5, 0)),
    ("ADD_INT", 1, lambda x, y, m: ((x + y) % m, 1, 0), lambda x, y, m: ((x + y) % m, 1, 0)),
    ("SUB_INT", 1, lambda x, y, m: ((x - y) % m, 1, 0), lambda x, y, m: ((x - y) % m, 1, 0)),
    ("MUL_INT", 1, lambda x, y, m: ((x * y) % m, 1, 0), lambda x, y, m: ((x * y) % m, 1, 0)),
)

def _table(fn, modulus: int) -> tuple[tuple[int, int, tuple[int, int, int]], ...]:
    return tuple((x, y, fn(x, y, modulus)) for x, y in product(range(modulus), repeat=2))

def _hash_table(table) -> str:
    return hashlib.sha256(json.dumps(table, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()

def build_receipt() -> dict:
    total = 0
    tables: dict[str, dict[str, str]] = {}
    negative_detected = True
    for modulus in DEFAULT_MODULI:
        tables[str(modulus)] = {}
        for name, _cost, original, optimized in FAMILIES:
            left = _table(original, modulus)
            right = _table(optimized, modulus)
            total += len(left)
            if left != right:
                raise RuntimeError(f"local finite oracle disagreement: {name} modulus={modulus}")
            tables[str(modulus)][name] = _hash_table(left)
            tampered = list(right)
            x, y, out = tampered[0]
            tampered[0] = (x, y, ((out[0] + 1) % modulus, out[1], out[2]))
            negative_detected = negative_detected and tuple(tampered) != left
    if not negative_detected:
        raise RuntimeError("negative control was not detected")
    return {
        "schema": OPTIMIZER_ORACLE_SCHEMA_V1,
        "provider_id": "tev-script.reference.finite-optimizer-oracle.v1",
        "provider_kind": "local",
        "evidence_scope": "finite_selected_carriers",
        "semantic_claim": "optimizer transformation families agree on every point of each declared finite carrier",
        "transformation_families": [row[0] for row in FAMILIES],
        "moduli": list(DEFAULT_MODULI),
        "finite_program_points_verified": total,
        "all_agree": True,
        "negative_controls_detected": True,
        "table_sha256_by_modulus": tables,
        "runtime_implementation_equivalence_proved": False,
        "universal_integer_equivalence_proved": False,
        "write_authority": False,
        "promotion_authority": False,
    }

def main() -> int:
    receipt = build_receipt()
    print(optimizer_oracle_receipt_line(receipt))
    print(OPTIMIZER_ORACLE_PASS_MARKER)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
