import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import path from "node:path";
import test from "node:test";
import { canonicalHash, canonicalJson, sha256Hex } from "../src/canonical.mjs";
import { runConformance } from "../src/conformance.mjs";
import { parseStrictJson } from "../src/strict-json.mjs";
import { readStrictJsonFile } from "../src/strict-json-node.mjs";
import { Rational, ScriptRuntime, TevScriptError, encodeTypedValue } from "../src/runtime.mjs";

const root = path.resolve(import.meta.dirname, "../fixtures");
const ir = await readStrictJsonFile(path.join(root, "examples/Player.tevs.ir.json"));
const scenario = await readStrictJsonFile(path.join(root, "conformance/player.scenario.json"));
const expected = await readFile(path.join(root, "conformance/player.expected.json"), "utf8");
const matrixIr = await readStrictJsonFile(
  path.join(root, "examples/ConformanceMatrix.tevs.ir.json"),
);
const matrixScenario = await readStrictJsonFile(
  path.join(root, "conformance/matrix.scenario.json"),
);
const matrixExpected = await readFile(
  path.join(root, "conformance/matrix.expected.json"),
  "utf8",
);
const idleScenario = await readStrictJsonFile(
  path.join(root, "conformance/player-idle.scenario.json"),
);
const idleExpected = await readFile(
  path.join(root, "conformance/player-idle.expected.json"),
  "utf8",
);
const eventChainIr = await readStrictJsonFile(
  path.join(root, "examples/EventChain.tevs.ir.json"),
);
const eventChainScenario = await readStrictJsonFile(
  path.join(root, "conformance/event-chain.scenario.json"),
);
const eventChainExpected = await readFile(
  path.join(root, "conformance/event-chain.expected.json"),
  "utf8",
);

function semanticPart(program) {
  return Object.fromEntries(
    Object.entries(program).filter(([key]) => !["semantic_hash", "debug", "debug_hash"].includes(key)),
  );
}

const canonicalVectors = await readStrictJsonFile(
  path.join(root, "conformance/canonical.vectors.json"),
);

test("pure JavaScript SHA-256 matches standard vectors", () => {
  assert.equal(
    sha256Hex("abc"),
    "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
  );
  assert.equal(
    sha256Hex(""),
    "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  );
});

test("TEV canonical JSON normative vectors match", () => {
  assert.equal(canonicalVectors.profile, "TEV_CANONICAL_JSON_V1");
  for (const vector of canonicalVectors.vectors) {
    assert.equal(canonicalJson(vector.value), vector.canonical, vector.id);
    assert.equal(sha256Hex(vector.canonical), vector.sha256, vector.id);
  }
});

test("JavaScript runtime matches Python receipt byte-for-byte", () => {
  const receipt = runConformance(ir, scenario);
  assert.equal(`${canonicalJson(receipt)}\n`, expected);
});

test("JavaScript full matrix matches Python receipt byte-for-byte", () => {
  const receipt = runConformance(matrixIr, matrixScenario);
  assert.equal(`${canonicalJson(receipt)}\n`, matrixExpected);
});



test("JavaScript exercises the Player else branch byte-for-byte", () => {
  const receipt = runConformance(ir, idleScenario);
  assert.equal(`${canonicalJson(receipt)}
`, idleExpected);
});

test("JavaScript event chain and direct call match Python byte-for-byte", () => {
  const receipt = runConformance(eventChainIr, eventChainScenario);
  assert.equal(`${canonicalJson(receipt)}
`, eventChainExpected);
});

test("semantic hash tampering fails closed", () => {
  const tampered = structuredClone(ir);
  tampered.entities[0].states[0].initial = { $int: "999" };
  assert.throws(() => new ScriptRuntime(tampered), /TEVS_RUNTIME_SEMANTIC_HASH/);
});

test("arbitrary integers remain exact", () => {
  const huge = 1234567890123456789012345678901234567890n;
  assert.deepEqual(encodeTypedValue("Int", huge), { $int: huge.toString() });
});

test("rational arithmetic is exact", () => {
  const value = new Rational(1n, 10n).add(new Rational(2n, 10n));
  assert.equal(value.numerator, 3n);
  assert.equal(value.denominator, 10n);
});

test("missing capabilities fail closed", () => {
  const runtime = new ScriptRuntime(ir);
  assert.throws(() => runtime.invoke("Player", "update"), /TEVS_RUNTIME_CAPABILITY_MISSING/);
});


test("strict JSON rejects duplicate object members", () => {
  assert.throws(
    () => parseStrictJson('{"a":1,"a":2}'),
    /TEVS_JSON_DUPLICATE_KEY/,
  );
});

test("strict JSON rejects floating-point numbers", () => {
  assert.throws(() => parseStrictJson('{"a":1.0}'), /TEVS_JSON_FLOAT_FORBIDDEN/);
});

test("strict JSON rejects unsafe structural integers", () => {
  assert.throws(
    () => parseStrictJson('{"a":9007199254740992}'),
    /TEVS_JSON_NUMBER_RANGE/,
  );
});

test("strict JSON preserves tagged semantic integers", () => {
  assert.deepEqual(
    parseStrictJson('{"value":{"$int":"9007199254740992"}}'),
    { value: { $int: "9007199254740992" } },
  );
});


test("strict JSON rejects negative zero", () => {
  assert.throws(() => parseStrictJson('{"a":-0}'), /TEVS_JSON_NEGATIVE_ZERO/);
});


test("debug hash tampering fails closed", () => {
  const tampered = structuredClone(ir);
  tampered.debug.source_path = "forged.tevs";
  assert.throws(() => new ScriptRuntime(tampered), /TEVS_RUNTIME_DEBUG_HASH/);
});

test("enabled boundaries fail closed even with recomputed semantic hash", () => {
  const tampered = structuredClone(ir);
  tampered.boundary.dynamic_code = true;
  tampered.semantic_hash = canonicalHash(semanticPart(tampered));
  assert.throws(() => new ScriptRuntime(tampered), /TEVS_RUNTIME_BOUNDARY/);
});

test("noncanonical semantic integers fail closed", () => {
  for (const text of ["+1", "01", "-0"]) {
    const tampered = structuredClone(ir);
    tampered.entities[0].states.find((state) => state.type === "Int").initial = { $int: text };
    tampered.semantic_hash = canonicalHash(semanticPart(tampered));
    assert.throws(() => new ScriptRuntime(tampered), /TEVS_RUNTIME_INT/);
  }
});

test("canonical JSON rejects negative zero and non-plain objects", () => {
  assert.throws(() => canonicalJson(-0), /TEVS_JS_CANONICAL_NEGATIVE_ZERO/);
  assert.throws(() => canonicalJson(new Date(0)), /TEVS_JS_CANONICAL_OBJECT/);
});

test("canonical JSON rejects symbol keys", () => {
  const value = { visible: true };
  value[Symbol("hidden")] = false;
  assert.throws(() => canonicalJson(value), /TEVS_JS_CANONICAL_SYMBOL_KEY/);
});

test("runtime owns a structured clone of the IR", () => {
  const mutable = structuredClone(ir);
  const runtime = new ScriptRuntime(mutable);
  mutable.entities[0].states[0].initial = { $int: "999" };
  assert.notDeepEqual(runtime.encodedState("Player"), mutable.entities[0].states);
});
