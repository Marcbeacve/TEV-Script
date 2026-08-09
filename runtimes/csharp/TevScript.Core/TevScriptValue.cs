using System;
using System.Collections.Generic;
using System.Linq;
using System.Numerics;

namespace Marcbeacve.TevScript.Core
{
    public sealed class TevScriptValue : IEquatable<TevScriptValue>
    {
        private TevScriptValue(string typeName, object value)
        {
            TypeName = typeName ?? throw new ArgumentNullException(nameof(typeName));
            Value = value;
        }

        public string TypeName { get; }
        public object Value { get; }

        public static TevScriptValue Bool(bool value)
        {
            return new TevScriptValue("Bool", value);
        }

        public static TevScriptValue Int(BigInteger value)
        {
            return new TevScriptValue("Int", value);
        }

        public static TevScriptValue Rat(TevRational value)
        {
            return new TevScriptValue("Rat", value);
        }

        public static TevScriptValue Text(string value)
        {
            return new TevScriptValue(
                "Text",
                value ?? throw new ArgumentNullException(nameof(value)));
        }

        public static TevScriptValue Vec2(
            TevRational x,
            TevRational y)
        {
            return new TevScriptValue(
                "Vec2",
                Array.AsReadOnly(new[] { x, y }));
        }

        public static TevScriptValue Vec3(
            TevRational x,
            TevRational y,
            TevRational z)
        {
            return new TevScriptValue(
                "Vec3",
                Array.AsReadOnly(new[] { x, y, z }));
        }

        public static TevScriptValue Unit()
        {
            return new TevScriptValue("Unit", null);
        }

        public bool AsBool()
        {
            RequireType("Bool");
            return (bool)Value;
        }

        public BigInteger AsInt()
        {
            RequireType("Int");
            return (BigInteger)Value;
        }

        public TevRational AsRat()
        {
            RequireType("Rat");
            return (TevRational)Value;
        }

        public string AsText()
        {
            RequireType("Text");
            return (string)Value;
        }

        public IReadOnlyList<TevRational> AsVector()
        {
            if (TypeName != "Vec2" && TypeName != "Vec3")
            {
                throw new TevContractException(
                    "TEVS_CS_VALUE_TYPE",
                    "Expected Vec2 or Vec3, got " + TypeName + ".");
            }
            return (IReadOnlyList<TevRational>)Value;
        }

        public object ToCanonicalObject()
        {
            switch (TypeName)
            {
                case "Bool":
                    return AsBool();
                case "Int":
                    return new Dictionary<string, object>(StringComparer.Ordinal)
                    {
                        ["$int"] = AsInt().ToString()
                    };
                case "Rat":
                    TevRational rational = AsRat();
                    return new Dictionary<string, object>(StringComparer.Ordinal)
                    {
                        ["$rat"] = new object[]
                        {
                            rational.Numerator.ToString(),
                            rational.Denominator.ToString()
                        }
                    };
                case "Text":
                    return AsText();
                case "Vec2":
                case "Vec3":
                    return AsVector()
                        .Select(item => Rat(item).ToCanonicalObject())
                        .ToArray();
                case "Unit":
                    return null;
                default:
                    throw new TevContractException(
                        "TEVS_CS_VALUE_TYPE",
                        "Unknown value type " + TypeName + ".");
            }
        }

        public static TevScriptValue Decode(string typeName, object raw)
        {
            switch (typeName)
            {
                case "Bool":
                    return Bool(TevJson.RequireBoolean(raw, "$value"));
                case "Int":
                    return Int(ParseTaggedInteger(raw));
                case "Rat":
                    return Rat(ParseTaggedRational(raw));
                case "Text":
                    return Text(TevJson.RequireString(raw, "$value"));
                case "Vec2":
                    return DecodeVector(raw, 2, "Vec2");
                case "Vec3":
                    return DecodeVector(raw, 3, "Vec3");
                case "Unit":
                    if (raw != null)
                    {
                        throw new TevContractException(
                            "TEVS_CS_VALUE_UNIT",
                            "Unit must be null.");
                    }
                    return Unit();
                default:
                    throw new TevContractException(
                        "TEVS_CS_VALUE_TYPE",
                        "Unknown value type " + typeName + ".");
            }
        }

        private static TevScriptValue DecodeVector(
            object raw,
            int expected,
            string typeName)
        {
            List<object> values = TevJson.RequireArray(raw, "$value");
            if (values.Count != expected)
            {
                throw new TevContractException(
                    "TEVS_CS_VALUE_VECTOR",
                    typeName + " requires " + expected + " elements.");
            }
            TevRational[] items = values
                .Select(ParseTaggedRational)
                .ToArray();
            return expected == 2
                ? Vec2(items[0], items[1])
                : Vec3(items[0], items[1], items[2]);
        }

        private static BigInteger ParseTaggedInteger(object raw)
        {
            Dictionary<string, object> tagged =
                TevJson.RequireObject(raw, "$int");
            TevJson.RequireExactKeys(tagged, "$int", "$int");
            string text = TevJson.RequireString(tagged, "$int");
            BigInteger value;
            if (!BigInteger.TryParse(text, out value) ||
                value.ToString() != text)
            {
                throw new TevContractException(
                    "TEVS_CS_VALUE_INT",
                    "Integer text must be canonical.");
            }
            return value;
        }

        private static TevRational ParseTaggedRational(object raw)
        {
            Dictionary<string, object> tagged =
                TevJson.RequireObject(raw, "$rat");
            TevJson.RequireExactKeys(tagged, "$rat", "$rat");
            List<object> pair = TevJson.RequireArray(tagged, "$rat");
            if (pair.Count != 2)
            {
                throw new TevContractException(
                    "TEVS_CS_VALUE_RAT",
                    "Rational requires numerator and denominator.");
            }
            string numeratorText = TevJson.RequireString(pair[0], "$rat[0]");
            string denominatorText = TevJson.RequireString(pair[1], "$rat[1]");
            BigInteger numerator;
            BigInteger denominator;
            if (!BigInteger.TryParse(numeratorText, out numerator) ||
                !BigInteger.TryParse(denominatorText, out denominator))
            {
                throw new TevContractException(
                    "TEVS_CS_VALUE_RAT",
                    "Rational text is invalid.");
            }
            TevRational value = new TevRational(numerator, denominator);
            if (value.Numerator.ToString() != numeratorText ||
                value.Denominator.ToString() != denominatorText)
            {
                throw new TevContractException(
                    "TEVS_CS_VALUE_RAT",
                    "Rational must be normalized.");
            }
            return value;
        }

        public bool Equals(TevScriptValue other)
        {
            if (ReferenceEquals(other, null) || TypeName != other.TypeName)
            {
                return false;
            }
            if (TypeName == "Vec2" || TypeName == "Vec3")
            {
                return AsVector().SequenceEqual(other.AsVector());
            }
            return Equals(Value, other.Value);
        }

        public override bool Equals(object obj)
        {
            return Equals(obj as TevScriptValue);
        }

        public override int GetHashCode()
        {
            unchecked
            {
                int hash = TypeName.GetHashCode();
                if (TypeName == "Vec2" || TypeName == "Vec3")
                {
                    foreach (TevRational item in AsVector())
                    {
                        hash = (hash * 397) ^ item.GetHashCode();
                    }
                    return hash;
                }
                return (hash * 397) ^ (Value == null ? 0 : Value.GetHashCode());
            }
        }

        private void RequireType(string expected)
        {
            if (TypeName != expected)
            {
                throw new TevContractException(
                    "TEVS_CS_VALUE_TYPE",
                    "Expected " + expected + ", got " + TypeName + ".");
            }
        }
    }
}
