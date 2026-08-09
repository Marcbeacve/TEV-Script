import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import {
  RecordValueV3,
  VariantValueV3,
  Rational,
  ScriptRuntimeV3,
} from "../src/runtime-v3.mjs";
import {
  buildTypeTableV3,
  decodeV3Value,
  encodeV3Value,
  v3ValuesEqual,
} from "../src/ir-v3-values.mjs";
import { validateProgramIrV3 } from "../src/ir-v3-validation.mjs";

const CASES = JSON.parse(
  readFileSync(new URL("../../conformance/ir-v3-validator-cases.json", import.meta.url), "utf8"),
);

function clone(value) {
  return structuredClone(value);
}

function mutate(program, mutation) {
  const result = clone(program);
  let target = result;
  for (const segment of mutation.path) target = target[segment];
  if (mutation.operation === "set") {
    let parent = result;
    for (const segment of mutation.path.slice(0, -1)) parent = parent[segment];
    parent[mutation.path.at(-1)] = clone(mutation.value);
  } else if (mutation.operation === "swap") {
    const left = mutation.left;
    const right = mutation.right;
    [target[left], target[right]] = [target[right], target[left]];
  } else {
    throw new Error(`unknown mutation ${mutation.operation}`);
  }
  return result;
}

function assertRational(value, numerator, denominator) {
  assert.ok(value instanceof Rational);
  assert.equal(value.numerator, BigInt(numerator));
  assert.equal(value.denominator, BigInt(denominator));
}

test("IR V3 JavaScript validates the shared portable positive program", () => {
  const table = validateProgramIrV3(clone(CASES.valid_program), {
    expectedSourceSemanticHash: "1".repeat(64),
  });
  assert.equal(table.require("Root.Pair").kind, "record");
  assert.equal(table.require("Option<Int>").argument, "Int");
  assert.equal(table.require("Result<Int,Text>").errType, "Text");
});

test("IR V3 JavaScript rejects every shared negative mutation with the expected category", () => {
  for (const mutation of CASES.negative_mutations) {
    const program = mutate(CASES.valid_program, mutation);
    assert.throws(
      () => validateProgramIrV3(program),
      (error) => {
        assert.equal(error.code, mutation.code, mutation.id);
        return true;
      },
      mutation.id,
    );
  }
});

test("IR V3 JavaScript codec roundtrips canonical records, enum, Option and Result", () => {
  const table = buildTypeTableV3(CASES.valid_program);
  const record = new RecordValueV3("Root.Pair", [
    ["b", new Rational(3n, 2n)],
    ["a", 7n],
  ]);
  const encodedRecord = encodeV3Value("Root.Pair", record, table);
  assert.deepEqual(encodedRecord, {
    $record: {
      type: "Root.Pair",
      fields: [
        { name: "a", value: { $int: "7" } },
        { name: "b", value: { $rat: ["3", "2"] } },
      ],
    },
  });
  const decodedRecord = decodeV3Value("Root.Pair", encodedRecord, table);
  assert.ok(v3ValuesEqual(
    "Root.Pair",
    decodedRecord,
    new RecordValueV3("Root.Pair", [["a", 7n], ["b", new Rational(3n, 2n)]]),
    table,
  ));

  for (const [typeId, value] of [
    ["Root.Kind", new VariantValueV3("Root.Kind", "B")],
    ["Option<Int>", new VariantValueV3("Option<Int>", "None")],
    ["Option<Int>", new VariantValueV3("Option<Int>", "Some", 9n)],
    ["Result<Int,Text>", new VariantValueV3("Result<Int,Text>", "Ok", 3n)],
    ["Result<Int,Text>", new VariantValueV3("Result<Int,Text>", "Err", "bad")],
  ]) {
    const encoded = encodeV3Value(typeId, value, table);
    const decoded = decodeV3Value(typeId, encoded, table);
    assert.ok(v3ValuesEqual(typeId, value, decoded, table), `${typeId}/${value.variant}`);
  }
});

test("IR V3 JavaScript preserves V0.2 Vec2 and Vec3 external encoding", () => {
  const table = buildTypeTableV3(CASES.valid_program);
  assert.deepEqual(
    encodeV3Value("Vec2", [new Rational(1n, 2n), new Rational(-3n)], table),
    [{ $rat: ["1", "2"] }, { $rat: ["-3", "1"] }],
  );
  assert.deepEqual(
    encodeV3Value("Vec3", [new Rational(0n), new Rational(1n, 3n), new Rational(2n)], table),
    [{ $rat: ["0", "1"] }, { $rat: ["1", "3"] }, { $rat: ["2", "1"] }],
  );
});

test("IR V3 JavaScript executes all new algebraic operations deterministically", () => {
  const runtime = new ScriptRuntimeV3(clone(CASES.valid_program), {}, {
    expectedSourceSemanticHash: "1".repeat(64),
  });
  assert.deepEqual(runtime.invoke("E", "start"), []);
  const state = runtime.state("E");
  assert.equal(state.count, 7n);
  assert.ok(state.pair instanceof RecordValueV3);
  assert.equal(state.pair.field("a"), 2n);
  assertRational(state.pair.field("b"), 3, 1);
  assert.deepEqual([state.kind.typeId, state.kind.variant], ["Root.Kind", "B"]);
  assert.deepEqual([state.opt.typeId, state.opt.variant, state.opt.payload], ["Option<Int>", "Some", 7n]);
  assert.deepEqual([state.result.typeId, state.result.variant, state.result.payload], ["Result<Int,Text>", "Err", "bad"]);
});

test("IR V3 JavaScript canonical state matches portable recursive encoding", () => {
  const runtime = new ScriptRuntimeV3(clone(CASES.valid_program));
  runtime.invoke("E", "start");
  const state = runtime.canonicalState("E");
  assert.deepEqual(state.count, { $int: "7" });
  assert.deepEqual(state.pair, {
    $record: {
      type: "Root.Pair",
      fields: [
        { name: "a", value: { $int: "2" } },
        { name: "b", value: { $rat: ["3", "1"] } },
      ],
    },
  });
  assert.deepEqual(state.opt, {
    $option: { type: "Option<Int>", variant: "Some", value: { $int: "7" } },
  });
});

test("IR V3 JavaScript capability boundary accepts canonical record output and passes semantic record input", () => {
  const observed = [];
  const runtime = new ScriptRuntimeV3(clone(CASES.valid_program), {
    "world.read": () => ({
      $record: {
        type: "Root.Pair",
        fields: [
          { name: "a", value: { $int: "10" } },
          { name: "b", value: { $rat: ["1", "2"] } },
        ],
      },
    }),
    "sink.write": (value) => observed.push(value),
  });
  runtime.invoke("E", "pulse");
  const pair = runtime.state("E").pair;
  assert.equal(pair.field("a"), 10n);
  assertRational(pair.field("b"), 1, 2);
  assert.equal(observed.length, 1);
  assert.ok(v3ValuesEqual("Root.Pair", observed[0], pair, runtime.typeTable));
});

test("IR V3 JavaScript emitted algebraic event carries the same typed canonical witness", () => {
  const runtime = new ScriptRuntimeV3(clone(CASES.valid_program));
  const emitted = runtime.invoke("E", "update");
  assert.equal(emitted.length, 1);
  assert.equal(emitted[0].event_id, "changed");
  assert.deepEqual(emitted[0].argument_types, ["Root.Pair", "Option<Int>"]);
  const encoded = runtime.canonicalEventArguments(emitted[0]);
  assert.deepEqual(encoded[0], CASES.valid_program.entities[0].states[3].initial);
  assert.deepEqual(encoded[1], CASES.valid_program.entities[0].states[2].initial);
});

test("IR V3 JavaScript wrong variant unwrap is a deterministic runtime fault", () => {
  const program = clone(CASES.valid_program);
  const start = program.entities[0].handlers[1];
  start.locals = [];
  start.instructions = [
    { op: "LOAD_STATE", name: "opt", type: "Option<Int>" },
    { op: "LOAD_VARIANT_PAYLOAD", type: "Option<Int>", variant: "Some", payload_type: "Int" },
    { op: "STORE_STATE", name: "count", type: "Int" },
    { op: "RETURN" },
  ];
  start.instruction_budget = 4;
  // The semantic hash must correspond to this deliberately different valid IR.
  const semantic = Object.fromEntries(
    Object.entries(program).filter(([key]) => !["semantic_hash", "debug", "debug_hash"].includes(key)),
  );
  // Avoid importing another helper only for this test.
  return import("../src/canonical.mjs").then(({ canonicalHash }) => {
    program.semantic_hash = canonicalHash(semantic);
    const runtime = new ScriptRuntimeV3(program);
    assert.throws(
      () => runtime.invoke("E", "start"),
      (error) => error.code === "TEVS_IR_V3_VARIANT_UNWRAP",
    );
    assert.equal(runtime.state("E").count, 0n);
  });
});

test("IR V3 JavaScript missing capability fails closed", () => {
  const runtime = new ScriptRuntimeV3(clone(CASES.valid_program));
  assert.throws(
    () => runtime.invoke("E", "pulse"),
    (error) => error.code === "TEVS_IR_V3_CAPABILITY_MISSING",
  );
});

test("IR V3 JavaScript unhandled zero-argument event remains observable without host inference", () => {
  const runtime = new ScriptRuntimeV3(clone(CASES.valid_program));
  const emitted = runtime.invoke("E", "external");
  assert.equal(emitted.length, 1);
  assert.deepEqual(emitted[0], {
    entity_id: "E",
    event_id: "external",
    argument_types: [],
    arguments: [],
  });
});

test("IR V3 JavaScript unhandled event with undeclared argument signature fails closed", () => {
  const runtime = new ScriptRuntimeV3(clone(CASES.valid_program));
  assert.throws(
    () => runtime.invoke("E", "external", 1n),
    (error) => error.code === "TEVS_IR_V3_EVENT_SIGNATURE_UNKNOWN",
  );
});
