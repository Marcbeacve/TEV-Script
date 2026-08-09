using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.Json.Nodes;
using Marcbeacve.TevScript.Core;

internal static class Program
{
    private static int Main(string[] args)
    {
        try
        {
            if (args.Length != 1 || !Directory.Exists(args[0]))
            {
                Console.Error.WriteLine(
                    "Usage: TevScript.LanguageClosureGate <repository-root>");
                return 2;
            }
            Run(Path.GetFullPath(args[0]));
            return 0;
        }
        catch (Exception error)
        {
            Console.Error.WriteLine(error);
            Console.WriteLine("TEV_SCRIPT_LANGUAGE_CLOSURE_CSHARP=FAIL");
            return 1;
        }
    }

    private static void Run(string root)
    {
        JsonObject corpus = JsonNode.Parse(File.ReadAllText(Path.Combine(
            root,
            "conformance",
            "language-negative-v1.json"))).AsObject();
        string baseRelative = corpus["base_program"].GetValue<string>();
        string original = File.ReadAllText(Path.Combine(
            root,
            baseRelative.Replace('/', Path.DirectorySeparatorChar)));
        TevScriptProgram program = TevScriptProgram.Parse(original);
        Console.WriteLine("LANGUAGE_CLOSURE_CSHARP_VALID_BASE=PASS");

        string expectedCode = corpus["expected_code"].GetValue<string>();
        int count = 0;
        foreach (JsonNode rawCase in corpus["cases"].AsArray())
        {
            JsonObject testCase = rawCase.AsObject();
            JsonObject mutated = JsonNode.Parse(original).AsObject();
            JsonObject handler = SelectedHandler(
                mutated,
                corpus["entity_id"].GetValue<string>(),
                corpus["handler_event_id"].GetValue<string>());
            handler["locals"] = testCase["locals"].DeepClone();
            handler["instructions"] = testCase["instructions"].DeepClone();
            handler["instruction_budget"] = Math.Max(
                1,
                handler["instructions"].AsArray().Count);
            RecomputeSemanticHash(mutated);
            string id = testCase["id"].GetValue<string>();
            ExpectCode(
                () => TevScriptProgram.Parse(mutated.ToJsonString()),
                expectedCode,
                id);
            count++;
        }
        if (count != 8)
            throw new InvalidOperationException(
                "Expected 8 negative cases, got " + count + ".");
        Console.WriteLine("LANGUAGE_CLOSURE_CSHARP_NEGATIVE_CORPUS=8_PASS");

        ExpectCode(
            () => new TevScriptRuntime(program).Invoke("Player", " start "),
            "TEVS_RUNTIME_INVOCATION_ID",
            "invocation-id");
        Console.WriteLine("LANGUAGE_CLOSURE_CSHARP_ABI_CANONICAL_ID=PASS");

        ExpectCode(
            () => new DelegateTevScriptCapability(
                " debug.log",
                arguments => TevScriptValue.Unit()),
            "TEVS_RUNTIME_CAPABILITY_BINDING_ID",
            "delegate-capability-binding-id");
        ExpectCode(
            () => new TevScriptRuntime(
                program,
                new ITevScriptCapability[] { new InvalidCapability() }),
            "TEVS_RUNTIME_CAPABILITY_BINDING_ID",
            "runtime-capability-binding-id");
        Console.WriteLine("LANGUAGE_CLOSURE_CSHARP_CAPABILITY_BINDING_ID=PASS");
        Console.WriteLine("TEV_SCRIPT_LANGUAGE_CLOSURE_CSHARP=PASS");
    }

    private static JsonObject SelectedHandler(
        JsonObject program,
        string entityId,
        string eventId)
    {
        JsonObject entity = program["entities"].AsArray()
            .Select(item => item.AsObject())
            .Single(item => item["entity_id"].GetValue<string>() == entityId);
        return entity["handlers"].AsArray()
            .Select(item => item.AsObject())
            .Single(item => item["event_id"].GetValue<string>() == eventId);
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

    private sealed class InvalidCapability : ITevScriptCapability
    {
        public string CapabilityId { get { return " debug.log"; } }

        public TevScriptValue Invoke(IReadOnlyList<TevScriptValue> arguments)
        {
            return TevScriptValue.Unit();
        }
    }

    private static void ExpectCode(Action action, string expected, string id)
    {
        try
        {
            action();
        }
        catch (TevContractException error)
        {
            if (error.Diagnostic.Code == expected) return;
            throw new InvalidOperationException(
                id + ": expected " + expected +
                ", got " + error.Diagnostic.Code + ".",
                error);
        }
        throw new InvalidOperationException(
            "Negative case was accepted: " + id + ".");
    }
}
