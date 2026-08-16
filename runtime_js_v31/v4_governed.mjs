import {
  canonicalHash,
  fail,
  obj,
  plain,
  positiveBound,
  requireFields,
  sameJson,
  sha,
} from "./core.mjs";

const V4_PURE_SCHEMA = "TEV_SCRIPT_PROGRAM_IR_V4_PURE_V1";
const V4_PURE_RUN_SCHEMA = "TEV_SCRIPT_PROGRAM_IR_V4_PURE_RUN_RECEIPT_V1";
const V4_RECURSIVE_SCHEMA = "TEV_SCRIPT_PROGRAM_IR_V4_RECURSIVE_V1";
const V4_RECURSIVE_RUN_SCHEMA = "TEV_SCRIPT_PROGRAM_IR_V4_RECURSIVE_RUN_RECEIPT_V1";
const V4_EFFECTS_SCHEMA = "TEV_SCRIPT_PROGRAM_IR_V4_EFFECTS_V1";
const V4_EFFECTS_RUN_SCHEMA = "TEV_SCRIPT_PROGRAM_IR_V4_EFFECTS_RUN_RECEIPT_V1";
const BASE_TYPES = new Set(["Bool", "Int", "Rat", "Text", "Unit", "Vec2", "Vec3"]);
const PURE_OPS = new Set(["CONST", "PARAM", "UNARY", "BINARY", "IF", "LET"]);
const EFFECT_OPS = new Set(["OBSERVE", "LET_LOCAL", "SET_STATE", "ASSERT"]);
const LOCAL_RE = /^[A-Za-z_][A-Za-z0-9_]*$/;
const CAP_RE = /^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*$/;

function localName(value) {
  if (typeof value !== "string" || !LOCAL_RE.test(value) || value.startsWith("__tev_")) fail("TEVS_V31_V4_NAME", "invalid local name");
  return value;
}
function capId(value) {
  if (typeof value !== "string" || !CAP_RE.test(value)) fail("TEVS_V31_V4_CAPABILITY", "invalid capability id");
  return value;
}
function gcd(a, b) {
  let x = a < 0n ? -a : a;
  let y = b < 0n ? -b : b;
  while (y !== 0n) { const t = x % y; x = y; y = t; }
  return x;
}
function rat(n, d = 1n) {
  if (d === 0n) fail("TEVS_V31_V4_DIVIDE_ZERO", "zero denominator");
  let nn = n;
  let dd = d;
  if (dd < 0n) { nn = -nn; dd = -dd; }
  const g = gcd(nn, dd);
  return { n: nn / g, d: dd / g };
}
function asRat(value) { return typeof value === "bigint" ? rat(value) : value; }
function ratCmp(a, b) { const x = asRat(a); const y = asRat(b); return x.n * y.d - y.n * x.d; }
function ratAdd(a, b) { const x = asRat(a); const y = asRat(b); return rat(x.n * y.d + y.n * x.d, x.d * y.d); }
function ratSub(a, b) { const x = asRat(a); const y = asRat(b); return rat(x.n * y.d - y.n * x.d, x.d * y.d); }
function ratMul(a, b) { const x = asRat(a); const y = asRat(b); return rat(x.n * y.n, x.d * y.d); }
function ratDiv(a, b) { const x = asRat(a); const y = asRat(b); return rat(x.n * y.d, x.d * y.n); }

function decodeValue(type, raw) {
  if (type === "Int") {
    requireFields(raw, ["$int"], "TEVS_V31_V4_VALUE");
    if (typeof raw.$int !== "string" || !/^-?(0|[1-9][0-9]*)$/.test(raw.$int) || raw.$int === "-0") fail("TEVS_V31_V4_VALUE", "invalid Int");
    return BigInt(raw.$int);
  }
  if (type === "Rat") {
    requireFields(raw, ["$rat"], "TEVS_V31_V4_VALUE");
    if (!Array.isArray(raw.$rat) || raw.$rat.length !== 2) fail("TEVS_V31_V4_VALUE", "invalid Rat");
    const [ns, ds] = raw.$rat;
    if (typeof ns !== "string" || typeof ds !== "string" || !/^-?(0|[1-9][0-9]*)$/.test(ns) || !/^-?(0|[1-9][0-9]*)$/.test(ds) || ns === "-0" || ds === "-0") fail("TEVS_V31_V4_VALUE", "invalid Rat text");
    const normalized = rat(BigInt(ns), BigInt(ds));
    if (normalized.n.toString() !== ns || normalized.d.toString() !== ds) fail("TEVS_V31_V4_VALUE", "Rat not normalized");
    return normalized;
  }
  if (type === "Bool") { if (typeof raw !== "boolean") fail("TEVS_V31_V4_VALUE", "invalid Bool"); return raw; }
  if (type === "Text") { if (typeof raw !== "string") fail("TEVS_V31_V4_VALUE", "invalid Text"); return raw; }
  if (type === "Vec2" || type === "Vec3") {
    const length = type === "Vec2" ? 2 : 3;
    if (!Array.isArray(raw) || raw.length !== length) fail("TEVS_V31_V4_VALUE", "invalid vector");
    return raw.map(item => decodeValue("Rat", item));
  }
  fail("TEVS_V31_V4_UNSUPPORTED", `type ${type} is outside governed values`);
}
function encodeValue(type, value) {
  if (type === "Int") { if (typeof value !== "bigint") fail("TEVS_V31_V4_VALUE", "Int runtime mismatch"); return { $int: value.toString() }; }
  if (type === "Rat") { const x = asRat(value); return { $rat: [x.n.toString(), x.d.toString()] }; }
  if (type === "Bool") { if (typeof value !== "boolean") fail("TEVS_V31_V4_VALUE", "Bool runtime mismatch"); return value; }
  if (type === "Text") { if (typeof value !== "string") fail("TEVS_V31_V4_VALUE", "Text runtime mismatch"); return value; }
  if (type === "Vec2" || type === "Vec3") return value.map(item => encodeValue("Rat", item));
  fail("TEVS_V31_V4_UNSUPPORTED", `type ${type} is outside governed values`);
}
function typedEqual(type, left, right) {
  if (type === "Int" || type === "Bool" || type === "Text") return left === right;
  if (type === "Rat") return ratCmp(left, right) === 0n;
  if (type === "Vec2" || type === "Vec3") return left.length === right.length && left.every((item, index) => ratCmp(item, right[index]) === 0n);
  return false;
}

function typeTable(raw) {
  requireFields(raw, ["boundary", "types"], "TEVS_V31_V4_TYPE_TABLE");
  requireFields(raw.boundary, ["maximum_value_nesting"], "TEVS_V31_V4_TYPE_TABLE");
  positiveBound(raw.boundary.maximum_value_nesting, "maximum_value_nesting", 128);
  if (!Array.isArray(raw.types) || raw.types.length !== 7) fail("TEVS_V31_V4_UNSUPPORTED", "governed subset requires the seven portable base descriptors only");
  const expected = ["Bool", "Int", "Rat", "Text", "Unit", "Vec2", "Vec3"];
  for (let index = 0; index < raw.types.length; index += 1) {
    const item = raw.types[index];
    requireFields(item, ["type_id", "kind"], "TEVS_V31_V4_TYPE_TABLE");
    if (item.type_id !== expected[index]) fail("TEVS_V31_V4_UNSUPPORTED", "non-base type table");
    if (item.type_id === "Unit" ? item.kind !== "unit" : item.kind !== "primitive") fail("TEVS_V31_V4_TYPE_TABLE", "base descriptor mismatch");
  }
  const hash = canonicalHash({ schema: "TEV_SCRIPT_IR_V4_TYPE_TABLE_IDENTITY_V1", maximum_value_nesting: raw.boundary.maximum_value_nesting, types: raw.types });
  return { raw, hash };
}
function irHash(raw) {
  const declared = sha(raw.program_ir_hash, "program_ir_hash", "TEVS_V31_V4_UNIT");
  const body = { ...raw }; delete body.program_ir_hash;
  const computed = canonicalHash(body);
  if (declared !== computed) fail("TEVS_V31_V4_UNIT_HASH", "embedded V4 program hash mismatch");
  return computed;
}
function sourceHash(raw) { obj(raw.source, "TEVS_V31_V4_SOURCE"); return sha(raw.source.semantic_hash, "source semantic_hash", "TEVS_V31_V4_SOURCE"); }

function binaryContract(operator, lt, rt, resultType) {
  const numeric = new Set(["Int", "Rat"]); const vectors = new Set(["Vec2", "Vec3"]);
  if (["AND", "OR"].includes(operator)) return lt === rt && rt === resultType && resultType === "Bool";
  if (["EQEQ", "NE"].includes(operator)) return resultType === "Bool" && (lt === rt || (numeric.has(lt) && numeric.has(rt)));
  if (["LT", "LE", "GT", "GE"].includes(operator)) return resultType === "Bool" && numeric.has(lt) && numeric.has(rt);
  if (["PLUS", "MINUS"].includes(operator)) return (lt === rt && rt === resultType && resultType === "Int") || (numeric.has(lt) && numeric.has(rt) && resultType === "Rat") || (lt === rt && rt === resultType && vectors.has(lt));
  if (operator === "STAR") return (lt === rt && rt === resultType && resultType === "Int") || (numeric.has(lt) && numeric.has(rt) && resultType === "Rat") || (vectors.has(lt) && numeric.has(rt) && resultType === lt) || (vectors.has(rt) && numeric.has(lt) && resultType === rt);
  if (operator === "SLASH") return (numeric.has(lt) && numeric.has(rt) && resultType === "Rat") || (vectors.has(lt) && numeric.has(rt) && resultType === lt);
  return false;
}
function requireOp(node, allowSelf = false) {
  obj(node, "TEVS_V31_V4_EXPRESSION");
  if (typeof node.op !== "string" || (!PURE_OPS.has(node.op) && !(allowSelf && node.op === "SELF_CALL"))) fail("TEVS_V31_V4_UNSUPPORTED", `expression op ${String(node.op)} outside governed subset`);
}
function staticInfo(node, envTypes) {
  requireOp(node, false);
  if (node.op === "CONST") { if (!BASE_TYPES.has(node.type) || node.type === "Unit") fail("TEVS_V31_V4_UNSUPPORTED", "CONST type unsupported"); const value = decodeValue(node.type, node.value); if (!sameJson(encodeValue(node.type, value), node.value)) fail("TEVS_V31_V4_VALUE", "noncanonical CONST"); return { type: node.type, steps: 1 }; }
  if (node.op === "PARAM") { if (envTypes[node.name] !== node.type) fail("TEVS_V31_V4_TYPE", "PARAM mismatch"); return { type: node.type, steps: 1 }; }
  if (node.op === "UNARY") { const child = staticInfo(node.operand, envTypes); const valid = child.type === node.operand_type && ((node.operator === "NOT" && node.operand_type === node.result_type && node.result_type === "Bool") || (node.operator === "MINUS" && ["Int", "Rat"].includes(node.operand_type) && node.result_type === node.operand_type)); if (!valid) fail("TEVS_V31_V4_TYPE", "UNARY mismatch"); return { type: node.result_type, steps: 1 + child.steps }; }
  if (node.op === "BINARY") { const left = staticInfo(node.left, envTypes); const right = staticInfo(node.right, envTypes); if (left.type !== node.left_type || right.type !== node.right_type || !binaryContract(node.operator, node.left_type, node.right_type, node.result_type)) fail("TEVS_V31_V4_TYPE", "BINARY mismatch"); return { type: node.result_type, steps: 1 + left.steps + right.steps }; }
  if (node.op === "IF") { const cond = staticInfo(node.condition, envTypes); const yes = staticInfo(node.then, envTypes); const no = staticInfo(node.else, envTypes); if (cond.type !== "Bool" || yes.type !== node.result_type || no.type !== node.result_type) fail("TEVS_V31_V4_TYPE", "IF mismatch"); return { type: node.result_type, steps: 1 + cond.steps + Math.max(yes.steps, no.steps) }; }
  if (node.op === "LET") { const value = staticInfo(node.value, envTypes); if (value.type !== node.type) fail("TEVS_V31_V4_TYPE", "LET mismatch"); const body = staticInfo(node.body, { ...envTypes, [node.name]: node.type }); if (body.type !== node.result_type) fail("TEVS_V31_V4_TYPE", "LET result mismatch"); return { type: node.result_type, steps: 1 + value.steps + body.steps }; }
  fail("TEVS_V31_V4_UNSUPPORTED", "unsupported expression");
}
function binaryValue(operator, lt, rt, resultType, left, right) {
  if (!binaryContract(operator, lt, rt, resultType)) fail("TEVS_V31_V4_TYPE", "invalid binary runtime contract");
  if (operator === "AND") return left && right; if (operator === "OR") return left || right;
  if (["EQEQ", "NE"].includes(operator)) { let equal; if (["Int", "Rat"].includes(lt) && ["Int", "Rat"].includes(rt)) equal = ratCmp(left, right) === 0n; else if (lt === rt) equal = typedEqual(lt, left, right); else fail("TEVS_V31_V4_TYPE", "invalid equality"); return operator === "EQEQ" ? equal : !equal; }
  if (["LT", "LE", "GT", "GE"].includes(operator)) { const c = ratCmp(left, right); return operator === "LT" ? c < 0n : operator === "LE" ? c <= 0n : operator === "GT" ? c > 0n : c >= 0n; }
  if (["PLUS", "MINUS"].includes(operator) && lt === "Int" && rt === "Int" && resultType === "Int") return operator === "PLUS" ? left + right : left - right;
  if (["PLUS", "MINUS"].includes(operator) && resultType === "Rat") return operator === "PLUS" ? ratAdd(left, right) : ratSub(left, right);
  if (operator === "STAR" && lt === "Int" && rt === "Int" && resultType === "Int") return left * right;
  if (operator === "STAR" && resultType === "Rat") return ratMul(left, right);
  if (operator === "SLASH" && resultType === "Rat") return ratDiv(left, right);
  if (["PLUS", "MINUS"].includes(operator) && ["Vec2", "Vec3"].includes(resultType)) return left.map((item, index) => operator === "PLUS" ? ratAdd(item, right[index]) : ratSub(item, right[index]));
  if (operator === "STAR" && ["Vec2", "Vec3"].includes(resultType)) return ["Vec2", "Vec3"].includes(lt) ? left.map(item => ratMul(item, right)) : right.map(item => ratMul(left, item));
  if (operator === "SLASH" && ["Vec2", "Vec3"].includes(resultType)) return left.map(item => ratDiv(item, right));
  fail("TEVS_V31_V4_TYPE", "unsupported binary runtime");
}
function evalExpr(node, env) {
  requireOp(node, false);
  if (node.op === "CONST") return { type: node.type, value: decodeValue(node.type, node.value), steps: 1 };
  if (node.op === "PARAM") { const binding = env[node.name]; if (!binding || binding.type !== node.type) fail("TEVS_V31_V4_TYPE", "PARAM runtime mismatch"); return { ...binding, steps: 1 }; }
  if (node.op === "UNARY") { const child = evalExpr(node.operand, env); let value; if (node.operator === "NOT") value = !child.value; else if (node.operator === "MINUS" && child.type === "Int") value = -child.value; else if (node.operator === "MINUS" && child.type === "Rat") value = rat(-child.value.n, child.value.d); else fail("TEVS_V31_V4_TYPE", "UNARY runtime mismatch"); return { type: node.result_type, value, steps: 1 + child.steps }; }
  if (node.op === "BINARY") { const left = evalExpr(node.left, env); const right = evalExpr(node.right, env); return { type: node.result_type, value: binaryValue(node.operator, node.left_type, node.right_type, node.result_type, left.value, right.value), steps: 1 + left.steps + right.steps }; }
  if (node.op === "IF") { const cond = evalExpr(node.condition, env); const branch = evalExpr(cond.value ? node.then : node.else, env); return { type: node.result_type, value: branch.value, steps: 1 + cond.steps + branch.steps }; }
  if (node.op === "LET") { const value = evalExpr(node.value, env); const body = evalExpr(node.body, { ...env, [node.name]: { type: value.type, value: value.value } }); return { type: node.result_type, value: body.value, steps: 1 + value.steps + body.steps }; }
  fail("TEVS_V31_V4_UNSUPPORTED", "unsupported runtime expression");
}
function signature(entry) {
  if (!Array.isArray(entry.parameters) || !Array.isArray(entry.arguments) || entry.parameters.length !== entry.arguments.length) fail("TEVS_V31_V4_SIGNATURE", "signature mismatch");
  const envTypes = Object.create(null); const env = Object.create(null); const wire = [];
  for (let index = 0; index < entry.parameters.length; index += 1) {
    const p = entry.parameters[index]; const a = entry.arguments[index];
    requireFields(p, ["name", "type"], "TEVS_V31_V4_SIGNATURE"); requireFields(a, ["name", "type", "value"], "TEVS_V31_V4_SIGNATURE");
    if (p.name !== a.name || p.type !== a.type || !BASE_TYPES.has(p.type) || p.type === "Unit" || envTypes[p.name] !== undefined) fail("TEVS_V31_V4_SIGNATURE", "argument signature mismatch");
    const value = decodeValue(p.type, a.value); if (!sameJson(encodeValue(p.type, value), a.value)) fail("TEVS_V31_V4_VALUE", "noncanonical argument");
    envTypes[p.name] = p.type; env[p.name] = { type: p.type, value }; wire.push({ name: p.name, type: p.type, value: a.value });
  }
  wire.sort((left, right) => left.name < right.name ? -1 : left.name > right.name ? 1 : 0);
  return { envTypes, env, environmentHash: canonicalHash({ schema: "TEV_SCRIPT_IR_V4_PURE_ENVIRONMENT_V1", bindings: wire }) };
}

function runPure(raw) {
  if (raw.schema !== V4_PURE_SCHEMA || raw.profile !== "pure") fail("TEVS_V31_V4_UNIT_SCHEMA", "expected V4 pure");
  const programHash = irHash(raw); const source = sourceHash(raw); const table = typeTable(raw.type_table); if (sha(raw.type_table_hash, "type_table_hash") !== table.hash) fail("TEVS_V31_V4_TYPE_TABLE_HASH", "type table hash mismatch");
  const sig = signature(raw.entry); const bodyHash = canonicalHash(raw.entry.body); if (sha(raw.entry.body_expression_hash, "body_expression_hash") !== bodyHash) fail("TEVS_V31_V4_BODY_HASH", "body hash mismatch");
  const info = staticInfo(raw.entry.body, sig.envTypes); if (info.type !== raw.entry.return_type || raw.entry.static_step_upper_bound !== info.steps) fail("TEVS_V31_V4_STATIC_BOUND", "pure static identity mismatch");
  const maximum = positiveBound(raw.entry.maximum_steps, "maximum_steps"); if (maximum < info.steps) fail("TEVS_V31_V4_BUDGET", "maximum below static bound");
  const result = evalExpr(raw.entry.body, sig.env); const encoded = encodeValue(result.type, result.value); const resultHash = canonicalHash({ type: result.type, value: encoded });
  const evaluation = { schema: "TEV_SCRIPT_IR_V4_PURE_EVALUATION_RECEIPT_V1", type_table_hash: table.hash, expression_hash: bodyHash, environment_hash: sig.environmentHash, result_type: result.type, result_encoded: encoded, result_hash: resultHash, evaluation_steps: result.steps, static_step_upper_bound: info.steps, maximum_steps: maximum, bounded_loop_iterations: 0 };
  const payload = { schema: V4_PURE_RUN_SCHEMA, program_ir_hash: programHash, source_semantic_hash: source, type_table_hash: table.hash, body_expression_hash: bodyHash, environment_hash: sig.environmentHash, evaluation_receipt_hash: canonicalHash(evaluation), result_type: result.type, result_encoded: encoded, result_hash: resultHash, evaluation_steps: result.steps, static_step_upper_bound: info.steps, bounded_loop_iterations: 0 };
  return { ...payload, receipt_hash: canonicalHash(payload) };
}

function countSelf(value) { if (Array.isArray(value)) return value.reduce((sum, item) => sum + countSelf(item), 0); if (!plain(value)) return 0; if (value.op === "SELF_CALL") return 1; return Object.values(value).reduce((sum, item) => sum + countSelf(item), 0); }
function containsSelf(value) { return countSelf(value) > 0; }
function findSelf(value, out = []) { if (Array.isArray(value)) { value.forEach(item => findSelf(item, out)); return out; } if (!plain(value)) return out; if (value.op === "SELF_CALL") { out.push(value); return out; } Object.values(value).forEach(item => findSelf(item, out)); return out; }
function replaceSelf(value, returnType) { if (Array.isArray(value)) return value.map(item => replaceSelf(item, returnType)); if (!plain(value)) return value; if (value.op === "SELF_CALL") return { op: "PARAM", name: "__tev_self_result", type: returnType }; return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, replaceSelf(item, returnType)])); }
function recursiveContract(raw, sig) {
  const rc = obj(raw.entry.recursion_contract, "TEVS_V31_V4_RECURSION"); const returnType = raw.entry.return_type; const names = raw.entry.parameters.map(item => item.name); const types = raw.entry.parameters.map(item => item.type);
  if (rc.kind !== "decreases_int" || rc.measure_type !== "Int" || rc.single_static_self_call !== true || rc.self_call_in_loops !== false || rc.self_call_in_conditions !== false || countSelf(raw.entry.body) !== 1) fail("TEVS_V31_V4_RECURSION", "invalid recursion contract");
  const measureIndex = names.indexOf(rc.measure_parameter); if (measureIndex < 0 || types[measureIndex] !== "Int" || rc.measure_parameter_index !== measureIndex) fail("TEVS_V31_V4_RECURSION", "measure mismatch");
  const maxDepth = positiveBound(rc.max_depth, "max_depth", 256); const maximum = positiveBound(rc.maximum_steps, "maximum_steps"); const selfNode = findSelf(raw.entry.body)[0];
  if (!Array.isArray(selfNode.arguments) || selfNode.arguments.length !== types.length) fail("TEVS_V31_V4_RECURSION", "SELF_CALL arity mismatch");
  const argInfos = selfNode.arguments.map((item, index) => { const info = staticInfo(item, sig.envTypes); if (info.type !== types[index]) fail("TEVS_V31_V4_RECURSION", "SELF_CALL argument mismatch"); return info; });
  const localInfo = staticInfo(replaceSelf(raw.entry.body, returnType), { ...sig.envTypes, __tev_self_result: returnType }); const recursiveBound = 4 * (localInfo.steps + argInfos.reduce((sum, item) => sum + item.steps, 0) + 4) * (maxDepth + 1); const bodyHash = canonicalHash(raw.entry.body);
  const contractPayload = { schema: "TEV_SCRIPT_IR_V4_RECURSIVE_CONTRACT_V1", parameter_names: names, parameter_type_ids: types, return_type_id: returnType, body_expression_hash: bodyHash, measure_parameter: rc.measure_parameter, measure_parameter_index: measureIndex, measure_type: "Int", max_depth: maxDepth, single_static_self_call: true, self_call_in_loops: false, self_call_in_conditions: false, local_static_step_upper_bound: localInfo.steps, recursive_static_step_upper_bound: recursiveBound, maximum_steps: maximum };
  const contractHash = canonicalHash(contractPayload); if (rc.local_static_step_upper_bound !== localInfo.steps || rc.recursive_static_step_upper_bound !== recursiveBound || sha(rc.contract_hash, "contract_hash") !== contractHash || sha(raw.entry.body_expression_hash, "body_expression_hash") !== bodyHash) fail("TEVS_V31_V4_RECURSION", "recursive contract identity mismatch");
  return { rc, names, types, returnType, measureIndex, maxDepth, maximum, body: raw.entry.body, bodyHash, contractHash, localInfo, recursiveBound };
}
function pureFragment(node, env, stats) { if (containsSelf(node)) fail("TEVS_V31_V4_RECURSION", "unresolved SELF_CALL"); const types = Object.fromEntries(Object.entries(env).map(([name, value]) => [name, value.type])); staticInfo(node, types); const result = evalExpr(node, env); stats.steps += result.steps; return result; }
function recursiveNode(node, contract, env, measure, depth, stats) {
  if (!containsSelf(node)) return pureFragment(node, env, stats);
  if (node.op === "SELF_CALL") { if (depth >= contract.maxDepth) fail("TEVS_V31_V4_RECURSION_DEPTH", "depth exhausted"); const next = node.arguments.map((item, index) => { const value = pureFragment(item, env, stats); if (value.type !== contract.types[index]) fail("TEVS_V31_V4_RECURSION", "SELF_CALL type mismatch"); return value.value; }); const nextMeasure = next[contract.measureIndex]; if (typeof nextMeasure !== "bigint" || nextMeasure < 0n || !(nextMeasure < measure)) fail("TEVS_V31_V4_RECURSION_MEASURE", "measure did not decrease"); stats.steps += 1; stats.calls += 1; return invokeRecursive(contract, next, depth + 1, measure, stats); }
  if (node.op === "IF") { const cond = pureFragment(node.condition, env, stats); return recursiveNode(cond.value ? node.then : node.else, contract, env, measure, depth, stats); }
  if (node.op === "LET") { const value = recursiveNode(node.value, contract, env, measure, depth, stats); return recursiveNode(node.body, contract, { ...env, [node.name]: { type: value.type, value: value.value } }, measure, depth, stats); }
  const materialized = materialize(node, contract, env, measure, depth, stats); return pureFragment(materialized, env, stats);
}
function materialize(value, contract, env, measure, depth, stats) { if (Array.isArray(value)) return value.map(item => materialize(item, contract, env, measure, depth, stats)); if (!plain(value)) return value; if (value.op === "SELF_CALL" || ((value.op === "IF" || value.op === "LET") && containsSelf(value))) { const result = recursiveNode(value, contract, env, measure, depth, stats); return { op: "CONST", type: result.type, value: encodeValue(result.type, result.value) }; } return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, materialize(item, contract, env, measure, depth, stats)])); }
function invokeRecursive(contract, args, depth, parentMeasure, stats) { stats.maxDepth = Math.max(stats.maxDepth, depth); const measure = args[contract.measureIndex]; if (typeof measure !== "bigint" || measure < 0n || (parentMeasure !== null && !(measure < parentMeasure))) fail("TEVS_V31_V4_RECURSION_MEASURE", "invalid recursion measure"); const env = Object.fromEntries(contract.names.map((name, index) => [name, { type: contract.types[index], value: args[index] }])); const result = recursiveNode(contract.body, contract, env, measure, depth, stats); if (stats.steps > contract.maximum) fail("TEVS_V31_V4_RECURSION_BUDGET", "runtime budget exceeded"); return result; }
function runRecursive(raw) {
  if (raw.schema !== V4_RECURSIVE_SCHEMA || raw.profile !== "recursive") fail("TEVS_V31_V4_UNIT_SCHEMA", "expected V4 recursive"); const programHash = irHash(raw); const source = sourceHash(raw); const table = typeTable(raw.type_table); if (sha(raw.type_table_hash, "type_table_hash") !== table.hash) fail("TEVS_V31_V4_TYPE_TABLE_HASH", "type table hash mismatch"); const sig = signature(raw.entry); const contract = recursiveContract(raw, sig);
  const args = raw.entry.arguments.map(item => decodeValue(item.type, item.value)); const argumentsWire = raw.entry.arguments.map(item => ({ name: item.name, type: item.type, value: item.value })); const argumentsHash = canonicalHash({ schema: "TEV_SCRIPT_IR_V4_RECURSIVE_ARGUMENTS_V1", arguments: argumentsWire }); const stats = { steps: 0, calls: 0, maxDepth: 0 }; const result = invokeRecursive(contract, args, 0, null, stats); const encoded = encodeValue(contract.returnType, result.value); const resultHash = canonicalHash({ type: contract.returnType, value: encoded });
  const evaluation = { schema: "TEV_SCRIPT_IR_V4_RECURSIVE_EVALUATION_RECEIPT_V1", contract_hash: contract.contractHash, type_table_hash: table.hash, arguments_hash: argumentsHash, result_type: contract.returnType, result_encoded: encoded, result_hash: resultHash, evaluation_steps: stats.steps, recursion_calls: stats.calls, maximum_observed_depth: stats.maxDepth, max_depth: contract.maxDepth, local_static_step_upper_bound: contract.localInfo.steps, recursive_static_step_upper_bound: contract.recursiveBound };
  const payload = { schema: V4_RECURSIVE_RUN_SCHEMA, program_ir_hash: programHash, source_semantic_hash: source, type_table_hash: table.hash, recursion_contract_hash: contract.contractHash, evaluation_receipt_hash: canonicalHash(evaluation), result_type: contract.returnType, result_encoded: encoded, result_hash: resultHash, evaluation_steps: stats.steps, recursion_calls: stats.calls, maximum_observed_depth: stats.maxDepth };
  return { ...payload, receipt_hash: canonicalHash(payload) };
}

function stateSchema(raw) { const states = raw.states.map(item => { requireFields(item, ["name", "type", "initial"], "TEVS_V31_V4_EFFECT_STATE"); localName(item.name); const value = decodeValue(item.type, item.initial); return { ...item, value }; }); const schemaHash = canonicalHash({ schema: "TEV_SCRIPT_IR_V4_STATE_SCHEMA_V1", states: states.map(item => ({ name: item.name, type: item.type })) }); const initialHash = canonicalHash({ schema: "TEV_SCRIPT_IR_V4_STATE_SNAPSHOT_V1", states: states.map(item => ({ name: item.name, type: item.type, value: item.initial })) }); if (raw.schema_hash !== schemaHash || raw.initial_state_hash !== initialHash) fail("TEVS_V31_V4_EFFECT_STATE_HASH", "state identity mismatch"); return { states, schemaHash }; }
function capabilityTable(raw) { const contracts = raw.contracts.map(item => { requireFields(item, ["capability_id", "parameters", "return_type", "kind", "contract_hash"], "TEVS_V31_V4_EFFECT_CAPABILITY"); capId(item.capability_id); if (item.kind !== "observation") fail("TEVS_V31_V4_UNSUPPORTED", "capability kind unsupported"); const body = { schema: "TEV_SCRIPT_IR_V4_CAPABILITY_CONTRACT_V1", capability_id: item.capability_id, parameters: item.parameters, return_type: item.return_type, kind: item.kind }; const contractHash = canonicalHash(body); if (item.contract_hash !== contractHash) fail("TEVS_V31_V4_EFFECT_CAPABILITY_HASH", "contract hash mismatch"); return { ...item, contractHash }; }); const tableHash = canonicalHash({ schema: "TEV_SCRIPT_IR_V4_CAPABILITY_TABLE_V1", contracts: contracts.map(item => ({ capability_id: item.capability_id, parameters: item.parameters, return_type: item.return_type, kind: item.kind, contract_hash: item.contractHash })) }); if (raw.table_hash !== tableHash) fail("TEVS_V31_V4_EFFECT_CAPABILITY_HASH", "capability table hash mismatch"); return { contracts, byId: Object.fromEntries(contracts.map(item => [item.capability_id, item])), tableHash }; }
function effectTypes(states, parameters, locals) { const out = Object.create(null); states.states.forEach(item => { out[`__tev_state_${item.name}`] = item.type; }); parameters.forEach(item => { out[`__tev_param_${item.name}`] = item.type; }); Object.entries(locals).forEach(([name, type]) => { out[`__tev_local_${name}`] = type; }); return out; }
function effectAction(raw, states, caps) { const parameters = raw.parameters; const locals = Object.create(null); const normalized = []; let staticBound = 0; let observationBound = 0; const stateByName = Object.fromEntries(states.states.map(item => [item.name, item])); for (const step of raw.steps) { if (!EFFECT_OPS.has(step.op)) fail("TEVS_V31_V4_UNSUPPORTED", `effect op ${String(step.op)} outside governed subset`); const types = effectTypes(states, parameters, locals); if (step.op === "OBSERVE") { const contract = caps.byId[step.capability_id]; if (!contract) fail("TEVS_V31_V4_EFFECT_ACTION", "unknown capability"); const args = step.arguments.map((expr, index) => { const info = staticInfo(expr, types); if (info.type !== contract.parameters[index]) fail("TEVS_V31_V4_EFFECT_ACTION", "OBSERVE argument mismatch"); staticBound += info.steps; return expr; }); normalized.push({ op: "OBSERVE", capability_id: step.capability_id, contract_hash: contract.contractHash, arguments: args, bind: step.bind, return_type: contract.return_type }); locals[step.bind] = contract.return_type; staticBound += 1; observationBound += 1; } else if (step.op === "LET_LOCAL") { const info = staticInfo(step.value, types); normalized.push({ op: "LET_LOCAL", name: step.name, type: step.type, value: step.value }); locals[step.name] = step.type; staticBound += info.steps + 1; } else if (step.op === "SET_STATE") { const slot = stateByName[step.state]; const info = staticInfo(step.value, types); if (!slot || info.type !== slot.type) fail("TEVS_V31_V4_EFFECT_ACTION", "SET_STATE mismatch"); normalized.push({ op: "SET_STATE", state: step.state, type: slot.type, value: step.value }); staticBound += info.steps + 1; } else { const info = staticInfo(step.condition, types); if (info.type !== "Bool") fail("TEVS_V31_V4_EFFECT_ACTION", "ASSERT mismatch"); normalized.push({ op: "ASSERT", condition: step.condition }); staticBound += info.steps + 1; } } const payload = { schema: "TEV_SCRIPT_IR_V4_EFFECT_ACTION_V1", action_id: raw.action_id, state_schema_hash: states.schemaHash, capability_table_hash: caps.tableHash, parameters, steps: normalized, static_step_upper_bound: staticBound, observation_call_upper_bound: observationBound }; const actionHash = canonicalHash(payload); if (raw.static_step_upper_bound !== staticBound || raw.observation_call_upper_bound !== observationBound || raw.action_hash !== actionHash) fail("TEVS_V31_V4_EFFECT_ACTION_HASH", "action identity mismatch"); return { parameters, steps: normalized, staticBound, actionHash }; }
function effectScenario(raw, caps) { const lanes = raw.capabilities.map(lane => { const contract = caps.byId[lane.capability_id]; if (!contract || lane.contract_hash !== contract.contractHash) fail("TEVS_V31_V4_EFFECT_SCENARIO", "lane mismatch"); const calls = lane.calls.map(call => ({ ...call, returned: decodeValue(contract.return_type, call.return) })); return { ...lane, calls }; }); const payload = { schema: "TEV_SCRIPT_IR_V4_EFFECT_SCENARIO_V1", capability_table_hash: caps.tableHash, capabilities: lanes.map(lane => ({ capability_id: lane.capability_id, contract_hash: lane.contract_hash, calls: lane.calls.map(call => ({ arguments: call.arguments, return: call.return })) })) }; const scenarioHash = canonicalHash(payload); if (raw.capability_table_hash !== caps.tableHash || raw.scenario_hash !== scenarioHash) fail("TEVS_V31_V4_EFFECT_SCENARIO_HASH", "scenario identity mismatch"); return { lanes, scenarioHash }; }
function runtimeEnv(states, working, action, params, localTypes, locals) { const env = Object.create(null); states.states.forEach(slot => { env[`__tev_state_${slot.name}`] = { type: slot.type, value: working[slot.name] }; }); action.parameters.forEach(item => { env[`__tev_param_${item.name}`] = { type: item.type, value: params[item.name] }; }); Object.entries(localTypes).forEach(([name, type]) => { env[`__tev_local_${name}`] = { type, value: locals[name] }; }); return env; }
function runEffects(raw) { if (raw.schema !== V4_EFFECTS_SCHEMA || raw.profile !== "effects") fail("TEVS_V31_V4_UNIT_SCHEMA", "expected V4 effects"); const programHash = irHash(raw); const source = sourceHash(raw); const table = typeTable(raw.type_table); if (raw.type_table_hash !== table.hash) fail("TEVS_V31_V4_TYPE_TABLE_HASH", "type table hash mismatch"); const states = stateSchema(raw.state_schema); const caps = capabilityTable(raw.capabilities); const action = effectAction(raw.action, states, caps); const scenario = effectScenario(raw.scenario, caps); const working = Object.create(null); const initialWire = raw.execution.current_state.map((item, index) => { const slot = states.states[index]; if (item.name !== slot.name || item.type !== slot.type) fail("TEVS_V31_V4_EFFECT_EXECUTION", "state signature mismatch"); working[slot.name] = decodeValue(slot.type, item.value); return item; }); const initialHash = canonicalHash({ schema: "TEV_SCRIPT_IR_V4_STATE_SNAPSHOT_V1", states: initialWire }); const params = Object.create(null); const argsWire = raw.execution.arguments.map((item, index) => { const p = action.parameters[index]; if (item.name !== p.name || item.type !== p.type) fail("TEVS_V31_V4_EFFECT_EXECUTION", "argument signature mismatch"); params[p.name] = decodeValue(p.type, item.value); return item; }); const argumentsHash = canonicalHash({ schema: "TEV_SCRIPT_IR_V4_EFFECT_ACTION_ARGUMENTS_V1", arguments: argsWire }); const laneById = Object.fromEntries(scenario.lanes.map(item => [item.capability_id, item])); const cursors = Object.fromEntries(scenario.lanes.map(item => [item.capability_id, 0])); const transcript = []; const locals = Object.create(null); const localTypes = Object.create(null); let evaluationSteps = 0; for (const step of action.steps) { const env = runtimeEnv(states, working, action, params, localTypes, locals); if (step.op === "OBSERVE") { const contract = caps.byId[step.capability_id]; const encodedArgs = step.arguments.map((expr, index) => { const result = evalExpr(expr, env); evaluationSteps += result.steps; if (result.type !== contract.parameters[index]) fail("TEVS_V31_V4_EFFECT_RUNTIME", "OBSERVE runtime mismatch"); return encodeValue(result.type, result.value); }); const lane = laneById[contract.capability_id]; const cursor = cursors[contract.capability_id] ?? 0; if (!lane || cursor >= lane.calls.length || !sameJson(lane.calls[cursor].arguments, encodedArgs)) fail("TEVS_V31_V4_EFFECT_RUNTIME", "observation script mismatch"); const call = lane.calls[cursor]; cursors[contract.capability_id] = cursor + 1; transcript.push({ capability_id: contract.capability_id, contract_hash: contract.contractHash, call_index: cursor, arguments: encodedArgs, return: call.return }); locals[step.bind] = call.returned; localTypes[step.bind] = contract.return_type; evaluationSteps += 1; } else if (step.op === "LET_LOCAL") { const result = evalExpr(step.value, env); locals[step.name] = result.value; localTypes[step.name] = step.type; evaluationSteps += result.steps + 1; } else if (step.op === "SET_STATE") { const result = evalExpr(step.value, env); working[step.state] = result.value; evaluationSteps += result.steps + 1; } else { const result = evalExpr(step.condition, env); if (result.type !== "Bool" || result.value !== true) fail("TEVS_V31_V4_EFFECT_ASSERT", "assertion failed"); evaluationSteps += result.steps + 1; } } scenario.lanes.forEach(lane => { if ((cursors[lane.capability_id] ?? 0) !== lane.calls.length) fail("TEVS_V31_V4_EFFECT_RUNTIME", "scenario underflow"); }); const finalWire = states.states.map(slot => ({ name: slot.name, type: slot.type, value: encodeValue(slot.type, working[slot.name]) })); const finalHash = canonicalHash({ schema: "TEV_SCRIPT_IR_V4_STATE_SNAPSHOT_V1", states: finalWire }); const transcriptHash = canonicalHash({ schema: "TEV_SCRIPT_IR_V4_EFFECT_CAPABILITY_TRANSCRIPT_V1", calls: transcript }); const transition = { schema: "TEV_SCRIPT_IR_V4_EFFECT_TRANSITION_RECEIPT_V1", action_hash: action.actionHash, state_schema_hash: states.schemaHash, capability_table_hash: caps.tableHash, scenario_hash: scenario.scenarioHash, initial_state_hash: initialHash, arguments_hash: argumentsHash, capability_transcript_hash: transcriptHash, final_state: finalWire, final_state_hash: finalHash, evaluation_steps: evaluationSteps, observation_calls: transcript.length }; const payload = { schema: V4_EFFECTS_RUN_SCHEMA, program_ir_hash: programHash, source_semantic_hash: source, type_table_hash: table.hash, state_schema_hash: states.schemaHash, capability_table_hash: caps.tableHash, action_hash: action.actionHash, scenario_hash: scenario.scenarioHash, transition_receipt_hash: canonicalHash(transition), initial_state_hash: initialHash, final_state: finalWire, final_state_hash: finalHash, capability_transcript_hash: transcriptHash, evaluation_steps: evaluationSteps, observation_calls: transcript.length }; return { ...payload, receipt_hash: canonicalHash(payload) }; }

export function runV4Unit(unit) {
  if (unit.profile === "pure") return runPure(unit.program_ir_v4);
  if (unit.profile === "recursive") return runRecursive(unit.program_ir_v4);
  if (unit.profile === "effects") return runEffects(unit.program_ir_v4);
  fail("TEVS_V31_V4_UNSUPPORTED", "unit profile outside governed subset");
}
