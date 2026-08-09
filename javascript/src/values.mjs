export class TevScriptError extends Error {
  constructor(code, message) {
    super(`${code}: ${message}`);
    this.name = "TevScriptError";
    this.code = code;
  }
}

function abs(value) {
  return value < 0n ? -value : value;
}

function gcd(left, right) {
  let a = abs(left);
  let b = abs(right);
  while (b !== 0n) {
    const next = a % b;
    a = b;
    b = next;
  }
  return a;
}

export class Rational {
  constructor(numerator, denominator = 1n) {
    let n = BigInt(numerator);
    let d = BigInt(denominator);
    if (d === 0n) {
      throw new TevScriptError("TEVS_RUNTIME_DIVIDE_ZERO", "rational denominator is zero");
    }
    if (d < 0n) {
      n = -n;
      d = -d;
    }
    const divisor = gcd(n, d);
    this.numerator = n / divisor;
    this.denominator = d / divisor;
    Object.freeze(this);
  }

  static from(value) {
    if (value instanceof Rational) return value;
    if (typeof value === "bigint") return new Rational(value);
    if (typeof value === "number" && Number.isSafeInteger(value)) {
      return new Rational(BigInt(value));
    }
    if (typeof value === "string" && /^-?(0|[1-9][0-9]*)$/.test(value)) {
      return new Rational(BigInt(value));
    }
    throw new TevScriptError("TEVS_RUNTIME_RAT", "value cannot be coerced to Rat");
  }

  add(other) {
    const right = Rational.from(other);
    return new Rational(
      this.numerator * right.denominator + right.numerator * this.denominator,
      this.denominator * right.denominator,
    );
  }

  sub(other) {
    const right = Rational.from(other);
    return new Rational(
      this.numerator * right.denominator - right.numerator * this.denominator,
      this.denominator * right.denominator,
    );
  }

  mul(other) {
    const right = Rational.from(other);
    return new Rational(
      this.numerator * right.numerator,
      this.denominator * right.denominator,
    );
  }

  div(other) {
    const right = Rational.from(other);
    if (right.numerator === 0n) {
      throw new TevScriptError("TEVS_RUNTIME_DIVIDE_ZERO", "division by zero");
    }
    return new Rational(
      this.numerator * right.denominator,
      this.denominator * right.numerator,
    );
  }

  neg() {
    return new Rational(-this.numerator, this.denominator);
  }

  compare(other) {
    const right = Rational.from(other);
    const leftScaled = this.numerator * right.denominator;
    const rightScaled = right.numerator * this.denominator;
    return leftScaled === rightScaled ? 0 : leftScaled < rightScaled ? -1 : 1;
  }

  equals(other) {
    return other instanceof Rational
      && this.numerator === other.numerator
      && this.denominator === other.denominator;
  }
}

function requireCanonicalIntegerText(text) {
  if (typeof text !== "string" || !/^-?(0|[1-9][0-9]*)$/.test(text) || text === "-0") {
    throw new TevScriptError("TEVS_RUNTIME_INT", "integer text is not canonical");
  }
  return BigInt(text);
}

export function decodeTypedValue(typeName, raw) {
  if (typeName === "Int") {
    if (raw === null || typeof raw !== "object" || Array.isArray(raw)
        || Object.keys(raw).length !== 1 || !("$int" in raw)) {
      throw new TevScriptError("TEVS_RUNTIME_INT", "invalid integer value");
    }
    return requireCanonicalIntegerText(raw.$int);
  }
  if (typeName === "Rat") {
    if (raw === null || typeof raw !== "object" || Array.isArray(raw)
        || Object.keys(raw).length !== 1 || !("$rat" in raw)
        || !Array.isArray(raw.$rat) || raw.$rat.length !== 2) {
      throw new TevScriptError("TEVS_RUNTIME_RAT", "invalid rational value");
    }
    const numerator = requireCanonicalIntegerText(raw.$rat[0]);
    const denominator = requireCanonicalIntegerText(raw.$rat[1]);
    const value = new Rational(numerator, denominator);
    if (value.numerator.toString() !== raw.$rat[0]
        || value.denominator.toString() !== raw.$rat[1]) {
      throw new TevScriptError("TEVS_RUNTIME_RAT", "rational must be normalized");
    }
    return value;
  }
  if (typeName === "Vec2" || typeName === "Vec3") {
    const expected = typeName === "Vec2" ? 2 : 3;
    if (!Array.isArray(raw) || raw.length !== expected) {
      throw new TevScriptError("TEVS_RUNTIME_VECTOR", `invalid ${typeName} value`);
    }
    return raw.map((item) => decodeTypedValue("Rat", item));
  }
  if (typeName === "Bool") {
    if (typeof raw !== "boolean") throw new TevScriptError("TEVS_RUNTIME_BOOL", "invalid Bool");
    return raw;
  }
  if (typeName === "Text") {
    if (typeof raw !== "string") throw new TevScriptError("TEVS_RUNTIME_TEXT", "invalid Text");
    return raw;
  }
  if (typeName === "Unit") {
    if (raw !== null) throw new TevScriptError("TEVS_RUNTIME_UNIT", "invalid Unit");
    return null;
  }
  throw new TevScriptError("TEVS_RUNTIME_TYPE", `unknown type ${typeName}`);
}

export function encodeTypedValue(typeName, value) {
  if (typeName === "Int") {
    if (typeof value !== "bigint") {
      throw new TevScriptError("TEVS_RUNTIME_INT", "expected BigInt");
    }
    return { $int: value.toString() };
  }
  if (typeName === "Rat") {
    const rational = Rational.from(value);
    return { $rat: [rational.numerator.toString(), rational.denominator.toString()] };
  }
  if (typeName === "Vec2" || typeName === "Vec3") {
    const expected = typeName === "Vec2" ? 2 : 3;
    if (!Array.isArray(value) || value.length !== expected) {
      throw new TevScriptError("TEVS_RUNTIME_VECTOR", `expected ${typeName}`);
    }
    return value.map((item) => encodeTypedValue("Rat", item));
  }
  if (typeName === "Bool") {
    if (typeof value !== "boolean") throw new TevScriptError("TEVS_RUNTIME_BOOL", "expected Bool");
    return value;
  }
  if (typeName === "Text") {
    if (typeof value !== "string") throw new TevScriptError("TEVS_RUNTIME_TEXT", "expected Text");
    return value;
  }
  if (typeName === "Unit") return null;
  throw new TevScriptError("TEVS_RUNTIME_TYPE", `unknown type ${typeName}`);
}

export function coerceRuntime(value, typeName) {
  if (typeName === "Int") {
    if (typeof value === "bigint") return value;
    if (typeof value === "number" && Number.isSafeInteger(value)) return BigInt(value);
    if (typeof value === "string") return requireCanonicalIntegerText(value);
    throw new TevScriptError("TEVS_RUNTIME_INT", "expected Int");
  }
  if (typeName === "Rat") return Rational.from(value);
  if (typeName === "Vec2" || typeName === "Vec3") {
    const expected = typeName === "Vec2" ? 2 : 3;
    if (!Array.isArray(value) || value.length !== expected) {
      throw new TevScriptError("TEVS_RUNTIME_VECTOR", `expected ${typeName}`);
    }
    return value.map((item) => Rational.from(item));
  }
  if (typeName === "Bool") {
    if (typeof value !== "boolean") throw new TevScriptError("TEVS_RUNTIME_BOOL", "expected Bool");
    return value;
  }
  if (typeName === "Text") {
    if (typeof value !== "string") throw new TevScriptError("TEVS_RUNTIME_TEXT", "expected Text");
    return value;
  }
  if (typeName === "Unit") return null;
  throw new TevScriptError("TEVS_RUNTIME_TYPE", `unknown type ${typeName}`);
}

export function valueEquals(left, right) {
  if (left instanceof Rational || right instanceof Rational) {
    return left instanceof Rational && right instanceof Rational && left.equals(right);
  }
  if (Array.isArray(left) || Array.isArray(right)) {
    return Array.isArray(left) && Array.isArray(right)
      && left.length === right.length
      && left.every((value, index) => valueEquals(value, right[index]));
  }
  return left === right;
}

export function compareValues(left, right) {
  if (left instanceof Rational || right instanceof Rational) {
    return Rational.from(left).compare(right);
  }
  if (typeof left === "bigint" && typeof right === "bigint") {
    return left === right ? 0 : left < right ? -1 : 1;
  }
  if (typeof left === "string" && typeof right === "string") {
    return left === right ? 0 : left < right ? -1 : 1;
  }
  throw new TevScriptError("TEVS_RUNTIME_COMPARE", "values are not comparable");
}
