import { TevScriptError } from "./values.mjs";

function fail(path, message) {
  throw new TevScriptError("TEVS_IR_FLOW_INVALID", `${path}: ${message}`);
}

function binarySignature(operator, left, right, result) {
  if (["AND", "OR"].includes(operator)) return left === "Bool" && right === "Bool" && result === "Bool";
  if (["EQEQ", "NE"].includes(operator)) return result === "Bool" && (left === right || (left === "Rat" && right === "Rat"));
  if (["LT", "LE", "GT", "GE"].includes(operator)) return left === right && ["Int", "Rat"].includes(left) && result === "Bool";
  if (["PLUS", "MINUS"].includes(operator)) {
    return (left === "Int" && right === "Int" && result === "Int")
      || (left === "Rat" && right === "Rat" && result === "Rat")
      || (left === right && result === left && ["Vec2", "Vec3"].includes(result));
  }
  if (operator === "STAR") {
    return (left === "Int" && right === "Int" && result === "Int")
      || (left === "Rat" && right === "Rat" && result === "Rat")
      || (["Vec2", "Vec3"].includes(left) && right === "Rat" && result === left)
      || (["Vec2", "Vec3"].includes(right) && left === "Rat" && result === right);
  }
  if (operator === "SLASH") {
    return (left === "Rat" && right === "Rat" && result === "Rat")
      || (["Vec2", "Vec3"].includes(left) && right === "Rat" && result === left);
  }
  return false;
}

function maps(entity, handler) {
  return {
    states: new Map(entity.states.map((item) => [item.name, item.type])),
    parameters: new Map(handler.parameters.map((item) => [item.name, item.type])),
    locals: new Map(handler.locals.map((item) => [item.name, item.type])),
    capabilities: new Map(entity.capabilities.map((item) => [item.capability_id, {
      parameters: [...item.parameters], returnType: item.return_type, kind: item.kind,
    }])),
    events: new Map(entity.emitted_events.map((item) => [item.event_id, [...item.parameters]])),
  };
}

function sameStack(left, right) {
  return left.length === right.length && left.every((value, index) => value === right[index]);
}

export function validateEntityHandlerFlow(entity, handler, path) {
  const { states, parameters, locals, capabilities, events } = maps(entity, handler);
  const instructions = handler.instructions;
  const incoming = new Array(instructions.length).fill(null);
  incoming[0] = { stack: [], initialized: new Set() };
  let reachedReturn = false;

  function merge(target, stack, initialized, source) {
    if (!Number.isInteger(target) || target < 0 || target >= instructions.length) {
      fail(source, "control flow must target an instruction, not handler exit");
    }
    const next = { stack: [...stack], initialized: new Set(initialized) };
    const current = incoming[target];
    if (current === null) {
      incoming[target] = next;
      return;
    }
    if (!sameStack(current.stack, next.stack)) fail(source, `CFG merge stack mismatch at instruction ${target}`);
    incoming[target] = {
      stack: current.stack,
      initialized: new Set([...current.initialized].filter((name) => next.initialized.has(name))),
    };
  }

  for (let pc = 0; pc < instructions.length; pc += 1) {
    const state = incoming[pc];
    if (state === null) continue;
    const stack = [...state.stack];
    const initialized = new Set(state.initialized);
    const instruction = instructions[pc];
    const op = instruction.op;
    const currentPath = `${path}.instructions[${pc}]`;

    function pop(expected) {
      if (stack.length === 0) fail(currentPath, `stack underflow; expected ${expected}`);
      const actual = stack.pop();
      if (actual !== expected) fail(currentPath, `stack type mismatch; expected ${expected}, got ${actual}`);
    }

    if (op === "CONST") stack.push(instruction.type);
    else if (op === "LOAD_STATE") stack.push(states.get(instruction.name));
    else if (op === "STORE_STATE") pop(states.get(instruction.name));
    else if (op === "LOAD_LOCAL") {
      if (!initialized.has(instruction.name)) fail(currentPath, `local ${JSON.stringify(instruction.name)} is not definitely initialized`);
      stack.push(locals.get(instruction.name));
    } else if (op === "STORE_LOCAL") {
      pop(locals.get(instruction.name));
      initialized.add(instruction.name);
    } else if (op === "LOAD_PARAM") stack.push(parameters.get(instruction.name));
    else if (op === "CONVERT_INT_TO_RAT") { pop("Int"); stack.push("Rat"); }
    else if (op === "UNARY") {
      pop(instruction.operator === "NOT" ? "Bool" : instruction.type);
      stack.push(instruction.type);
    } else if (op === "BINARY") {
      if (!binarySignature(instruction.operator, instruction.left_type, instruction.right_type, instruction.result_type)) {
        fail(currentPath, "binary operator/type contract is not a V0.2 lowering");
      }
      pop(instruction.right_type);
      pop(instruction.left_type);
      stack.push(instruction.result_type);
    } else if (op === "CALL_PURE") {
      let expected;
      if (instruction.function_id === "vec2") expected = ["Rat", "Rat"];
      else if (instruction.function_id === "vec3") expected = ["Rat", "Rat", "Rat"];
      else if (["max", "min"].includes(instruction.function_id)) expected = [instruction.return_type, instruction.return_type];
      else fail(currentPath, `unknown pure function ${JSON.stringify(instruction.function_id)}`);
      [...expected].reverse().forEach(pop);
      if (instruction.return_type !== "Unit") stack.push(instruction.return_type);
    } else if (op === "CALL_CAPABILITY") {
      const signature = capabilities.get(instruction.capability_id);
      [...signature.parameters].reverse().forEach(pop);
      if (signature.returnType !== "Unit") stack.push(signature.returnType);
    } else if (op === "EMIT_EVENT") {
      [...events.get(instruction.event_id)].reverse().forEach(pop);
    } else if (op === "JUMP_IF_FALSE") {
      pop("Bool");
      merge(instruction.target, stack, initialized, currentPath);
      if (pc + 1 >= instructions.length) fail(currentPath, "conditional fallthrough exits the handler");
      merge(pc + 1, stack, initialized, currentPath);
      continue;
    } else if (op === "JUMP") {
      merge(instruction.target, stack, initialized, currentPath);
      continue;
    } else if (op === "RETURN") {
      if (stack.length !== 0) fail(currentPath, `RETURN requires empty stack, found ${JSON.stringify(stack)}`);
      reachedReturn = true;
      continue;
    } else fail(currentPath, `unknown opcode ${JSON.stringify(op)}`);

    if (pc + 1 >= instructions.length) fail(currentPath, "reachable control flow falls off the handler");
    merge(pc + 1, stack, initialized, currentPath);
  }
  if (!reachedReturn) fail(path, "no reachable RETURN");
}
