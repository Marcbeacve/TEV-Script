using System.Collections;
using System.Text;
using System.Text.Encodings.Web;
using System.Text.Json;

namespace TevScript.Core.V3;

internal static class TevScriptObjectTreeJsonV3
{
    private const long MaximumStructuralInteger = 9007199254740991L;

    public static JsonElement Element(object? value) =>
        TevScriptStrictJsonV3.ParseElement(Json(value));

    public static string Json(object? value)
    {
        using var stream = new MemoryStream();
        using (var writer = new Utf8JsonWriter(
            stream,
            new JsonWriterOptions
            {
                Indented = false,
                SkipValidation = false,
                Encoder = JavaScriptEncoder.Default,
            }))
        {
            Write(writer, value);
        }
        var raw = Encoding.UTF8.GetString(stream.ToArray());
        return TevScriptCanonicalV3.Json(TevScriptStrictJsonV3.ParseElement(raw));
    }

    private static void Write(Utf8JsonWriter writer, object? value)
    {
        switch (value)
        {
            case null:
                writer.WriteNullValue();
                return;
            case JsonElement element:
                writer.WriteRawValue(TevScriptCanonicalV3.Json(element), skipInputValidation: false);
                return;
            case bool boolean:
                writer.WriteBooleanValue(boolean);
                return;
            case string text:
                writer.WriteStringValue(text);
                return;
            case byte number:
                writer.WriteNumberValue(number);
                return;
            case sbyte number:
                writer.WriteNumberValue(number);
                return;
            case short number:
                writer.WriteNumberValue(number);
                return;
            case ushort number:
                writer.WriteNumberValue(number);
                return;
            case int number:
                writer.WriteNumberValue(number);
                return;
            case uint number:
                writer.WriteNumberValue(number);
                return;
            case long number:
                RequireStructuralInteger(number);
                writer.WriteNumberValue(number);
                return;
            case ulong number:
                if (number > (ulong)MaximumStructuralInteger)
                    throw new TevScriptV3Exception(
                        "TEVS_IR_V3_OBJECT_TREE_NUMBER",
                        $"structural integer exceeds portable safe range: {number}");
                writer.WriteNumberValue(number);
                return;
            case IDictionary<string, object?> dictionary:
                writer.WriteStartObject();
                foreach (var pair in dictionary.OrderBy(item => item.Key, StringComparer.Ordinal))
                {
                    writer.WritePropertyName(pair.Key);
                    Write(writer, pair.Value);
                }
                writer.WriteEndObject();
                return;
            case IDictionary dictionary:
            {
                var entries = new List<(string Key, object? Value)>();
                foreach (DictionaryEntry entry in dictionary)
                {
                    if (entry.Key is not string key)
                        throw new TevScriptV3Exception(
                            "TEVS_IR_V3_OBJECT_TREE_KEY",
                            "closed object-tree dictionary keys must be strings");
                    entries.Add((key, entry.Value));
                }
                writer.WriteStartObject();
                foreach (var entry in entries.OrderBy(item => item.Key, StringComparer.Ordinal))
                {
                    writer.WritePropertyName(entry.Key);
                    Write(writer, entry.Value);
                }
                writer.WriteEndObject();
                return;
            }
            case IEnumerable sequence:
                writer.WriteStartArray();
                foreach (var item in sequence) Write(writer, item);
                writer.WriteEndArray();
                return;
            default:
                throw new TevScriptV3Exception(
                    "TEVS_IR_V3_OBJECT_TREE_TYPE",
                    $"unsupported closed object-tree value type {value.GetType().FullName}");
        }
    }

    private static void RequireStructuralInteger(long value)
    {
        if (value is < -MaximumStructuralInteger or > MaximumStructuralInteger)
            throw new TevScriptV3Exception(
                "TEVS_IR_V3_OBJECT_TREE_NUMBER",
                $"structural integer exceeds portable safe range: {value}");
    }
}

// Namespace-local facade deliberately shadows System.Text.Json.JsonSerializer
// inside TevScript.Core.V3. It exposes only the one operation conformance needs
// and routes it through the closed writer above, so AOT execution never falls
// back to reflection-based arbitrary-type serialization.
internal static class JsonSerializer
{
    public static JsonElement SerializeToElement<T>(T value) =>
        TevScriptObjectTreeJsonV3.Element(value);
}
