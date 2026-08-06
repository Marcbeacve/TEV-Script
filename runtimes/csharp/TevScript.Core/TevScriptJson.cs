using System;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using System.Numerics;
using System.Security.Cryptography;
using System.Text;

namespace Marcbeacve.TevScript.Core
{
    internal static class TevJson
    {
        public const int DefaultMaximumDepth = 128;
        public const int DefaultMaximumCharacters = 4_000_000;

        private static readonly IComparer<string> CanonicalKeyComparer =
            new UnicodeScalarStringComparer();
        private static readonly BigInteger MaximumStructuralInteger =
            new BigInteger(9007199254740991L);

        public static object Parse(
            string text,
            int maximumCharacters = DefaultMaximumCharacters,
            int maximumDepth = DefaultMaximumDepth)
        {
            if (text == null) throw new ArgumentNullException(nameof(text));
            if (maximumCharacters < 0)
                throw new ArgumentOutOfRangeException(nameof(maximumCharacters));
            if (maximumDepth < 0)
                throw new ArgumentOutOfRangeException(nameof(maximumDepth));
            if (text.Length > maximumCharacters)
                throw new TevContractException(
                    "TEVS_JSON_BUDGET",
                    "JSON character budget exceeded.");

            var parser = new Parser(text, maximumDepth);
            object value = parser.ReadValue(0);
            parser.SkipWhitespace();
            if (!parser.End)
                throw parser.Error(
                    "TEVS_JSON_TRAILING",
                    "Unexpected trailing JSON content.");
            return value;
        }

        public static string Canonicalize(object value)
        {
            var builder = new StringBuilder();
            WriteCanonical(builder, value);
            return builder.ToString();
        }

        public static string Hash(object value)
        {
            return Sha256(Canonicalize(value));
        }

        public static string Sha256(string text)
        {
            if (text == null) throw new ArgumentNullException(nameof(text));
            byte[] bytes = Encoding.UTF8.GetBytes(text);
            using (SHA256 sha = SHA256.Create())
            {
                byte[] digest = sha.ComputeHash(bytes);
                var builder = new StringBuilder(64);
                for (int index = 0; index < digest.Length; index++)
                {
                    builder.Append(digest[index].ToString(
                        "x2", CultureInfo.InvariantCulture));
                }
                return builder.ToString();
            }
        }

        public static Dictionary<string, object> RequireObject(
            object value,
            string path)
        {
            var result = value as Dictionary<string, object>;
            if (result == null)
                throw new TevContractException(
                    "TEVS_JSON_OBJECT", "Expected an object.", path);
            return result;
        }

        public static Dictionary<string, object> RequireObject(
            IDictionary<string, object> value,
            string key)
        {
            return RequireObject(Select(value, key), key);
        }

        public static List<object> RequireArray(object value, string path)
        {
            var result = value as List<object>;
            if (result == null)
                throw new TevContractException(
                    "TEVS_JSON_ARRAY", "Expected an array.", path);
            return result;
        }

        public static List<object> RequireArray(
            IDictionary<string, object> value,
            string key)
        {
            return RequireArray(Select(value, key), key);
        }

        public static string RequireString(object value, string path)
        {
            string result = value as string;
            if (result == null)
                throw new TevContractException(
                    "TEVS_JSON_STRING", "Expected a string.", path);
            return result;
        }

        public static string RequireString(
            IDictionary<string, object> value,
            string key)
        {
            return RequireString(Select(value, key), key);
        }

        public static bool RequireBoolean(object value, string path)
        {
            if (!(value is bool))
                throw new TevContractException(
                    "TEVS_JSON_BOOL", "Expected a boolean.", path);
            return (bool)value;
        }

        public static BigInteger RequireInteger(object value, string path)
        {
            if (!(value is BigInteger))
                throw new TevContractException(
                    "TEVS_JSON_INTEGER", "Expected an integer.", path);
            return (BigInteger)value;
        }

        public static void RequireExactKeys(
            IDictionary<string, object> value,
            string path,
            params string[] keys)
        {
            if (value == null) throw new ArgumentNullException(nameof(value));
            if (keys == null) throw new ArgumentNullException(nameof(keys));
            if (value.Count != keys.Length)
                throw new TevContractException(
                    "TEVS_JSON_KEYS",
                    "Object field set does not match the contract.",
                    path);
            for (int index = 0; index < keys.Length; index++)
            {
                if (!value.ContainsKey(keys[index]))
                    throw new TevContractException(
                        "TEVS_JSON_KEYS",
                        "Missing required field '" + keys[index] + "'.",
                        path);
            }
        }

        private static object Select(
            IDictionary<string, object> value,
            string key)
        {
            object selected;
            if (value == null || !value.TryGetValue(key, out selected))
                throw new TevContractException(
                    "TEVS_JSON_KEYS",
                    "Missing required field '" + key + "'.",
                    key);
            return selected;
        }

        private static void WriteCanonical(StringBuilder builder, object value)
        {
            if (value == null) { builder.Append("null"); return; }
            if (value is bool)
            {
                builder.Append((bool)value ? "true" : "false");
                return;
            }
            if (value is string)
            {
                WriteString(builder, (string)value);
                return;
            }
            if (value is BigInteger)
            {
                BigInteger integer = (BigInteger)value;
                if (integer < -MaximumStructuralInteger ||
                    integer > MaximumStructuralInteger)
                {
                    throw new TevContractException(
                        "TEVS_JSON_NUMBER_RANGE",
                        "Structural integer exceeds the portable safe range.");
                }
                builder.Append(integer.ToString(CultureInfo.InvariantCulture));
                return;
            }
            if (value is sbyte || value is byte ||
                value is short || value is ushort ||
                value is int || value is uint ||
                value is long || value is ulong)
            {
                builder.Append(Convert.ToString(
                    value, CultureInfo.InvariantCulture));
                return;
            }
            if (value is TevRational)
            {
                TevRational rational = (TevRational)value;
                builder.Append("{\"$rat\":[\"");
                builder.Append(rational.Numerator.ToString(
                    CultureInfo.InvariantCulture));
                builder.Append("\",\"");
                builder.Append(rational.Denominator.ToString(
                    CultureInfo.InvariantCulture));
                builder.Append("\"]}");
                return;
            }
            if (value is TevScriptValue)
            {
                WriteCanonical(builder,
                    ((TevScriptValue)value).ToCanonicalObject());
                return;
            }

            var dictionary = value as IDictionary<string, object>;
            if (dictionary != null)
            {
                var keys = new List<string>(dictionary.Keys);
                keys.Sort(CanonicalKeyComparer);
                builder.Append('{');
                for (int index = 0; index < keys.Count; index++)
                {
                    if (index != 0) builder.Append(',');
                    WriteString(builder, keys[index]);
                    builder.Append(':');
                    WriteCanonical(builder, dictionary[keys[index]]);
                }
                builder.Append('}');
                return;
            }

            var enumerable = value as IEnumerable;
            if (enumerable != null)
            {
                builder.Append('[');
                bool first = true;
                foreach (object item in enumerable)
                {
                    if (!first) builder.Append(',');
                    first = false;
                    WriteCanonical(builder, item);
                }
                builder.Append(']');
                return;
            }

            throw new TevContractException(
                "TEVS_JSON_CANONICAL_TYPE",
                "Unsupported canonical value type: " +
                value.GetType().FullName + ".");
        }

        private static void WriteString(StringBuilder builder, string value)
        {
            builder.Append('"');
            for (int index = 0; index < value.Length; index++)
            {
                char character = value[index];
                switch (character)
                {
                    case '"': builder.Append("\\\""); break;
                    case '\\': builder.Append("\\\\"); break;
                    case '\b': builder.Append("\\b"); break;
                    case '\f': builder.Append("\\f"); break;
                    case '\n': builder.Append("\\n"); break;
                    case '\r': builder.Append("\\r"); break;
                    case '\t': builder.Append("\\t"); break;
                    default:
                        if (character < 0x20 || character > 0x7e)
                        {
                            builder.Append("\\u");
                            builder.Append(((int)character).ToString(
                                "x4", CultureInfo.InvariantCulture));
                        }
                        else builder.Append(character);
                        break;
                }
            }
            builder.Append('"');
        }

        private sealed class UnicodeScalarStringComparer : IComparer<string>
        {
            public int Compare(string left, string right)
            {
                if (ReferenceEquals(left, right)) return 0;
                if (left == null) return -1;
                if (right == null) return 1;
                int leftIndex = 0;
                int rightIndex = 0;
                while (leftIndex < left.Length && rightIndex < right.Length)
                {
                    int leftScalar = NextScalar(left, ref leftIndex);
                    int rightScalar = NextScalar(right, ref rightIndex);
                    if (leftScalar != rightScalar)
                        return leftScalar < rightScalar ? -1 : 1;
                }
                if (leftIndex == left.Length && rightIndex == right.Length)
                    return 0;
                return leftIndex == left.Length ? -1 : 1;
            }

            private static int NextScalar(string value, ref int index)
            {
                char first = value[index++];
                if (char.IsHighSurrogate(first) &&
                    index < value.Length &&
                    char.IsLowSurrogate(value[index]))
                {
                    char second = value[index++];
                    return char.ConvertToUtf32(first, second);
                }
                return first;
            }
        }

        private sealed class Parser
        {
            private readonly string _text;
            private readonly int _maximumDepth;
            private int _index;

            public Parser(string text, int maximumDepth)
            {
                _text = text;
                _maximumDepth = maximumDepth;
            }

            public bool End { get { return _index >= _text.Length; } }

            public object ReadValue(int depth)
            {
                if (depth > _maximumDepth)
                    throw Error("TEVS_JSON_DEPTH", "JSON depth budget exceeded.");
                SkipWhitespace();
                if (End)
                    throw Error("TEVS_JSON_EOF", "Unexpected end of JSON.");
                char current = _text[_index];
                if (current == '{') return ReadObject(depth + 1);
                if (current == '[') return ReadArray(depth + 1);
                if (current == '"') return ReadString();
                if (current == 't') { ReadLiteral("true"); return true; }
                if (current == 'f') { ReadLiteral("false"); return false; }
                if (current == 'n') { ReadLiteral("null"); return null; }
                if (current == '-' || (current >= '0' && current <= '9'))
                    return ReadInteger();
                throw Error("TEVS_JSON_VALUE", "Unexpected JSON value.");
            }

            public void SkipWhitespace()
            {
                while (!End)
                {
                    char current = _text[_index];
                    if (current != ' ' && current != '\t' &&
                        current != '\r' && current != '\n') return;
                    _index++;
                }
            }

            public TevContractException Error(string code, string message)
            {
                return new TevContractException(
                    code, message, "$[" + _index + "]");
            }

            private Dictionary<string, object> ReadObject(int depth)
            {
                _index++;
                var result = new Dictionary<string, object>(StringComparer.Ordinal);
                SkipWhitespace();
                if (Consume('}')) return result;
                while (true)
                {
                    SkipWhitespace();
                    if (End || _text[_index] != '"')
                        throw Error("TEVS_JSON_OBJECT_KEY", "Expected object key.");
                    string key = ReadString();
                    if (result.ContainsKey(key))
                        throw Error("TEVS_JSON_DUPLICATE_KEY",
                            "Duplicate JSON key '" + key + "'.");
                    SkipWhitespace();
                    Require(':');
                    result.Add(key, ReadValue(depth));
                    SkipWhitespace();
                    if (Consume('}')) return result;
                    Require(',');
                }
            }

            private List<object> ReadArray(int depth)
            {
                _index++;
                var result = new List<object>();
                SkipWhitespace();
                if (Consume(']')) return result;
                while (true)
                {
                    result.Add(ReadValue(depth));
                    SkipWhitespace();
                    if (Consume(']')) return result;
                    Require(',');
                }
            }

            private string ReadString()
            {
                Require('"');
                var builder = new StringBuilder();
                while (!End)
                {
                    char current = _text[_index++];
                    if (current == '"') return builder.ToString();
                    if (current < 0x20)
                        throw Error("TEVS_JSON_STRING_CONTROL",
                            "Unescaped control character in string.");
                    if (current != '\\')
                    {
                        builder.Append(current);
                        continue;
                    }
                    if (End)
                        throw Error("TEVS_JSON_STRING_ESCAPE",
                            "Incomplete string escape.");
                    char escaped = _text[_index++];
                    switch (escaped)
                    {
                        case '"': builder.Append('"'); break;
                        case '\\': builder.Append('\\'); break;
                        case '/': builder.Append('/'); break;
                        case 'b': builder.Append('\b'); break;
                        case 'f': builder.Append('\f'); break;
                        case 'n': builder.Append('\n'); break;
                        case 'r': builder.Append('\r'); break;
                        case 't': builder.Append('\t'); break;
                        case 'u': builder.Append(ReadUnicodeEscape()); break;
                        default:
                            throw Error("TEVS_JSON_STRING_ESCAPE",
                                "Unsupported string escape.");
                    }
                }
                throw Error("TEVS_JSON_STRING_UNTERMINATED",
                    "Unterminated JSON string.");
            }

            private char ReadUnicodeEscape()
            {
                if (_index + 4 > _text.Length)
                    throw Error("TEVS_JSON_UNICODE_ESCAPE",
                        "Incomplete Unicode escape.");
                int value = 0;
                for (int offset = 0; offset < 4; offset++)
                {
                    int digit = Hex(_text[_index++]);
                    if (digit < 0)
                        throw Error("TEVS_JSON_UNICODE_ESCAPE",
                            "Invalid Unicode escape.");
                    value = (value << 4) | digit;
                }
                return (char)value;
            }

            private BigInteger ReadInteger()
            {
                int start = _index;
                if (_text[_index] == '-') _index++;
                if (End) throw Error("TEVS_JSON_INTEGER", "Incomplete integer.");
                if (_text[_index] == '0')
                {
                    _index++;
                    if (!End && IsAsciiDigit(_text[_index]))
                        throw Error("TEVS_JSON_INTEGER", "Leading zero is forbidden.");
                }
                else
                {
                    if (_text[_index] < '1' || _text[_index] > '9')
                        throw Error("TEVS_JSON_INTEGER", "Invalid integer.");
                    while (!End && IsAsciiDigit(_text[_index])) _index++;
                }
                if (!End && (_text[_index] == '.' ||
                    _text[_index] == 'e' || _text[_index] == 'E'))
                    throw Error("TEVS_JSON_FLOAT", "Floating JSON numbers are forbidden.");
                string token = _text.Substring(start, _index - start);
                BigInteger value;
                if (token == "-0")
                    throw Error("TEVS_JSON_NEGATIVE_ZERO", "Negative zero is forbidden.");
                if (!BigInteger.TryParse(
                        token,
                        NumberStyles.AllowLeadingSign,
                        CultureInfo.InvariantCulture,
                        out value))
                    throw Error("TEVS_JSON_INTEGER", "Invalid integer.");
                if (value < -MaximumStructuralInteger ||
                    value > MaximumStructuralInteger)
                    throw Error(
                        "TEVS_JSON_NUMBER_RANGE",
                        "Structural integer exceeds the portable safe range.");
                return value;
            }

            private void ReadLiteral(string literal)
            {
                if (_index + literal.Length > _text.Length ||
                    string.CompareOrdinal(_text, _index, literal, 0, literal.Length) != 0)
                    throw Error("TEVS_JSON_LITERAL", "Invalid JSON literal.");
                _index += literal.Length;
            }

            private bool Consume(char expected)
            {
                if (!End && _text[_index] == expected)
                {
                    _index++;
                    return true;
                }
                return false;
            }

            private void Require(char expected)
            {
                if (!Consume(expected))
                    throw Error("TEVS_JSON_TOKEN",
                        "Expected '" + expected + "'.");
            }

            private static bool IsAsciiDigit(char value)
            {
                return value >= '0' && value <= '9';
            }

            private static int Hex(char value)
            {
                if (value >= '0' && value <= '9') return value - '0';
                if (value >= 'a' && value <= 'f') return value - 'a' + 10;
                if (value >= 'A' && value <= 'F') return value - 'A' + 10;
                return -1;
            }
        }
    }
}
