export class CanonicalError extends Error {
  constructor(code, message) {
    super(`${code}: ${message}`);
    this.name = "CanonicalError";
    this.code = code;
  }
}

export function scalarCompare(left, right) {
  if (left === right) return 0;
  const a = Array.from(left);
  const b = Array.from(right);
  const length = Math.min(a.length, b.length);
  for (let index = 0; index < length; index += 1) {
    const av = a[index].codePointAt(0);
    const bv = b[index].codePointAt(0);
    if (av !== bv) return av < bv ? -1 : 1;
  }
  return a.length < b.length ? -1 : 1;
}

function writeString(value) {
  let output = '"';
  for (let index = 0; index < value.length; index += 1) {
    const unit = value.charCodeAt(index);
    switch (unit) {
      case 0x22: output += '\\"'; break;
      case 0x5c: output += '\\\\'; break;
      case 0x08: output += '\\b'; break;
      case 0x0c: output += '\\f'; break;
      case 0x0a: output += '\\n'; break;
      case 0x0d: output += '\\r'; break;
      case 0x09: output += '\\t'; break;
      default:
        if (unit < 0x20 || unit > 0x7e) {
          output += `\\u${unit.toString(16).padStart(4, "0")}`;
        } else {
          output += String.fromCharCode(unit);
        }
        break;
    }
  }
  return `${output}"`;
}

export function canonicalJson(value) {
  if (value === null) return "null";
  if (typeof value === "boolean") return value ? "true" : "false";
  if (typeof value === "string") return writeString(value);
  if (typeof value === "number") {
    if (Object.is(value, -0)) {
      throw new CanonicalError(
        "TEVS_JS_CANONICAL_NEGATIVE_ZERO",
        "negative zero is forbidden",
      );
    }
    if (!Number.isSafeInteger(value)) {
      throw new CanonicalError(
        "TEVS_JS_CANONICAL_NUMBER",
        "only bounded structural integers may use JSON numbers",
      );
    }
    return String(value);
  }
  if (typeof value === "bigint") {
    throw new CanonicalError(
      "TEVS_JS_CANONICAL_BIGINT",
      "semantic integers must use {$int:string}",
    );
  }
  if (Array.isArray(value)) {
    return `[${value.map(canonicalJson).join(",")}]`;
  }
  if (typeof value === "object") {
    const prototype = Object.getPrototypeOf(value);
    if (prototype !== Object.prototype && prototype !== null) {
      throw new CanonicalError(
        "TEVS_JS_CANONICAL_OBJECT",
        "only plain objects may be canonicalized",
      );
    }
    if (Object.getOwnPropertySymbols(value).length !== 0) {
      throw new CanonicalError(
        "TEVS_JS_CANONICAL_SYMBOL_KEY",
        "symbol keys are forbidden",
      );
    }
    const keys = Object.keys(value).sort(scalarCompare);
    return `{${keys.map((key) => `${writeString(key)}:${canonicalJson(value[key])}`).join(",")}}`;
  }
  throw new CanonicalError(
    "TEVS_JS_CANONICAL_TYPE",
    `unsupported value ${typeof value}`,
  );
}

const SHA256_K = Object.freeze([
  0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5,
  0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
  0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3,
  0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
  0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc,
  0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
  0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7,
  0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
  0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13,
  0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
  0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3,
  0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
  0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5,
  0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
  0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208,
  0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
]);

function rotateRight(value, count) {
  return (value >>> count) | (value << (32 - count));
}

export function sha256Hex(text) {
  const bytes = new TextEncoder().encode(text);
  const bitLength = BigInt(bytes.length) * 8n;
  const paddedLength = Math.ceil((bytes.length + 9) / 64) * 64;
  const padded = new Uint8Array(paddedLength);
  padded.set(bytes);
  padded[bytes.length] = 0x80;
  for (let index = 0; index < 8; index += 1) {
    padded[padded.length - 1 - index] = Number(
      (bitLength >> BigInt(index * 8)) & 0xffn,
    );
  }

  const state = new Uint32Array([
    0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
    0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19,
  ]);
  const words = new Uint32Array(64);

  for (let offset = 0; offset < padded.length; offset += 64) {
    for (let index = 0; index < 16; index += 1) {
      const base = offset + index * 4;
      words[index] = (
        (padded[base] << 24)
        | (padded[base + 1] << 16)
        | (padded[base + 2] << 8)
        | padded[base + 3]
      ) >>> 0;
    }
    for (let index = 16; index < 64; index += 1) {
      const s0 = (
        rotateRight(words[index - 15], 7)
        ^ rotateRight(words[index - 15], 18)
        ^ (words[index - 15] >>> 3)
      ) >>> 0;
      const s1 = (
        rotateRight(words[index - 2], 17)
        ^ rotateRight(words[index - 2], 19)
        ^ (words[index - 2] >>> 10)
      ) >>> 0;
      words[index] = (
        words[index - 16] + s0 + words[index - 7] + s1
      ) >>> 0;
    }

    let a = state[0]; let b = state[1]; let c = state[2]; let d = state[3];
    let e = state[4]; let f = state[5]; let g = state[6]; let h = state[7];
    for (let index = 0; index < 64; index += 1) {
      const s1 = (rotateRight(e, 6) ^ rotateRight(e, 11) ^ rotateRight(e, 25)) >>> 0;
      const choice = ((e & f) ^ (~e & g)) >>> 0;
      const temp1 = (h + s1 + choice + SHA256_K[index] + words[index]) >>> 0;
      const s0 = (rotateRight(a, 2) ^ rotateRight(a, 13) ^ rotateRight(a, 22)) >>> 0;
      const majority = ((a & b) ^ (a & c) ^ (b & c)) >>> 0;
      const temp2 = (s0 + majority) >>> 0;
      h = g; g = f; f = e; e = (d + temp1) >>> 0;
      d = c; c = b; b = a; a = (temp1 + temp2) >>> 0;
    }
    state[0] = (state[0] + a) >>> 0;
    state[1] = (state[1] + b) >>> 0;
    state[2] = (state[2] + c) >>> 0;
    state[3] = (state[3] + d) >>> 0;
    state[4] = (state[4] + e) >>> 0;
    state[5] = (state[5] + f) >>> 0;
    state[6] = (state[6] + g) >>> 0;
    state[7] = (state[7] + h) >>> 0;
  }

  return Array.from(state)
    .map((value) => value.toString(16).padStart(8, "0"))
    .join("");
}

export function canonicalHash(value) {
  return sha256Hex(canonicalJson(value));
}
