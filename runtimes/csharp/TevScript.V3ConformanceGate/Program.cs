using System.Text.Json;
using System.Text.Json.Nodes;
using TevScript.Core.V3;

static JsonElement ReadStrict(string path) =>
    TevScriptStrictJsonV3.ParseElement(File.ReadAllText(path));

static JsonNode ReadNode(string path) =>
    JsonNode.Parse(
        File.ReadAllText(path),
        documentOptions: new JsonDocumentOptions
        {
            AllowTrailingCommas = false,
            CommentHandling = JsonCommentHandling.Disallow,
            MaxDepth = 256,
        }) ?? throw new InvalidOperationException($"empty JSON document {path}");

static JsonNode Resolve(JsonNode root, JsonArray path)
{
    JsonNode current = root;
    foreach (var raw in path)
    {
        if (raw is null) throw new InvalidOperationException("null mutation path segment");
        if (raw.GetValueKind() == JsonValueKind.Number)
        {
            current = current.AsArray()[raw.GetValue<int>()]
                ?? throw new InvalidOperationException("missing array mutation target");
        }
        else
        {
            current = current.AsObject()[raw.GetValue<string>()]
                ?? throw new InvalidOperationException("missing object mutation target");
        }
    }
    return current;
}

static JsonNode ApplyMutation(JsonNode baseProgram, JsonObject mutation)
{
    var result = baseProgram.DeepClone();
    var path = mutation["path"]?.AsArray()
        ?? throw new InvalidOperationException("mutation path missing");
    var operation = mutation["operation"]?.GetValue<string>()
        ?? throw new InvalidOperationException("mutation operation missing");
    if (operation == "swap")
    {
        var target = Resolve(result, path).AsArray();
        var left = mutation["left"]!.GetValue<int>();
        var right = mutation["right"]!.GetValue<int>();
        var leftValue = target[left]?.DeepClone();
        var rightValue = target[right]?.DeepClone();
        target[left] = rightValue;
        target[right] = leftValue;
        return result;
    }
    if (operation == "set")
    {
        if (path.Count == 0) throw new InvalidOperationException("set mutation cannot replace root");
        var parentPath = new JsonArray();
        for (var index = 0; index < path.Count - 1; ++index)
            parentPath.Add(path[index]!.DeepClone());
        var parent = Resolve(result, parentPath);
        var last = path[^1]!;
        var replacement = mutation["value"]?.DeepClone();
        if (last.GetValueKind() == JsonValueKind.Number)
            parent.AsArray()[last.GetValue<int>()] = replacement;
        else
            parent.AsObject()[last.GetValue<string>()] = replacement;
        return result;
    }
    throw new InvalidOperationException($"unknown mutation operation {operation}");
}

static int RunSelfTest(string casesPath, string scenarioPath)
{
    var cases = ReadNode(casesPath).AsObject();
    var baseProgram = cases["valid_program"]
        ?? throw new InvalidOperationException("valid_program missing");
    var baseElement = TevScriptStrictJsonV3.ParseElement(baseProgram.ToJsonString());
    TevScriptProgramValidatorV3.Validate(baseElement, new string('1', 64));
    Console.WriteLine("CSHARP_IR_V3_VALID_PROGRAM=PASS");

    var negative = cases["negative_mutations"]?.AsArray()
        ?? throw new InvalidOperationException("negative_mutations missing");
    var checkedCount = 0;
    foreach (var rawMutation in negative)
    {
        var mutation = rawMutation?.AsObject()
            ?? throw new InvalidOperationException("invalid mutation entry");
        var id = mutation["id"]!.GetValue<string>();
        var expectedCode = mutation["code"]!.GetValue<string>();
        var mutated = ApplyMutation(baseProgram, mutation);
        try
        {
            var element = TevScriptStrictJsonV3.ParseElement(mutated.ToJsonString());
            TevScriptProgramValidatorV3.Validate(element);
            Console.Error.WriteLine($"CSHARP_IR_V3_NEGATIVE=FAIL id={id} expected={expectedCode} observed=ACCEPTED");
            return 1;
        }
        catch (TevScriptV3Exception error)
        {
            if (!StringComparer.Ordinal.Equals(error.Code, expectedCode))
            {
                Console.Error.WriteLine($"CSHARP_IR_V3_NEGATIVE=FAIL id={id} expected={expectedCode} observed={error.Code}");
                return 1;
            }
        }
        ++checkedCount;
    }
    Console.WriteLine($"CSHARP_IR_V3_NEGATIVE_CORPUS=PASS count={checkedCount}");

    var scenario = ReadStrict(scenarioPath);
    var receipt = TevScriptV3Conformance.Run(baseElement, scenario);
    Console.WriteLine("CSHARP_IR_V3_CONFORMANCE_RECEIPT=PASS");
    Console.WriteLine("CSHARP_IR_V3_RECEIPT_HASH=" + receipt.ReceiptHash);

    var checkpointRuntime = new TevScriptRuntimeV3(
        baseElement,
        capabilities: null,
        expectedSourceSemanticHash: scenario.GetProperty("source_semantic_hash").GetString());
    var checkpoint = TevScriptRuntimeCheckpointV2.Capture(checkpointRuntime);
    var checkpointReceipt = TevScriptV3Conformance.Run(baseElement, scenario, checkpoint);
    if (!StringComparer.Ordinal.Equals(receipt.CanonicalJson, checkpointReceipt.CanonicalJson))
        throw new InvalidOperationException("checkpoint-backed conformance diverged from equivalent fresh baseline");
    Console.WriteLine("CSHARP_IR_V3_CONFORMANCE_CHECKPOINT_EQUIVALENCE=PASS");
    return 0;
}

try
{
    if (args.Length == 3 && args[0] == "--self-test")
        return RunSelfTest(args[1], args[2]);
    if (args.Length != 2)
    {
        Console.Error.WriteLine("usage: TevScript.V3ConformanceGate <program.json> <scenario.json>");
        Console.Error.WriteLine("   or: TevScript.V3ConformanceGate --self-test <validator-cases.json> <scenario.json>");
        return 2;
    }
    var program = ReadStrict(args[0]);
    var scenario = ReadStrict(args[1]);
    var receipt = TevScriptV3Conformance.Run(program, scenario);
    Console.Out.Write(receipt.CanonicalJson);
    return 0;
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
