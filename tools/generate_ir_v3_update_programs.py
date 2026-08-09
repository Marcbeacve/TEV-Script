from __future__ import annotations

import argparse
import json
from pathlib import Path

from tev_script.linked_program_v1 import emit_linked_program_v1
from tev_script.linker_v1 import SourceInputV1, link_v1_sources
from tev_script.lowering_ir_v3_linked_v1 import lower_linked_program_v1_to_ir_v3
from tev_script.static_semantics_v1 import analyze_v1_static_semantics


BASE = '''script Root version "1.0.0";
record Pair { a: Int; b: Rat; }
capability sink.write(Pair) -> Unit effect;
entity E {
  state opt: Option<Int> = Some(1);
  state out: Int = 0;
  state pair: Pair = Pair(a = 1, b = 2);
  on pulse { call sink.write(pair); }
  on start {
    match opt {
      Some(value) => { out = value; }
      None => { out = 0; }
    }
  }
}
'''

TARGET1 = '''script Root version "1.0.0";
record Pair { a: Int; b: Rat; }
capability sink.write(Pair) -> Unit effect;
entity E {
  state marker: Int = 11;
  state opt: Option<Int> = Some(1);
  state out: Int = 0;
  state pair: Pair = Pair(a = 1, b = 2);
  on pulse { call sink.write(pair); }
  on start {
    match opt {
      Some(value) => { out = value + 10; }
      None => { out = 10; }
    }
  }
}
'''

TARGET2 = TARGET1.replace("value + 10", "value + 20").replace("out = 10", "out = 20").replace("marker: Int = 11", "marker: Int = 22")
TARGET3 = TARGET1.replace("value + 10", "value + 30").replace("out = 10", "out = 30").replace("marker: Int = 11", "marker: Int = 33")

REMOVED_STATE = '''script Root version "1.0.0";
record Pair { a: Int; b: Rat; }
capability sink.write(Pair) -> Unit effect;
entity E {
  state opt: Option<Int> = Some(1);
  state pair: Pair = Pair(a = 1, b = 2);
  on pulse { call sink.write(pair); }
  on start { return; }
}
'''

TYPE_CHANGED = '''script Root version "1.0.0";
record Pair { a: Int; b: Rat; }
capability sink.write(Pair) -> Unit effect;
entity E {
  state opt: Option<Int> = Some(1);
  state out: Rat = 0;
  state pair: Pair = Pair(a = 1, b = 2);
  on pulse { call sink.write(pair); }
  on start {
    match opt {
      Some(value) => { out = value; }
      None => { out = 0; }
    }
  }
}
'''

CAPABILITY_ABI_CHANGED = '''script Root version "1.0.0";
record Pair { a: Int; b: Rat; }
capability sink.write(Text) -> Unit effect;
entity E {
  state opt: Option<Int> = Some(1);
  state out: Int = 0;
  state pair: Pair = Pair(a = 1, b = 2);
  on pulse { call sink.write("changed"); }
  on start { out = 9; }
}
'''

RECORD_ABI_CHANGED = '''script Root version "1.0.0";
record Pair { a: Int; b: Rat; c: Int; }
capability sink.write(Pair) -> Unit effect;
entity E {
  state opt: Option<Int> = Some(1);
  state out: Int = 0;
  state pair: Pair = Pair(a = 1, b = 2, c = 3);
  on pulse { call sink.write(pair); }
  on start {
    match opt {
      Some(value) => { out = value + 40; }
      None => { out = 40; }
    }
  }
}
'''

PROGRAMS = {
    "base": BASE,
    "target1": TARGET1,
    "target2": TARGET2,
    "target3": TARGET3,
    "removed_state": REMOVED_STATE,
    "type_changed": TYPE_CHANGED,
    "capability_abi_changed": CAPABILITY_ABI_CHANGED,
    "record_abi_changed": RECORD_ABI_CHANGED,
}


def compile_v3(source: str):
    plan = link_v1_sources([SourceInputV1("root.tevs", source.encode("utf-8"))])
    semantics = analyze_v1_static_semantics(plan)
    linked = emit_linked_program_v1(semantics)
    target = lower_linked_program_v1_to_ir_v3(linked)
    if target.ir["source_semantic_hash"] != linked.semantic_hash:
        raise RuntimeError("IR V3 source semantic hash binding mismatch")
    return linked, target


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    arguments = parser.parse_args()
    output = Path(arguments.out)
    output.mkdir(parents=True, exist_ok=True)

    manifest: dict[str, object] = {
        "schema": "TEV_SCRIPT_IR_V3_UPDATE_PROGRAM_FIXTURES_V1",
        "programs": [],
    }
    hashes: set[str] = set()
    source_hashes: set[str] = set()
    for name, source in PROGRAMS.items():
        linked, target = compile_v3(source)
        if target.ir["semantic_hash"] in hashes:
            raise RuntimeError(f"duplicate target IR semantic hash for {name}")
        if linked.semantic_hash in source_hashes:
            raise RuntimeError(f"duplicate linked source semantic hash for {name}")
        hashes.add(target.ir["semantic_hash"])
        source_hashes.add(linked.semantic_hash)
        path = output / f"{name}.ir.json"
        path.write_text(target.canonical_json, encoding="utf-8", newline="")
        manifest["programs"].append(
            {
                "id": name,
                "file": path.name,
                "source_semantic_hash": linked.semantic_hash,
                "ir_semantic_hash": target.ir["semantic_hash"],
            }
        )

    manifest["programs"] = sorted(manifest["programs"], key=lambda item: item["id"])
    manifest_path = output / "programs.manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False),
        encoding="utf-8",
        newline="",
    )
    print("TEV_SCRIPT_IR_V3_UPDATE_SOURCE_DERIVATION=PASS")
    print("TEV_SCRIPT_IR_V3_UPDATE_PROGRAMS=" + str(len(PROGRAMS)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
