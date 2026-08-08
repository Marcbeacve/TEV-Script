using System.Text.Json;
using System.Text.RegularExpressions;

namespace TevScript.Core.V3;

public sealed record TevScriptV3ConformanceReceipt(
    JsonElement Receipt,
    string CanonicalJson,
    string ReceiptHash);

public static class TevScriptV3Conformance
{
    private static readonly Regex Stable = new("^[A-Za-z_][A-Za-z0-9_.:/-]*$", RegexOptions.CultureInvariant | RegexOptions.NonBacktracking);
    private static readonly Regex Local = new("^[A-Za-z_][A-Za-z0-9_]*$", RegexOptions.CultureInvariant | RegexOptions.NonBacktracking);
    private static readonly Regex Hash = new("^[0-9a-f]{64}$", RegexOptions.CultureInvariant | RegexOptions.NonBacktracking);

    private sealed record CapabilityContract(string[] Parameters, string ReturnType, string Kind);

    private sealed class ScriptedCapability
    {
        public required string Id { get; init; }
        public required string[] Parameters { get; init; }
        public required string ReturnType { get; init; }
        public required JsonElement[] Calls { get; init; }
        public int Cursor { get; set; }
    }

    private sealed class ScenarioHost
    {
        private TevScriptRuntimeV3 _runtime;
        private readonly Dictionary<string, ScriptedCapability> _scripts;
        private readonly List<object?> _transcript = new();

        public ScenarioHost(TevScriptRuntimeV3 runtime, JsonElement capabilityScripts)
        {
            _runtime = runtime;
            var contracts = GlobalCapabilityContracts(runtimeProgram: runtime);
            _scripts = new Dictionary<string, ScriptedCapability>(StringComparer.Ordinal);
            string? previousId = null;
            var index = 0;
            foreach (var raw in capabilityScripts.EnumerateArray())
            {
                var path = $"$.capabilities[{index++}]";
                RequireExactKeys(raw, path, "capability_id", "calls");
                var id = RequireStable(raw.GetProperty("capability_id"), path + ".capability_id");
                if (_scripts.ContainsKey(id)) Fail("TEVS_IR_V3_CONFORMANCE_CAPABILITY_DUPLICATE", path, $"duplicate capability script {id}");
                if (previousId is not null && StringComparer.Ordinal.Compare(id, previousId) <= 0)
                    Fail("TEVS_IR_V3_CONFORMANCE_CAPABILITY_ORDER", path, "capability scripts must be strictly sorted by id");
                previousId = id;
                if (!contracts.TryGetValue(id, out var contract))
                {
                    Fail("TEVS_IR_V3_CONFORMANCE_CAPABILITY_UNKNOWN", path, $"scenario scripts undeclared capability {id}");
                    continue;
                }
                var callsRaw = raw.GetProperty("calls");
                if (callsRaw.ValueKind != JsonValueKind.Array || callsRaw.GetArrayLength() > 4096)
                    Fail("TEVS_IR_V3_CONFORMANCE_SHAPE", path + ".calls", "expected array length in [0,4096]");
                var calls = callsRaw.EnumerateArray().Select(item => item.Clone()).ToArray();
                for (var callIndex = 0; callIndex < calls.Length; ++callIndex)
                    ValidateScriptedCall(calls[callIndex], contract, runtime, $"{path}.calls[{callIndex}]");
                _scripts[id] = new ScriptedCapability
                {
                    Id = id,
                    Parameters = contract.Parameters,
                    ReturnType = contract.ReturnType,
                    Calls = calls,
                    Cursor = 0,
                };
            }
        }

        public void BindRuntime(TevScriptRuntimeV3 runtime) => _runtime = runtime;

        public IReadOnlyDictionary<string, TevScriptCapabilityV3> Bindings() =>
            _scripts.ToDictionary(
                pair => pair.Key,
                pair => (TevScriptCapabilityV3)(arguments => Invoke(pair.Value, arguments)),
                StringComparer.Ordinal);

        public IReadOnlyList<object?> Transcript => _transcript.AsReadOnly();

        public void VerifyConsumed()
        {
            var pending = _scripts
                .Where(pair => pair.Value.Cursor != pair.Value.Calls.Length)
                .ToDictionary(
                    pair => pair.Key,
                    pair => pair.Value.Calls.Length - pair.Value.Cursor,
                    StringComparer.Ordinal);
            if (pending.Count != 0)
                Fail(
                    "TEVS_IR_V3_CONFORMANCE_CAPABILITY_CALL_UNDERFLOW",
                    "$.capabilities",
                    "scripted capability calls not consumed exactly: " + JsonOf(pending));
        }

        private TevScriptValueV3? Invoke(ScriptedCapability script, IReadOnlyList<TevScriptValueV3> arguments)
        {
            if (script.Cursor >= script.Calls.Length)
                Fail(
                    "TEVS_IR_V3_CONFORMANCE_CAPABILITY_CALL_OVERFLOW",
                    script.Id,
                    "runtime invoked capability more times than scripted");
            var expected = script.Calls[script.Cursor];
            var encodedArguments = new List<object?>();
            for (var index = 0; index < script.Parameters.Length; ++index)
            {
                encodedArguments.Add(new Dictionary<string, object?>
                {
                    ["type"] = script.Parameters[index],
                    ["value"] = TevScriptValueCodecV3.EncodeElement(
                        script.Parameters[index],
                        arguments[index],
                        _runtime.TypeTable,
                        $"capability {script.Id} argument {index}"),
                });
            }
            var actualArgumentsElement = ElementOf(encodedArguments);
            if (TevScriptCanonicalV3.Json(actualArgumentsElement) != TevScriptCanonicalV3.Json(expected.GetProperty("arguments")))
                Fail(
                    "TEVS_IR_V3_CONFORMANCE_CAPABILITY_ARGUMENTS",
                    script.Id,
                    $"call {script.Cursor} arguments differ from scripted canonical values");

            var transcript = new Dictionary<string, object?>
            {
                ["index"] = _transcript.Count,
                ["capability_id"] = script.Id,
                ["arguments"] = actualArgumentsElement,
            };
            ++script.Cursor;
            if (script.ReturnType == "Unit")
            {
                if (expected.TryGetProperty("return", out _))
                    Fail("TEVS_IR_V3_CONFORMANCE_CAPABILITY_RETURN", script.Id, "Unit scripted call must not contain return");
                _transcript.Add(transcript);
                return null;
            }
            if (!expected.TryGetProperty("return", out var rawReturn))
                Fail("TEVS_IR_V3_CONFORMANCE_CAPABILITY_RETURN", script.Id, "non-Unit scripted call requires return");
            transcript["return"] = rawReturn.Clone();
            _transcript.Add(transcript);
            return TevScriptValueCodecV3.Decode(
                script.ReturnType,
                rawReturn.GetProperty("value"),
                _runtime.TypeTable,
                $"capability {script.Id} scripted return");
        }
    }

    public static TevScriptV3ConformanceReceipt Run(JsonElement ir, JsonElement scenario)
    {
        var program = ir.Clone();
        TevScriptProgramValidatorV3.Validate(program);
        var scenarioValue = scenario.Clone();
        ValidateScenario(scenarioValue, program);
        var scenarioHash = TevScriptCanonicalV3.Sha256(scenarioValue);

        var bootstrap = new TevScriptRuntimeV3(
            program,
            capabilities: null,
            expectedSourceSemanticHash: scenarioValue.GetProperty("source_semantic_hash").GetString());
        var host = new ScenarioHost(bootstrap, scenarioValue.GetProperty("capabilities"));
        var runtime = new TevScriptRuntimeV3(
            program,
            host.Bindings(),
            scenarioValue.GetProperty("source_semantic_hash").GetString());
        host.BindRuntime(runtime);

        var initialState = StateWitness(runtime, program);
        var initialStateHash = TevScriptCanonicalV3.Sha256(initialState);
        var stepReceipts = new List<object?>();
        var stepIndex = 0;
        foreach (var step in scenarioValue.GetProperty("steps").EnumerateArray())
        {
            var entityId = step.GetProperty("entity_id").GetString()!;
            var eventId = step.GetProperty("event_id").GetString()!;
            var arguments = DecodeInvocationArguments(runtime, program, entityId, eventId, step.GetProperty("arguments"));
            var emitted = runtime.Invoke(entityId, eventId, arguments.ToArray());
            var state = StateWitness(runtime, program);
            stepReceipts.Add(new Dictionary<string, object?>
            {
                ["index"] = stepIndex++,
                ["entity_id"] = entityId,
                ["event_id"] = eventId,
                ["emitted"] = emitted.Select(value => EventWitness(value, runtime)).ToArray(),
                ["state_hash"] = TevScriptCanonicalV3.Sha256(state),
            });
        }
        host.VerifyConsumed();
        var finalState = StateWitness(runtime, program);
        var finalStateHash = TevScriptCanonicalV3.Sha256(finalState);
        var body = new Dictionary<string, object?>
        {
            ["schema"] = "TEV_SCRIPT_IR_V3_CONFORMANCE_RECEIPT_V1",
            ["scenario_id"] = scenarioValue.GetProperty("scenario_id").GetString(),
            ["scenario_hash"] = scenarioHash,
            ["program_semantic_hash"] = program.GetProperty("semantic_hash").GetString(),
            ["source_semantic_hash"] = program.GetProperty("source_semantic_hash").GetString(),
            ["initial_state_hash"] = initialStateHash,
            ["steps"] = stepReceipts,
            ["capability_calls"] = host.Transcript,
            ["final_state"] = finalState,
            ["final_state_hash"] = finalStateHash,
        };
        var bodyElement = ElementOf(body);
        var receiptHash = TevScriptCanonicalV3.Sha256(bodyElement);
        var receipt = new Dictionary<string, object?>(body, StringComparer.Ordinal)
        {
            ["receipt_hash"] = receiptHash,
        };
        var receiptElement = ElementOf(receipt);
        return new TevScriptV3ConformanceReceipt(
            receiptElement,
            TevScriptCanonicalV3.Json(receiptElement),
            receiptHash);
    }

    private static JsonElement StateWitness(TevScriptRuntimeV3 runtime, JsonElement program)
    {
        var entities = new List<object?>();
        foreach (var rawEntity in program.GetProperty("entities").EnumerateArray().OrderBy(item => item.GetProperty("entity_id").GetString(), StringComparer.Ordinal))
        {
            var entityId = rawEntity.GetProperty("entity_id").GetString()!;
            var stateValues = runtime.State(entityId);
            var typeByState = rawEntity.GetProperty("states").EnumerateArray().ToDictionary(
                item => item.GetProperty("name").GetString()!,
                item => item.GetProperty("type").GetString()!,
                StringComparer.Ordinal);
            var state = new SortedDictionary<string, object?>(StringComparer.Ordinal);
            foreach (var stateName in stateValues.Keys.OrderBy(item => item, StringComparer.Ordinal))
            {
                var typeId = typeByState[stateName];
                state[stateName] = new Dictionary<string, object?>
                {
                    ["type"] = typeId,
                    ["value"] = TevScriptValueCodecV3.EncodeElement(
                        typeId,
                        stateValues[stateName],
                        runtime.TypeTable,
                        $"state witness {entityId}.{stateName}"),
                };
            }
            entities.Add(new Dictionary<string, object?>
            {
                ["entity_id"] = entityId,
                ["state"] = state,
            });
        }
        return ElementOf(entities);
    }

    private static object EventWitness(TevScriptEmittedEventV3 emitted, TevScriptRuntimeV3 runtime)
    {
        var arguments = new List<object?>();
        for (var index = 0; index < emitted.ArgumentTypes.Count; ++index)
        {
            arguments.Add(new Dictionary<string, object?>
            {
                ["type"] = emitted.ArgumentTypes[index],
                ["value"] = TevScriptValueCodecV3.EncodeElement(
                    emitted.ArgumentTypes[index],
                    emitted.Arguments[index],
                    runtime.TypeTable,
                    $"event witness {emitted.EventId}[{index}]"),
            });
        }
        return new Dictionary<string, object?>
        {
            ["entity_id"] = emitted.EntityId,
            ["event_id"] = emitted.EventId,
            ["arguments"] = arguments,
        };
    }

    private static IReadOnlyList<TevScriptValueV3> DecodeInvocationArguments(
        TevScriptRuntimeV3 runtime,
        JsonElement program,
        string entityId,
        string eventId,
        JsonElement arguments)
    {
        var entity = program.GetProperty("entities").EnumerateArray().SingleOrDefault(item => item.GetProperty("entity_id").GetString() == entityId);
        if (entity.ValueKind == JsonValueKind.Undefined)
            Fail("TEVS_IR_V3_CONFORMANCE_ENTITY", entityId, "unknown scenario entity");
        var handler = entity.GetProperty("handlers").EnumerateArray().SingleOrDefault(item => item.GetProperty("event_id").GetString() == eventId);
        string[] expected;
        if (handler.ValueKind != JsonValueKind.Undefined)
            expected = handler.GetProperty("parameters").EnumerateArray().Select(item => item.GetProperty("type").GetString()!).ToArray();
        else
        {
            var eventValue = entity.GetProperty("emitted_events").EnumerateArray().SingleOrDefault(item => item.GetProperty("event_id").GetString() == eventId);
            if (eventValue.ValueKind == JsonValueKind.Undefined)
            {
                if (arguments.GetArrayLength() != 0)
                    Fail("TEVS_IR_V3_CONFORMANCE_EVENT_SIGNATURE", eventId, "unhandled scenario event with arguments has no portable signature");
                expected = Array.Empty<string>();
            }
            else expected = eventValue.GetProperty("parameters").EnumerateArray().Select(item => item.GetString()!).ToArray();
        }
        if (expected.Length != arguments.GetArrayLength())
            Fail("TEVS_IR_V3_CONFORMANCE_EVENT_ARITY", eventId, $"expected {expected.Length} arguments, got {arguments.GetArrayLength()}");
        var decoded = new List<TevScriptValueV3>();
        for (var index = 0; index < expected.Length; ++index)
        {
            var typed = arguments[index];
            RequireExactKeys(typed, $"scenario argument {index}", "type", "value");
            if (typed.GetProperty("type").GetString() != expected[index])
                Fail("TEVS_IR_V3_CONFORMANCE_EVENT_TYPE", eventId, $"argument {index} expected {expected[index]}, got {typed.GetProperty("type").GetString()}");
            decoded.Add(TevScriptValueCodecV3.Decode(expected[index], typed.GetProperty("value"), runtime.TypeTable, $"scenario {entityId}.{eventId}[{index}]"));
        }
        return decoded;
    }

    private static Dictionary<string, CapabilityContract> GlobalCapabilityContracts(TevScriptRuntimeV3 runtimeProgram)
    {
        var ir = runtimeProgram.IrForCheckpoint;
        var result = new Dictionary<string, CapabilityContract>(StringComparer.Ordinal);
        foreach (var entity in ir.GetProperty("entities").EnumerateArray())
        {
            foreach (var capability in entity.GetProperty("capabilities").EnumerateArray())
            {
                var id = capability.GetProperty("capability_id").GetString()!;
                var contract = new CapabilityContract(
                    capability.GetProperty("parameters").EnumerateArray().Select(item => item.GetString()!).ToArray(),
                    capability.GetProperty("return_type").GetString()!,
                    capability.GetProperty("kind").GetString()!);
                if (result.TryGetValue(id, out var previous)
                    && (previous.ReturnType != contract.ReturnType
                        || previous.Kind != contract.Kind
                        || !previous.Parameters.SequenceEqual(contract.Parameters, StringComparer.Ordinal)))
                    Fail("TEVS_IR_V3_CONFORMANCE_CAPABILITY_CONFLICT", id, "program contains conflicting capability contracts");
                result[id] = contract;
            }
        }
        return result;
    }

    private static void ValidateScriptedCall(
        JsonElement call,
        CapabilityContract contract,
        TevScriptRuntimeV3 runtime,
        string path)
    {
        RequireExactKeys(call, path, contract.ReturnType == "Unit" ? new[] { "arguments" } : new[] { "arguments", "return" });
        var arguments = call.GetProperty("arguments");
        if (arguments.ValueKind != JsonValueKind.Array || arguments.GetArrayLength() != contract.Parameters.Length)
            Fail("TEVS_IR_V3_CONFORMANCE_CAPABILITY_ARITY", path, $"expected {contract.Parameters.Length} arguments");
        for (var index = 0; index < contract.Parameters.Length; ++index)
        {
            var typed = arguments[index];
            RequireExactKeys(typed, $"{path}.arguments[{index}]", "type", "value");
            if (typed.GetProperty("type").GetString() != contract.Parameters[index])
                Fail("TEVS_IR_V3_CONFORMANCE_CAPABILITY_TYPE", path, $"argument {index} expected {contract.Parameters[index]}");
            TevScriptValueCodecV3.Decode(contract.Parameters[index], typed.GetProperty("value"), runtime.TypeTable, $"{path}.arguments[{index}]");
        }
        if (contract.ReturnType != "Unit")
        {
            var rawReturn = call.GetProperty("return");
            RequireExactKeys(rawReturn, path + ".return", "type", "value");
            if (rawReturn.GetProperty("type").GetString() != contract.ReturnType)
                Fail("TEVS_IR_V3_CONFORMANCE_CAPABILITY_RETURN_TYPE", path, $"expected return {contract.ReturnType}");
            TevScriptValueCodecV3.Decode(contract.ReturnType, rawReturn.GetProperty("value"), runtime.TypeTable, path + ".return");
        }
    }

    private static void ValidateScenario(JsonElement scenario, JsonElement program)
    {
        RequireExactKeys(scenario, "$", "schema", "scenario_id", "program_semantic_hash", "source_semantic_hash", "capabilities", "steps");
        if (scenario.GetProperty("schema").GetString() != "TEV_SCRIPT_IR_V3_SCENARIO_V1")
            Fail("TEVS_IR_V3_CONFORMANCE_SCENARIO_SCHEMA", "$.schema", "unexpected scenario schema");
        RequireStable(scenario.GetProperty("scenario_id"), "$.scenario_id");
        var programHash = RequireHash(scenario.GetProperty("program_semantic_hash"), "$.program_semantic_hash");
        var sourceHash = RequireHash(scenario.GetProperty("source_semantic_hash"), "$.source_semantic_hash");
        if (programHash != program.GetProperty("semantic_hash").GetString())
            Fail("TEVS_IR_V3_CONFORMANCE_PROGRAM_HASH", "$.program_semantic_hash", "scenario targets a different IR V3 semantic hash");
        if (sourceHash != program.GetProperty("source_semantic_hash").GetString())
            Fail("TEVS_IR_V3_CONFORMANCE_SOURCE_HASH", "$.source_semantic_hash", "scenario targets a different source semantic hash");
        var capabilities = scenario.GetProperty("capabilities");
        if (capabilities.ValueKind != JsonValueKind.Array || capabilities.GetArrayLength() > 8192)
            Fail("TEVS_IR_V3_CONFORMANCE_SHAPE", "$.capabilities", "expected array length in [0,8192]");
        var steps = scenario.GetProperty("steps");
        if (steps.ValueKind != JsonValueKind.Array || steps.GetArrayLength() > 1024)
            Fail("TEVS_IR_V3_CONFORMANCE_SHAPE", "$.steps", "expected array length in [0,1024]");
        var index = 0;
        foreach (var step in steps.EnumerateArray())
        {
            var path = $"$.steps[{index++}]";
            RequireExactKeys(step, path, "entity_id", "event_id", "arguments");
            RequireLocal(step.GetProperty("entity_id"), path + ".entity_id");
            RequireLocal(step.GetProperty("event_id"), path + ".event_id");
            if (step.GetProperty("arguments").ValueKind != JsonValueKind.Array || step.GetProperty("arguments").GetArrayLength() > 64)
                Fail("TEVS_IR_V3_CONFORMANCE_SHAPE", path + ".arguments", "expected array length in [0,64]");
        }
    }

    private static JsonElement ElementOf<T>(T value) => JsonSerializer.SerializeToElement(value);
    private static string JsonOf<T>(T value) => TevScriptCanonicalV3.Json(ElementOf(value));

    private static void RequireExactKeys(JsonElement value, string path, params string[] expected)
    {
        if (value.ValueKind != JsonValueKind.Object) Fail("TEVS_IR_V3_CONFORMANCE_SHAPE", path, "expected object");
        var observed = value.EnumerateObject().Select(item => item.Name).OrderBy(item => item, StringComparer.Ordinal).ToArray();
        var target = expected.OrderBy(item => item, StringComparer.Ordinal).ToArray();
        if (!observed.SequenceEqual(target, StringComparer.Ordinal))
            Fail("TEVS_IR_V3_CONFORMANCE_SHAPE", path, $"field set mismatch; expected=[{string.Join(',', target)}], observed=[{string.Join(',', observed)}]");
    }

    private static string RequireStable(JsonElement value, string path)
    {
        if (value.ValueKind != JsonValueKind.String || !Stable.IsMatch(value.GetString()!))
            Fail("TEVS_IR_V3_CONFORMANCE_IDENTIFIER", path, "invalid stable id");
        return value.GetString()!;
    }

    private static string RequireLocal(JsonElement value, string path)
    {
        if (value.ValueKind != JsonValueKind.String || !Local.IsMatch(value.GetString()!))
            Fail("TEVS_IR_V3_CONFORMANCE_IDENTIFIER", path, "invalid local id");
        return value.GetString()!;
    }

    private static string RequireHash(JsonElement value, string path)
    {
        if (value.ValueKind != JsonValueKind.String || !Hash.IsMatch(value.GetString()!))
            Fail("TEVS_IR_V3_CONFORMANCE_HASH", path, "expected lowercase SHA-256");
        return value.GetString()!;
    }

    private static void Fail(string code, string path, string message) => throw new TevScriptV3Exception(code, $"{path}: {message}");
}
