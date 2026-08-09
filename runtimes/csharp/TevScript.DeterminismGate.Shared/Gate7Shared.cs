using System;
using System.Collections.Generic;
using System.Globalization;
using System.Numerics;
using System.Text;
using System.Text.Json.Nodes;
using Marcbeacve.TevScript.Core;
using Marcbeacve.TevScript.Update;

internal sealed class Gate7TraceSession
{
    private readonly List<JsonNode> _trace = new List<JsonNode>();

    public IReadOnlyList<JsonNode> Trace { get { return _trace; } }

    public void Clear()
    {
        _trace.Clear();
    }

    public ITevScriptCapability[] CreateCapabilities()
    {
        return new ITevScriptCapability[]
        {
            new DelegateTevScriptCapability(
                "debug.log",
                arguments =>
                {
                    AddTrace("debug.log", arguments, TevScriptValue.Unit());
                    return TevScriptValue.Unit();
                }),
            new DelegateTevScriptCapability(
                "input.move2d",
                arguments =>
                {
                    TevScriptValue result = TevScriptValue.Vec2(
                        TevRational.One,
                        TevRational.Zero);
                    AddTrace("input.move2d", arguments, result);
                    return result;
                }),
            new DelegateTevScriptCapability(
                "motion.move2d",
                arguments =>
                {
                    AddTrace("motion.move2d", arguments, TevScriptValue.Unit());
                    return TevScriptValue.Unit();
                }),
            new DelegateTevScriptCapability(
                "animation.play",
                arguments =>
                {
                    AddTrace("animation.play", arguments, TevScriptValue.Unit());
                    return TevScriptValue.Unit();
                })
        };
    }

    private void AddTrace(
        string capabilityId,
        IReadOnlyList<TevScriptValue> arguments,
        TevScriptValue result)
    {
        var rawArguments = new JsonArray();
        for (int index = 0; index < arguments.Count; index++)
            rawArguments.Add(Gate7Shared.EncodeValue(arguments[index]));

        JsonNode encodedResult =
            result.TypeName == "Unit"
                ? null
                : Gate7Shared.EncodeValue(result);

        _trace.Add(
            new JsonObject
            {
                [ "capability_id" ] = Gate7Shared.StringNode(capabilityId),
                [ "arguments" ] = rawArguments,
                [ "result" ] = encodedResult
            });
    }
}

internal sealed class Gate7CheckpointFreshResult
{
    public Gate7CheckpointFreshResult(
        string checkpointJson,
        string continuationReceipt)
    {
        CheckpointJson = checkpointJson;
        ContinuationReceipt = continuationReceipt;
    }

    public string CheckpointJson { get; }
    public string ContinuationReceipt { get; }
}

internal sealed class Gate7MemoryInstalledUpdateStore :
    ITevInstalledUpdateStore
{
    private TevInstalledUpdateRecord _record;

    public TevInstalledUpdateRecord Load(string channelId)
    {
        if (_record == null) return null;
        if (!string.Equals(
                _record.ChannelId,
                channelId,
                StringComparison.Ordinal))
        {
            throw new TevContractException(
                "TEVS_GATE7_STORE_CHANNEL",
                "Gate-7 in-memory record belongs to another channel.");
        }
        return _record;
    }

    public void Save(TevInstalledUpdateRecord record)
    {
        _record = record ??
            throw new ArgumentNullException(nameof(record));
    }
}

internal static class Gate7Shared
{
    public const int CheckpointStepCount = 5;
    public const int DivergenceStepOneBased = 7;

    private readonly struct Step
    {
        public Step(string eventId, int damage)
        {
            EventId = eventId;
            Damage = damage;
        }

        public string EventId { get; }
        public int Damage { get; }
    }

    private static readonly Step[] Steps =
    {
        new Step("start", 0),
        new Step("update", 0),
        new Step("damage", 7),
        new Step("update", 0),
        new Step("damage", 13),
        new Step("update", 0),
        new Step("damage", 30),
        new Step("damage", 49),
        new Step("damage", 1),
        new Step("update", 0)
    };

    public static string RunFullConformanceReceipt(
        string programJson,
        string scenarioJson)
    {
        return TevScriptConformance.RunCanonicalReceipt(
            programJson,
            scenarioJson);
    }

    public static Gate7CheckpointFreshResult RunCheckpointFresh(
        string programJson)
    {
        TevScriptProgram program = TevScriptProgram.Parse(programJson);
        var trace = new Gate7TraceSession();
        var runtime = new TevScriptRuntime(
            program,
            trace.CreateCapabilities());

        var ignoredEvents = new List<TevScriptEvent>();
        RunSteps(
            runtime,
            0,
            CheckpointStepCount,
            ignoredEvents);

        TevScriptRuntimeCheckpoint checkpoint =
            TevScriptRuntimeCheckpoint.Capture(runtime);
        string checkpointJson = checkpoint.ToCanonicalJson();

        trace.Clear();
        var suffixEvents = new List<TevScriptEvent>();
        RunSteps(
            runtime,
            CheckpointStepCount,
            Steps.Length,
            suffixEvents);

        string receipt = BuildContinuationReceipt(
            checkpoint,
            TevScriptRuntimeCheckpoint.Capture(runtime),
            suffixEvents,
            trace.Trace);

        return new Gate7CheckpointFreshResult(
            checkpointJson,
            receipt);
    }

    public static string RunCheckpointRestore(
        string programJson,
        string checkpointJson)
    {
        TevScriptProgram program = TevScriptProgram.Parse(programJson);
        TevScriptRuntimeCheckpoint checkpoint =
            TevScriptRuntimeCheckpoint.Parse(checkpointJson);

        var trace = new Gate7TraceSession();
        TevScriptRuntime runtime = checkpoint.RestoreExact(
            program,
            trace.CreateCapabilities());

        var suffixEvents = new List<TevScriptEvent>();
        RunSteps(
            runtime,
            CheckpointStepCount,
            Steps.Length,
            suffixEvents);

        return BuildContinuationReceipt(
            checkpoint,
            TevScriptRuntimeCheckpoint.Capture(runtime),
            suffixEvents,
            trace.Trace);
    }

    public static string RunSignedUpdateLockstep(
        string baseProgramJson,
        string packageJson,
        string authorityJson)
    {
        TevScriptProgram baseProgram =
            TevScriptProgram.Parse(baseProgramJson);

        JsonObject authorityRoot =
            (JsonObject)JsonNode.Parse(authorityJson);
        string keyId =
            authorityRoot["key_id"].GetValue<string>();
        string x =
            authorityRoot["x"].GetValue<string>();
        string y =
            authorityRoot["y"].GetValue<string>();

        var verifier = new TevManagedEcdsaP256Sha256Verifier(
            keyId,
            x,
            y);

        var trace = new Gate7TraceSession();
        var host = new TevScriptRuntimeHost(
            baseProgram,
            trace.CreateCapabilities(),
            CapabilityCeiling(baseProgram));
        var store = new Gate7MemoryInstalledUpdateStore();
        var updateAuthority = new TevScriptUpdateAuthority(
            host,
            "stable",
            verifier,
            store);

        string sourceHash = host.ActiveSemanticHash;
        TevScriptUpdatePlan plan =
            updateAuthority.Prepare(packageJson);

        if (store.Load("stable") != null ||
            !string.Equals(
                sourceHash,
                host.ActiveSemanticHash,
                StringComparison.Ordinal))
        {
            throw new InvalidOperationException(
                "Gate-7 signed update Prepare became authoritative.");
        }

        TevScriptUpdateReceipt updateReceipt =
            updateAuthority.Commit(plan);

        string replayCode = ExpectCode(
            delegate { updateAuthority.Prepare(packageJson); },
            "TEVS_CS_UPDATE_REPLAY");

        host.Invoke(
            "Player",
            "damage",
            TevScriptValue.Int(new BigInteger(10)));

        TevScriptRuntimeCheckpoint finalCheckpoint =
            TevScriptRuntimeCheckpoint.Capture(
                host.CaptureSnapshot());

        var receipt = new JsonObject
        {
            [ "schema" ] = StringNode(
                "TEV_SCRIPT_GATE7_SIGNED_UPDATE_LOCKSTEP_RECEIPT_V1"),
            [ "package_sha256" ] = StringNode(
                updateReceipt.PackageSha256),
            [ "epoch" ] = IntegerNode(updateReceipt.Epoch),
            [ "sequence" ] = IntegerNode(updateReceipt.Sequence),
            [ "generation" ] = IntegerNode(updateReceipt.Generation),
            [ "active_semantic_hash" ] = StringNode(
                host.ActiveSemanticHash),
            [ "final_checkpoint_hash" ] = StringNode(
                finalCheckpoint.CheckpointHash),
            [ "final_checkpoint" ] =
                JsonNode.Parse(finalCheckpoint.ToCanonicalJson()),
            [ "replay_rejected_code" ] = StringNode(replayCode)
        };

        return CanonicalLine(receipt);
    }

    public static string HashCanonicalLine(string canonicalLine)
    {
        if (canonicalLine == null)
            throw new ArgumentNullException(nameof(canonicalLine));
        string text = canonicalLine.EndsWith(
            "\n",
            StringComparison.Ordinal)
                ? canonicalLine.Substring(
                    0,
                    canonicalLine.Length - 1)
                : canonicalLine;
        return TevScriptCanonicalJson.Hash(text);
    }

    public static JsonNode EncodeValue(TevScriptValue value)
    {
        if (value == null)
            throw new ArgumentNullException(nameof(value));

        switch (value.TypeName)
        {
            case "Bool":
                return BooleanNode(value.AsBool());
            case "Int":
                return new JsonObject
                {
                    [ "$int" ] = StringNode(
                        value.AsInt().ToString(
                            CultureInfo.InvariantCulture))
                };
            case "Rat":
                return EncodeRational(value.AsRat());
            case "Text":
                return StringNode(value.AsText());
            case "Vec2":
            case "Vec3":
                var vector = new JsonArray();
                foreach (TevRational item in value.AsVector())
                    vector.Add(EncodeRational(item));
                return vector;
            case "Unit":
                return null;
            default:
                throw new InvalidOperationException(
                    "Unsupported Gate-7 value type " +
                    value.TypeName + ".");
        }
    }

    public static string[] CapabilityCeiling(
        TevScriptProgram program)
    {
        var result = new List<string>();
        foreach (TevScriptEntityDefinition entity
                 in program.Entities)
        {
            foreach (string capabilityId
                     in entity.Capabilities.Keys)
            {
                if (!result.Contains(capabilityId))
                    result.Add(capabilityId);
            }
        }
        return result.ToArray();
    }

    private static JsonObject EncodeRational(
        TevRational value)
    {
        var parts = new JsonArray();
        parts.Add(StringNode(value.Numerator.ToString(
            CultureInfo.InvariantCulture)));
        parts.Add(StringNode(value.Denominator.ToString(
            CultureInfo.InvariantCulture)));
        return new JsonObject
        {
            [ "$rat" ] = parts
        };
    }

    private static void RunSteps(
        TevScriptRuntime runtime,
        int start,
        int end,
        List<TevScriptEvent> observedEvents)
    {
        for (int index = start; index < end; index++)
        {
            Step step = Steps[index];
            IReadOnlyList<TevScriptEvent> emitted;
            if (step.EventId == "damage")
            {
                emitted = runtime.Invoke(
                    "Player",
                    "damage",
                    TevScriptValue.Int(
                        new BigInteger(step.Damage)));
            }
            else
            {
                emitted = runtime.Invoke(
                    "Player",
                    step.EventId);
            }

            foreach (TevScriptEvent item in emitted)
                observedEvents.Add(item);
        }
    }

    private static string BuildContinuationReceipt(
        TevScriptRuntimeCheckpoint sourceCheckpoint,
        TevScriptRuntimeCheckpoint finalCheckpoint,
        IReadOnlyList<TevScriptEvent> events,
        IReadOnlyList<JsonNode> trace)
    {
        var rawEvents = new JsonArray();
        foreach (TevScriptEvent item in events)
        {
            var arguments = new JsonArray();
            foreach (TevScriptValue argument in item.Arguments)
                arguments.Add(EncodeValue(argument));

            rawEvents.Add(
                new JsonObject
                {
                    [ "entity_id" ] = StringNode(item.EntityId),
                    [ "event_id" ] = StringNode(item.EventId),
                    [ "arguments" ] = arguments
                });
        }

        var rawTrace = new JsonArray();
        foreach (JsonNode item in trace)
            rawTrace.Add(item.DeepClone());

        var receipt = new JsonObject
        {
            [ "schema" ] = StringNode(
                "TEV_SCRIPT_GATE7_CHECKPOINT_CONTINUATION_RECEIPT_V1"),
            [ "source_checkpoint_hash" ] = StringNode(
                sourceCheckpoint.CheckpointHash),
            [ "final_checkpoint_hash" ] = StringNode(
                finalCheckpoint.CheckpointHash),
            [ "final_checkpoint" ] =
                JsonNode.Parse(finalCheckpoint.ToCanonicalJson()),
            [ "suffix_events" ] = rawEvents,
            [ "capability_trace" ] = rawTrace
        };

        return CanonicalLine(receipt);
    }

    private static JsonNode BooleanNode(bool value)
    {
        return JsonNode.Parse(value ? "true" : "false");
    }

    private static JsonNode IntegerNode(long value)
    {
        return JsonNode.Parse(value.ToString(
            CultureInfo.InvariantCulture));
    }

    internal static JsonNode StringNode(string value)
    {
        if (value == null)
            throw new ArgumentNullException(nameof(value));
        return JsonNode.Parse(QuoteJsonString(value));
    }

    private static string QuoteJsonString(string value)
    {
        var result = new StringBuilder(value.Length + 2);
        result.Append('"');
        for (int index = 0; index < value.Length; index++)
        {
            char unit = value[index];
            switch (unit)
            {
                case '"': result.Append("\\\""); break;
                case '\\': result.Append("\\\\"); break;
                case '\b': result.Append("\\b"); break;
                case '\f': result.Append("\\f"); break;
                case '\n': result.Append("\\n"); break;
                case '\r': result.Append("\\r"); break;
                case '\t': result.Append("\\t"); break;
                default:
                    if (unit < 0x20 || unit > 0x7e)
                    {
                        result.Append("\\u");
                        result.Append(((int)unit).ToString(
                            "x4",
                            CultureInfo.InvariantCulture));
                    }
                    else
                    {
                        result.Append(unit);
                    }
                    break;
            }
        }
        result.Append('"');
        return result.ToString();
    }

    private static string CanonicalLine(JsonNode node)
    {
        return TevScriptCanonicalJson.Canonicalize(
            node.ToJsonString()) + "\n";
    }

    private static string ExpectCode(
        Action action,
        string expectedCode)
    {
        try
        {
            action();
        }
        catch (TevContractException exception)
        {
            if (exception.Diagnostic.Code == expectedCode)
                return expectedCode;
            throw;
        }

        throw new InvalidOperationException(
            "Expected TEV failure " + expectedCode + ".");
    }
}
