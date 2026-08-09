import { canonicalHash } from "./canonical.mjs";
import { validateEntityHandlerFlowV3 } from "./ir-v3-flow.mjs";
import { buildTypeTableV3, decodeV3Value, TevScriptError } from "./ir-v3-values.mjs";

const HASH = /^[0-9a-f]{64}$/;
const LOCAL = /^[A-Za-z_][A-Za-z0-9_]*$/;
const STABLE = /^[A-Za-z_][A-Za-z0-9_.:/-]*$/;
const ROOT_KEYS = new Set([
  "schema", "language_version", "lowering_profile", "source_schema",
  "source_semantic_hash", "program_id", "types", "entities", "boundary",
  "semantic_hash", "debug", "debug_hash",
]);
const BOUNDARY_KEYS = new Set([
  "dynamic_code", "reflection", "unbounded_loops", "implicit_physical_effects",
  "runtime_source_compilation", "automatic_authority_escalation",
  "host_object_references", "maximum_event_chain", "maximum_value_nesting",
]);

function fail(path, message, code = "TEVS_IR_V3_CONTRACT") {
  throw new TevScriptError(code, `${path}: ${message}`);
}

function objectValue(value, path) {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    fail(path, "expected object with string keys");
  }
  for (const key of Reflect.ownKeys(value)) {
    if (typeof key !== "string") fail(path, "expected object with string keys");
  }
  return value;
}

function arrayValue(value, path, minimum, maximum) {
  if (!Array.isArray(value)) fail(path, "expected array");
  if (value.length < minimum || value.length > maximum) {
    fail(path, `array length must be in [${minimum}, ${maximum}]`);
  }
  return value;
}

function exactKeys(value, path, expected) {
  const observed = Object.keys(value).sort();
  const target = [...expected].sort();
  if (observed.length !== target.length || observed.some((key, index) => key !== target[index])) {
    const missing = target.filter((key) => !observed.includes(key));
    const extra = observed.filter((key) => !target.includes(key));
    fail(path, `field set mismatch; missing=${JSON.stringify(missing)}, extra=${JSON.stringify(extra)}`);
  }
}

function stringValue(value, path) {
  if (typeof value !== "string") fail(path, "expected string");
  return value;
}

function localName(value, path) {
  const result = stringValue(value, path);
  if (!LOCAL.test(result)) fail(path, `expected local identifier, got ${JSON.stringify(result)}`);
  return result;
}

function stableId(value, path) {
  const result = stringValue(value, path);
  if (!STABLE.test(result)) fail(path, `expected stable identifier, got ${JSON.stringify(result)}`);
  return result;
}

function hashValue(value, path) {
  const result = stringValue(value, path);
  if (!HASH.test(result)) fail(path, "expected lowercase SHA-256");
  return result;
}

function integer(value, path, minimum, maximum) {
  if (!Number.isSafeInteger(value) || value < minimum || value > maximum) {
    fail(path, `expected integer in [${minimum}, ${maximum}]`);
  }
  return value;
}

function storableType(table, value, path) {
  const typeId = stringValue(value, path);
  if (!table.isStorable(typeId)) fail(path, `type ${JSON.stringify(typeId)} is unknown or not storable`);
  return typeId;
}

function typedBinding(raw, table, path) {
  const item = objectValue(raw, path);
  exactKeys(item, path, new Set(["name", "type"]));
  return [localName(item.name, `${path}.name`), storableType(table, item.type, `${path}.type`)];
}

function validateInstructionShape(
  instruction, table, states, parameters, locals, capabilities, events,
  pc, count, path,
) {
  const op = stringValue(instruction.op, `${path}.op`);
  if (op === "CONST") {
    exactKeys(instruction, path, new Set(["op", "type", "value"]));
    const typeId = storableType(table, instruction.type, `${path}.type`);
    decodeV3Value(typeId, instruction.value, table, { context: `${path}.value` });
    return;
  }
  if (["LOAD_STATE", "STORE_STATE", "LOAD_LOCAL", "STORE_LOCAL", "LOAD_PARAM"].includes(op)) {
    exactKeys(instruction, path, new Set(["op", "name", "type"]));
    const name = localName(instruction.name, `${path}.name`);
    const typeId = storableType(table, instruction.type, `${path}.type`);
    const namespace = op === "LOAD_STATE" || op === "STORE_STATE"
      ? states : op === "LOAD_LOCAL" || op === "STORE_LOCAL" ? locals : parameters;
    if (namespace.get(name) !== typeId) fail(path, `${op} references unknown/mismatched binding ${JSON.stringify(name)}`);
    return;
  }
  if (op === "CONVERT_INT_TO_RAT") {
    exactKeys(instruction, path, new Set(["op"]));
    return;
  }
  if (op === "UNARY") {
    exactKeys(instruction, path, new Set(["op", "operator", "type"]));
    stringValue(instruction.operator, `${path}.operator`);
    storableType(table, instruction.type, `${path}.type`);
    return;
  }
  if (op === "BINARY") {
    exactKeys(instruction, path, new Set(["op", "operator", "left_type", "right_type", "result_type"]));
    stringValue(instruction.operator, `${path}.operator`);
    for (const key of ["left_type", "right_type", "result_type"]) storableType(table, instruction[key], `${path}.${key}`);
    return;
  }
  if (op === "CALL_PURE") {
    exactKeys(instruction, path, new Set(["op", "function_id", "argc", "return_type"]));
    if (!["vec2", "vec3", "min", "max"].includes(instruction.function_id)) fail(`${path}.function_id`, "unsupported runtime pure intrinsic");
    integer(instruction.argc, `${path}.argc`, 0, 64);
    storableType(table, instruction.return_type, `${path}.return_type`);
    return;
  }
  if (op === "CALL_CAPABILITY") {
    exactKeys(instruction, path, new Set(["op", "capability_id", "argc", "return_type", "kind"]));
    const capabilityId = stableId(instruction.capability_id, `${path}.capability_id`);
    const signature = capabilities.get(capabilityId);
    if (!signature) fail(path, `undeclared capability ${JSON.stringify(capabilityId)}`);
    if (instruction.argc !== signature.parameters.length
        || instruction.return_type !== signature.returnType
        || instruction.kind !== signature.kind) {
      fail(path, `capability contract mismatch for ${JSON.stringify(capabilityId)}`);
    }
    return;
  }
  if (op === "EMIT_EVENT") {
    exactKeys(instruction, path, new Set(["op", "event_id", "argument_types", "argc"]));
    const eventId = localName(instruction.event_id, `${path}.event_id`);
    const signature = events.get(eventId);
    if (!signature) fail(path, `undeclared emitted event ${JSON.stringify(eventId)}`);
    const argumentTypes = arrayValue(instruction.argument_types, `${path}.argument_types`, 0, 64)
      .map((value, position) => storableType(table, value, `${path}.argument_types[${position}]`));
    if (instruction.argc !== signature.length
        || argumentTypes.length !== signature.length
        || argumentTypes.some((typeId, index) => typeId !== signature[index])) {
      fail(path, `event contract mismatch for ${JSON.stringify(eventId)}`);
    }
    return;
  }
  if (op === "JUMP" || op === "JUMP_IF_FALSE") {
    exactKeys(instruction, path, new Set(["op", "target"]));
    const target = integer(instruction.target, `${path}.target`, 0, count - 1);
    if (target <= pc) fail(`${path}.target`, "backward/self jumps are forbidden");
    return;
  }
  if (op === "RETURN") {
    exactKeys(instruction, path, new Set(["op"]));
    return;
  }
  if (op === "MAKE_RECORD") {
    exactKeys(instruction, path, new Set(["op", "type", "fields"]));
    const typeId = storableType(table, instruction.type, `${path}.type`);
    const descriptor = table.require(typeId);
    if (descriptor.kind !== "record") fail(`${path}.type`, "MAKE_RECORD requires record descriptor");
    const fields = arrayValue(instruction.fields, `${path}.fields`, 1, 256)
      .map((value, position) => localName(value, `${path}.fields[${position}]`));
    if (new Set(fields).size !== fields.length
        || fields.length !== descriptor.fields.length
        || fields.some((name) => descriptor.fieldType(name) === null)) {
      fail(`${path}.fields`, "MAKE_RECORD fields must equal descriptor field set");
    }
    return;
  }
  if (op === "LOAD_FIELD") {
    exactKeys(instruction, path, new Set(["op", "record_type", "field", "result_type"]));
    const recordType = storableType(table, instruction.record_type, `${path}.record_type`);
    const descriptor = table.require(recordType);
    if (descriptor.kind !== "record") fail(`${path}.record_type`, "LOAD_FIELD requires record type");
    const field = localName(instruction.field, `${path}.field`);
    const resultType = storableType(table, instruction.result_type, `${path}.result_type`);
    if (descriptor.fieldType(field) !== resultType) fail(path, "LOAD_FIELD descriptor mismatch");
    return;
  }
  if (op === "MAKE_VARIANT") {
    exactKeys(instruction, path, new Set(["op", "type", "variant", "argc"]));
    const typeId = storableType(table, instruction.type, `${path}.type`);
    const variant = localName(instruction.variant, `${path}.variant`);
    const payloadType = table.variantPayloadType(typeId, variant);
    const expectedArgc = payloadType === null ? 0 : 1;
    if (integer(instruction.argc, `${path}.argc`, 0, 1) !== expectedArgc) fail(`${path}.argc`, `variant requires argc ${expectedArgc}`);
    return;
  }
  if (op === "TEST_VARIANT") {
    exactKeys(instruction, path, new Set(["op", "type", "variant"]));
    const typeId = storableType(table, instruction.type, `${path}.type`);
    const variant = localName(instruction.variant, `${path}.variant`);
    table.variantPayloadType(typeId, variant);
    return;
  }
  if (op === "LOAD_VARIANT_PAYLOAD") {
    exactKeys(instruction, path, new Set(["op", "type", "variant", "payload_type"]));
    const typeId = storableType(table, instruction.type, `${path}.type`);
    const variant = localName(instruction.variant, `${path}.variant`);
    const payloadType = table.variantPayloadType(typeId, variant);
    if (payloadType === null) fail(path, "selected variant has no payload");
    if (instruction.payload_type !== payloadType) fail(`${path}.payload_type`, "variant payload type mismatch");
    return;
  }
  fail(`${path}.op`, `unknown V3 opcode ${JSON.stringify(op)}`, "TEVS_IR_V3_OPCODE");
}

function validateEntity(entity, table, path) {
  exactKeys(entity, path, new Set(["entity_id", "states", "handlers", "capabilities", "emitted_events"]));
  const entityId = localName(entity.entity_id, `${path}.entity_id`);

  const states = new Map();
  const stateOrder = [];
  arrayValue(entity.states, `${path}.states`, 0, 256).forEach((rawState, index) => {
    const statePath = `${path}.states[${index}]`;
    const state = objectValue(rawState, statePath);
    exactKeys(state, statePath, new Set(["name", "type", "initial"]));
    const name = localName(state.name, `${statePath}.name`);
    if (states.has(name)) fail(`${statePath}.name`, `duplicate state ${JSON.stringify(name)}`);
    const typeId = storableType(table, state.type, `${statePath}.type`);
    decodeV3Value(typeId, state.initial, table, { context: `${statePath}.initial` });
    states.set(name, typeId);
    stateOrder.push(name);
  });
  if (JSON.stringify(stateOrder) !== JSON.stringify([...stateOrder].sort())) fail(`${path}.states`, "states must be sorted lexically by name");

  const capabilities = new Map();
  const capabilityOrder = [];
  arrayValue(entity.capabilities, `${path}.capabilities`, 0, 8192).forEach((rawCapability, index) => {
    const capabilityPath = `${path}.capabilities[${index}]`;
    const capability = objectValue(rawCapability, capabilityPath);
    exactKeys(capability, capabilityPath, new Set(["capability_id", "parameters", "return_type", "kind"]));
    const capabilityId = stableId(capability.capability_id, `${capabilityPath}.capability_id`);
    if (capabilities.has(capabilityId)) fail(`${capabilityPath}.capability_id`, `duplicate capability ${JSON.stringify(capabilityId)}`);
    const parameters = arrayValue(capability.parameters, `${capabilityPath}.parameters`, 0, 64)
      .map((value, position) => storableType(table, value, `${capabilityPath}.parameters[${position}]`));
    const returnType = stringValue(capability.return_type, `${capabilityPath}.return_type`);
    const returnDescriptor = table.require(returnType, `${capabilityPath}.return_type`);
    if (returnDescriptor.kind !== "unit" && !table.isStorable(returnType)) fail(`${capabilityPath}.return_type`, `invalid capability return ${returnType}`);
    const kind = stringValue(capability.kind, `${capabilityPath}.kind`);
    if (kind !== "observation" && kind !== "effect") fail(`${capabilityPath}.kind`, "kind must be observation or effect");
    capabilities.set(capabilityId, { parameters, returnType, kind });
    capabilityOrder.push(capabilityId);
  });
  if (JSON.stringify(capabilityOrder) !== JSON.stringify([...capabilityOrder].sort())) fail(`${path}.capabilities`, "capabilities must be sorted lexically by id");

  const events = new Map();
  const eventOrder = [];
  arrayValue(entity.emitted_events, `${path}.emitted_events`, 0, 256).forEach((rawEvent, index) => {
    const eventPath = `${path}.emitted_events[${index}]`;
    const event = objectValue(rawEvent, eventPath);
    exactKeys(event, eventPath, new Set(["event_id", "parameters"]));
    const eventId = localName(event.event_id, `${eventPath}.event_id`);
    if (events.has(eventId)) fail(`${eventPath}.event_id`, `duplicate emitted event ${JSON.stringify(eventId)}`);
    const eventParameters = arrayValue(event.parameters, `${eventPath}.parameters`, 0, 64)
      .map((value, position) => storableType(table, value, `${eventPath}.parameters[${position}]`));
    events.set(eventId, eventParameters);
    eventOrder.push(eventId);
  });
  if (JSON.stringify(eventOrder) !== JSON.stringify([...eventOrder].sort())) fail(`${path}.emitted_events`, "emitted events must be sorted lexically by id");

  const handlers = arrayValue(entity.handlers, `${path}.handlers`, 0, 256);
  const handlerIds = new Set();
  const handlerOrder = [];
  handlers.forEach((rawHandler, index) => {
    const handlerPath = `${path}.handlers[${index}]`;
    const handler = objectValue(rawHandler, handlerPath);
    exactKeys(handler, handlerPath, new Set(["event_id", "parameters", "locals", "instructions", "instruction_budget"]));
    const eventId = localName(handler.event_id, `${handlerPath}.event_id`);
    if (handlerIds.has(eventId)) fail(`${handlerPath}.event_id`, `duplicate handler ${JSON.stringify(eventId)}`);
    handlerIds.add(eventId); handlerOrder.push(eventId);

    const parameters = new Map();
    arrayValue(handler.parameters, `${handlerPath}.parameters`, 0, 64).forEach((rawParameter, position) => {
      const parameterPath = `${handlerPath}.parameters[${position}]`;
      const [name, typeId] = typedBinding(rawParameter, table, parameterPath);
      if (parameters.has(name) || states.has(name)) fail(`${parameterPath}.name`, `duplicate/state-shadowing parameter ${JSON.stringify(name)}`);
      parameters.set(name, typeId);
    });

    const locals = new Map();
    const localOrder = [];
    arrayValue(handler.locals, `${handlerPath}.locals`, 0, 256).forEach((rawLocal, position) => {
      const localPath = `${handlerPath}.locals[${position}]`;
      const [name, typeId] = typedBinding(rawLocal, table, localPath);
      if (locals.has(name) || parameters.has(name) || states.has(name)) fail(`${localPath}.name`, `duplicate/shadowing local ${JSON.stringify(name)}`);
      locals.set(name, typeId); localOrder.push(name);
    });
    if (JSON.stringify(localOrder) !== JSON.stringify([...localOrder].sort())) fail(`${handlerPath}.locals`, "locals must be sorted lexically by name");

    const instructions = arrayValue(handler.instructions, `${handlerPath}.instructions`, 1, 8192);
    const budget = integer(handler.instruction_budget, `${handlerPath}.instruction_budget`, 1, 8192);
    if (instructions.length > budget) fail(`${handlerPath}.instruction_budget`, "budget smaller than instruction count");
    if (instructions[instructions.length - 1]?.op !== "RETURN") fail(`${handlerPath}.instructions`, "handler must end in RETURN");
    instructions.forEach((rawInstruction, pc) => validateInstructionShape(
      objectValue(rawInstruction, `${handlerPath}.instructions[${pc}]`),
      table, states, parameters, locals, capabilities, events,
      pc, instructions.length, `${handlerPath}.instructions[${pc}]`,
    ));
    validateEntityHandlerFlowV3(entity, handler, table, handlerPath);
  });
  if (JSON.stringify(handlerOrder) !== JSON.stringify([...handlerOrder].sort())) fail(`${path}.handlers`, "handlers must be sorted lexically by event id");
  return entityId;
}

function validateClosedTypeTable(root, table) {
  const needed = new Set(["Bool", "Int", "Rat", "Text", "Vec2", "Vec3", "Unit"]);
  for (const entity of root.entities) {
    entity.states.forEach((state) => needed.add(state.type));
    entity.capabilities.forEach((capability) => {
      capability.parameters.forEach((typeId) => needed.add(typeId));
      needed.add(capability.return_type);
    });
    entity.emitted_events.forEach((event) => event.parameters.forEach((typeId) => needed.add(typeId)));
    entity.handlers.forEach((handler) => {
      handler.parameters.forEach((item) => needed.add(item.type));
      handler.locals.forEach((item) => needed.add(item.type));
      handler.instructions.forEach((instruction) => {
        ["type", "left_type", "right_type", "result_type", "return_type", "record_type", "payload_type"]
          .forEach((key) => { if (typeof instruction[key] === "string") needed.add(instruction[key]); });
        if (Array.isArray(instruction.argument_types)) instruction.argument_types.forEach((typeId) => needed.add(typeId));
      });
    });
  }
  const queue = [...needed];
  while (queue.length > 0) {
    const typeId = queue.pop();
    const descriptor = table.require(typeId, "closed type table");
    let children = [];
    if (descriptor.kind === "record") children = descriptor.fields.map(([, child]) => child);
    else if (descriptor.kind === "option") children = [descriptor.argument];
    else if (descriptor.kind === "result") children = [descriptor.okType, descriptor.errType];
    for (const child of children) {
      if (!needed.has(child)) { needed.add(child); queue.push(child); }
    }
  }
  const observed = new Set(table.descriptors.map((item) => item.typeId));
  const missing = [...needed].filter((item) => !observed.has(item)).sort();
  const extra = [...observed].filter((item) => !needed.has(item)).sort();
  if (missing.length) fail("$.types", `closed type table missing referenced descriptors ${JSON.stringify(missing)}`);
  if (extra.length) fail("$.types", `closed type table contains unused descriptors ${JSON.stringify(extra)}`);
}

export function validateProgramIrV3(ir, { expectedSourceSemanticHash = null } = {}) {
  const root = objectValue(ir, "$");
  exactKeys(root, "$", ROOT_KEYS);
  if (root.schema !== "TEV_SCRIPT_PROGRAM_IR_V3") fail("$.schema", "expected TEV_SCRIPT_PROGRAM_IR_V3", "TEVS_IR_V3_SCHEMA");
  if (root.language_version !== "1.0.0") fail("$.language_version", "expected 1.0.0", "TEVS_IR_V3_LANGUAGE_VERSION");

  const sourceSchema = stringValue(root.source_schema, "$.source_schema");
  const profile = stringValue(root.lowering_profile, "$.lowering_profile");
  const expectedProfile = sourceSchema === "TEV_SCRIPT_LINKED_PROGRAM_V1"
    ? "TEV_SCRIPT_V1_IR_V3_PROFILE_V1"
    : sourceSchema === "TEV_SCRIPT_PROGRAM_IR_V2"
      ? "TEV_SCRIPT_V2_LIFT_TO_IR_V3_PROFILE_V1" : null;
  if (expectedProfile === null || profile !== expectedProfile) {
    fail("$.lowering_profile", `profile/source mismatch: ${JSON.stringify(profile)} / ${JSON.stringify(sourceSchema)}`, "TEVS_IR_V3_LOWERING_PROFILE");
  }
  const sourceHash = hashValue(root.source_semantic_hash, "$.source_semantic_hash");
  if (expectedSourceSemanticHash !== null && sourceHash !== expectedSourceSemanticHash) {
    fail("$.source_semantic_hash", "source semantic hash does not match expected source artifact", "TEVS_IR_V3_SOURCE_HASH");
  }
  localName(root.program_id, "$.program_id");
  hashValue(root.semantic_hash, "$.semantic_hash");
  hashValue(root.debug_hash, "$.debug_hash");

  const boundary = objectValue(root.boundary, "$.boundary");
  exactKeys(boundary, "$.boundary", BOUNDARY_KEYS);
  for (const flag of [
    "dynamic_code", "reflection", "unbounded_loops", "implicit_physical_effects",
    "runtime_source_compilation", "automatic_authority_escalation", "host_object_references",
  ]) {
    if (boundary[flag] !== false) fail(`$.boundary.${flag}`, "must be false", "TEVS_IR_V3_BOUNDARY");
  }
  integer(boundary.maximum_event_chain, "$.boundary.maximum_event_chain", 1, 128);
  integer(boundary.maximum_value_nesting, "$.boundary.maximum_value_nesting", 1, 128);

  const table = buildTypeTableV3(root);
  const entities = arrayValue(root.entities, "$.entities", 1, 128);
  const entityIds = new Set();
  const entityOrder = [];
  entities.forEach((rawEntity, index) => {
    const entityId = validateEntity(objectValue(rawEntity, `$.entities[${index}]`), table, `$.entities[${index}]`);
    if (entityIds.has(entityId)) fail(`$.entities[${index}].entity_id`, `duplicate entity ${JSON.stringify(entityId)}`);
    entityIds.add(entityId); entityOrder.push(entityId);
  });
  if (JSON.stringify(entityOrder) !== JSON.stringify([...entityOrder].sort())) fail("$.entities", "entities must be sorted lexically by entity_id");
  validateClosedTypeTable(root, table);

  const debug = objectValue(root.debug, "$.debug");
  if (canonicalHash(debug) !== root.debug_hash) fail("$.debug_hash", "debug hash mismatch", "TEVS_IR_V3_DEBUG_HASH");
  const semantic = Object.fromEntries(
    Object.entries(root).filter(([key]) => !["semantic_hash", "debug", "debug_hash"].includes(key)),
  );
  if (canonicalHash(semantic) !== root.semantic_hash) fail("$.semantic_hash", "semantic hash mismatch", "TEVS_IR_V3_SEMANTIC_HASH");
  return table;
}

export const IR_V3_SCHEMA = "TEV_SCRIPT_PROGRAM_IR_V3";
export const IR_V3_LANGUAGE_VERSION = "1.0.0";
