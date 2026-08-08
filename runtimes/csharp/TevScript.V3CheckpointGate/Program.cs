using System.Text.Json;
using System.Text.Json.Nodes;
using TevScript.Core.V3;

static JsonElement LoadProgram(string casesPath)
{
    var root = TevScriptStrictJsonV3.ParseElement(File.ReadAllText(casesPath));
    return root.GetProperty("valid_program").Clone();
}

static string MutateCheckpoint(
    TevScriptRuntimeCheckpointV2 checkpoint,
    Action<JsonObject> mutation)
{
    var node = JsonNode.Parse(checkpoint.ToCanonicalJson())?.AsObject()
        ?? throw new InvalidOperationException("checkpoint parse failed");
    mutation(node);
    var element = TevScriptStrictJsonV3.ParseElement(node.ToJsonString());
    return TevScriptCanonicalV3.Json(element);
}

static void ExpectCode(string expected, Action action)
{
    try
    {
        action();
        throw new InvalidOperationException($"expected {expected}, observed ACCEPTED");
    }
    catch (TevScriptV3Exception error) when (error.Code == expected)
    {
    }
}

static int SelfTest(string casesPath)
{
    var program = LoadProgram(casesPath);
    var runtime = new TevScriptRuntimeV3(program);
    runtime.Invoke("E", "start");
    var checkpoint = TevScriptRuntimeCheckpointV2.Capture(runtime);
    var bytes = checkpoint.ToCanonicalJson();
    var parsed = TevScriptRuntimeCheckpointV2.Parse(bytes);
    if (!StringComparer.Ordinal.Equals(parsed.ToCanonicalJson(), bytes))
        throw new InvalidOperationException("checkpoint canonical roundtrip mismatch");
    if (!StringComparer.Ordinal.Equals(parsed.CheckpointHash, checkpoint.CheckpointHash))
        throw new InvalidOperationException("checkpoint hash roundtrip mismatch");

    var restored = parsed.RestoreExact(program);
    if (!StringComparer.Ordinal.Equals(restored.CanonicalStateJson("E"), runtime.CanonicalStateJson("E")))
        throw new InvalidOperationException("checkpoint restored state mismatch");
    var events = restored.Invoke("E", "update");
    if (events.Count != 1 || events[0].EventId != "changed")
        throw new InvalidOperationException("checkpoint continuation event mismatch");

    ExpectCode("TEVS_CHECKPOINT_V2_CANONICAL", () =>
        TevScriptRuntimeCheckpointV2.Parse(bytes + "\n"));

    var hashTamper = TevScriptRuntimeCheckpointV2.Parse(MutateCheckpoint(checkpoint, root =>
        root["semantic_hash"] = new string('0', 64)));
    ExpectCode("TEVS_CHECKPOINT_V2_SEMANTIC_HASH", () =>
        hashTamper.RestoreExact(program));

    var typeTamper = TevScriptRuntimeCheckpointV2.Parse(MutateCheckpoint(checkpoint, root =>
        root["entities"]![0]!["state"]!["opt"]!["type"] = "Int"));
    ExpectCode("TEVS_CHECKPOINT_V2_STATE_TYPE", () =>
        typeTamper.RestoreExact(program));

    var valueTamper = TevScriptRuntimeCheckpointV2.Parse(MutateCheckpoint(checkpoint, root =>
        root["entities"]![0]!["state"]!["opt"]!["value"]!["$option"]!["type"] = "Option<Rat>"));
    ExpectCode("TEVS_IR_V3_VALUE_INVALID", () =>
        valueTamper.RestoreExact(program));

    Console.WriteLine("CSHARP_IR_V3_CHECKPOINT_CAPTURE=PASS");
    Console.WriteLine("CSHARP_IR_V3_CHECKPOINT_CANONICAL_ROUNDTRIP=PASS");
    Console.WriteLine("CSHARP_IR_V3_CHECKPOINT_RESTORE_CONTINUATION=PASS");
    Console.WriteLine("CSHARP_IR_V3_CHECKPOINT_TAMPER=PASS");
    Console.WriteLine("CSHARP_IR_V3_CHECKPOINT_HASH=" + checkpoint.CheckpointHash);
    return 0;
}

try
{
    if (args.Length == 2 && args[0] == "--self-test")
        return SelfTest(args[1]);
    if (args.Length == 2 && args[0] == "--capture")
    {
        var program = LoadProgram(args[1]);
        var runtime = new TevScriptRuntimeV3(program);
        runtime.Invoke("E", "start");
        Console.Out.Write(TevScriptRuntimeCheckpointV2.Capture(runtime).ToCanonicalJson());
        return 0;
    }
    Console.Error.WriteLine("usage: TevScript.V3CheckpointGate --self-test <validator-cases.json>");
    Console.Error.WriteLine("   or: TevScript.V3CheckpointGate --capture <validator-cases.json>");
    return 2;
}
catch (TevScriptV3Exception error)
{
    Console.Error.WriteLine(error.Code + ": " + error.Message);
    return 1;
}
catch (Exception error)
{
    Console.Error.WriteLine(error.GetType().Name + ": " + error.Message);
    return 1;
}
