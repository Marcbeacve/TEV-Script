const MAX_STRUCTURAL_INTEGER = Number.MAX_SAFE_INTEGER;
const DEFAULT_MAX_DEPTH = 256;

export class StrictJsonError extends Error {
  constructor(code, message, offset = null) {
    const location = offset === null ? "" : ` at offset ${offset}`;
    super(`${code}${location}: ${message}`);
    this.name = "StrictJsonError";
    this.code = code;
    this.offset = offset;
  }
}

class Parser {
  constructor(text, maxDepth) {
    this.text = text;
    this.index = 0;
    this.maxDepth = maxDepth;
  }

  parse() {
    this.skipWhitespace();
    const value = this.parseValue(0);
    this.skipWhitespace();
    if (this.index !== this.text.length) {
      this.fail("TEVS_JSON_TRAILING_DATA", "unexpected trailing data");
    }
    return value;
  }

  parseValue(depth) {
    if (depth > this.maxDepth) {
      this.fail("TEVS_JSON_DEPTH", `nesting exceeds ${this.maxDepth}`);
    }
    const character = this.text[this.index];
    if (character === "{") return this.parseObject(depth + 1);
    if (character === "[") return this.parseArray(depth + 1);
    if (character === '"') return this.parseString();
    if (character === "t") return this.parseLiteral("true", true);
    if (character === "f") return this.parseLiteral("false", false);
    if (character === "n") return this.parseLiteral("null", null);
    if (character === "-" || this.isDigit(character)) return this.parseInteger();
    this.fail("TEVS_JSON_SYNTAX", "expected a JSON value");
  }

  parseObject(depth) {
    const result = {};
    const keys = new Set();
    this.index += 1;
    this.skipWhitespace();
    if (this.text[this.index] === "}") {
      this.index += 1;
      return result;
    }
    while (true) {
      if (this.text[this.index] !== '"') {
        this.fail("TEVS_JSON_SYNTAX", "object member name must be a string");
      }
      const key = this.parseString();
      if (keys.has(key)) {
        this.fail("TEVS_JSON_DUPLICATE_KEY", `duplicate JSON object member ${JSON.stringify(key)}`);
      }
      keys.add(key);
      this.skipWhitespace();
      if (this.text[this.index] !== ":") {
        this.fail("TEVS_JSON_SYNTAX", "expected ':' after object member name");
      }
      this.index += 1;
      this.skipWhitespace();
      Object.defineProperty(result, key, {
        value: this.parseValue(depth),
        enumerable: true,
        configurable: true,
        writable: true,
      });
      this.skipWhitespace();
      const separator = this.text[this.index];
      if (separator === "}") {
        this.index += 1;
        return result;
      }
      if (separator !== ",") {
        this.fail("TEVS_JSON_SYNTAX", "expected ',' or '}' in object");
      }
      this.index += 1;
      this.skipWhitespace();
    }
  }

  parseArray(depth) {
    const result = [];
    this.index += 1;
    this.skipWhitespace();
    if (this.text[this.index] === "]") {
      this.index += 1;
      return result;
    }
    while (true) {
      result.push(this.parseValue(depth));
      this.skipWhitespace();
      const separator = this.text[this.index];
      if (separator === "]") {
        this.index += 1;
        return result;
      }
      if (separator !== ",") {
        this.fail("TEVS_JSON_SYNTAX", "expected ',' or ']' in array");
      }
      this.index += 1;
      this.skipWhitespace();
    }
  }

  parseString() {
    let output = "";
    this.index += 1;
    while (this.index < this.text.length) {
      const character = this.text[this.index];
      const unit = this.text.charCodeAt(this.index);
      if (character === '"') {
        this.index += 1;
        return output;
      }
      if (character === "\\") {
        this.index += 1;
        const escape = this.text[this.index];
        switch (escape) {
          case '"': output += '"'; this.index += 1; break;
          case "\\": output += "\\"; this.index += 1; break;
          case "/": output += "/"; this.index += 1; break;
          case "b": output += "\b"; this.index += 1; break;
          case "f": output += "\f"; this.index += 1; break;
          case "n": output += "\n"; this.index += 1; break;
          case "r": output += "\r"; this.index += 1; break;
          case "t": output += "\t"; this.index += 1; break;
          case "u": output += this.parseUnicodeEscape(); break;
          default: this.fail("TEVS_JSON_STRING_ESCAPE", "invalid JSON string escape");
        }
        continue;
      }
      if (unit < 0x20) {
        this.fail("TEVS_JSON_STRING_CONTROL", "unescaped control character in string");
      }
      output += character;
      this.index += 1;
    }
    this.fail("TEVS_JSON_SYNTAX", "unterminated JSON string");
  }

  parseUnicodeEscape() {
    const start = this.index + 1;
    const hex = this.text.slice(start, start + 4);
    if (!/^[0-9a-fA-F]{4}$/.test(hex)) {
      this.fail("TEVS_JSON_STRING_ESCAPE", "invalid Unicode escape");
    }
    this.index = start + 4;
    return String.fromCharCode(Number.parseInt(hex, 16));
  }

  parseLiteral(token, value) {
    if (this.text.slice(this.index, this.index + token.length) !== token) {
      this.fail("TEVS_JSON_SYNTAX", `invalid literal; expected ${token}`);
    }
    this.index += token.length;
    return value;
  }

  parseInteger() {
    const start = this.index;
    if (this.text[this.index] === "-") {
      this.index += 1;
      if (!this.isDigit(this.text[this.index])) {
        this.fail("TEVS_JSON_SYNTAX", "minus sign must be followed by a digit");
      }
    }
    if (this.text[this.index] === "0") {
      this.index += 1;
      if (this.isDigit(this.text[this.index])) {
        this.fail("TEVS_JSON_SYNTAX", "leading zero in JSON number");
      }
    } else {
      if (!this.isDigitOneToNine(this.text[this.index])) {
        this.fail("TEVS_JSON_SYNTAX", "invalid JSON number");
      }
      while (this.isDigit(this.text[this.index])) this.index += 1;
    }
    if ([".", "e", "E"].includes(this.text[this.index])) {
      this.fail("TEVS_JSON_FLOAT_FORBIDDEN", "floating-point JSON numbers are forbidden");
    }
    const token = this.text.slice(start, this.index);
    if (token === "-0") {
      this.fail("TEVS_JSON_NEGATIVE_ZERO", "negative zero is not a canonical structural integer");
    }
    const value = Number(token);
    if (!Number.isSafeInteger(value) || Math.abs(value) > MAX_STRUCTURAL_INTEGER) {
      this.fail("TEVS_JSON_NUMBER_RANGE", "JSON structural integer exceeds the portable safe range");
    }
    return value;
  }

  skipWhitespace() {
    while ([" ", "\t", "\n", "\r"].includes(this.text[this.index])) this.index += 1;
  }

  isDigit(character) {
    return character >= "0" && character <= "9";
  }

  isDigitOneToNine(character) {
    return character >= "1" && character <= "9";
  }

  fail(code, message) {
    throw new StrictJsonError(code, message, this.index);
  }
}

export function parseStrictJson(text, { maxDepth = DEFAULT_MAX_DEPTH } = {}) {
  if (typeof text !== "string") {
    throw new StrictJsonError("TEVS_JSON_INPUT_TYPE", "JSON input must be a string");
  }
  return new Parser(text, maxDepth).parse();
}

