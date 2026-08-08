using System.Collections.ObjectModel;
using System.Globalization;
using System.Numerics;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;

namespace TevScript.Core.V3;

public sealed class TevScriptV3Exception : InvalidOperationException
{
    public TevScriptV3Exception(string code, string message) : base($"{code}: {message}")
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

public abstract record TevScriptValueV3;
public sealed record TevBoolV3(bool Value) : TevScriptValueV3;
public sealed record TevIntV3(BigInteger Value) : TevScriptValueV3;
public sealed record TevRatV3(TevRationalV3 Value) : TevScriptValueV3;
public sealed record TevTextV3(string Value) : TevScriptValueV3;
public sealed record TevVectorV3(string TypeId, IReadOnlyList<TevRationalV3> Components) : TevScriptValueV3;
public sealed record TevRecordV3(string TypeId, IReadOnlyList<KeyValuePair<string, TevScriptValueV3>> Fields) : TevScriptValueV3
{
    public TevScriptValueV3 Field(string name)
    {
        foreach (var pair in Fields)
            if (StringComparer.Ordinal.Equals(pair.Key, name))
                return pair.Value;
        throw new TevScriptV3Exception("TEVS_IR_V3_RUNTIME_RECORD", $"record {TypeId} has no field {name}");
    }
}
public sealed record TevVariantV3(string TypeId, string Variant, bool HasPayload, TevScriptValueV3? Payload) : TevScriptValueV3
{
    public static TevVariantV3 Empty(string typeId, string variant) => new(typeId, variant, false, null);
    public static TevVariantV3 WithPayload(string typeId, string variant, TevScriptValueV3 payload) => new(typeId, variant, true, payload);
}

public enum TevScriptTypeKindV3
{
    Primitive,
    Unit,
    Record,
    Enum,
    Option,
    Result,
}

public sealed record TevScriptFieldV3(string Name, string TypeId);

public sealed record TevScriptTypeDescriptorV3(
    string TypeId,
    TevScriptTypeKindV3 Kind,
    IReadOnlyList<TevScriptFieldV3> Fields,
    IReadOnlyList<string> Variants,
    string? Argument,
    string? OkType,
    string? ErrType)
{
    public string? FieldType(string name)
    {
        foreach (var field in Fields)
            if (StringComparer.Ordinal.Equals(field.Name, name))
                return field.TypeId;
        return null;
    }
}

public sealed class TevScriptTypeTableV3
{
    private static readonly string[] BaseTypeIds = { "Bool", "Int", "Rat", "Text", "Unit", "Vec2", "Vec3" };
    private static readonly Regex LocalName = new("^[A-Za-z_][A-Za-z0-9_]*$", RegexOptions.CultureInvariant | RegexOptions.NonBacktracking);
    private static readonly Regex NominalName = new("^[A-Za-z_][A-Za-z0-9_]*(\\.[A-Za-z_][A-Za-z0-9_]*)+$", RegexOptions.CultureInvariant | RegexOptions.NonBacktracking);
    private readonly Dictionary<string, TevScriptTypeDescriptorV3> _byId;

    private TevScriptTypeTableV3(IReadOnlyList<TevScriptTypeDescriptorV3> descriptors, int maximumValueNesting)
    {
        Descriptors = descriptors;
        MaximumValueNesting = maximumValueNesting;
        _byId = descriptors.ToDictionary(item => item.TypeId, StringComparer.Ordinal);
    }

    public IReadOnlyList<TevScriptTypeDescriptorV3> Descriptors { get; }
    public int MaximumValueNesting { get; }

    public TevScriptTypeDescriptorV3 Require(string typeId, string context = "type")
    {
        if (!_byId.TryGetValue(typeId, out var descriptor))
            throw new TevScriptV3Exception("TEVS_IR_V3_TYPE_UNKNOWN", $"{context} references unknown V3 type {typeId}");
        return descriptor;
    }

    public bool IsStorable(string typeId) => _byId.TryGetValue(typeId, out var descriptor) && descriptor.Kind != TevScriptTypeKindV3.Unit;

    public string? VariantPayloadType(string typeId, string variant)
    {
        var descriptor = Require(typeId);
        switch (descriptor.Kind)
        {
            case TevScriptTypeKindV3.Enum:
                if (!descriptor.Variants.Contains(variant, StringComparer.Ordinal))
                    throw new TevScriptV3Exception("TEVS_IR_V3_VARIANT_UNKNOWN", $"enum {typeId} has no variant {variant}");
                return null;
            case TevScriptTypeKindV3.Option:
                if (variant == "None") return null;
                if (variant == "Some") return descriptor.Argument;
                break;
            case TevScriptTypeKindV3.Result:
                if (variant == "Ok") return descriptor.OkType;
                if (variant == "Err") return descriptor.ErrType;
                break;
        }
        throw new TevScriptV3Exception("TEVS_IR_V3_VARIANT_UNKNOWN", $"type {typeId} does not define variant {variant}");
    }

    public static TevScriptTypeTableV3 Build(JsonElement root)
    {
        if (!root.TryGetProperty("boundary", out var boundary) || boundary.ValueKind != JsonValueKind.Object)
            Contract("$.boundary", "expected object");
        var maximumValueNesting = RequireInt(boundary, "maximum_value_nesting", "$.boundary.maximum_value_nesting", 1, 128);
        if (!root.TryGetProperty("types", out var types) || types.ValueKind != JsonValueKind.Array)
            Contract("$.types", "expected array");
        if (types.GetArrayLength() < 7 || types.GetArrayLength() > 16384)
            Contract("$.types", "type table must contain 7..16384 descriptors");

        var descriptors = new List<TevScriptTypeDescriptorV3>();
        var seen = new HashSet<string>(StringComparer.Ordinal);
        string? previous = null;
        var index = 0;
        foreach (var raw in types.EnumerateArray())
        {
            var path = $"$.types[{index++}]";
            if (raw.ValueKind != JsonValueKind.Object) Contract(path, "expected object");
            var typeId = RequireString(raw, "type_id", path + ".type_id");
            if (!seen.Add(typeId)) Contract(path + ".type_id", $"duplicate type id {typeId}");
            if (previous is not null && StringComparer.Ordinal.Compare(typeId, previous) <= 0)
                Contract("$.types", "type table must be strictly sorted by type_id");
            previous = typeId;
            var kind = RequireString(raw, "kind", path + ".kind");
            descriptors.Add(ParseDescriptor(raw, typeId, kind, path));
        }

        foreach (var baseType in BaseTypeIds)
            if (!seen.Contains(baseType)) Contract("$.types", $"missing portable base descriptor {baseType}");

        var table = new TevScriptTypeTableV3(new ReadOnlyCollection<TevScriptTypeDescriptorV3>(descriptors), maximumValueNesting);
        ValidateDescriptorReferences(table);
        ValidateTypeNesting(table);
        ValidateRecordAcyclic(table);
        return table;
    }

    private static TevScriptTypeDescriptorV3 ParseDescriptor(JsonElement raw, string typeId, string kind, string path)
    {
        if (kind == "primitive")
        {
            RequireExactKeys(raw, path, "type_id", "kind");
            if (typeId is not ("Bool" or "Int" or "Rat" or "Text" or "Vec2" or "Vec3")) Contract(path, "invalid primitive descriptor");
            return New(typeId, TevScriptTypeKindV3.Primitive);
        }
        if (kind == "unit")
        {
            RequireExactKeys(raw, path, "type_id", "kind");
            if (typeId != "Unit") Contract(path, "invalid Unit descriptor");
            return New(typeId, TevScriptTypeKindV3.Unit);
        }
        if (kind == "record")
        {
            RequireExactKeys(raw, path, "type_id", "kind", "fields");
            if (!NominalName.IsMatch(typeId)) Contract(path + ".type_id", "record type id must be nominal and qualified");
            var fieldsRaw = raw.GetProperty("fields");
            if (fieldsRaw.ValueKind != JsonValueKind.Array || fieldsRaw.GetArrayLength() is < 1 or > 256) Contract(path + ".fields", "record requires 1..256 fields");
            var fields = new List<TevScriptFieldV3>();
            var names = new HashSet<string>(StringComparer.Ordinal);
            string? previousField = null;
            var fieldIndex = 0;
            foreach (var fieldRaw in fieldsRaw.EnumerateArray())
            {
                var fieldPath = $"{path}.fields[{fieldIndex++}]";
                RequireExactKeys(fieldRaw, fieldPath, "name", "type");
                var name = RequireString(fieldRaw, "name", fieldPath + ".name");
                if (!LocalName.IsMatch(name)) Contract(fieldPath + ".name", "invalid field identifier");
                if (!names.Add(name)) Contract(fieldPath + ".name", $"duplicate field {name}");
                if (previousField is not null && StringComparer.Ordinal.Compare(name, previousField) <= 0) Contract(path + ".fields", "record fields must be strictly sorted");
                previousField = name;
                fields.Add(new TevScriptFieldV3(name, RequireString(fieldRaw, "type", fieldPath + ".type")));
            }
            return new TevScriptTypeDescriptorV3(typeId, TevScriptTypeKindV3.Record, fields.AsReadOnly(), Array.Empty<string>(), null, null, null);
        }
        if (kind == "enum")
        {
            RequireExactKeys(raw, path, "type_id", "kind", "variants");
            if (!NominalName.IsMatch(typeId)) Contract(path + ".type_id", "enum type id must be nominal and qualified");
            var variantsRaw = raw.GetProperty("variants");
            if (variantsRaw.ValueKind != JsonValueKind.Array || variantsRaw.GetArrayLength() is < 1 or > 256) Contract(path + ".variants", "enum requires 1..256 variants");
            var variants = new List<string>();
            var seenVariants = new HashSet<string>(StringComparer.Ordinal);
            string? previousVariant = null;
            foreach (var value in variantsRaw.EnumerateArray())
            {
                if (value.ValueKind != JsonValueKind.String) Contract(path + ".variants", "variant must be text");
                var variant = value.GetString()!;
                if (!LocalName.IsMatch(variant) || !seenVariants.Add(variant)) Contract(path + ".variants", $"invalid or duplicate variant {variant}");
                if (previousVariant is not null && StringComparer.Ordinal.Compare(variant, previousVariant) <= 0) Contract(path + ".variants", "enum variants must be strictly sorted");
                previousVariant = variant;
                variants.Add(variant);
            }
            return new TevScriptTypeDescriptorV3(typeId, TevScriptTypeKindV3.Enum, Array.Empty<TevScriptFieldV3>(), variants.AsReadOnly(), null, null, null);
        }
        if (kind == "option")
        {
            RequireExactKeys(raw, path, "type_id", "kind", "argument");
            var argument = RequireString(raw, "argument", path + ".argument");
            if (typeId != $"Option<{argument}>") Contract(path + ".type_id", "Option type id does not match argument");
            return new TevScriptTypeDescriptorV3(typeId, TevScriptTypeKindV3.Option, Array.Empty<TevScriptFieldV3>(), Array.Empty<string>(), argument, null, null);
        }
        if (kind == "result")
        {
            RequireExactKeys(raw, path, "type_id", "kind", "ok_type", "err_type");
            var ok = RequireString(raw, "ok_type", path + ".ok_type");
            var err = RequireString(raw, "err_type", path + ".err_type");
            if (typeId != $"Result<{ok},{err}>") Contract(path + ".type_id", "Result type id does not match arguments");
            return new TevScriptTypeDescriptorV3(typeId, TevScriptTypeKindV3.Result, Array.Empty<TevScriptFieldV3>(), Array.Empty<string>(), null, ok, err);
        }
        Contract(path + ".kind", $"unsupported V3 type kind {kind}");
        throw new UnreachableException();
    }

    private static TevScriptTypeDescriptorV3 New(string id, TevScriptTypeKindV3 kind) => new(id, kind, Array.Empty<TevScriptFieldV3>(), Array.Empty<string>(), null, null, null);

    private static void ValidateDescriptorReferences(TevScriptTypeTableV3 table)
    {
        foreach (var descriptor in table.Descriptors)
        {
            IEnumerable<string> referenced = descriptor.Kind switch
            {
                TevScriptTypeKindV3.Record => descriptor.Fields.Select(field => field.TypeId),
                TevScriptTypeKindV3.Option => new[] { descriptor.Argument! },
                TevScriptTypeKindV3.Result => new[] { descriptor.OkType!, descriptor.ErrType! },
                _ => Array.Empty<string>(),
            };
            foreach (var typeId in referenced)
            {
                var child = table.Require(typeId, $"descriptor {descriptor.TypeId}");
                if (child.Kind == TevScriptTypeKindV3.Unit) Contract("$.types", $"Unit is not storable inside {descriptor.TypeId}");
            }
        }
    }

    private static void ValidateTypeNesting(TevScriptTypeTableV3 table)
    {
        var memo = new Dictionary<string, int>(StringComparer.Ordinal);
        foreach (var start in table.Descriptors.Select(item => item.TypeId).Order(StringComparer.Ordinal))
        {
            if (memo.ContainsKey(start)) continue;
            var active = new HashSet<string>(StringComparer.Ordinal);
            var stack = new Stack<(string TypeId, bool Expanded)>();
            stack.Push((start, false));
            while (stack.Count > 0)
            {
                var (typeId, expanded) = stack.Pop();
                if (memo.ContainsKey(typeId)) continue;
                var descriptor = table.Require(typeId);
                var children = descriptor.Kind switch
                {
                    TevScriptTypeKindV3.Option => new[] { descriptor.Argument! },
                    TevScriptTypeKindV3.Result => new[] { descriptor.OkType!, descriptor.ErrType! },
                    _ => Array.Empty<string>(),
                };
                if (!expanded && children.Length > 0)
                {
                    if (!active.Add(typeId)) Contract("$.types", $"constructed type dependency cycle at {typeId}");
                    stack.Push((typeId, true));
                    for (var i = children.Length - 1; i >= 0; --i)
                    {
                        var child = children[i];
                        if (active.Contains(child)) Contract("$.types", $"constructed type dependency cycle at {child}");
                        if (!memo.ContainsKey(child)) stack.Push((child, false));
                    }
                }
                else
                {
                    var observed = children.Length == 0 ? 1 : 1 + children.Max(child => memo[child]);
                    active.Remove(typeId);
                    memo[typeId] = observed;
                    if (observed > 128) Contract("$.types", $"type nesting exceeds 128 at {typeId}: got {observed}");
                }
            }
        }
    }

    private static void ValidateRecordAcyclic(TevScriptTypeTableV3 table)
    {
        var graph = new Dictionary<string, string[]>(StringComparer.Ordinal);
        foreach (var descriptor in table.Descriptors.Where(item => item.Kind == TevScriptTypeKindV3.Record))
        {
            var dependencies = new HashSet<string>(StringComparer.Ordinal);
            var pending = new Stack<string>(descriptor.Fields.Select(field => field.TypeId));
            var seen = new HashSet<string>(StringComparer.Ordinal);
            while (pending.Count > 0)
            {
                var typeId = pending.Pop();
                if (!seen.Add(typeId)) continue;
                var child = table.Require(typeId);
                if (child.Kind == TevScriptTypeKindV3.Record) dependencies.Add(typeId);
                else if (child.Kind == TevScriptTypeKindV3.Option) pending.Push(child.Argument!);
                else if (child.Kind == TevScriptTypeKindV3.Result) { pending.Push(child.OkType!); pending.Push(child.ErrType!); }
            }
            graph[descriptor.TypeId] = dependencies.Order(StringComparer.Ordinal).ToArray();
        }
        var state = new Dictionary<string, int>(StringComparer.Ordinal);
        foreach (var start in graph.Keys.Order(StringComparer.Ordinal))
        {
            if (state.GetValueOrDefault(start) == 2) continue;
            var frames = new Stack<(string Node, int Next)>();
            var path = new List<string>();
            frames.Push((start, 0));
            while (frames.Count > 0)
            {
                var frame = frames.Pop();
                var node = frame.Node;
                if (state.GetValueOrDefault(node) == 0) { state[node] = 1; path.Add(node); }
                var deps = graph[node];
                if (frame.Next < deps.Length)
                {
                    var child = deps[frame.Next];
                    frames.Push((node, frame.Next + 1));
                    var mark = state.GetValueOrDefault(child);
                    if (mark == 0) { frames.Push((child, 0)); continue; }
                    if (mark == 1)
                    {
                        var index = path.IndexOf(child);
                        if (index < 0) index = 0;
                        Contract("$.types", "recursive record dependency: " + string.Join(" -> ", path.Skip(index).Append(child)));
                    }
                    continue;
                }
                if (path.Count == 0 || path[^1] != node) throw new InvalidOperationException("internal V3 record graph invariant");
                path.RemoveAt(path.Count - 1);
                state[node] = 2;
            }
        }
    }

    internal static void RequireExactKeys(JsonElement value, string path, params string[] expected)
    {
        if (value.ValueKind != JsonValueKind.Object) Contract(path, "expected object");
        var observed = value.EnumerateObject().Select(property => property.Name).Order(StringComparer.Ordinal).ToArray();
        var target = expected.Order(StringComparer.Ordinal).ToArray();
        if (!observed.SequenceEqual(target, StringComparer.Ordinal)) Contract(path, $"field set mismatch; expected=[{string.Join(',', target)}], observed=[{string.Join(',', observed)}]");
    }

    internal static string RequireString(JsonElement value, string property, string path)
    {
        if (!value.TryGetProperty(property, out var raw) || raw.ValueKind != JsonValueKind.String) Contract(path, "expected string");
        return raw.GetString()!;
    }

    internal static int RequireInt(JsonElement value, string property, string path, int min, int max)
    {
        if (!value.TryGetProperty(property, out var raw) || raw.ValueKind != JsonValueKind.Number || !raw.TryGetInt32(out var result) || result < min || result > max)
            Contract(path, $"expected integer in [{min},{max}]");
        return result;
    }

    internal static void Contract(string path, string message) => throw new TevScriptV3Exception("TEVS_IR_V3_CONTRACT", $"{path}: {message}");
}

public static class TevScriptValueCodecV3
{
    private static readonly Regex CanonicalInteger = new("^-?(0|[1-9][0-9]*)$", RegexOptions.CultureInvariant | RegexOptions.NonBacktracking);

    public static TevScriptValueV3 Decode(string typeId, JsonElement raw, TevScriptTypeTableV3 table, string context = "value", int depth = 1)
    {
        if (depth > table.MaximumValueNesting)
            throw new TevScriptV3Exception("TEVS_IR_V3_VALUE_NESTING", $"{context}: value nesting exceeds {table.MaximumValueNesting}");
        var descriptor = table.Require(typeId, context);
        if (descriptor.Kind == TevScriptTypeKindV3.Unit)
            throw new TevScriptV3Exception("TEVS_IR_V3_UNIT_VALUE", $"{context}: Unit is not a runtime value");
        if (descriptor.Kind == TevScriptTypeKindV3.Primitive) return DecodePrimitive(typeId, raw, context);
        if (descriptor.Kind == TevScriptTypeKindV3.Record)
        {
            RequireObjectSingle(raw, "$record", context, out var record);
            TevScriptTypeTableV3.RequireExactKeys(record, context + ".$record", "type", "fields");
            if (record.GetProperty("type").GetString() != typeId) ValueFail(context, typeId, "record encoded type mismatch");
            var fieldsRaw = record.GetProperty("fields");
            if (fieldsRaw.ValueKind != JsonValueKind.Array || fieldsRaw.GetArrayLength() != descriptor.Fields.Count) ValueFail(context, typeId, "record field count mismatch");
            var fields = new List<KeyValuePair<string, TevScriptValueV3>>();
            for (var index = 0; index < descriptor.Fields.Count; ++index)
            {
                var expected = descriptor.Fields[index];
                var field = fieldsRaw[index];
                TevScriptTypeTableV3.RequireExactKeys(field, $"{context}.$record.fields[{index}]", "name", "value");
                if (field.GetProperty("name").GetString() != expected.Name) ValueFail(context, typeId, $"expected canonical field {expected.Name}");
                fields.Add(new KeyValuePair<string, TevScriptValueV3>(
                    expected.Name,
                    Decode(expected.TypeId, field.GetProperty("value"), table, $"{context}.{expected.Name}", depth + 1)));
            }
            return new TevRecordV3(typeId, fields.AsReadOnly());
        }
        if (descriptor.Kind == TevScriptTypeKindV3.Enum)
        {
            RequireObjectSingle(raw, "$enum", context, out var value);
            TevScriptTypeTableV3.RequireExactKeys(value, context + ".$enum", "type", "variant");
            if (value.GetProperty("type").GetString() != typeId) ValueFail(context, typeId, "enum encoded type mismatch");
            var variant = value.GetProperty("variant").GetString()!;
            table.VariantPayloadType(typeId, variant);
            return TevVariantV3.Empty(typeId, variant);
        }
        if (descriptor.Kind == TevScriptTypeKindV3.Option)
        {
            RequireObjectSingle(raw, "$option", context, out var value);
            if (value.GetProperty("type").GetString() != typeId) ValueFail(context, typeId, "Option encoded type mismatch");
            var variant = value.GetProperty("variant").GetString()!;
            if (variant == "None")
            {
                TevScriptTypeTableV3.RequireExactKeys(value, context + ".$option", "type", "variant");
                return TevVariantV3.Empty(typeId, "None");
            }
            if (variant == "Some")
            {
                TevScriptTypeTableV3.RequireExactKeys(value, context + ".$option", "type", "variant", "value");
                return TevVariantV3.WithPayload(typeId, "Some", Decode(descriptor.Argument!, value.GetProperty("value"), table, context + ".$option.value", depth + 1));
            }
            ValueFail(context, typeId, $"unknown Option variant {variant}");
        }
        if (descriptor.Kind == TevScriptTypeKindV3.Result)
        {
            RequireObjectSingle(raw, "$result", context, out var value);
            TevScriptTypeTableV3.RequireExactKeys(value, context + ".$result", "type", "variant", "value");
            if (value.GetProperty("type").GetString() != typeId) ValueFail(context, typeId, "Result encoded type mismatch");
            var variant = value.GetProperty("variant").GetString()!;
            var payloadType = variant == "Ok" ? descriptor.OkType : variant == "Err" ? descriptor.ErrType : null;
            if (payloadType is null) ValueFail(context, typeId, $"unknown Result variant {variant}");
            return TevVariantV3.WithPayload(typeId, variant, Decode(payloadType, value.GetProperty("value"), table, context + ".$result.value", depth + 1));
        }
        throw new TevScriptV3Exception("TEVS_IR_V3_VALUE_INVALID", $"{context}: unsupported descriptor {descriptor.Kind}");
    }

    public static string EncodeCanonical(string typeId, TevScriptValueV3 value, TevScriptTypeTableV3 table, string context = "value")
    {
        using var stream = new MemoryStream();
        using (var writer = new Utf8JsonWriter(stream, new JsonWriterOptions { Indented = false, SkipValidation = false }))
            Write(writer, typeId, value, table, context, 1);
        return Encoding.UTF8.GetString(stream.ToArray());
    }

    public static JsonElement EncodeElement(string typeId, TevScriptValueV3 value, TevScriptTypeTableV3 table, string context = "value")
    {
        using var document = JsonDocument.Parse(EncodeCanonical(typeId, value, table, context));
        return document.RootElement.Clone();
    }

    public static bool ValuesEqual(string typeId, TevScriptValueV3 left, TevScriptValueV3 right, TevScriptTypeTableV3 table)
    {
        var descriptor = table.Require(typeId);
        if (descriptor.Kind == TevScriptTypeKindV3.Primitive) return PrimitiveEqual(typeId, left, right);
        if (descriptor.Kind == TevScriptTypeKindV3.Record)
        {
            if (left is not TevRecordV3 a || right is not TevRecordV3 b || a.TypeId != typeId || b.TypeId != typeId) return false;
            foreach (var field in descriptor.Fields)
            {
                if (!ValuesEqual(field.TypeId, a.Field(field.Name), b.Field(field.Name), table)) return false;
            }
            return true;
        }
        if (descriptor.Kind is TevScriptTypeKindV3.Enum or TevScriptTypeKindV3.Option or TevScriptTypeKindV3.Result)
        {
            if (left is not TevVariantV3 a || right is not TevVariantV3 b || a.TypeId != typeId || b.TypeId != typeId || a.Variant != b.Variant || a.HasPayload != b.HasPayload) return false;
            if (!a.HasPayload) return true;
            var payloadType = table.VariantPayloadType(typeId, a.Variant);
            return payloadType is not null && a.Payload is not null && b.Payload is not null && ValuesEqual(payloadType, a.Payload, b.Payload, table);
        }
        return false;
    }

    private static void Write(Utf8JsonWriter writer, string typeId, TevScriptValueV3 value, TevScriptTypeTableV3 table, string context, int depth)
    {
        if (depth > table.MaximumValueNesting) throw new TevScriptV3Exception("TEVS_IR_V3_VALUE_NESTING", $"{context}: nesting exceeds {table.MaximumValueNesting}");
        var descriptor = table.Require(typeId, context);
        if (descriptor.Kind == TevScriptTypeKindV3.Primitive) { WritePrimitive(writer, typeId, value, context); return; }
        if (descriptor.Kind == TevScriptTypeKindV3.Unit) throw new TevScriptV3Exception("TEVS_IR_V3_UNIT_VALUE", $"{context}: Unit is not encodable");
        if (descriptor.Kind == TevScriptTypeKindV3.Record)
        {
            if (value is not TevRecordV3 record || record.TypeId != typeId) ValueFail(context, typeId, "expected exact record value");
            writer.WriteStartObject(); writer.WritePropertyName("$record"); writer.WriteStartObject();
            writer.WriteString("type", typeId); writer.WritePropertyName("fields"); writer.WriteStartArray();
            foreach (var field in descriptor.Fields)
            {
                writer.WriteStartObject(); writer.WriteString("name", field.Name); writer.WritePropertyName("value");
                Write(writer, field.TypeId, record.Field(field.Name), table, context + "." + field.Name, depth + 1);
                writer.WriteEndObject();
            }
            writer.WriteEndArray(); writer.WriteEndObject(); writer.WriteEndObject(); return;
        }
        if (value is not TevVariantV3 variant || variant.TypeId != typeId) ValueFail(context, typeId, "expected exact variant value");
        var payloadType = table.VariantPayloadType(typeId, variant.Variant);
        var key = descriptor.Kind == TevScriptTypeKindV3.Enum ? "$enum" : descriptor.Kind == TevScriptTypeKindV3.Option ? "$option" : "$result";
        writer.WriteStartObject(); writer.WritePropertyName(key); writer.WriteStartObject(); writer.WriteString("type", typeId); writer.WriteString("variant", variant.Variant);
        if (payloadType is null)
        {
            if (variant.HasPayload) ValueFail(context, typeId, $"{variant.Variant} cannot carry payload");
        }
        else
        {
            if (!variant.HasPayload || variant.Payload is null) ValueFail(context, typeId, $"{variant.Variant} requires payload");
            writer.WritePropertyName("value"); Write(writer, payloadType, variant.Payload, table, context + ".value", depth + 1);
        }
        writer.WriteEndObject(); writer.WriteEndObject();
    }

    private static TevScriptValueV3 DecodePrimitive(string typeId, JsonElement raw, string context)
    {
        if (typeId == "Bool")
        {
            if (raw.ValueKind is not (JsonValueKind.True or JsonValueKind.False)) ValueFail(context, typeId, "expected boolean");
            return new TevBoolV3(raw.GetBoolean());
        }
        if (typeId == "Text")
        {
            if (raw.ValueKind != JsonValueKind.String) ValueFail(context, typeId, "expected text");
            return new TevTextV3(raw.GetString()!);
        }
        if (typeId == "Int")
        {
            RequireObjectSingle(raw, "$int", context, out var value);
            if (value.ValueKind != JsonValueKind.String) ValueFail(context, typeId, "integer must be canonical text");
            return new TevIntV3(ParseCanonicalInteger(value.GetString()!, context));
        }
        if (typeId == "Rat")
        {
            RequireObjectSingle(raw, "$rat", context, out var pair);
            if (pair.ValueKind != JsonValueKind.Array || pair.GetArrayLength() != 2 || pair[0].ValueKind != JsonValueKind.String || pair[1].ValueKind != JsonValueKind.String) ValueFail(context, typeId, "invalid rational pair");
            var numerator = ParseCanonicalInteger(pair[0].GetString()!, context);
            var denominatorText = pair[1].GetString()!;
            if (!Regex.IsMatch(denominatorText, "^[1-9][0-9]*$", RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)) ValueFail(context, typeId, "invalid denominator");
            var denominator = BigInteger.Parse(denominatorText, CultureInfo.InvariantCulture);
            var result = new TevRationalV3(numerator, denominator);
            if (result.Numerator.ToString(CultureInfo.InvariantCulture) != pair[0].GetString() || result.Denominator.ToString(CultureInfo.InvariantCulture) != denominatorText) ValueFail(context, typeId, "rational must be normalized");
            return new TevRatV3(result);
        }
        if (typeId is "Vec2" or "Vec3")
        {
            var expected = typeId == "Vec2" ? 2 : 3;
            if (raw.ValueKind != JsonValueKind.Array || raw.GetArrayLength() != expected) ValueFail(context, typeId, $"expected {expected} rational components");
            var values = new List<TevRationalV3>();
            for (var index = 0; index < expected; ++index)
            {
                var value = DecodePrimitive("Rat", raw[index], $"{context}[{index}]");
                values.Add(((TevRatV3)value).Value);
            }
            return new TevVectorV3(typeId, values.AsReadOnly());
        }
        ValueFail(context, typeId, "unknown primitive");
        throw new UnreachableException();
    }

    private static void WritePrimitive(Utf8JsonWriter writer, string typeId, TevScriptValueV3 value, string context)
    {
        switch (typeId)
        {
            case "Bool" when value is TevBoolV3 b: writer.WriteBooleanValue(b.Value); return;
            case "Text" when value is TevTextV3 t: writer.WriteStringValue(t.Value); return;
            case "Int" when value is TevIntV3 i:
                writer.WriteStartObject(); writer.WriteString("$int", i.Value.ToString(CultureInfo.InvariantCulture)); writer.WriteEndObject(); return;
            case "Rat" when value is TevRatV3 r:
                writer.WriteStartObject(); writer.WritePropertyName("$rat"); writer.WriteStartArray(); writer.WriteStringValue(r.Value.Numerator.ToString(CultureInfo.InvariantCulture)); writer.WriteStringValue(r.Value.Denominator.ToString(CultureInfo.InvariantCulture)); writer.WriteEndArray(); writer.WriteEndObject(); return;
            case "Vec2" or "Vec3" when value is TevVectorV3 vector && vector.TypeId == typeId:
                var expected = typeId == "Vec2" ? 2 : 3;
                if (vector.Components.Count != expected) ValueFail(context, typeId, "vector arity mismatch");
                writer.WriteStartArray(); foreach (var component in vector.Components) WritePrimitive(writer, "Rat", new TevRatV3(component), context); writer.WriteEndArray(); return;
        }
        ValueFail(context, typeId, "runtime value kind mismatch");
    }

    private static bool PrimitiveEqual(string typeId, TevScriptValueV3 left, TevScriptValueV3 right) => typeId switch
    {
        "Bool" => left is TevBoolV3 a && right is TevBoolV3 b && a.Value == b.Value,
        "Int" => left is TevIntV3 a && right is TevIntV3 b && a.Value == b.Value,
        "Rat" => left is TevRatV3 a && right is TevRatV3 b && a.Value.Equals(b.Value),
        "Text" => left is TevTextV3 a && right is TevTextV3 b && a.Value == b.Value,
        "Vec2" or "Vec3" => left is TevVectorV3 a && right is TevVectorV3 b && a.TypeId == typeId && b.TypeId == typeId && a.Components.SequenceEqual(b.Components),
        _ => false,
    };

    private static BigInteger ParseCanonicalInteger(string text, string context)
    {
        if (!CanonicalInteger.IsMatch(text) || text == "-0") ValueFail(context, "Int", "integer text is not canonical");
        return BigInteger.Parse(text, CultureInfo.InvariantCulture);
    }

    private static void RequireObjectSingle(JsonElement raw, string key, string context, out JsonElement value)
    {
        if (raw.ValueKind != JsonValueKind.Object) ValueFail(context, key, "expected object");
        var properties = raw.EnumerateObject().ToArray();
        if (properties.Length != 1 || properties[0].Name != key) ValueFail(context, key, $"expected exact wrapper {key}");
        value = properties[0].Value;
    }

    private static void ValueFail(string context, string typeId, string message) => throw new TevScriptV3Exception("TEVS_IR_V3_VALUE_INVALID", $"{context}: {message} for expected type {typeId}");
}
