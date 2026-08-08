import {
  Rational,
  TevScriptError,
  decodeTypedValue,
  encodeTypedValue,
} from "./values.mjs";

const PRIMITIVES = new Set(["Bool", "Int", "Rat", "Text", "Vec2", "Vec3"]);
const BASE_TYPES = new Set([...PRIMITIVES, "Unit"]);
const LOCAL = /^[A-Za-z_][A-Za-z0-9_]*$/;
const NOMINAL = /^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+$/;
const MISSING = Symbol("TEV_SCRIPT_V3_MISSING_PAYLOAD");

function fail(path, message, code = "TEVS_IR_V3_CONTRACT") {
  throw new TevScriptError(code, `${path}: ${message}`);
}

function valueFail(path, typeId, message) {
  throw new TevScriptError(
    "TEVS_IR_V3_VALUE_INVALID",
    `${path}: ${message} for expected type ${JSON.stringify(typeId)}`,
  );
}

function objectValue(value, path) {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    fail(path, "expected object");
  }
  for (const key of Reflect.ownKeys(value)) {
    if (typeof key !== "string") fail(path, "object keys must be strings");
  }
  return value;
}

function arrayValue(value, path) {
  if (!Array.isArray(value)) fail(path, "expected array");
  return value;
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

function integer(value, path, minimum, maximum) {
  if (!Number.isSafeInteger(value) || value < minimum || value > maximum) {
    fail(path, `expected integer in [${minimum}, ${maximum}]`);
  }
  return value;
}

function exactKeys(value, path, expected) {
  const observed = Object.keys(value).sort();
  const target = [...expected].sort();
  if (observed.length !== target.length || observed.some((key, index) => key !== target[index])) {
    fail(path, `field set mismatch; expected=${JSON.stringify(target)}, observed=${JSON.stringify(observed)}`);
  }
}

export class TypeDescriptorV3 {
  constructor({ typeId, kind, fields = [], variants = [], argument = null, okType = null, errType = null }) {
    this.typeId = typeId;
    this.kind = kind;
    this.fields = Object.freeze(fields.map(([name, type]) => Object.freeze([name, type])));
    this.variants = Object.freeze([...variants]);
    this.argument = argument;
    this.okType = okType;
    this.errType = errType;
    Object.freeze(this);
  }

  fieldType(name) {
    for (const [fieldName, typeId] of this.fields) {
      if (fieldName === name) return typeId;
    }
    return null;
  }
}

export class RecordValueV3 {
  constructor(typeId, fields) {
    this.typeId = typeId;
    this.fields = Object.freeze(
      fields.map(([name, value]) => Object.freeze([name, value])),
    );
    Object.freeze(this);
  }

  field(name) {
    for (const [fieldName, value] of this.fields) {
      if (fieldName === name) return value;
    }
    throw new TevScriptError("TEVS_IR_V3_RUNTIME_RECORD", `record ${this.typeId} has no field ${name}`);
  }
}

export class VariantValueV3 {
  constructor(typeId, variant, payload = MISSING) {
    this.typeId = typeId;
    this.variant = variant;
    this.payload = payload;
    Object.freeze(this);
  }

  get hasPayload() {
    return this.payload !== MISSING;
  }
}

export class TypeTableV3 {
  constructor(descriptors, maximumValueNesting) {
    this.descriptors = Object.freeze([...descriptors]);
    this.maximumValueNesting = maximumValueNesting;
    this.byId = new Map(descriptors.map((descriptor) => [descriptor.typeId, descriptor]));
    Object.freeze(this);
  }

  get(typeId) {
    return this.byId.get(typeId) ?? null;
  }

  require(typeId, context = "type") {
    const descriptor = this.get(typeId);
    if (!descriptor) {
      throw new TevScriptError(
        "TEVS_IR_V3_TYPE_UNKNOWN",
        `${context} references unknown V3 type ${JSON.stringify(typeId)}`,
      );
    }
    return descriptor;
  }

  isStorable(typeId) {
    const descriptor = this.get(typeId);
    return descriptor !== null && descriptor.kind !== "unit";
  }

  variantPayloadType(typeId, variant) {
    const descriptor = this.require(typeId);
    if (descriptor.kind === "enum") {
      if (!descriptor.variants.includes(variant)) {
        throw new TevScriptError(
          "TEVS_IR_V3_VARIANT_UNKNOWN",
          `enum ${JSON.stringify(typeId)} has no variant ${JSON.stringify(variant)}`,
        );
      }
      return null;
    }
    if (descriptor.kind === "option") {
      if (variant === "None") return null;
      if (variant === "Some") return descriptor.argument;
    }
    if (descriptor.kind === "result") {
      if (variant === "Ok") return descriptor.okType;
      if (variant === "Err") return descriptor.errType;
    }
    throw new TevScriptError(
      "TEVS_IR_V3_VARIANT_UNKNOWN",
      `type ${JSON.stringify(typeId)} does not define variant ${JSON.stringify(variant)}`,
    );
  }
}

export function buildTypeTableV3(ir) {
  const boundary = objectValue(ir?.boundary, "$.boundary");
  const maximumValueNesting = integer(
    boundary.maximum_value_nesting,
    "$.boundary.maximum_value_nesting",
    1,
    128,
  );
  const rawTypes = arrayValue(ir?.types, "$.types");
  if (rawTypes.length < 7 || rawTypes.length > 16384) {
    fail("$.types", "type table must contain between 7 and 16384 descriptors");
  }

  const descriptors = [];
  const seen = new Set();
  const observedOrder = [];
  rawTypes.forEach((raw, index) => {
    const path = `$.types[${index}]`;
    const item = objectValue(raw, path);
    const typeId = stringValue(item.type_id, `${path}.type_id`);
    if (seen.has(typeId)) fail(`${path}.type_id`, `duplicate type id ${JSON.stringify(typeId)}`);
    seen.add(typeId);
    observedOrder.push(typeId);
    const kind = stringValue(item.kind, `${path}.kind`);
    let descriptor;

    if (kind === "primitive") {
      exactKeys(item, path, ["type_id", "kind"]);
      if (!PRIMITIVES.has(typeId)) fail(path, "invalid primitive descriptor");
      descriptor = new TypeDescriptorV3({ typeId, kind });
    } else if (kind === "unit") {
      exactKeys(item, path, ["type_id", "kind"]);
      if (typeId !== "Unit") fail(path, "invalid Unit descriptor");
      descriptor = new TypeDescriptorV3({ typeId, kind });
    } else if (kind === "record") {
      exactKeys(item, path, ["type_id", "kind", "fields"]);
      if (!NOMINAL.test(typeId)) fail(`${path}.type_id`, "record type id must be nominal and qualified");
      const rawFields = arrayValue(item.fields, `${path}.fields`);
      if (rawFields.length < 1 || rawFields.length > 256) fail(`${path}.fields`, "record requires 1..256 fields");
      const fields = [];
      const fieldNames = new Set();
      rawFields.forEach((rawField, fieldIndex) => {
        const fieldPath = `${path}.fields[${fieldIndex}]`;
        const field = objectValue(rawField, fieldPath);
        exactKeys(field, fieldPath, ["name", "type"]);
        const name = localName(field.name, `${fieldPath}.name`);
        const fieldType = stringValue(field.type, `${fieldPath}.type`);
        if (fieldNames.has(name)) fail(`${fieldPath}.name`, `duplicate record field ${JSON.stringify(name)}`);
        fieldNames.add(name);
        fields.push([name, fieldType]);
      });
      const names = fields.map(([name]) => name);
      if (JSON.stringify(names) !== JSON.stringify([...names].sort())) {
        fail(`${path}.fields`, "record fields must be sorted lexically by name");
      }
      descriptor = new TypeDescriptorV3({ typeId, kind, fields });
    } else if (kind === "enum") {
      exactKeys(item, path, ["type_id", "kind", "variants"]);
      if (!NOMINAL.test(typeId)) fail(`${path}.type_id`, "enum type id must be nominal and qualified");
      const variants = arrayValue(item.variants, `${path}.variants`).map((value, position) =>
        localName(value, `${path}.variants[${position}]`));
      if (variants.length < 1 || variants.length > 256) fail(`${path}.variants`, "enum requires 1..256 variants");
      if (new Set(variants).size !== variants.length) fail(`${path}.variants`, "enum variants must be unique");
      if (JSON.stringify(variants) !== JSON.stringify([...variants].sort())) fail(`${path}.variants`, "enum variants must be sorted lexically");
      descriptor = new TypeDescriptorV3({ typeId, kind, variants });
    } else if (kind === "option") {
      exactKeys(item, path, ["type_id", "kind", "argument"]);
      const argument = stringValue(item.argument, `${path}.argument`);
      if (typeId !== `Option<${argument}>`) fail(`${path}.type_id`, "Option type id does not match argument");
      descriptor = new TypeDescriptorV3({ typeId, kind, argument });
    } else if (kind === "result") {
      exactKeys(item, path, ["type_id", "kind", "ok_type", "err_type"]);
      const okType = stringValue(item.ok_type, `${path}.ok_type`);
      const errType = stringValue(item.err_type, `${path}.err_type`);
      if (typeId !== `Result<${okType},${errType}>`) fail(`${path}.type_id`, "Result type id does not match arguments");
      descriptor = new TypeDescriptorV3({ typeId, kind, okType, errType });
    } else {
      fail(`${path}.kind`, `unsupported V3 type kind ${JSON.stringify(kind)}`);
    }
    descriptors.push(descriptor);
  });

  if (JSON.stringify(observedOrder) !== JSON.stringify([...observedOrder].sort())) {
    fail("$.types", "type table must be sorted lexically by type_id");
  }
  const missingBase = [...BASE_TYPES].filter((item) => !seen.has(item)).sort();
  if (missingBase.length !== 0) fail("$.types", `missing portable base descriptors ${JSON.stringify(missingBase)}`);

  const table = new TypeTableV3(descriptors, maximumValueNesting);
  validateDescriptorReferences(table);
  validateTypeNesting(table);
  validateRecordAcyclic(table);
  return table;
}

export function decodeV3Value(typeId, raw, table, { context = "value", depth = 1 } = {}) {
  if (depth > table.maximumValueNesting) {
    throw new TevScriptError(
      "TEVS_IR_V3_VALUE_NESTING",
      `${context}: value nesting exceeds ${table.maximumValueNesting}`,
    );
  }
  const descriptor = table.require(typeId, context);
  if (descriptor.kind === "unit") {
    throw new TevScriptError("TEVS_IR_V3_UNIT_VALUE", `${context}: Unit is not a runtime value`);
  }
  if (descriptor.kind === "primitive") {
    try {
      return decodeTypedValue(typeId, raw);
    } catch (error) {
      throw new TevScriptError(
        "TEVS_IR_V3_VALUE_INVALID",
        `${context}: invalid ${typeId} value: ${error.message}`,
      );
    }
  }
  if (descriptor.kind === "record") {
    const outer = objectValue(raw, context);
    exactKeys(outer, context, ["$record"]);
    const payload = objectValue(outer.$record, `${context}.$record`);
    exactKeys(payload, `${context}.$record`, ["type", "fields"]);
    if (payload.type !== typeId) valueFail(context, typeId, "record encoded type mismatch");
    const rawFields = arrayValue(payload.fields, `${context}.$record.fields`);
    if (rawFields.length !== descriptor.fields.length) valueFail(context, typeId, "record field count mismatch");
    const decoded = [];
    descriptor.fields.forEach(([expectedName, fieldType], index) => {
      const fieldPath = `${context}.$record.fields[${index}]`;
      const field = objectValue(rawFields[index], fieldPath);
      exactKeys(field, fieldPath, ["name", "value"]);
      if (field.name !== expectedName) {
        valueFail(fieldPath, fieldType, `expected canonical field ${JSON.stringify(expectedName)}, got ${JSON.stringify(field.name)}`);
      }
      decoded.push([
        expectedName,
        decodeV3Value(fieldType, field.value, table, { context: `${fieldPath}.value`, depth: depth + 1 }),
      ]);
    });
    return new RecordValueV3(typeId, decoded);
  }
  if (descriptor.kind === "enum") {
    const outer = objectValue(raw, context);
    exactKeys(outer, context, ["$enum"]);
    const payload = objectValue(outer.$enum, `${context}.$enum`);
    exactKeys(payload, `${context}.$enum`, ["type", "variant"]);
    if (payload.type !== typeId) valueFail(context, typeId, "enum encoded type mismatch");
    const variant = localName(payload.variant, `${context}.$enum.variant`);
    if (!descriptor.variants.includes(variant)) valueFail(context, typeId, `unknown enum variant ${JSON.stringify(variant)}`);
    return new VariantValueV3(typeId, variant);
  }
  if (descriptor.kind === "option") {
    const outer = objectValue(raw, context);
    exactKeys(outer, context, ["$option"]);
    const payload = objectValue(outer.$option, `${context}.$option`);
    if (payload.type !== typeId) valueFail(context, typeId, "Option encoded type mismatch");
    if (payload.variant === "None") {
      exactKeys(payload, `${context}.$option`, ["type", "variant"]);
      return new VariantValueV3(typeId, "None");
    }
    if (payload.variant === "Some") {
      exactKeys(payload, `${context}.$option`, ["type", "variant", "value"]);
      return new VariantValueV3(
        typeId,
        "Some",
        decodeV3Value(descriptor.argument, payload.value, table, {
          context: `${context}.$option.value`, depth: depth + 1,
        }),
      );
    }
    valueFail(context, typeId, `unknown Option variant ${JSON.stringify(payload.variant)}`);
  }
  if (descriptor.kind === "result") {
    const outer = objectValue(raw, context);
    exactKeys(outer, context, ["$result"]);
    const payload = objectValue(outer.$result, `${context}.$result`);
    if (payload.type !== typeId) valueFail(context, typeId, "Result encoded type mismatch");
    const payloadType = payload.variant === "Ok" ? descriptor.okType : payload.variant === "Err" ? descriptor.errType : null;
    if (payloadType === null) valueFail(context, typeId, `unknown Result variant ${JSON.stringify(payload.variant)}`);
    exactKeys(payload, `${context}.$result`, ["type", "variant", "value"]);
    return new VariantValueV3(
      typeId,
      payload.variant,
      decodeV3Value(payloadType, payload.value, table, {
        context: `${context}.$result.value`, depth: depth + 1,
      }),
    );
  }
  throw new TevScriptError("TEVS_IR_V3_VALUE_INVALID", `${context}: unsupported descriptor ${descriptor.kind}`);
}

export function encodeV3Value(typeId, value, table, { context = "value", depth = 1 } = {}) {
  if (depth > table.maximumValueNesting) {
    throw new TevScriptError(
      "TEVS_IR_V3_VALUE_NESTING",
      `${context}: value nesting exceeds ${table.maximumValueNesting}`,
    );
  }
  const descriptor = table.require(typeId, context);
  if (descriptor.kind === "unit") {
    throw new TevScriptError("TEVS_IR_V3_UNIT_VALUE", `${context}: Unit is not encodable`);
  }
  if (descriptor.kind === "primitive") return encodeTypedValue(typeId, value);
  if (descriptor.kind === "record") {
    if (!(value instanceof RecordValueV3) || value.typeId !== typeId) valueFail(context, typeId, "expected exact RecordValueV3");
    const actual = new Map(value.fields);
    if (actual.size !== descriptor.fields.length || descriptor.fields.some(([name]) => !actual.has(name))) {
      valueFail(context, typeId, "record field set mismatch");
    }
    return {
      $record: {
        type: typeId,
        fields: descriptor.fields.map(([name, fieldType]) => ({
          name,
          value: encodeV3Value(fieldType, actual.get(name), table, {
            context: `${context}.${name}`, depth: depth + 1,
          }),
        })),
      },
    };
  }
  if (!(value instanceof VariantValueV3) || value.typeId !== typeId) valueFail(context, typeId, "expected exact VariantValueV3");
  const payloadType = table.variantPayloadType(typeId, value.variant);
  if (descriptor.kind === "enum") {
    if (value.hasPayload) valueFail(context, typeId, "enum variant cannot carry payload");
    return { $enum: { type: typeId, variant: value.variant } };
  }
  const key = descriptor.kind === "option" ? "$option" : "$result";
  const payload = { type: typeId, variant: value.variant };
  if (payloadType === null) {
    if (value.hasPayload) valueFail(context, typeId, `${value.variant} cannot carry payload`);
  } else {
    if (!value.hasPayload) valueFail(context, typeId, `${value.variant} requires payload`);
    payload.value = encodeV3Value(payloadType, value.payload, table, {
      context: `${context}.value`, depth: depth + 1,
    });
  }
  return { [key]: payload };
}

export function v3ValuesEqual(typeId, left, right, table) {
  const descriptor = table.require(typeId);
  if (descriptor.kind === "primitive") {
    if (typeId === "Rat") {
      return left instanceof Rational && right instanceof Rational && left.equals(right);
    }
    if (typeId === "Vec2" || typeId === "Vec3") {
      return Array.isArray(left) && Array.isArray(right)
        && left.length === right.length
        && left.every((value, index) => value instanceof Rational && right[index] instanceof Rational && value.equals(right[index]));
    }
    return left === right;
  }
  if (descriptor.kind === "record") {
    if (!(left instanceof RecordValueV3) || !(right instanceof RecordValueV3)
        || left.typeId !== typeId || right.typeId !== typeId) return false;
    const leftFields = new Map(left.fields);
    const rightFields = new Map(right.fields);
    if (leftFields.size !== descriptor.fields.length || rightFields.size !== descriptor.fields.length) return false;
    return descriptor.fields.every(([name, fieldType]) =>
      leftFields.has(name) && rightFields.has(name)
      && v3ValuesEqual(fieldType, leftFields.get(name), rightFields.get(name), table));
  }
  if (descriptor.kind === "enum" || descriptor.kind === "option" || descriptor.kind === "result") {
    if (!(left instanceof VariantValueV3) || !(right instanceof VariantValueV3)
        || left.typeId !== typeId || right.typeId !== typeId
        || left.variant !== right.variant || left.hasPayload !== right.hasPayload) return false;
    if (!left.hasPayload) return true;
    const payloadType = table.variantPayloadType(typeId, left.variant);
    return payloadType !== null && v3ValuesEqual(payloadType, left.payload, right.payload, table);
  }
  return false;
}

function validateDescriptorReferences(table) {
  for (const descriptor of table.descriptors) {
    let referenced = [];
    if (descriptor.kind === "record") referenced = descriptor.fields.map(([, typeId]) => typeId);
    else if (descriptor.kind === "option") referenced = [descriptor.argument];
    else if (descriptor.kind === "result") referenced = [descriptor.okType, descriptor.errType];
    for (const typeId of referenced) {
      const child = table.require(typeId, `descriptor ${descriptor.typeId}`);
      if (child.kind === "unit") fail("$.types", `Unit is not storable inside ${JSON.stringify(descriptor.typeId)}`);
    }
  }
}

function validateTypeNesting(table) {
  const memo = new Map();
  for (const start of [...table.byId.keys()].sort()) {
    if (memo.has(start)) continue;
    const frames = [[start, false]];
    const active = new Set();
    while (frames.length > 0) {
      const [typeId, expanded] = frames.pop();
      if (memo.has(typeId)) continue;
      const descriptor = table.require(typeId);
      let children = [];
      if (descriptor.kind === "option") children = [descriptor.argument];
      else if (descriptor.kind === "result") children = [descriptor.okType, descriptor.errType];
      if (!expanded && children.length > 0) {
        if (active.has(typeId)) fail("$.types", `constructed type dependency cycle at ${JSON.stringify(typeId)}`);
        active.add(typeId);
        frames.push([typeId, true]);
        for (const child of [...children].reverse()) {
          if (active.has(child)) fail("$.types", `constructed type dependency cycle at ${JSON.stringify(child)}`);
          if (!memo.has(child)) frames.push([child, false]);
        }
      } else {
        const observed = children.length === 0 ? 1 : 1 + Math.max(...children.map((child) => memo.get(child)));
        active.delete(typeId);
        memo.set(typeId, observed);
        if (observed > 128) fail("$.types", `type nesting exceeds 128 at ${JSON.stringify(typeId)}: got ${observed}`);
      }
    }
  }
}

function validateRecordAcyclic(table) {
  const graph = new Map();
  for (const descriptor of table.descriptors) {
    if (descriptor.kind !== "record") continue;
    const dependencies = new Set();
    const stack = descriptor.fields.map(([, typeId]) => typeId);
    const seenTypes = new Set();
    while (stack.length > 0) {
      const typeId = stack.pop();
      if (seenTypes.has(typeId)) continue;
      seenTypes.add(typeId);
      const child = table.require(typeId);
      if (child.kind === "record") dependencies.add(typeId);
      else if (child.kind === "option") stack.push(child.argument);
      else if (child.kind === "result") stack.push(child.okType, child.errType);
    }
    graph.set(descriptor.typeId, [...dependencies].sort());
  }
  const state = new Map();
  for (const start of [...graph.keys()].sort()) {
    if ((state.get(start) ?? 0) === 2) continue;
    const frames = [[start, 0]];
    const path = [];
    while (frames.length > 0) {
      const frame = frames[frames.length - 1];
      const node = frame[0];
      if ((state.get(node) ?? 0) === 0) {
        state.set(node, 1);
        path.push(node);
      }
      const dependencies = graph.get(node);
      if (frame[1] < dependencies.length) {
        const child = dependencies[frame[1]];
        frame[1] += 1;
        const mark = state.get(child) ?? 0;
        if (mark === 0) {
          frames.push([child, 0]);
          continue;
        }
        if (mark === 1) {
          const startIndex = Math.max(0, path.indexOf(child));
          fail("$.types", `recursive record dependency: ${[...path.slice(startIndex), child].join(" -> ")}`);
        }
        continue;
      }
      frames.pop();
      const popped = path.pop();
      if (popped !== node) throw new Error("internal V3 record graph invariant");
      state.set(node, 2);
    }
  }
}

export { Rational, TevScriptError } from "./values.mjs";
