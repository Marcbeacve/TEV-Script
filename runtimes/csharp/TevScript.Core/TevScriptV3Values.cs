using System.Collections.ObjectModel;
using System.Globalization;
using System.Numerics;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;

namespace TevScript.Core.V3;

public sealed class TevScriptV3Exception : InvalidOperationException
{
    public TevScriptV3Exception(string code, string message)
        : base($"{code}: {message}")
    {
        Code = code;
    }

    public TevScriptV3Exception(string code, string message, Exception innerException)
        : base($"{code}: {message}", innerException)
    {
        Code = code;
    }

    public string Code { get; }
}

public readonly struct TevRationalV3 : IEquatable<TevRationalV3>, IComparable<TevRationalV3>
{
    public TevRationalV3(BigInteger numerator, BigInteger denominator)
    {
        if (denominator.IsZero)
            throw new DivideByZeroException("rational denominator cannot be zero");
        if (denominator.Sign < 0)
        {
            numerator = BigInteger.Negate(numerator);
            denominator = BigInteger.Negate(denominator);
        }
        var gcd = BigInteger.GreatestCommonDivisor(BigInteger.Abs(numerator), denominator);
        Numerator = numerator / gcd;
        Denominator = denominator / gcd;
    }

    public BigInteger Numerator { get; }
    public BigInteger Denominator { get; }

    public static TevRationalV3 FromInteger(BigInteger value) => new(value, BigInteger.One);
    public TevRationalV3 Negate() => new(BigInteger.Negate(Numerator), Denominator);
    public TevRationalV3 Add(TevRationalV3 other) => new(Numerator * other.Denominator + other.Numerator * Denominator, Denominator * other.Denominator);
    public TevRationalV3 Subtract(TevRationalV3 other) => new(Numerator * other.Denominator - other.Numerator * Denominator, Denominator * other.Denominator);
    public TevRationalV3 Multiply(TevRationalV3 other) => new(Numerator * other.Numerator, Denominator * other.Denominator);
    public TevRationalV3 Divide(TevRationalV3 other)
    {
        if (other.Numerator.IsZero) throw new DivideByZeroException("division by zero");
        return new TevRationalV3(Numerator * other.Denominator, Denominator * other.Numerator);
    }

    public int CompareTo(TevRationalV3 other) => (Numerator * other.Denominator).CompareTo(other.Numerator * Denominator);
    public bool Equals(TevRationalV3 other) => Numerator == other.Numerator && Denominator == other.Denominator;
    public override bool Equals(object? obj) => obj is TevRationalV3 value && Equals(value);
    public override int GetHashCode() => HashCode.Combine(Numerator, Denominator);
    public override string ToString() => $"{Numerator.ToString(CultureInfo.InvariantCulture)}/{Denominator.ToString(CultureInfo.InvariantCulture)}";
}

public abstract record TevScriptValueV3(string TypeId);
public sealed record TevBoolV3(bool Value) : TevScriptValueV3("Bool");
public sealed record TevIntV3(BigInteger Value) : TevScriptValueV3("Int");
public sealed record TevRatV3(TevRationalV3 Value) : TevScriptValueV3("Rat");
public sealed record TevTextV3(string Value) : TevScriptValueV3("Text");
public sealed record TevVectorV3 : TevScriptValueV3
{
    public TevVectorV3(string typeId, IReadOnlyList<TevRationalV3> components)
        : base(typeId)
    {
        if (typeId != "Vec2" && typeId != "Vec3") throw new ArgumentException("expected Vec2 or Vec3", nameof(typeId));
        var expected = typeId == "Vec2" ? 2 : 3;
        if (components.Count != expected) throw new ArgumentException($"{typeId} requires {expected} components", nameof(components));
        Components = new ReadOnlyCollection<TevRationalV3>(components.ToArray());
    }
    public IReadOnlyList<TevRationalV3> Components { get; }
}
public sealed record TevRecordV3 : TevScriptValueV3
{
    public TevRecordV3(string typeId, IReadOnlyList<KeyValuePair<string, TevScriptValueV3>> fields)
        : base(typeId)
    {
        Fields = new ReadOnlyCollection<KeyValuePair<string, TevScriptValueV3>>(fields.ToArray());
    }
    public IReadOnlyList<KeyValuePair<string, TevScriptValueV3>> Fields { get; }
    public TevScriptValueV3 Field(string name)
    {
        foreach (var pair in Fields)
            if (StringComparer.Ordinal.Equals(pair.Key, name)) return pair.Value;
        throw new KeyNotFoundException(name);
    }
}
public sealed record TevVariantV3 : TevScriptValueV3
{
    private TevVariantV3(string typeId, string variant, TevScriptValueV3? payload, bool hasPayload)
        : base(typeId)
    {
        Variant = variant;
        Payload = payload;
        HasPayload = hasPayload;
    }
    public string Variant { get; }
    public TevScriptValueV3? Payload { get; }
    public bool HasPayload { get; }
    public static TevVariantV3 Empty(string typeId, string variant) => new(typeId, variant, null, false);
    public static TevVariantV3 WithPayload(string typeId, string variant, TevScriptValueV3 payload) =>
        new(typeId, variant, payload ?? throw new ArgumentNullException(nameof(payload)), true);
}

public sealed record TevScriptTypeDescriptorV3(
    string TypeId,
    string Kind,
    IReadOnlyList<(string Name, string TypeId)> Fields,
    IReadOnlyList<string> Variants,
    string? Argument,
    string? OkType,
    string? ErrType)
{
    public string? FieldType(string name)
    {
        foreach (var field in Fields)
            if (StringComparer.Ordinal.Equals(field.Name, name)) return field.TypeId;
        return null;
    }
}

public sealed class TevScriptTypeTableV3
{
    private readonly IReadOnlyDictionary<string, TevScriptTypeDescriptorV3> _byId;

    internal TevScriptTypeTableV3(
        IReadOnlyList<TevScriptTypeDescriptorV3> descriptors,
        int maximumValueNesting)
    {
        Descriptors = descriptors;
        MaximumValueNesting = maximumValueNesting;
        _byId = descriptors.ToDictionary(item => item.TypeId, item => item, StringComparer.Ordinal);
    }

    public IReadOnlyList<TevScriptTypeDescriptorV3> Descriptors { get; }
    public int MaximumValueNesting { get; }
    public TevScriptTypeDescriptorV3 Require(string typeId, string context = "type") =>
        _byId.TryGetValue(typeId, out var descriptor)
            ? descriptor
            : throw new TevScriptV3Exception("TEVS_IR_V3_TYPE_UNKNOWN", $"{context} references unknown V3 type {typeId}");
    public bool IsStorable(string typeId) => _byId.TryGetValue(typeId, out var descriptor) && descriptor.Kind != "unit";

    public string? VariantPayloadType(string typeId, string variant)
    {
        var descriptor = Require(typeId);
        return descriptor.Kind switch
        {
            "enum" when descriptor.Variants.Contains(variant, StringComparer.Ordinal) => null,
            "option" when variant == "None" => null,
            "option" when variant == "Some" => descriptor.Argument,
            "result" when variant == "Ok" => descriptor.OkType,
            "result" when variant == "Err" => descriptor.ErrType,
            _ => throw new TevScriptV3Exception(
                "TEVS_IR_V3_VARIANT_UNKNOWN",
                $"type {typeId} does not define variant {variant}"),
        };
    }
}

public static class TevScriptValueCodecV3
{
    private static readonly Regex CanonicalInteger = new("^-?(0|[1-9][0-9]*)$", RegexOptions.CultureInvariant | RegexOptions.NonBacktracking);

    public static TevScriptValueV3 Decode(
        string typeId,
        JsonElement raw,
        TevScriptTypeTableV3 table,
        string context = "value",
        int depth = 1)
    {
        if (depth > table.MaximumValueNesting)
            throw new TevScriptV3Exception("TEVS_IR_V3_VALUE_NESTING", $"{context}: value nesting exceeds {table.MaximumValueNesting}");
        var descriptor = table.Require(typeId, context);
        if (descriptor.Kind == "unit")
            throw new TevScriptV3Exception("TEVS_IR_V3_UNIT_VALUE", $"{context}: Unit is not a runtime value");
        if (descriptor.Kind == "primitive") return DecodePrimitive(typeId, raw, context);
        if (descriptor.Kind == "record") return DecodeRecord(typeId, raw, table, descriptor, context, depth);
        if (descriptor.Kind == "enum") return DecodeEnum(typeId, raw, descriptor, context);
        if (descriptor.Kind == "option") return DecodeOption(typeId, raw, table, descriptor, context, depth);
        if (descriptor.Kind == "result") return DecodeResult(typeId, raw, table, descriptor, context, depth);
        throw new TevScriptV3Exception("TEVS_IR_V3_VALUE_INVALID", $"{context}: unsupported descriptor kind {descriptor.Kind}");
    }

    public static JsonElement EncodeElement(
        string typeId,
        TevScriptValueV3 value,
        TevScriptTypeTableV3 table,
        string context = "value") =>
        TevScriptStrictJsonV3.ParseElement(EncodeCanonical(typeId, value, table, context));

    public static string EncodeCanonical(
        string typeId,
        TevScriptValueV3 value,
        TevScriptTypeTableV3 table,
        string context = "value",
        int depth = 1)
    {
        if (depth > table.MaximumValueNesting)
            throw new TevScriptV3Exception("TEVS_IR_V3_VALUE_NESTING", $"{context}: value nesting exceeds {table.MaximumValueNesting}");
        var descriptor = table.Require(typeId, context);
        using var stream = new MemoryStream();
        using (var writer = new Utf8JsonWriter(stream, new JsonWriterOptions { Indented = false, SkipValidation = false }))
            WriteValue(writer, typeId, value, table, descriptor, context, depth);
        return Encoding.UTF8.GetString(stream.ToArray());
    }

    public static bool ValuesEqual(
        string typeId,
        TevScriptValueV3 left,
        TevScriptValueV3 right,
        TevScriptTypeTableV3 table)
    {
        var descriptor = table.Require(typeId);
        if (descriptor.Kind == "primitive") return PrimitiveEqual(left, right);
        if (descriptor.Kind == "record")
        {
            if (left is not TevRecordV3 a || right is not TevRecordV3 b || a.TypeId != typeId || b.TypeId != typeId)
                return false;
            return descriptor.Fields.All(field => ValuesEqual(
                field.TypeId,
                a.Field(field.Name),
                b.Field(field.Name),
                table));
        }
        if (descriptor.Kind is "enum" or "option" or "result")
        {
            if (left is not TevVariantV3 a || right is not TevVariantV3 b
                || a.TypeId != typeId || b.TypeId != typeId
                || a.Variant != b.Variant || a.HasPayload != b.HasPayload)
                return false;
            if (!a.HasPayload) return true;
            var payloadType = table.VariantPayloadType(typeId, a.Variant)
                ?? throw new TevScriptV3Exception("TEVS_IR_V3_VALUE_INVALID", "payload type missing");
            return a.Payload is not null && b.Payload is not null
                && ValuesEqual(payloadType, a.Payload, b.Payload, table);
        }
        return false;
    }

    private static TevScriptValueV3 DecodePrimitive(string typeId, JsonElement raw, string context)
    {
        try
        {
            return typeId switch
            {
                "Bool" => raw.ValueKind == JsonValueKind.True || raw.ValueKind == JsonValueKind.False
                    ? new TevBoolV3(raw.GetBoolean())
                    : throw Invalid(context, "expected Bool"),
                "Text" => raw.ValueKind == JsonValueKind.String
                    ? new TevTextV3(raw.GetString()!)
                    : throw Invalid(context, "expected Text"),
                "Int" => new TevIntV3(DecodeIntegerWrapper(raw, context)),
                "Rat" => new TevRatV3(DecodeRatWrapper(raw, context)),
                "Vec2" => new TevVectorV3("Vec2", DecodeVector(raw, 2, context)),
                "Vec3" => new TevVectorV3("Vec3", DecodeVector(raw, 3, context)),
                _ => throw Invalid(context, $"unknown primitive {typeId}"),
            };
        }
        catch (TevScriptV3Exception)
        {
            throw;
        }
        catch (Exception error)
        {
            throw new TevScriptV3Exception("TEVS_IR_V3_VALUE_INVALID", $"{context}: invalid {typeId}: {error.GetType().Name}");
        }
    }

    private static BigInteger DecodeIntegerWrapper(JsonElement raw, string context)
    {
        RequireObject(raw, context, "$int");
        return ParseCanonicalInteger(raw.GetProperty("$int"), context + ".$int");
    }

    private static TevRationalV3 DecodeRatWrapper(JsonElement raw, string context)
    {
        RequireObject(raw, context, "$rat");
        var array = raw.GetProperty("$rat");
        if (array.ValueKind != JsonValueKind.Array || array.GetArrayLength() != 2)
            throw Invalid(context, "invalid $rat shape");
        var numerator = ParseCanonicalInteger(array[0], context + ".$rat[0]");
        var denominator = ParseCanonicalInteger(array[1], context + ".$rat[1]");
        if (denominator <= BigInteger.Zero) throw Invalid(context, "rational denominator must be positive");
        var result = new TevRationalV3(numerator, denominator);
        if (result.Numerator != numerator || result.Denominator != denominator)
            throw Invalid(context, "rational must be normalized");
        return result;
    }

    private static IReadOnlyList<TevRationalV3> DecodeVector(JsonElement raw, int expected, string context)
    {
        if (raw.ValueKind != JsonValueKind.Array || raw.GetArrayLength() != expected)
            throw Invalid(context, $"expected vector length {expected}");
        return raw.EnumerateArray().Select((item, index) => DecodeRatWrapper(item, $"{context}[{index}]")).ToArray();
    }

    private static TevRecordV3 DecodeRecord(
        string typeId,
        JsonElement raw,
        TevScriptTypeTableV3 table,
        TevScriptTypeDescriptorV3 descriptor,
        string context,
        int depth)
    {
        RequireObject(raw, context, "$record");
        var payload = raw.GetProperty("$record");
        RequireExactKeys(payload, context + ".$record", "type", "fields");
        if (payload.GetProperty("type").GetString() != typeId) throw Invalid(context, "record encoded type mismatch");
        var fields = payload.GetProperty("fields");
        if (fields.ValueKind != JsonValueKind.Array || fields.GetArrayLength() != descriptor.Fields.Count)
            throw Invalid(context, "record field count mismatch");
        var decoded = new List<KeyValuePair<string, TevScriptValueV3>>();
        for (var index = 0; index < descriptor.Fields.Count; ++index)
        {
            var rawField = fields[index];
            RequireExactKeys(rawField, $"{context}.$record.fields[{index}]", "name", "value");
            var expected = descriptor.Fields[index];
            if (rawField.GetProperty("name").GetString() != expected.Name)
                throw Invalid(context, $"record field order mismatch at {index}");
            decoded.Add(new KeyValuePair<string, TevScriptValueV3>(
                expected.Name,
                Decode(expected.TypeId, rawField.GetProperty("value"), table, $"{context}.{expected.Name}", depth + 1)));
        }
        return new TevRecordV3(typeId, decoded);
    }

    private static TevVariantV3 DecodeEnum(
        string typeId,
        JsonElement raw,
        TevScriptTypeDescriptorV3 descriptor,
        string context)
    {
        RequireObject(raw, context, "$enum");
        var payload = raw.GetProperty("$enum");
        RequireExactKeys(payload, context + ".$enum", "type", "variant");
        if (payload.GetProperty("type").GetString() != typeId) throw Invalid(context, "enum encoded type mismatch");
        var variant = payload.GetProperty("variant").GetString()!;
        if (!descriptor.Variants.Contains(variant, StringComparer.Ordinal)) throw Invalid(context, $"unknown enum variant {variant}");
        return TevVariantV3.Empty(typeId, variant);
    }

    private static TevVariantV3 DecodeOption(
        string typeId,
        JsonElement raw,
        TevScriptTypeTableV3 table,
        TevScriptTypeDescriptorV3 descriptor,
        string context,
        int depth)
    {
        RequireObject(raw, context, "$option");
        var payload = raw.GetProperty("$option");
        if (!payload.TryGetProperty("type", out var encodedType) || encodedType.GetString() != typeId)
            throw Invalid(context, "Option encoded type mismatch");
        var variant = payload.TryGetProperty("variant", out var rawVariant) ? rawVariant.GetString() : null;
        if (variant == "None")
        {
            RequireExactKeys(payload, context + ".$option", "type", "variant");
            return TevVariantV3.Empty(typeId, "None");
        }
        if (variant == "Some")
        {
            RequireExactKeys(payload, context + ".$option", "type", "variant", "value");
            return TevVariantV3.WithPayload(
                typeId,
                "Some",
                Decode(descriptor.Argument!, payload.GetProperty("value"), table, context + ".$option.value", depth + 1));
        }
        throw Invalid(context, $"unknown Option variant {variant}");
    }

    private static TevVariantV3 DecodeResult(
        string typeId,
        JsonElement raw,
        TevScriptTypeTableV3 table,
        TevScriptTypeDescriptorV3 descriptor,
        string context,
        int depth)
    {
        RequireObject(raw, context, "$result");
        var payload = raw.GetProperty("$result");
        if (!payload.TryGetProperty("type", out var encodedType) || encodedType.GetString() != typeId)
            throw Invalid(context, "Result encoded type mismatch");
        var variant = payload.TryGetProperty("variant", out var rawVariant) ? rawVariant.GetString() : null;
        var payloadType = variant == "Ok" ? descriptor.OkType : variant == "Err" ? descriptor.ErrType : null;
        if (payloadType is null) throw Invalid(context, $"unknown Result variant {variant}");
        RequireExactKeys(payload, context + ".$result", "type", "variant", "value");
        return TevVariantV3.WithPayload(
            typeId,
            variant!,
            Decode(payloadType, payload.GetProperty("value"), table, context + ".$result.value", depth + 1));
    }

    private static void WriteValue(
        Utf8JsonWriter writer,
        string typeId,
        TevScriptValueV3 value,
        TevScriptTypeTableV3 table,
        TevScriptTypeDescriptorV3 descriptor,
        string context,
        int depth)
    {
        if (value.TypeId != typeId) throw Invalid(context, $"value type {value.TypeId} does not match {typeId}");
        switch (descriptor.Kind)
        {
            case "primitive":
                WritePrimitive(writer, typeId, value, context);
                return;
            case "record":
                if (value is not TevRecordV3 record) throw Invalid(context, "expected record value");
                writer.WriteStartObject();
                writer.WritePropertyName("$record");
                writer.WriteStartObject();
                writer.WriteString("type", typeId);
                writer.WritePropertyName("fields");
                writer.WriteStartArray();
                foreach (var field in descriptor.Fields)
                {
                    writer.WriteStartObject();
                    writer.WriteString("name", field.Name);
                    writer.WritePropertyName("value");
                    WriteValue(writer, field.TypeId, record.Field(field.Name), table, table.Require(field.TypeId), $"{context}.{field.Name}", depth + 1);
                    writer.WriteEndObject();
                }
                writer.WriteEndArray();
                writer.WriteEndObject();
                writer.WriteEndObject();
                return;
            case "enum":
            case "option":
            case "result":
                if (value is not TevVariantV3 variant) throw Invalid(context, "expected variant value");
                var key = descriptor.Kind == "enum" ? "$enum" : descriptor.Kind == "option" ? "$option" : "$result";
                var payloadType = table.VariantPayloadType(typeId, variant.Variant);
                writer.WriteStartObject();
                writer.WritePropertyName(key);
                writer.WriteStartObject();
                writer.WriteString("type", typeId);
                writer.WriteString("variant", variant.Variant);
                if (payloadType is not null)
                {
                    if (!variant.HasPayload || variant.Payload is null) throw Invalid(context, "variant requires payload");
                    writer.WritePropertyName("value");
                    WriteValue(writer, payloadType, variant.Payload, table, table.Require(payloadType), context + ".value", depth + 1);
                }
                else if (variant.HasPayload) throw Invalid(context, "variant must not carry payload");
                writer.WriteEndObject();
                writer.WriteEndObject();
                return;
            default:
                throw Invalid(context, $"cannot encode descriptor kind {descriptor.Kind}");
        }
    }

    private static void WritePrimitive(Utf8JsonWriter writer, string typeId, TevScriptValueV3 value, string context)
    {
        switch (typeId, value)
        {
            case ("Bool", TevBoolV3 boolean): writer.WriteBooleanValue(boolean.Value); return;
            case ("Text", TevTextV3 text): writer.WriteStringValue(text.Value); return;
            case ("Int", TevIntV3 integer):
                writer.WriteStartObject(); writer.WriteString("$int", integer.Value.ToString(CultureInfo.InvariantCulture)); writer.WriteEndObject(); return;
            case ("Rat", TevRatV3 rational): WriteRat(writer, rational.Value); return;
            case ("Vec2", TevVectorV3 vector) when vector.TypeId == "Vec2": WriteVector(writer, vector); return;
            case ("Vec3", TevVectorV3 vector) when vector.TypeId == "Vec3": WriteVector(writer, vector); return;
            default: throw Invalid(context, $"invalid primitive value for {typeId}");
        }
    }

    private static void WriteRat(Utf8JsonWriter writer, TevRationalV3 value)
    {
        writer.WriteStartObject();
        writer.WritePropertyName("$rat");
        writer.WriteStartArray();
        writer.WriteStringValue(value.Numerator.ToString(CultureInfo.InvariantCulture));
        writer.WriteStringValue(value.Denominator.ToString(CultureInfo.InvariantCulture));
        writer.WriteEndArray();
        writer.WriteEndObject();
    }

    private static void WriteVector(Utf8JsonWriter writer, TevVectorV3 vector)
    {
        writer.WriteStartArray();
        foreach (var item in vector.Components) WriteRat(writer, item);
        writer.WriteEndArray();
    }

    private static BigInteger ParseCanonicalInteger(JsonElement value, string context)
    {
        if (value.ValueKind != JsonValueKind.String) throw Invalid(context, "integer must be text");
        var text = value.GetString()!;
        if (!CanonicalInteger.IsMatch(text) || text == "-0") throw Invalid(context, "integer text is not canonical");
        return BigInteger.Parse(text, CultureInfo.InvariantCulture);
    }

    private static bool PrimitiveEqual(TevScriptValueV3 left, TevScriptValueV3 right)
    {
        if (left.GetType() != right.GetType()) return false;
        return (left, right) switch
        {
            (TevBoolV3 a, TevBoolV3 b) => a.Value == b.Value,
            (TevIntV3 a, TevIntV3 b) => a.Value == b.Value,
            (TevRatV3 a, TevRatV3 b) => a.Value.Equals(b.Value),
            (TevTextV3 a, TevTextV3 b) => a.Value == b.Value,
            (TevVectorV3 a, TevVectorV3 b) => a.TypeId == b.TypeId && a.Components.SequenceEqual(b.Components),
            _ => false,
        };
    }

    private static void RequireObject(JsonElement value, string context, params string[] keys)
    {
        if (value.ValueKind != JsonValueKind.Object) throw Invalid(context, "expected object");
        RequireExactKeys(value, context, keys);
    }

    private static void RequireExactKeys(JsonElement value, string context, params string[] keys)
    {
        var observed = value.EnumerateObject().Select(item => item.Name).OrderBy(item => item, StringComparer.Ordinal).ToArray();
        var expected = keys.OrderBy(item => item, StringComparer.Ordinal).ToArray();
        if (!observed.SequenceEqual(expected, StringComparer.Ordinal)) throw Invalid(context, "object field set mismatch");
    }

    private static TevScriptV3Exception Invalid(string context, string message) =>
        new("TEVS_IR_V3_VALUE_INVALID", $"{context}: {message}");
}
