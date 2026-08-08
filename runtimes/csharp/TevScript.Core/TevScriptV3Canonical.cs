using System.Globalization;
using System.Text;
using System.Text.Encodings.Web;
using System.Text.Json;

namespace TevScript.Core.V3;

public static class TevScriptCanonicalV3
{
    private static readonly uint[] Sha256RoundConstants =
    {
        0x428a2f98U, 0x71374491U, 0xb5c0fbcfU, 0xe9b5dba5U,
        0x3956c25bU, 0x59f111f1U, 0x923f82a4U, 0xab1c5ed5U,
        0xd807aa98U, 0x12835b01U, 0x243185beU, 0x550c7dc3U,
        0x72be5d74U, 0x80deb1feU, 0x9bdc06a7U, 0xc19bf174U,
        0xe49b69c1U, 0xefbe4786U, 0x0fc19dc6U, 0x240ca1ccU,
        0x2de92c6fU, 0x4a7484aaU, 0x5cb0a9dcU, 0x76f988daU,
        0x983e5152U, 0xa831c66dU, 0xb00327c8U, 0xbf597fc7U,
        0xc6e00bf3U, 0xd5a79147U, 0x06ca6351U, 0x14292967U,
        0x27b70a85U, 0x2e1b2138U, 0x4d2c6dfcU, 0x53380d13U,
        0x650a7354U, 0x766a0abbU, 0x81c2c92eU, 0x92722c85U,
        0xa2bfe8a1U, 0xa81a664bU, 0xc24b8b70U, 0xc76c51a3U,
        0xd192e819U, 0xd6990624U, 0xf40e3585U, 0x106aa070U,
        0x19a4c116U, 0x1e376c08U, 0x2748774cU, 0x34b0bcb5U,
        0x391c0cb3U, 0x4ed8aa4aU, 0x5b9cca4fU, 0x682e6ff3U,
        0x748f82eeU, 0x78a5636fU, 0x84c87814U, 0x8cc70208U,
        0x90befffaU, 0xa4506cebU, 0xbef9a3f7U, 0xc67178f2U,
    };

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

    public static string Sha256Text(string text)
    {
        if (text is null) throw new ArgumentNullException(nameof(text));
        var digest = ComputeSha256(Encoding.UTF8.GetBytes(text));
        var builder = new StringBuilder(64);
        foreach (var item in digest)
            builder.Append(item.ToString("x2", CultureInfo.InvariantCulture));
        return builder.ToString();
    }

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

    private static byte[] ComputeSha256(byte[] input)
    {
        ulong bitLength = (ulong)input.LongLength * 8UL;
        var remainder = (input.Length + 1 + 8) % 64;
        var zeroPadding = remainder == 0 ? 0 : 64 - remainder;
        var message = new byte[input.Length + 1 + zeroPadding + 8];
        Buffer.BlockCopy(input, 0, message, 0, input.Length);
        message[input.Length] = 0x80;
        for (var index = 0; index < 8; ++index)
            message[message.Length - 1 - index] = (byte)(bitLength >> (index * 8));

        uint h0 = 0x6a09e667U;
        uint h1 = 0xbb67ae85U;
        uint h2 = 0x3c6ef372U;
        uint h3 = 0xa54ff53aU;
        uint h4 = 0x510e527fU;
        uint h5 = 0x9b05688cU;
        uint h6 = 0x1f83d9abU;
        uint h7 = 0x5be0cd19U;
        var schedule = new uint[64];

        unchecked
        {
            for (var block = 0; block < message.Length; block += 64)
            {
                for (var index = 0; index < 16; ++index)
                {
                    var offset = block + index * 4;
                    schedule[index] =
                        ((uint)message[offset] << 24)
                        | ((uint)message[offset + 1] << 16)
                        | ((uint)message[offset + 2] << 8)
                        | message[offset + 3];
                }
                for (var index = 16; index < 64; ++index)
                {
                    var s0 = RotateRight(schedule[index - 15], 7)
                        ^ RotateRight(schedule[index - 15], 18)
                        ^ (schedule[index - 15] >> 3);
                    var s1 = RotateRight(schedule[index - 2], 17)
                        ^ RotateRight(schedule[index - 2], 19)
                        ^ (schedule[index - 2] >> 10);
                    schedule[index] = schedule[index - 16] + s0 + schedule[index - 7] + s1;
                }

                var a = h0;
                var b = h1;
                var c = h2;
                var d = h3;
                var e = h4;
                var f = h5;
                var g = h6;
                var h = h7;
                for (var index = 0; index < 64; ++index)
                {
                    var bigS1 = RotateRight(e, 6) ^ RotateRight(e, 11) ^ RotateRight(e, 25);
                    var choice = (e & f) ^ (~e & g);
                    var temp1 = h + bigS1 + choice + Sha256RoundConstants[index] + schedule[index];
                    var bigS0 = RotateRight(a, 2) ^ RotateRight(a, 13) ^ RotateRight(a, 22);
                    var majority = (a & b) ^ (a & c) ^ (b & c);
                    var temp2 = bigS0 + majority;
                    h = g;
                    g = f;
                    f = e;
                    e = d + temp1;
                    d = c;
                    c = b;
                    b = a;
                    a = temp1 + temp2;
                }
                h0 += a;
                h1 += b;
                h2 += c;
                h3 += d;
                h4 += e;
                h5 += f;
                h6 += g;
                h7 += h;
            }
        }

        var digest = new byte[32];
        WriteUInt32BigEndian(digest, 0, h0);
        WriteUInt32BigEndian(digest, 4, h1);
        WriteUInt32BigEndian(digest, 8, h2);
        WriteUInt32BigEndian(digest, 12, h3);
        WriteUInt32BigEndian(digest, 16, h4);
        WriteUInt32BigEndian(digest, 20, h5);
        WriteUInt32BigEndian(digest, 24, h6);
        WriteUInt32BigEndian(digest, 28, h7);
        return digest;
    }

    private static uint RotateRight(uint value, int bits) =>
        (value >> bits) | (value << (32 - bits));

    private static void WriteUInt32BigEndian(byte[] destination, int offset, uint value)
    {
        destination[offset] = (byte)(value >> 24);
        destination[offset + 1] = (byte)(value >> 16);
        destination[offset + 2] = (byte)(value >> 8);
        destination[offset + 3] = (byte)value;
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
