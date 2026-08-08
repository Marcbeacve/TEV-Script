using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;

namespace TevScript.Core.V3;

public sealed class TevScriptRuntimeCheckpointV2
{
    public const string Schema = "TEV_SCRIPT_RUNTIME_CHECKPOINT_V2";
    private static readonly Regex Local = new("^[A-Za-z_][A-Za-z0-9_]*$", RegexOptions.CultureInvariant | RegexOptions.NonBacktracking);
    private static readonly Regex Sha = new("^[0-9a-f]{64}$", RegexOptions.CultureInvariant | RegexOptions.NonBacktracking);

    private sealed record StateEntry(string Name, string TypeId, JsonElement Value);
    private sealed record EntityEntry(string EntityId, IReadOnlyList<StateEntry> State);
    private readonly IReadOnlyList<EntityEntry> _entities;

    private TevScriptRuntimeCheckpointV2(
        string programId,
        string irSchema,
        string semanticHash,
        string sourceSchema,
        string sourceSemanticHash,
        IReadOnlyList<EntityEntry> entities)
    {
        ProgramId = programId;
        IrSchema = irSchema;
        SemanticHash = semanticHash;
        SourceSchema = sourceSchema;
        SourceSemanticHash = sourceSemanticHash;
        _entities = entities;
    }

    public string ProgramId { get; }
    public string IrSchema { get; }
    public string SemanticHash { get; }
    public string SourceSchema { get; }
    public string SourceSemanticHash { get; }
    public string CheckpointHash => TevScriptCanonicalV3.Sha256Text(ToCanonicalJson());

    public static TevScriptRuntimeCheckpointV2 Capture(TevScriptRuntimeV3 runtime)
    {
        ArgumentNullException.ThrowIfNull(runtime);
        var ir = runtime.IrForCheckpoint;
        var entities = new List<EntityEntry>();
        foreach (var entityId in runtime.EntityIdsForCheckpoint)
        {
            var values = runtime.State(entityId);
            var types = runtime.StateTypesForCheckpoint(entityId);
            var state = new List<StateEntry>();
            foreach (var stateName in types.Keys.OrderBy(item => item, StringComparer.Ordinal))
            {
                var typeId = types[stateName];
                var canonical = TevScriptValueCodecV3.EncodeCanonical(
                    typeId,
                    values[stateName],
                    runtime.TypeTable,
                    $"checkpoint {entityId}.{stateName}");
                state.Add(new StateEntry(
                    stateName,
                    typeId,
                    TevScriptStrictJsonV3.ParseElement(canonical)));
            }
            entities.Add(new EntityEntry(entityId, state.AsReadOnly()));
        }
        return new TevScriptRuntimeCheckpointV2(
            runtime.ProgramId,
            ir.GetProperty("schema").GetString()!,
            runtime.SemanticHash,
            ir.GetProperty("source_schema").GetString()!,
            runtime.SourceSemanticHash,
            entities.AsReadOnly());
    }

    public static TevScriptRuntimeCheckpointV2 Parse(string text)
    {
        ArgumentNullException.ThrowIfNull(text);
        var root = TevScriptStrictJsonV3.ParseElement(text);
        if (!string.Equals(TevScriptCanonicalV3.Json(root), text, StringComparison.Ordinal))
            throw new TevScriptV3Exception(
                "TEVS_CHECKPOINT_V2_CANONICAL",
                "runtime checkpoint must use exact canonical JSON bytes");
        RequireObject(root, "$");
        RequireExactKeys(root, "$", new[]
        {
            "schema", "program_id", "ir_schema", "semantic_hash",
            "source_schema", "source_semantic_hash", "entities",
        });
        if (RequireString(root.GetProperty("schema"), "$.schema") != Schema)
            Fail("TEVS_CHECKPOINT_V2_SCHEMA", "$.schema", $"expected {Schema}");
        var programId = RequireLocal(root.GetProperty("program_id"), "$.program_id");
        var irSchema = RequireString(root.GetProperty("ir_schema"), "$.ir_schema");
        if (irSchema != "TEV_SCRIPT_PROGRAM_IR_V3")
            Fail("TEVS_CHECKPOINT_V2_IR_SCHEMA", "$.ir_schema", "expected TEV_SCRIPT_PROGRAM_IR_V3");
        var semanticHash = RequireSha(root.GetProperty("semantic_hash"), "$.semantic_hash");
        var sourceSchema = RequireString(root.GetProperty("source_schema"), "$.source_schema");
        if (sourceSchema is not ("TEV_SCRIPT_LINKED_PROGRAM_V1" or "TEV_SCRIPT_PROGRAM_IR_V2"))
            Fail("TEVS_CHECKPOINT_V2_SOURCE_SCHEMA", "$.source_schema", $"unsupported source schema {sourceSchema}");
        var sourceHash = RequireSha(root.GetProperty("source_semantic_hash"), "$.source_semantic_hash");

        var rawEntities = root.GetProperty("entities");
        if (rawEntities.ValueKind != JsonValueKind.Array)
            Fail("TEVS_CHECKPOINT_V2_SHAPE", "$.entities", "expected array");
        var entities = new List<EntityEntry>();
        string? previousEntity = null;
        var seen = new HashSet<string>(StringComparer.Ordinal);
        var entityIndex = 0;
        foreach (var rawEntity in rawEntities.EnumerateArray())
        {
            var path = $"$.entities[{entityIndex++}]";
            RequireObject(rawEntity, path);
            RequireExactKeys(rawEntity, path, new[] { "entity_id", "state" });
            var entityId = RequireLocal(rawEntity.GetProperty("entity_id"), path + ".entity_id");
            if (!seen.Add(entityId) || (previousEntity is not null && string.CompareOrdinal(previousEntity, entityId) >= 0))
                Fail("TEVS_CHECKPOINT_V2_ENTITY_ORDER", path + ".entity_id", "entities must be unique and strictly sorted");
            previousEntity = entityId;
            var rawState = rawEntity.GetProperty("state");
            RequireObject(rawState, path + ".state");
            var state = new List<StateEntry>();
            foreach (var property in rawState.EnumerateObject().OrderBy(item => item.Name, StringComparer.Ordinal))
            {
                if (!Local.IsMatch(property.Name))
                    Fail("TEVS_CHECKPOINT_V2_IDENTIFIER", path + ".state key", $"expected identifier, got {property.Name}");
                RequireObject(property.Value, path + ".state." + property.Name);
                RequireExactKeys(property.Value, path + ".state." + property.Name, new[] { "type", "value" });
                state.Add(new StateEntry(
                    property.Name,
                    RequireString(property.Value.GetProperty("type"), path + ".state." + property.Name + ".type"),
                    property.Value.GetProperty("value").Clone()));
            }
            entities.Add(new EntityEntry(entityId, state.AsReadOnly()));
        }
        return new TevScriptRuntimeCheckpointV2(
            programId,
            irSchema,
            semanticHash,
            sourceSchema,
            sourceHash,
            entities.AsReadOnly());
    }

    public string ToCanonicalJson()
    {
        using var stream = new MemoryStream();
        using (var writer = new Utf8JsonWriter(stream, new JsonWriterOptions { Indented = false, SkipValidation = false }))
        {
            writer.WriteStartObject();
            writer.WritePropertyName("entities");
            writer.WriteStartArray();
            foreach (var entity in _entities)
            {
                writer.WriteStartObject();
                writer.WriteString("entity_id", entity.EntityId);
                writer.WritePropertyName("state");
                writer.WriteStartObject();
                foreach (var state in entity.State.OrderBy(item => item.Name, StringComparer.Ordinal))
                {
                    writer.WritePropertyName(state.Name);
                    writer.WriteStartObject();
                    writer.WriteString("type", state.TypeId);
                    writer.WritePropertyName("value");
                    state.Value.WriteTo(writer);
                    writer.WriteEndObject();
                }
                writer.WriteEndObject();
                writer.WriteEndObject();
            }
            writer.WriteEndArray();
            writer.WriteString("ir_schema", IrSchema);
            writer.WriteString("program_id", ProgramId);
            writer.WriteString("schema", Schema);
            writer.WriteString("semantic_hash", SemanticHash);
            writer.WriteString("source_schema", SourceSchema);
            writer.WriteString("source_semantic_hash", SourceSemanticHash);
            writer.WriteEndObject();
        }
        var raw = Encoding.UTF8.GetString(stream.ToArray());
        return TevScriptCanonicalV3.Json(TevScriptStrictJsonV3.ParseElement(raw));
    }

    public TevScriptRuntimeV3 RestoreExact(
        JsonElement ir,
        IReadOnlyDictionary<string, TevScriptCapabilityV3>? capabilities = null)
    {
        var target = ir.Clone();
        var table = TevScriptProgramValidatorV3.Validate(target, SourceSemanticHash);
        if (target.GetProperty("program_id").GetString() != ProgramId)
            Fail("TEVS_CHECKPOINT_V2_PROGRAM_ID", "$.program_id", "checkpoint program id does not match target");
        if (target.GetProperty("schema").GetString() != IrSchema)
            Fail("TEVS_CHECKPOINT_V2_IR_SCHEMA", "$.ir_schema", "checkpoint IR schema does not match target");
        if (target.GetProperty("semantic_hash").GetString() != SemanticHash)
            Fail("TEVS_CHECKPOINT_V2_SEMANTIC_HASH", "$.semantic_hash", "checkpoint semantic hash does not match target");
        if (target.GetProperty("source_schema").GetString() != SourceSchema)
            Fail("TEVS_CHECKPOINT_V2_SOURCE_SCHEMA", "$.source_schema", "checkpoint source schema does not match target");
        if (target.GetProperty("source_semantic_hash").GetString() != SourceSemanticHash)
            Fail("TEVS_CHECKPOINT_V2_SOURCE_HASH", "$.source_semantic_hash", "checkpoint source hash does not match target");

        var expectedEntities = target.GetProperty("entities").EnumerateArray().ToDictionary(
            item => item.GetProperty("entity_id").GetString()!,
            item => item,
            StringComparer.Ordinal);
        var checkpointEntities = _entities.ToDictionary(item => item.EntityId, item => item, StringComparer.Ordinal);
        if (expectedEntities.Count != checkpointEntities.Count || expectedEntities.Keys.Any(id => !checkpointEntities.ContainsKey(id)))
            Fail("TEVS_CHECKPOINT_V2_ENTITY_SET", "$.entities", "checkpoint entity set does not exactly match target");

        var decoded = new Dictionary<string, IReadOnlyDictionary<string, TevScriptValueV3>>(StringComparer.Ordinal);
        foreach (var entityId in expectedEntities.Keys.OrderBy(item => item, StringComparer.Ordinal))
        {
            var definition = expectedEntities[entityId];
            var expectedStates = definition.GetProperty("states").EnumerateArray().ToDictionary(
                item => item.GetProperty("name").GetString()!,
                item => item.GetProperty("type").GetString()!,
                StringComparer.Ordinal);
            var checkpointState = checkpointEntities[entityId].State.ToDictionary(item => item.Name, item => item, StringComparer.Ordinal);
            if (expectedStates.Count != checkpointState.Count || expectedStates.Keys.Any(name => !checkpointState.ContainsKey(name)))
                Fail("TEVS_CHECKPOINT_V2_STATE_SET", $"entity {entityId}", "checkpoint state set does not exactly match target");
            var values = new Dictionary<string, TevScriptValueV3>(StringComparer.Ordinal);
            foreach (var stateName in expectedStates.Keys.OrderBy(item => item, StringComparer.Ordinal))
            {
                var expectedType = expectedStates[stateName];
                var observed = checkpointState[stateName];
                if (observed.TypeId != expectedType)
                    Fail("TEVS_CHECKPOINT_V2_STATE_TYPE", $"{entityId}.{stateName}", $"expected {expectedType}, got {observed.TypeId}");
                values.Add(
                    stateName,
                    TevScriptValueCodecV3.Decode(
                        expectedType,
                        observed.Value,
                        table,
                        $"checkpoint {entityId}.{stateName}"));
            }
            decoded.Add(entityId, values);
        }

        var runtime = new TevScriptRuntimeV3(target, capabilities, SourceSemanticHash);
        foreach (var pair in decoded)
            runtime.RestoreStateForCheckpoint(pair.Key, pair.Value);
        return runtime;
    }

    private static void RequireObject(JsonElement value, string path)
    {
        if (value.ValueKind != JsonValueKind.Object)
            Fail("TEVS_CHECKPOINT_V2_SHAPE", path, "expected object");
    }

    private static void RequireExactKeys(JsonElement value, string path, IEnumerable<string> expected)
    {
        var observed = value.EnumerateObject().Select(item => item.Name).OrderBy(item => item, StringComparer.Ordinal).ToArray();
        var wanted = expected.OrderBy(item => item, StringComparer.Ordinal).ToArray();
        if (!observed.SequenceEqual(wanted, StringComparer.Ordinal))
            Fail("TEVS_CHECKPOINT_V2_SHAPE", path, $"field set mismatch; expected={string.Join(",", wanted)}, observed={string.Join(",", observed)}");
    }

    private static string RequireString(JsonElement value, string path)
    {
        if (value.ValueKind != JsonValueKind.String)
            Fail("TEVS_CHECKPOINT_V2_SHAPE", path, "expected string");
        return value.GetString()!;
    }

    private static string RequireLocal(JsonElement value, string path)
    {
        var result = RequireString(value, path);
        if (!Local.IsMatch(result))
            Fail("TEVS_CHECKPOINT_V2_IDENTIFIER", path, $"expected identifier, got {result}");
        return result;
    }

    private static string RequireSha(JsonElement value, string path)
    {
        var result = RequireString(value, path);
        if (!Sha.IsMatch(result))
            Fail("TEVS_CHECKPOINT_V2_SHA256", path, "expected lowercase SHA-256");
        return result;
    }

    private static void Fail(string code, string path, string message) =>
        throw new TevScriptV3Exception(code, $"{path}: {message}");
}
