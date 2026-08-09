import { TevScriptError } from "./values.mjs";

function fail(path, message) {
  throw new TevScriptError("TEVS_IR_V3_FLOW_INVALID", `${path}: ${message}`);
}

function stateKey(stack, initialized) {
  return `${stack.join("\u0000")}\u0001${[...initialized].sort().join("\u0000")}`;
}

function mergeState(incoming, target, stack, initialized, source, instructionCount) {
  if (target < 0 || target >= instructionCount) {
    fail(source, "control flow must target an instruction, not handler exit");
  }
  const current = incoming[target];
  if (current === null) {
    incoming[target] = { stack: [...stack], initialized: new Set(initialized) };
    return;
  }
  if (current.stack.length !== stack.length
      || current.stack.some((typeId, index) => typeId !== stack[index])) {
    fail(source, `CFG merge stack mismatch at instruction ${target}: ${JSON.stringify(current.stack)} vs ${JSON.stringify(stack)}`);
  }
  const intersection = new Set(
    [...current.initialized].filter((name) => initialized.has(name)),
  );
  incoming[target] = { stack: [...stack], initialized: intersection };
}

function requireStorable(table, typeId, path) {
  if (!table.isStorable(typeId)) fail(path, `type ${JSON.stringify(typeId)} is not storable`);
}

function pureSignature(functionId, returnType) {
  if (functionId === "vec2" && returnType === "Vec2") return ["Rat", "Rat"];
  if (functionId === "vec3" && returnType === "Vec3") return ["Rat", "Rat", "Rat"];
  if ((functionId === "min" || functionId === "max") && (returnType === "Int" || returnType === "Rat")) {
    return [returnType, returnType];
  }
  fail("CALL_PURE", `invalid pure intrinsic signature ${JSON.stringify(functionId)}->${returnType}`);
}

function binarySignatureV3(operator, left, right, result, table) {
  if (operator === "AND" || operator === "OR") return left === "Bool" && right === "Bool" && result === "Bool";
  if (operator === "EQEQ" || operator === "NE") {
    if (result !== "Bool") return false;
    if (left === right && table.isStorable(left)) return true;
    return new Set([left, right]).size === 2 && [left, right].every((value) => value === "Int" || value === "Rat");
  }
  if (["LT", "LE", "GT", "GE"].includes(operator)) {
    return left === right && (left === "Int" || left === "Rat") && result === "Bool";
  }
  if (operator === "PLUS" || operator === "MINUS") {
    return (left === "Int" && right === "Int" && result === "Int")
      || (left === "Rat" && right === "Rat" && result === "Rat")
      || ((result === "Vec2" || result === "Vec3") && left === result && right === result);
  }
  if (operator === "STAR") {
    return (left === "Int" && right === "Int" && result === "Int")
      || (left === "Rat" && right === "Rat" && result === "Rat")
      || ((left === "Vec2" || left === "Vec3") && right === "Rat" && result === left)
      || ((right === "Vec2" || right === "Vec3") && left === "Rat" && result === right);
  }
  if (operator === "SLASH") {
    return (left === "Rat" && right === "Rat" && result === "Rat")
      || ((left === "Vec2" || left === "Vec3") && right === "Rat" && result === left);
  }
  return false;
}

export function validateEntityHandlerFlowV3(entity, handler, table, path) {
  const states = new Map(entity.states.map((item) => [item.name, item.type]));
  const parameters = new Map(handler.parameters.map((item) => [item.name, item.type]));
  const locals = new Map(handler.locals.map((item) => [item.name, item.type]));
  const capabilities = new Map(entity.capabilities.map((item) => [
    item.capability_id,
    { parameters: [...item.parameters], returnType: item.return_type, kind: item.kind },
  ]));
  const events = new Map(entity.emitted_events.map((item) => [item.event_id, [...item.parameters]]));
  const instructions = handler.instructions;
  const incoming = Array.from({ length: instructions.length }, () => null);
  incoming[0] = { stack: [], initialized: new Set() };
  let reachedReturn = false;

  for (let pc = 0; pc < instructions.length; pc += 1) {
    const flow = incoming[pc];
    if (flow === null) continue;
    const stack = [...flow.stack];
    const initialized = new Set(flow.initialized);
    const instruction = instructions[pc];
    const op = instruction.op;
    const currentPath = `${path}.instructions[${pc}]`;

    const pop = (expected) => {
      if (stack.length === 0) fail(currentPath, `stack underflow; expected ${expected}`);
      const actual = stack.pop();
      if (actual !== expected) fail(currentPath, `stack type mismatch; expected ${expected}, got ${actual}`);
    };

    if (op === "CONST") {
      requireStorable(table, instruction.type, currentPath);
      stack.push(instruction.type);
    } else if (op === "LOAD_STATE") {
      stack.push(states.get(instruction.name));
    } else if (op === "STORE_STATE") {
      pop(states.get(instruction.name));
    } else if (op === "LOAD_LOCAL") {
      if (!initialized.has(instruction.name)) fail(currentPath, `local ${JSON.stringify(instruction.name)} is not definitely initialized`);
      stack.push(locals.get(instruction.name));
    } else if (op === "STORE_LOCAL") {
      pop(locals.get(instruction.name));
      initialized.add(instruction.name);
    } else if (op === "LOAD_PARAM") {
      stack.push(parameters.get(instruction.name));
    } else if (op === "CONVERT_INT_TO_RAT") {
      pop("Int"); stack.push("Rat");
    } else if (op === "UNARY") {
      if (instruction.operator === "NOT") {
        if (instruction.type !== "Bool") fail(currentPath, "NOT must produce Bool");
        pop("Bool");
      } else if (instruction.operator === "MINUS") {
        if (instruction.type !== "Int" && instruction.type !== "Rat") fail(currentPath, "MINUS requires Int or Rat");
        pop(instruction.type);
      } else fail(currentPath, `unsupported unary operator ${JSON.stringify(instruction.operator)}`);
      stack.push(instruction.type);
    } else if (op === "BINARY") {
      if (!binarySignatureV3(instruction.operator, instruction.left_type, instruction.right_type, instruction.result_type, table)) {
        fail(currentPath, `invalid V3 binary signature ${instruction.operator}(${instruction.left_type},${instruction.right_type})->${instruction.result_type}`);
      }
      pop(instruction.right_type); pop(instruction.left_type); stack.push(instruction.result_type);
    } else if (op === "CALL_PURE") {
      const expected = pureSignature(instruction.function_id, instruction.return_type);
      if (expected.length !== instruction.argc) fail(currentPath, `${instruction.function_id} argc mismatch`);
      [...expected].reverse().forEach(pop);
      if (instruction.return_type !== "Unit") {
        requireStorable(table, instruction.return_type, currentPath);
        stack.push(instruction.return_type);
      }
    } else if (op === "CALL_CAPABILITY") {
      const signature = capabilities.get(instruction.capability_id);
      if (!signature) fail(currentPath, `undeclared capability ${JSON.stringify(instruction.capability_id)}`);
      if (instruction.argc !== signature.parameters.length
          || instruction.return_type !== signature.returnType
          || instruction.kind !== signature.kind) {
        fail(currentPath, `capability instruction contract mismatch for ${JSON.stringify(instruction.capability_id)}`);
      }
      [...signature.parameters].reverse().forEach(pop);
      if (signature.returnType !== "Unit") stack.push(signature.returnType);
    } else if (op === "EMIT_EVENT") {
      const expected = events.get(instruction.event_id);
      if (!expected) fail(currentPath, `undeclared emitted event ${JSON.stringify(instruction.event_id)}`);
      if (instruction.argc !== expected.length
          || instruction.argument_types.length !== expected.length
          || instruction.argument_types.some((typeId, index) => typeId !== expected[index])) {
        fail(currentPath, `event instruction contract mismatch for ${JSON.stringify(instruction.event_id)}`);
      }
      [...expected].reverse().forEach(pop);
    } else if (op === "MAKE_RECORD") {
      const descriptor = table.require(instruction.type, currentPath);
      if (descriptor.kind !== "record") fail(currentPath, `MAKE_RECORD requires record type, got ${instruction.type}`);
      const fields = instruction.fields;
      const descriptorFields = new Map(descriptor.fields);
      if (fields.length !== descriptor.fields.length
          || new Set(fields).size !== fields.length
          || fields.some((name) => !descriptorFields.has(name))) {
        fail(currentPath, "MAKE_RECORD fields must equal descriptor field set exactly");
      }
      [...fields].reverse().forEach((name) => pop(descriptorFields.get(name)));
      stack.push(instruction.type);
    } else if (op === "LOAD_FIELD") {
      const descriptor = table.require(instruction.record_type, currentPath);
      if (descriptor.kind !== "record") fail(currentPath, "LOAD_FIELD target type is not a record");
      if (descriptor.fieldType(instruction.field) !== instruction.result_type) {
        fail(currentPath, `LOAD_FIELD descriptor mismatch for ${instruction.record_type}.${instruction.field}`);
      }
      pop(instruction.record_type); stack.push(instruction.result_type);
    } else if (op === "MAKE_VARIANT") {
      const payloadType = table.variantPayloadType(instruction.type, instruction.variant);
      const expectedArgc = payloadType === null ? 0 : 1;
      if (instruction.argc !== expectedArgc) fail(currentPath, `MAKE_VARIANT ${instruction.type}.${instruction.variant} expects argc=${expectedArgc}`);
      if (payloadType !== null) pop(payloadType);
      stack.push(instruction.type);
    } else if (op === "TEST_VARIANT") {
      table.variantPayloadType(instruction.type, instruction.variant);
      pop(instruction.type); stack.push("Bool");
    } else if (op === "LOAD_VARIANT_PAYLOAD") {
      const payloadType = table.variantPayloadType(instruction.type, instruction.variant);
      if (payloadType === null) fail(currentPath, `${instruction.type}.${instruction.variant} is payload-free and cannot be loaded`);
      if (payloadType !== instruction.payload_type) fail(currentPath, "LOAD_VARIANT_PAYLOAD result type mismatch");
      pop(instruction.type); stack.push(payloadType);
    } else if (op === "JUMP_IF_FALSE") {
      pop("Bool");
      if (instruction.target <= pc) fail(currentPath, "backward/self jump is forbidden");
      mergeState(incoming, instruction.target, stack, initialized, currentPath, instructions.length);
      if (pc + 1 >= instructions.length) fail(currentPath, "conditional fallthrough exits handler");
      mergeState(incoming, pc + 1, stack, initialized, currentPath, instructions.length);
      continue;
    } else if (op === "JUMP") {
      if (instruction.target <= pc) fail(currentPath, "backward/self jump is forbidden");
      mergeState(incoming, instruction.target, stack, initialized, currentPath, instructions.length);
      continue;
    } else if (op === "RETURN") {
      if (stack.length !== 0) fail(currentPath, `RETURN requires empty stack, found ${JSON.stringify(stack)}`);
      reachedReturn = true;
      continue;
    } else {
      fail(currentPath, `unknown V3 opcode ${JSON.stringify(op)}`);
    }

    if (pc + 1 >= instructions.length) fail(currentPath, "reachable control flow falls off handler");
    mergeState(incoming, pc + 1, stack, initialized, currentPath, instructions.length);
  }

  if (!reachedReturn) fail(path, "no reachable RETURN");
}
