# TEV Script V1 lexical profile

Status: **normative V1 candidate**.

This profile extends the certified V0.2 lexical contract in `spec/SOURCE_LEXICAL_GRAMMAR_V1.md` without changing that historical V0.2 authority.

## 1. Source decoding

- Source bytes are UTF-8.
- One leading UTF-8 BOM is accepted and discarded.
- NUL bytes are forbidden.
- Invalid UTF-8 fails closed before parsing.
- Source byte limits are defined by `spec/TEV_SCRIPT_V1_BUDGETS.md`.

## 2. Identifiers

Identifiers are exactly:

```text
[A-Za-z_][A-Za-z0-9_]*
```

Identifiers are ASCII, case-sensitive and are never Unicode-normalized, case-folded, transliterated or locale-dependent.

A non-ASCII alphabetic/digit character encountered where a token may begin is a lexical error rather than an identifier character.

Qualified semantic names are sequences of identifiers separated by `.`. Empty segments are invalid by grammar.

## 3. Numeric tokens

Integer source tokens use ASCII decimal digits only.

Decimal source tokens use exactly:

```text
DIGIT+ '.' DIGIT+
```

There is no exponent notation, hexadecimal, binary, octal, digit separator, NaN or infinity syntax.

Decimals are source notation for exact rational values and never imply IEEE-754 conversion.

### 3.1 Decimal/range disambiguation

Lexing is deterministic:

- `1.0` is one `DECIMAL` token;
- `1..4` is `INT(1) RANGE(..) INT(4)`;
- `1...4` is `INT(1) RANGE(..) DOT(.) INT(4)` and is rejected by the parser where a range is expected.

A `.` begins the fractional part of a decimal only when it is immediately followed by an ASCII digit.

## 4. Strings

Strings are delimited by `"` and cannot cross a physical CR or LF.

Supported escapes are exactly:

```text
\n
\r
\t
\"
\\
```

No other escape is accepted. Unicode scalar values other than NUL/newline are preserved literally inside string contents; there is no `\uXXXX` escape in V1.0.

## 5. Comments and whitespace

Outside strings, `#` begins a line comment that ends immediately before the next LF or at EOF.

Whitespace characters recognized by the portable lexer are space, horizontal tab, carriage return and line feed. They separate tokens and otherwise carry no semantics.

## 6. Reserved words

V1 reserves the following exact case-sensitive words:

```text
script module version import export
capability observation effect
record enum fn behavior entity use
state on let if else call emit log move animate
match for in return
true false and or not
Option Result Some None Ok Err
```

The first groups are lowercase. The built-in sum-type families and constructors are reserved with the exact capitalization shown above.

`option`, `result`, `some`, `none`, `ok`, and `err` are ordinary identifiers unless another rule forbids them. Conversely, `Option`, `Result`, `Some`, `None`, `Ok`, and `Err` cannot be user identifiers.

Primitive type names `Bool`, `Int`, `Rat`, `Text`, `Vec2`, `Vec3`, and `Unit` are parsed as identifiers and resolved as predeclared type names by static semantics rather than as lexer keywords.

## 7. Operators and delimiters

The lexer recognizes these two-character tokens before any one-character prefix:

```text
->  =>  ..  ::  ==  !=  <=  >=
```

It then recognizes these one-character tokens:

```text
{ } ( ) : ; , . = + - * / < >
```

This longest-token rule is normative. No host regular-expression engine priority or locale behavior may change tokenization.

## 8. Compatibility rule

The V1 lexer is a superset at the token-classification level, but a V1-capable version dispatcher must route a `script ... version "0.2.0";` source through the certified V0.2 parser/compiler semantics.

New V1 reserved-word classification must not silently reinterpret an already valid V0.2 program. The dispatcher may inspect the source header with the V1 lexer only when subsequent V0.2 parsing is performed again through the certified V0.2 lexer/parser path.

## 9. Determinism counterfactuals

A conforming V1 lexer must produce the same token kinds/text/spans for identical decoded source regardless of locale, timezone, filesystem path separator or host Unicode normalization defaults.

Changing only the debug path may change `SourceSpan.path`; it must not change token kinds or token text.
