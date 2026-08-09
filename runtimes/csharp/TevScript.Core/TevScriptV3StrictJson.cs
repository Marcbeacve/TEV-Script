using System.Text;
using System.Text.Json;

namespace TevScript.Core.V3;

public static class TevScriptStrictJsonV3
{
    public static JsonElement ParseElement(string text)
    {
        var utf8 = Encoding.UTF8.GetBytes(text);
        ValidateNoDuplicateKeys(utf8);
        using var document = JsonDocument.Parse(
            utf8,
            new JsonDocumentOptions
            {
                AllowTrailingCommas = false,
                CommentHandling = JsonCommentHandling.Disallow,
                MaxDepth = 256,
            });
        return document.RootElement.Clone();
    }

    public static JsonElement ParseElement(ReadOnlySpan<byte> utf8)
    {
        var owned = utf8.ToArray();
        ValidateNoDuplicateKeys(owned);
        using var document = JsonDocument.Parse(
            owned,
            new JsonDocumentOptions
            {
                AllowTrailingCommas = false,
                CommentHandling = JsonCommentHandling.Disallow,
                MaxDepth = 256,
            });
        return document.RootElement.Clone();
    }

    private static void ValidateNoDuplicateKeys(ReadOnlySpan<byte> utf8)
    {
        var reader = new Utf8JsonReader(
            utf8,
            new JsonReaderOptions
            {
                AllowTrailingCommas = false,
                CommentHandling = JsonCommentHandling.Disallow,
                MaxDepth = 256,
            });
        var containers = new Stack<HashSet<string>?>(capacity: 32);
        while (reader.Read())
        {
            switch (reader.TokenType)
            {
                case JsonTokenType.StartObject:
                    containers.Push(new HashSet<string>(StringComparer.Ordinal));
                    break;
                case JsonTokenType.StartArray:
                    containers.Push(null);
                    break;
                case JsonTokenType.EndObject:
                case JsonTokenType.EndArray:
                    if (containers.Count == 0)
                        throw new TevScriptV3Exception("TEVS_IR_V3_JSON", "container stack underflow while parsing JSON");
                    containers.Pop();
                    break;
                case JsonTokenType.PropertyName:
                    if (containers.Count == 0 || containers.Peek() is not { } names)
                        throw new TevScriptV3Exception("TEVS_IR_V3_JSON", "property name encountered outside object");
                    var name = reader.GetString()!;
                    if (!names.Add(name))
                        throw new TevScriptV3Exception(
                            "TEVS_IR_V3_JSON_DUPLICATE_KEY",
                            $"duplicate JSON object key {name}");
                    break;
            }
        }
        if (containers.Count != 0)
            throw new TevScriptV3Exception("TEVS_IR_V3_JSON", "unterminated JSON container");
    }
}
