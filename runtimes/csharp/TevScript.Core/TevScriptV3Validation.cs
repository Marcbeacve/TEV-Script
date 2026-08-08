using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;

namespace TevScript.Core.V3;

public static class TevScriptProgramValidatorV3
{
    private static readonly Regex Hash = new("^[0-9a-f]{64}$", RegexOptions.CultureInvariant | RegexOptions.NonBacktracking);
    private static readonly Regex Local = new("^[A-Za-z_][A-Za-z0-9_]*$", RegexOptions.CultureInvariant | RegexOptions.NonBacktracking);
    private static readonly Regex Stable = new("^[A-Za-z_][A-Za-z0-9_.:/-]*$", RegexOptions.CultureInvariant | RegexOptions.NonBacktracking);
    private static readonly string[] RootKeys =
    {
        "schema", "language_version", "lowering_profile", "source_schema",
        "source_semantic_hash", "program_id", "types", "entities", "boundary",
        "semantic_hash", "debug", "debug_hash",
    };
    private static readonly string[] BoundaryKeys =
    {
        "dynamic_code", "reflection", "unbounded_loops", "implicit_physical_effects",
        "runtime_source_compilation", "automatic_authority_escalation",
        "host_object_references", "maximum_event_chain", "maximum_value_nesting",
    };

    public static TevScriptTypeTableV3 Validate(string json, string? expectedSourceSemanticHash = null)
    {
        var root = TevScriptStrictJsonV3.ParseElement(json);
        return Validate(root, expectedSourceSemanticHash);
    }

    public static TevScriptTypeTableV3 Validate(JsonElement root, string? expectedSourceSemanticHash = null)
    {
        RequireExactKeys(root, "$", RootKeys);
        if (RequireString(root, "schema", "$.schema") != "TEV_SCRIPT_PROGRAM_IR_V3")
            Fail("TEVS_IR_V3_SCHEMA", "$.schema", "expected TEV_SCRIPT_PROGRAM_IR_V3");
        if (RequireString(root, "language_version", "$.language_version") != "1.0.0")
            Fail("TEVS_IR_V3_LANGUAGE_VERSION", "$.language_version", "expected 1.0.0");

        var sourceSchema = RequireString(root, "source_schema", "$.source_schema");
        var profile = RequireString(root, "lowering_profile", "$.lowering_profile");
        var expectedProfile = sourceSchema switch
        {
            "TEV_SCRIPT_LINKED_PROGRAM_V1" => "TEV_SCRIPT_V1_IR_V3_PROFILE_V1",
            "TEV_SCRIPT_PROGRAM_IR_V2" => "TEV_SCRIPT_V2_LIFT_TO_IR_V3_PROFILE_V1",
            _ => null,
        };
        if (expectedProfile is null || profile != expectedProfile)
            Fail("TEVS_IR_V3_LOWERING_PROFILE", "$.lowering_profile", $"profile/source mismatch: {profile} / {sourceSchema}");
        var sourceHash = RequireHash(root, "source_semantic_hash", "$.source_semantic_hash");
        if (expectedSourceSemanticHash is not null && sourceHash != expectedSourceSemanticHash)
            Fail("TEVS_IR_V3_SOURCE_HASH", "$.source_semantic_hash", "source semantic hash does not match expected source artifact");
        RequireLocal(root, "program_id", "$.program_id");
        var semanticHash = RequireHash(root, "semantic_hash", "$.semantic_hash");
        var debugHash = RequireHash(root, "debug_hash", "$.debug_hash");

        ValidateBoundary(root.GetProperty("boundary"));
        var table = TevScriptTypeTableV3.Build(root);
        var entities = root.GetProperty("entities");
        if (entities.ValueKind != JsonValueKind.Array || entities.GetArrayLength() is < 1 or > 128)
            Contract("$.entities", "expected 1..128 entities");
        var ids = new HashSet<string>(StringComparer.Ordinal);
        string? previousEntity = null;
        var entityIndex = 0;
        foreach (var entity in entities.EnumerateArray())
        {
            var path = $"$.entities[{entityIndex++}]";
            var entityId = ValidateEntity(entity, table, path);
            if (!ids.Add(entityId)) Contract(path + ".entity_id", $"duplicate entity {entityId}");
            if (previousEntity is not null && StringComparer.Ordinal.Compare(entityId, previousEntity) <= 0)
                Contract("$.entities", "entities must be strictly sorted by entity_id");
            previousEntity = entityId;
        }
        ValidateClosedTypeTable(root, table);

        var observedDebugHash = TevScriptCanonicalV3.Sha256(root.GetProperty("debug"));
        if (observedDebugHash != debugHash)
            Fail("TEVS_IR_V3_DEBUG_HASH", "$.debug_hash", "debug hash mismatch");
        var semanticJson = CanonicalWithout(root, "semantic_hash", "debug", "debug_hash");
        var observedSemanticHash = TevScriptCanonicalV3.Sha256Text(semanticJson);
        if (observedSemanticHash != semanticHash)
            Fail("TEVS_IR_V3_SEMANTIC_HASH", "$.semantic_hash", "semantic hash mismatch");
        return table;
    }

    private static void ValidateBoundary(JsonElement boundary)
    {
        RequireExactKeys(boundary, "$.boundary", BoundaryKeys);
        foreach (var flag in new[]
                 {
                     "dynamic_code", "reflection", "unbounded_loops", "implicit_physical_effects",
                     "runtime_source_compilation", "automatic_authority_escalation", "host_object_references",
                 })
        {
            if (!boundary.TryGetProperty(flag, out var raw) || raw.ValueKind != JsonValueKind.False)
                Fail("TEVS_IR_V3_BOUNDARY", "$.boundary." + flag, "must be false");
        }
        RequireInt(boundary, "maximum_event_chain", "$.boundary.maximum_event_chain", 1, 128);
        RequireInt(boundary, "maximum_value_nesting", "$.boundary.maximum_value_nesting", 1, 128);
    }

    private static string ValidateEntity(JsonElement entity, TevScriptTypeTableV3 table, string path)
    {
        RequireExactKeys(entity, path, "entity_id", "states", "handlers", "capabilities", "emitted_events");
        var entityId = RequireLocal(entity, "entity_id", path + ".entity_id");
        var states = new Dictionary<string, string>(StringComparer.Ordinal);
        var previousState = (string?)null;
        var stateIndex = 0;
        foreach (var state in RequireArray(entity, "states", path + ".states", 0, 256).EnumerateArray())
        {
            var statePath = $"{path}.states[{stateIndex++}]";
            RequireExactKeys(state, statePath, "name", "type", "initial");
            var name = RequireLocal(state, "name", statePath + ".name");
            if (!states.TryAdd(name, RequireStorable(table, state, "type", statePath + ".type")))
                Contract(statePath + ".name", $"duplicate state {name}");
            if (previousState is not null && StringComparer.Ordinal.Compare(name, previousState) <= 0)
                Contract(path + ".states", "states must be strictly sorted by name");
            previousState = name;
            TevScriptValueCodecV3.Decode(states[name], state.GetProperty("initial"), table, statePath + ".initial");
        }

        var capabilities = new Dictionary<string, CapabilitySignature>(StringComparer.Ordinal);
        string? previousCapability = null;
        var capIndex = 0;
        foreach (var capability in RequireArray(entity, "capabilities", path + ".capabilities", 0, 8192).EnumerateArray())
        {
            var capPath = $"{path}.capabilities[{capIndex++}]";
            RequireExactKeys(capability, capPath, "capability_id", "parameters", "return_type", "kind");
            var id = RequireStable(capability, "capability_id", capPath + ".capability_id");
            if (capabilities.ContainsKey(id)) Contract(capPath + ".capability_id", $"duplicate capability {id}");
            if (previousCapability is not null && StringComparer.Ordinal.Compare(id, previousCapability) <= 0)
                Contract(path + ".capabilities", "capabilities must be strictly sorted by id");
            previousCapability = id;
            var parameterTypes = RequireArray(capability, "parameters", capPath + ".parameters", 0, 64)
                .EnumerateArray().Select((item, index) => RequireStorable(table, item, $"{capPath}.parameters[{index}]")).ToArray();
            var returnType = RequireString(capability, "return_type", capPath + ".return_type");
            var returnDescriptor = table.Require(returnType, capPath + ".return_type");
            if (returnDescriptor.Kind != TevScriptTypeKindV3.Unit && !table.IsStorable(returnType))
                Contract(capPath + ".return_type", $"invalid capability return {returnType}");
            var kind = RequireString(capability, "kind", capPath + ".kind");
            if (kind is not ("observation" or "effect")) Contract(capPath + ".kind", "kind must be observation or effect");
            capabilities[id] = new CapabilitySignature(parameterTypes, returnType, kind);
        }

        var events = new Dictionary<string, string[]>(StringComparer.Ordinal);
        string? previousEvent = null;
        var eventIndex = 0;
        foreach (var eventValue in RequireArray(entity, "emitted_events", path + ".emitted_events", 0, 256).EnumerateArray())
        {
            var eventPath = $"{path}.emitted_events[{eventIndex++}]";
            RequireExactKeys(eventValue, eventPath, "event_id", "parameters");
            var eventId = RequireLocal(eventValue, "event_id", eventPath + ".event_id");
            if (events.ContainsKey(eventId)) Contract(eventPath + ".event_id", $"duplicate emitted event {eventId}");
            if (previousEvent is not null && StringComparer.Ordinal.Compare(eventId, previousEvent) <= 0)
                Contract(path + ".emitted_events", "emitted events must be strictly sorted by id");
            previousEvent = eventId;
            events[eventId] = RequireArray(eventValue, "parameters", eventPath + ".parameters", 0, 64)
                .EnumerateArray().Select((item, index) => RequireStorable(table, item, $"{eventPath}.parameters[{index}]")).ToArray();
        }

        var handlerIds = new HashSet<string>(StringComparer.Ordinal);
        string? previousHandler = null;
        var handlerIndex = 0;
        foreach (var handler in RequireArray(entity, "handlers", path + ".handlers", 0, 256).EnumerateArray())
        {
            var handlerPath = $"{path}.handlers[{handlerIndex++}]";
            RequireExactKeys(handler, handlerPath, "event_id", "parameters", "locals", "instructions", "instruction_budget");
            var eventId = RequireLocal(handler, "event_id", handlerPath + ".event_id");
            if (!handlerIds.Add(eventId)) Contract(handlerPath + ".event_id", $"duplicate handler {eventId}");
            if (previousHandler is not null && StringComparer.Ordinal.Compare(eventId, previousHandler) <= 0)
                Contract(path + ".handlers", "handlers must be strictly sorted by event id");
            previousHandler = eventId;

            var parameters = new Dictionary<string, string>(StringComparer.Ordinal);
            var parameterIndex = 0;
            foreach (var parameter in RequireArray(handler, "parameters", handlerPath + ".parameters", 0, 64).EnumerateArray())
            {
                var parameterPath = $"{handlerPath}.parameters[{parameterIndex++}]";
                var pair = RequireBinding(parameter, table, parameterPath);
                if (parameters.ContainsKey(pair.Name) || states.ContainsKey(pair.Name)) Contract(parameterPath + ".name", $"duplicate/state-shadowing parameter {pair.Name}");
                parameters[pair.Name] = pair.TypeId;
            }

            var locals = new Dictionary<string, string>(StringComparer.Ordinal);
            string? previousLocal = null;
            var localIndex = 0;
            foreach (var local in RequireArray(handler, "locals", handlerPath + ".locals", 0, 256).EnumerateArray())
            {
                var localPath = $"{handlerPath}.locals[{localIndex++}]";
                var pair = RequireBinding(local, table, localPath);
                if (locals.ContainsKey(pair.Name) || parameters.ContainsKey(pair.Name) || states.ContainsKey(pair.Name)) Contract(localPath + ".name", $"duplicate/shadowing local {pair.Name}");
                if (previousLocal is not null && StringComparer.Ordinal.Compare(pair.Name, previousLocal) <= 0) Contract(handlerPath + ".locals", "locals must be strictly sorted by name");
                previousLocal = pair.Name;
                locals[pair.Name] = pair.TypeId;
            }

            var instructions = RequireArray(handler, "instructions", handlerPath + ".instructions", 1, 8192);
            var budget = RequireInt(handler, "instruction_budget", handlerPath + ".instruction_budget", 1, 8192);
            if (instructions.GetArrayLength() > budget) Contract(handlerPath + ".instruction_budget", "budget smaller than instruction count");
            if (instructions[instructions.GetArrayLength() - 1].GetProperty("op").GetString() != "RETURN")
                Contract(handlerPath + ".instructions", "handler must end in RETURN");
            for (var pc = 0; pc < instructions.GetArrayLength(); ++pc)
                ValidateInstruction(instructions[pc], table, states, parameters, locals, capabilities, events, pc, instructions.GetArrayLength(), $"{handlerPath}.instructions[{pc}]");
            TevScriptFlowV3.ValidateEntityHandler(entity, handler, table, handlerPath);
        }
        return entityId;
    }

    private static void ValidateInstruction(
        JsonElement instruction,
        TevScriptTypeTableV3 table,
        Dictionary<string, string> states,
        Dictionary<string, string> parameters,
        Dictionary<string, string> locals,
        Dictionary<string, CapabilitySignature> capabilities,
        Dictionary<string, string[]> events,
        int pc,
        int count,
        string path)
    {
        var op = RequireString(instruction, "op", path + ".op");
        if (op == "CONST")
        {
            RequireExactKeys(instruction, path, "op", "type", "value");
            var typeId = RequireStorable(table, instruction, "type", path + ".type");
            TevScriptValueCodecV3.Decode(typeId, instruction.GetProperty("value"), table, path + ".value");
            return;
        }
        if (op is "LOAD_STATE" or "STORE_STATE" or "LOAD_LOCAL" or "STORE_LOCAL" or "LOAD_PARAM")
        {
            RequireExactKeys(instruction, path, "op", "name", "type");
            var name = RequireLocal(instruction, "name", path + ".name");
            var typeId = RequireStorable(table, instruction, "type", path + ".type");
            var ns = op is "LOAD_STATE" or "STORE_STATE" ? states : op is "LOAD_LOCAL" or "STORE_LOCAL" ? locals : parameters;
            if (!ns.TryGetValue(name, out var expected) || expected != typeId) Contract(path, $"{op} references unknown/mismatched binding {name}");
            return;
        }
        if (op == "CONVERT_INT_TO_RAT") { RequireExactKeys(instruction, path, "op"); return; }
        if (op == "UNARY") { RequireExactKeys(instruction, path, "op", "operator", "type"); RequireString(instruction, "operator", path + ".operator"); RequireStorable(table, instruction, "type", path + ".type"); return; }
        if (op == "BINARY")
        {
            RequireExactKeys(instruction, path, "op", "operator", "left_type", "right_type", "result_type");
            RequireString(instruction, "operator", path + ".operator");
            foreach (var key in new[] { "left_type", "right_type", "result_type" }) RequireStorable(table, instruction, key, path + "." + key);
            return;
        }
        if (op == "CALL_PURE")
        {
            RequireExactKeys(instruction, path, "op", "function_id", "argc", "return_type");
            var functionId = RequireStable(instruction, "function_id", path + ".function_id");
            if (functionId is not ("vec2" or "vec3" or "min" or "max")) Contract(path + ".function_id", "unsupported runtime pure intrinsic");
            RequireInt(instruction, "argc", path + ".argc", 0, 64);
            RequireStorable(table, instruction, "return_type", path + ".return_type");
            return;
        }
        if (op == "CALL_CAPABILITY")
        {
            RequireExactKeys(instruction, path, "op", "capability_id", "argc", "return_type", "kind");
            var id = RequireStable(instruction, "capability_id", path + ".capability_id");
            if (!capabilities.TryGetValue(id, out var contract)) Contract(path, $"undeclared capability {id}");
            if (RequireInt(instruction, "argc", path + ".argc", 0, 64) != contract.Parameters.Length
                || RequireString(instruction, "return_type", path + ".return_type") != contract.ReturnType
                || RequireString(instruction, "kind", path + ".kind") != contract.Kind)
                Contract(path, $"capability contract mismatch for {id}");
            return;
        }
        if (op == "EMIT_EVENT")
        {
            RequireExactKeys(instruction, path, "op", "event_id", "argument_types", "argc");
            var id = RequireLocal(instruction, "event_id", path + ".event_id");
            if (!events.TryGetValue(id, out var contract)) Contract(path, $"undeclared emitted event {id}");
            var types = RequireArray(instruction, "argument_types", path + ".argument_types", 0, 64).EnumerateArray().Select((item, index) => RequireStorable(table, item, $"{path}.argument_types[{index}]")).ToArray();
            if (RequireInt(instruction, "argc", path + ".argc", 0, 64) != contract.Length || !types.SequenceEqual(contract, StringComparer.Ordinal)) Contract(path, $"event contract mismatch for {id}");
            return;
        }
        if (op is "JUMP" or "JUMP_IF_FALSE")
        {
            RequireExactKeys(instruction, path, "op", "target");
            var target = RequireInt(instruction, "target", path + ".target", 0, count - 1);
            if (target <= pc) Contract(path + ".target", "backward/self jumps are forbidden");
            return;
        }
        if (op == "RETURN") { RequireExactKeys(instruction, path, "op"); return; }
        if (op == "MAKE_RECORD")
        {
            RequireExactKeys(instruction, path, "op", "type", "fields");
            var typeId = RequireStorable(table, instruction, "type", path + ".type");
            var descriptor = table.Require(typeId);
            if (descriptor.Kind != TevScriptTypeKindV3.Record) Contract(path + ".type", "MAKE_RECORD requires record descriptor");
            var fields = RequireArray(instruction, "fields", path + ".fields", 1, 256).EnumerateArray().Select((item, index) => RequireLocal(item, $"{path}.fields[{index}]")).ToArray();
            if (fields.Distinct(StringComparer.Ordinal).Count() != fields.Length || fields.Length != descriptor.Fields.Count || fields.Any(name => descriptor.FieldType(name) is null)) Contract(path + ".fields", "MAKE_RECORD fields must equal descriptor field set");
            return;
        }
        if (op == "LOAD_FIELD")
        {
            RequireExactKeys(instruction, path, "op", "record_type", "field", "result_type");
            var recordType = RequireStorable(table, instruction, "record_type", path + ".record_type");
            var descriptor = table.Require(recordType);
            if (descriptor.Kind != TevScriptTypeKindV3.Record) Contract(path + ".record_type", "LOAD_FIELD requires record type");
            var field = RequireLocal(instruction, "field", path + ".field");
            var resultType = RequireStorable(table, instruction, "result_type", path + ".result_type");
            if (descriptor.FieldType(field) != resultType) Contract(path, "LOAD_FIELD descriptor mismatch");
            return;
        }
        if (op == "MAKE_VARIANT")
        {
            RequireExactKeys(instruction, path, "op", "type", "variant", "argc");
            var typeId = RequireStorable(table, instruction, "type", path + ".type");
            var variant = RequireLocal(instruction, "variant", path + ".variant");
            var expectedArgc = table.VariantPayloadType(typeId, variant) is null ? 0 : 1;
            if (RequireInt(instruction, "argc", path + ".argc", 0, 1) != expectedArgc) Contract(path + ".argc", $"variant requires argc {expectedArgc}");
            return;
        }
        if (op == "TEST_VARIANT")
        {
            RequireExactKeys(instruction, path, "op", "type", "variant");
            var typeId = RequireStorable(table, instruction, "type", path + ".type");
            table.VariantPayloadType(typeId, RequireLocal(instruction, "variant", path + ".variant"));
            return;
        }
        if (op == "LOAD_VARIANT_PAYLOAD")
        {
            RequireExactKeys(instruction, path, "op", "type", "variant", "payload_type");
            var typeId = RequireStorable(table, instruction, "type", path + ".type");
            var variant = RequireLocal(instruction, "variant", path + ".variant");
            var payload = table.VariantPayloadType(typeId, variant);
            if (payload is null) Contract(path, "selected variant has no payload");
            if (RequireString(instruction, "payload_type", path + ".payload_type") != payload) Contract(path + ".payload_type", "variant payload type mismatch");
            return;
        }
        Fail("TEVS_IR_V3_OPCODE", path + ".op", $"unknown V3 opcode {op}");
    }

    private static void ValidateClosedTypeTable(JsonElement root, TevScriptTypeTableV3 table)
    {
        var needed = new HashSet<string>(new[] { "Bool", "Int", "Rat", "Text", "Vec2", "Vec3", "Unit" }, StringComparer.Ordinal);
        foreach (var entity in root.GetProperty("entities").EnumerateArray())
        {
            foreach (var state in entity.GetProperty("states").EnumerateArray()) needed.Add(state.GetProperty("type").GetString()!);
            foreach (var capability in entity.GetProperty("capabilities").EnumerateArray())
            {
                foreach (var type in capability.GetProperty("parameters").EnumerateArray()) needed.Add(type.GetString()!);
                needed.Add(capability.GetProperty("return_type").GetString()!);
            }
            foreach (var eventValue in entity.GetProperty("emitted_events").EnumerateArray()) foreach (var type in eventValue.GetProperty("parameters").EnumerateArray()) needed.Add(type.GetString()!);
            foreach (var handler in entity.GetProperty("handlers").EnumerateArray())
            {
                foreach (var parameter in handler.GetProperty("parameters").EnumerateArray()) needed.Add(parameter.GetProperty("type").GetString()!);
                foreach (var local in handler.GetProperty("locals").EnumerateArray()) needed.Add(local.GetProperty("type").GetString()!);
                foreach (var instruction in handler.GetProperty("instructions").EnumerateArray())
                {
                    foreach (var key in new[] { "type", "left_type", "right_type", "result_type", "return_type", "record_type", "payload_type" })
                        if (instruction.TryGetProperty(key, out var raw) && raw.ValueKind == JsonValueKind.String) needed.Add(raw.GetString()!);
                    if (instruction.TryGetProperty("argument_types", out var argumentTypes)) foreach (var type in argumentTypes.EnumerateArray()) needed.Add(type.GetString()!);
                }
            }
        }
        var pending = new Stack<string>(needed);
        while (pending.Count > 0)
        {
            var typeId = pending.Pop();
            var descriptor = table.Require(typeId, "closed type table");
            IEnumerable<string> children = descriptor.Kind switch
            {
                TevScriptTypeKindV3.Record => descriptor.Fields.Select(field => field.TypeId),
                TevScriptTypeKindV3.Option => new[] { descriptor.Argument! },
                TevScriptTypeKindV3.Result => new[] { descriptor.OkType!, descriptor.ErrType! },
                _ => Array.Empty<string>(),
            };
            foreach (var child in children) if (needed.Add(child)) pending.Push(child);
        }
        var observed = table.Descriptors.Select(item => item.TypeId).ToHashSet(StringComparer.Ordinal);
        var missing = needed.Except(observed, StringComparer.Ordinal).OrderBy(item => item, StringComparer.Ordinal).ToArray();
        var extra = observed.Except(needed, StringComparer.Ordinal).OrderBy(item => item, StringComparer.Ordinal).ToArray();
        if (missing.Length > 0) Contract("$.types", $"closed type table missing referenced descriptors [{string.Join(',', missing)}]");
        if (extra.Length > 0) Contract("$.types", $"closed type table contains unused descriptors [{string.Join(',', extra)}]");
    }

    private sealed record CapabilitySignature(string[] Parameters, string ReturnType, string Kind);
    private sealed record Binding(string Name, string TypeId);

    private static Binding RequireBinding(JsonElement item, TevScriptTypeTableV3 table, string path)
    {
        RequireExactKeys(item, path, "name", "type");
        return new Binding(RequireLocal(item, "name", path + ".name"), RequireStorable(table, item, "type", path + ".type"));
    }

    private static string CanonicalWithout(JsonElement root, params string[] excluded)
    {
        var skip = excluded.ToHashSet(StringComparer.Ordinal);
        using var stream = new MemoryStream();
        using (var writer = new Utf8JsonWriter(stream, new JsonWriterOptions { Indented = false, SkipValidation = false }))
        {
            writer.WriteStartObject();
            foreach (var property in root.EnumerateObject().Where(item => !skip.Contains(item.Name)).OrderBy(item => item.Name, StringComparer.Ordinal))
            {
                writer.WritePropertyName(property.Name);
                writer.WriteRawValue(TevScriptCanonicalV3.Json(property.Value), skipInputValidation: false);
            }
            writer.WriteEndObject();
        }
        return Encoding.UTF8.GetString(stream.ToArray());
    }

    private static JsonElement RequireArray(JsonElement parent, string property, string path, int min, int max)
    {
        if (!parent.TryGetProperty(property, out var value) || value.ValueKind != JsonValueKind.Array || value.GetArrayLength() < min || value.GetArrayLength() > max)
            Contract(path, $"expected array length in [{min},{max}]");
        return value;
    }

    private static int RequireInt(JsonElement parent, string property, string path, int min, int max)
    {
        if (!parent.TryGetProperty(property, out var raw) || raw.ValueKind != JsonValueKind.Number || !raw.TryGetInt32(out var value) || value < min || value > max)
            Contract(path, $"expected integer in [{min},{max}]");
        return value;
    }

    private static string RequireString(JsonElement parent, string property, string path)
    {
        if (!parent.TryGetProperty(property, out var raw) || raw.ValueKind != JsonValueKind.String) Contract(path, "expected string");
        return raw.GetString()!;
    }

    private static string RequireString(JsonElement value, string path)
    {
        if (value.ValueKind != JsonValueKind.String) Contract(path, "expected string");
        return value.GetString()!;
    }

    private static string RequireLocal(JsonElement parent, string property, string path)
    {
        var result = RequireString(parent, property, path);
        if (!Local.IsMatch(result)) Contract(path, $"expected local identifier, got {result}");
        return result;
    }

    private static string RequireLocal(JsonElement value, string path)
    {
        var result = RequireString(value, path);
        if (!Local.IsMatch(result)) Contract(path, $"expected local identifier, got {result}");
        return result;
    }

    private static string RequireStable(JsonElement parent, string property, string path)
    {
        var result = RequireString(parent, property, path);
        if (!Stable.IsMatch(result)) Contract(path, $"expected stable identifier, got {result}");
        return result;
    }

    private static string RequireHash(JsonElement parent, string property, string path)
    {
        var result = RequireString(parent, property, path);
        if (!Hash.IsMatch(result)) Contract(path, "expected lowercase SHA-256");
        return result;
    }

    private static string RequireStorable(TevScriptTypeTableV3 table, JsonElement parent, string property, string path)
    {
        var typeId = RequireString(parent, property, path);
        if (!table.IsStorable(typeId)) Contract(path, $"type {typeId} is unknown or not storable");
        return typeId;
    }

    private static string RequireStorable(TevScriptTypeTableV3 table, JsonElement value, string path)
    {
        var typeId = RequireString(value, path);
        if (!table.IsStorable(typeId)) Contract(path, $"type {typeId} is unknown or not storable");
        return typeId;
    }

    private static void RequireExactKeys(JsonElement value, string path, params string[] expected)
    {
        if (value.ValueKind != JsonValueKind.Object) Contract(path, "expected object");
        var observed = value.EnumerateObject().Select(item => item.Name).OrderBy(item => item, StringComparer.Ordinal).ToArray();
        var target = expected.OrderBy(item => item, StringComparer.Ordinal).ToArray();
        if (!observed.SequenceEqual(target, StringComparer.Ordinal)) Contract(path, $"field set mismatch; expected=[{string.Join(',', target)}], observed=[{string.Join(',', observed)}]");
    }

    private static void Contract(string path, string message) => Fail("TEVS_IR_V3_CONTRACT", path, message);
    private static void Fail(string code, string path, string message) => throw new TevScriptV3Exception(code, $"{path}: {message}");
}
