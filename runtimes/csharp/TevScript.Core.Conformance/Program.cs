using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using System.Text.Json.Nodes;
using Marcbeacve.TevScript.Core;

internal static class Program
{
    private static readonly UTF8Encoding StrictUtf8 =
        new UTF8Encoding(false, true);

    private static readonly VectorDefinition[] Vectors =
    {
        new VectorDefinition("player", "Player.tevs.ir.json"),
        new VectorDefinition("matrix", "ConformanceMatrix.tevs.ir.json"),
        new VectorDefinition("player-idle", "Player.tevs.ir.json"),
        new VectorDefinition("event-chain", "EventChain.tevs.ir.json")
    };

    private static int Main(string[] args)
    {
        try
        {
            if (args.Length != 1 || !Directory.Exists(args[0]))
            {
                Console.Error.WriteLine(
                    "Usage: TevScript.Core.Conformance <repository-root>");
                return 2;
            }
            string root = Path.GetFullPath(args[0]);
            Run(root);
            return 0;
        }
        catch (Exception error)
        {
            Console.Error.WriteLine(
                "TEV_SCRIPT_CSHARP_GATE_2=FAIL:" +
                error.GetType().Name + ":" + error.Message);
            return 1;
        }
    }

    private static void Run(string root)
    {
        int vectorCount = TevScriptCanonicalJson.VerifyVectorSet(
            ReadStrictUtf8(Path.Combine(
                root,
                "conformance",
                "canonical.vectors.json")));
        Console.WriteLine(
            "CSHARP_CANONICAL_VECTORS=" + vectorCount + "_PASS");

        VerifyStrictJsonNegatives();
        Console.WriteLine("CSHARP_STRICT_JSON_BOUNDARY=PASS");

        VerifyStrictUtf8Boundary();
        Console.WriteLine("CSHARP_STRICT_UTF8_BOUNDARY=PASS");

        VerifyProgramNegatives(root);
        Console.WriteLine("CSHARP_IR_NEGATIVE_CAMPAIGN=PASS");

        VerifyMissingCapability(root);
        Console.WriteLine("CSHARP_MISSING_CAPABILITY_FAIL_CLOSED=PASS");

        var receiptHashes = new Dictionary<string, string>(StringComparer.Ordinal);
        foreach (VectorDefinition vector in Vectors)
        {
            string programJson = ReadStrictUtf8(Path.Combine(
                root,
                "examples",
                vector.ProgramFile));
            string scenarioJson = ReadStrictUtf8(Path.Combine(
                root,
                "conformance",
                vector.Id + ".scenario.json"));
            string observed = TevScriptConformance.RunCanonicalReceipt(
                programJson,
                scenarioJson);
            byte[] observedBytes = StrictUtf8.GetBytes(observed);
            string expectedPath = Path.Combine(
                root,
                "conformance",
                vector.Id + ".expected.json");
            byte[] expectedBytes = File.ReadAllBytes(expectedPath);
            if (!observedBytes.SequenceEqual(expectedBytes))
            {
                throw new InvalidOperationException(
                    "receipt byte mismatch for " + vector.Id);
            }
            JsonNode receipt = JsonNode.Parse(observed);
            string receiptHash = receipt["receipt_hash"].GetValue<string>();
            receiptHashes.Add(vector.Id, receiptHash);
            Console.WriteLine(
                "CSHARP_" + Marker(vector.Id) + "_BYTE_PARITY=PASS");
        }

        Console.WriteLine("CSHARP_CONFORMANCE_SCENARIOS=4_PASS");
        Console.WriteLine("CSHARP_PYTHON_JAVASCRIPT_BYTE_PARITY=PASS");
        foreach (KeyValuePair<string, string> item in receiptHashes)
        {
            Console.WriteLine(
                "CSHARP_" + Marker(item.Key) + "_RECEIPT_HASH=" + item.Value);
        }
        Console.WriteLine("TEV_SCRIPT_CSHARP_GATE_2=PASS");
    }

    private static void VerifyStrictJsonNegatives()
    {
        ExpectContract(
            () => TevScriptCanonicalJson.Canonicalize("{\"a\":1,\"a\":2}"),
            "duplicate-key");
        ExpectContract(
            () => TevScriptCanonicalJson.Canonicalize("1.5"),
            "float");
        ExpectContract(
            () => TevScriptCanonicalJson.Canonicalize("-0"),
            "negative-zero");
        ExpectContract(
            () => TevScriptCanonicalJson.Canonicalize("9007199254740992"),
            "unsafe-structural-integer");

        string tagged = TevScriptCanonicalJson.Canonicalize(
            "{\"value\":{\"$int\":\"123456789012345678901234567890\"}}");
        if (!string.Equals(
                tagged,
                "{\"value\":{\"$int\":\"123456789012345678901234567890\"}}",
                StringComparison.Ordinal))
        {
            throw new InvalidOperationException(
                "tagged large integer was not preserved");
        }
    }

    private static void VerifyStrictUtf8Boundary()
    {
        string path = Path.Combine(
            Path.GetTempPath(),
            "tev-script-invalid-utf8-" + Guid.NewGuid().ToString("N") + ".json");
        try
        {
            File.WriteAllBytes(path, new byte[]
            {
                0x7b, 0x22, 0x78, 0x22, 0x3a, 0x22,
                0xc3, 0x28,
                0x22, 0x7d
            });
            try
            {
                ReadStrictUtf8(path);
            }
            catch (DecoderFallbackException)
            {
                return;
            }
            throw new InvalidOperationException(
                "malformed UTF-8 was accepted");
        }
        finally
        {
            if (File.Exists(path)) File.Delete(path);
        }
    }

    private static void VerifyProgramNegatives(string root)
    {
        string original = ReadStrictUtf8(Path.Combine(
            root,
            "examples",
            "Player.tevs.ir.json"));

        JsonObject semanticTamper = ParseObject(original);
        semanticTamper["semantic_hash"] = new string('0', 64);
        ExpectContract(
            () => TevScriptProgram.Parse(semanticTamper.ToJsonString()),
            "semantic-hash-tamper");

        JsonObject debugTamper = ParseObject(original);
        debugTamper["debug_hash"] = new string('0', 64);
        ExpectContract(
            () => TevScriptProgram.Parse(debugTamper.ToJsonString()),
            "debug-hash-tamper");

        JsonObject boundaryTamper = ParseObject(original);
        boundaryTamper["boundary"]["dynamic_code"] = true;
        RecomputeSemanticHash(boundaryTamper);
        ExpectContract(
            () => TevScriptProgram.Parse(boundaryTamper.ToJsonString()),
            "enabled-boundary");

        JsonObject extraInstructionField = ParseObject(original);
        JsonObject firstInstruction = FindFirstInstruction(extraInstructionField);
        firstInstruction["unexpected"] = true;
        RecomputeSemanticHash(extraInstructionField);
        ExpectContract(
            () => TevScriptProgram.Parse(extraInstructionField.ToJsonString()),
            "instruction-extra-field");

        JsonObject unknownOpcode = ParseObject(original);
        FindFirstInstruction(unknownOpcode)["op"] = "NOPE";
        RecomputeSemanticHash(unknownOpcode);
        ExpectContract(
            () => TevScriptProgram.Parse(unknownOpcode.ToJsonString()),
            "unknown-opcode");

        JsonObject nonCanonicalInteger = ParseObject(original);
        JsonObject taggedInteger = FindFirstTaggedInteger(nonCanonicalInteger);
        taggedInteger["$int"] = "00";
        RecomputeSemanticHash(nonCanonicalInteger);
        ExpectContract(
            () => TevScriptProgram.Parse(nonCanonicalInteger.ToJsonString()),
            "noncanonical-tagged-integer");

        JsonObject budgetTamper = ParseObject(original);
        JsonObject handler = FirstHandler(budgetTamper);
        handler["instruction_budget"] = 1;
        RecomputeSemanticHash(budgetTamper);
        ExpectContract(
            () => TevScriptProgram.Parse(budgetTamper.ToJsonString()),
            "instruction-budget");
    }

    private static void VerifyMissingCapability(string root)
    {
        TevScriptProgram program = TevScriptProgram.Parse(ReadStrictUtf8(
            Path.Combine(root, "examples", "Player.tevs.ir.json")));
        var runtime = new TevScriptRuntime(program);
        ExpectContract(
            () => runtime.Invoke("Player", "start"),
            "missing-capability");
    }

    private static void RecomputeSemanticHash(JsonObject root)
    {
        var semantic = new JsonObject();
        foreach (KeyValuePair<string, JsonNode> item in root)
        {
            if (item.Key == "semantic_hash" ||
                item.Key == "debug" ||
                item.Key == "debug_hash")
            {
                continue;
            }
            semantic[item.Key] = item.Value == null
                ? null
                : item.Value.DeepClone();
        }
        root["semantic_hash"] = TevScriptCanonicalJson.Hash(
            semantic.ToJsonString());
    }

    private static JsonObject FindFirstInstruction(JsonObject root)
    {
        return FirstHandler(root)["instructions"][0].AsObject();
    }

    private static JsonObject FirstHandler(JsonObject root)
    {
        return root["entities"][0]["handlers"][0].AsObject();
    }

    private static JsonObject FindFirstTaggedInteger(JsonObject root)
    {
        JsonNode found = FindProperty(root, "$int");
        if (found == null || found.Parent == null)
            throw new InvalidOperationException("no tagged integer found");
        return found.Parent.AsObject();
    }

    private static JsonNode FindProperty(JsonNode node, string propertyName)
    {
        JsonObject obj = node as JsonObject;
        if (obj != null)
        {
            JsonNode direct;
            if (obj.TryGetPropertyValue(propertyName, out direct))
                return direct;
            foreach (KeyValuePair<string, JsonNode> item in obj)
            {
                if (item.Value == null) continue;
                JsonNode found = FindProperty(item.Value, propertyName);
                if (found != null) return found;
            }
        }
        JsonArray array = node as JsonArray;
        if (array != null)
        {
            foreach (JsonNode item in array)
            {
                if (item == null) continue;
                JsonNode found = FindProperty(item, propertyName);
                if (found != null) return found;
            }
        }
        return null;
    }

    private static JsonObject ParseObject(string json)
    {
        JsonNode node = JsonNode.Parse(json);
        JsonObject result = node as JsonObject;
        if (result == null)
            throw new InvalidOperationException("expected JSON object");
        return result;
    }

    private static void ExpectContract(Action action, string id)
    {
        try
        {
            action();
        }
        catch (TevContractException)
        {
            return;
        }
        throw new InvalidOperationException(
            "negative case was accepted: " + id);
    }

    private static string ReadStrictUtf8(string path)
    {
        byte[] bytes = File.ReadAllBytes(path);
        return StrictUtf8.GetString(bytes);
    }

    private static string Marker(string id)
    {
        return id.Replace('-', '_').ToUpperInvariant();
    }

    private sealed class VectorDefinition
    {
        public VectorDefinition(string id, string programFile)
        {
            Id = id;
            ProgramFile = programFile;
        }

        public string Id { get; }
        public string ProgramFile { get; }
    }
}
