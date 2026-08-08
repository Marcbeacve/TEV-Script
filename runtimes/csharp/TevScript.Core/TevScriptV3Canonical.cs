using System.Globalization;
using System.Text;
using System.Text.Encodings.Web;
using System.Text.Json;

namespace TevScript.Core.V3;

public static class TevScriptCanonicalV3
{
    public static string Json(JsonElement value)
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
        return Encoding.UTF8.GetString(stream.ToArray());
    }

    public static string Json(string rawJson)
    {
        using var document = JsonDocument.Parse(
            rawJson,
            new JsonDocumentOptions
            {
                AllowTrailingCommas = false,
                CommentHandling = JsonCommentHandling.Disallow,
                MaxDepth = 256,
            });
        return Json(document.RootElement);
    }

    public static string Sha256(JsonElement value) => Sha256Text(Json(value));

    public static string Sha256Text(string text) =>
        Marcbeacve.TevScript.Core.TevJson.Sha256(text);

    public static JsonElement ParseClone(string json)
    {
        using var document = JsonDocument.Parse(
            json,
            new JsonDocumentOptions
            {
                AllowTrailingCommas = false,
                CommentHandling = JsonCommentHandling.Disallow,
                MaxDepth = 256,
            });
        return document.RootElement.Clone();
    }

    private static void Write(Utf8JsonWriter writer, JsonElement value)
    {
        switch (value.ValueKind)
        {
            case JsonValueKind.Object:
                writer.WriteStartObject();
                foreach (var property in value.EnumerateObject().OrderBy(item => item.Name, StringComparer.Ordinal))
                {
                    writer.WritePropertyName(property.Name);
                    Write(writer, property.Value);
                }
                writer.WriteEndObject();
                return;
            case JsonValueKind.Array:
                writer.WriteStartArray();
                foreach (var item in value.EnumerateArray()) Write(writer, item);
                writer.WriteEndArray();
                return;
            case JsonValueKind.String:
                writer.WriteStringValue(value.GetString());
                return;
            case JsonValueKind.True:
                writer.WriteBooleanValue(true);
                return;
            case JsonValueKind.False:
                writer.WriteBooleanValue(false);
                return;
            case JsonValueKind.Null:
                writer.WriteNullValue();
                return;
            case JsonValueKind.Number:
                if (!value.TryGetInt64(out var integer))
                    throw new TevScriptV3Exception(
                        "TEVS_IR_V3_CANONICAL_NUMBER",
                        $"structural JSON number must be a signed 64-bit integer, got {value.GetRawText()}");
                if (integer is < -9007199254740991L or > 9007199254740991L)
                    throw new TevScriptV3Exception(
                        "TEVS_IR_V3_CANONICAL_NUMBER",
                        $"structural integer exceeds portable safe range: {integer.ToString(CultureInfo.InvariantCulture)}");
                writer.WriteNumberValue(integer);
                return;
            default:
                throw new TevScriptV3Exception(
                    "TEVS_IR_V3_CANONICAL_KIND",
                    $"unsupported JSON value kind {value.ValueKind}");
        }
    }
}
