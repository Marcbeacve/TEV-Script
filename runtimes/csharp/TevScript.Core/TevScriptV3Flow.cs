using System.Text.Json;

namespace TevScript.Core.V3;

public static class TevScriptFlowV3
{
    private sealed record FlowState(string[] Stack, HashSet<string> Initialized);

    public static void ValidateEntityHandler(
        JsonElement entity,
        JsonElement handler,
        TevScriptTypeTableV3 table,
        string path)
    {
        var states = BindingMap(entity.GetProperty("states"));
        var parameters = BindingMap(handler.GetProperty("parameters"));
        var locals = BindingMap(handler.GetProperty("locals"));
        var capabilities = CapabilityMap(entity.GetProperty("capabilities"));
        var events = EventMap(entity.GetProperty("emitted_events"));
        var instructions = handler.GetProperty("instructions");
        var count = instructions.GetArrayLength();
        var incoming = new FlowState?[count];
        incoming[0] = new FlowState(Array.Empty<string>(), new HashSet<string>(StringComparer.Ordinal));
        var reachedReturn = false;

        for (var pc = 0; pc < count; ++pc)
        {
            var flow = incoming[pc];
            if (flow is null) continue;
            var stack = flow.Stack.ToList();
            var initialized = new HashSet<string>(flow.Initialized, StringComparer.Ordinal);
            var instruction = instructions[pc];
            var op = instruction.GetProperty("op").GetString()!;
            var currentPath = $"{path}.instructions[{pc}]";

            void Pop(string expected)
            {
                if (stack.Count == 0) Fail(currentPath, $"stack underflow; expected {expected}");
                var actual = stack[^1];
                stack.RemoveAt(stack.Count - 1);
                if (!StringComparer.Ordinal.Equals(actual, expected))
                    Fail(currentPath, $"stack type mismatch; expected {expected}, got {actual}");
            }

            switch (op)
            {
                case "CONST":
                    var constType = instruction.GetProperty("type").GetString()!;
                    RequireStorable(table, constType, currentPath);
                    stack.Add(constType);
                    break;
                case "LOAD_STATE":
                    stack.Add(states[instruction.GetProperty("name").GetString()!]);
                    break;
                case "STORE_STATE":
                    Pop(states[instruction.GetProperty("name").GetString()!]);
                    break;
                case "LOAD_LOCAL":
                {
                    var name = instruction.GetProperty("name").GetString()!;
                    if (!initialized.Contains(name)) Fail(currentPath, $"local {name} is not definitely initialized");
                    stack.Add(locals[name]);
                    break;
                }
                case "STORE_LOCAL":
                {
                    var name = instruction.GetProperty("name").GetString()!;
                    Pop(locals[name]);
                    initialized.Add(name);
                    break;
                }
                case "LOAD_PARAM":
                    stack.Add(parameters[instruction.GetProperty("name").GetString()!]);
                    break;
                case "CONVERT_INT_TO_RAT":
                    Pop("Int");
                    stack.Add("Rat");
                    break;
                case "UNARY":
                {
                    var kind = instruction.GetProperty("operator").GetString()!;
                    var typeId = instruction.GetProperty("type").GetString()!;
                    if (kind == "NOT")
                    {
                        if (typeId != "Bool") Fail(currentPath, "NOT must produce Bool");
                        Pop("Bool");
                    }
                    else if (kind == "MINUS")
                    {
                        if (typeId is not ("Int" or "Rat")) Fail(currentPath, "MINUS requires Int or Rat");
                        Pop(typeId);
                    }
                    else Fail(currentPath, $"unsupported unary operator {kind}");
                    stack.Add(typeId);
                    break;
                }
                case "BINARY":
                {
                    var kind = instruction.GetProperty("operator").GetString()!;
                    var left = instruction.GetProperty("left_type").GetString()!;
                    var right = instruction.GetProperty("right_type").GetString()!;
                    var result = instruction.GetProperty("result_type").GetString()!;
                    if (!BinarySignature(kind, left, right, result, table))
                        Fail(currentPath, $"invalid V3 binary signature {kind}({left},{right})->{result}");
                    Pop(right);
                    Pop(left);
                    stack.Add(result);
                    break;
                }
                case "CALL_PURE":
                {
                    var functionId = instruction.GetProperty("function_id").GetString()!;
                    var returnType = instruction.GetProperty("return_type").GetString()!;
                    var signature = PureSignature(functionId, returnType);
                    if (instruction.GetProperty("argc").GetInt32() != signature.Length)
                        Fail(currentPath, $"{functionId} argc mismatch");
                    for (var index = signature.Length - 1; index >= 0; --index) Pop(signature[index]);
                    if (returnType != "Unit")
                    {
                        RequireStorable(table, returnType, currentPath);
                        stack.Add(returnType);
                    }
                    break;
                }
                case "CALL_CAPABILITY":
                {
                    var capabilityId = instruction.GetProperty("capability_id").GetString()!;
                    if (!capabilities.TryGetValue(capabilityId, out var signature))
                        Fail(currentPath, $"undeclared capability {capabilityId}");
                    if (instruction.GetProperty("argc").GetInt32() != signature.Parameters.Length
                        || instruction.GetProperty("return_type").GetString() != signature.ReturnType
                        || instruction.GetProperty("kind").GetString() != signature.Kind)
                        Fail(currentPath, $"capability contract mismatch for {capabilityId}");
                    for (var index = signature.Parameters.Length - 1; index >= 0; --index) Pop(signature.Parameters[index]);
                    if (signature.ReturnType != "Unit") stack.Add(signature.ReturnType);
                    break;
                }
                case "EMIT_EVENT":
                {
                    var eventId = instruction.GetProperty("event_id").GetString()!;
                    if (!events.TryGetValue(eventId, out var signature))
                        Fail(currentPath, $"undeclared emitted event {eventId}");
                    var argumentTypes = instruction.GetProperty("argument_types").EnumerateArray().Select(item => item.GetString()!).ToArray();
                    if (instruction.GetProperty("argc").GetInt32() != signature.Length || !argumentTypes.SequenceEqual(signature, StringComparer.Ordinal))
                        Fail(currentPath, $"event contract mismatch for {eventId}");
                    for (var index = signature.Length - 1; index >= 0; --index) Pop(signature[index]);
                    break;
                }
                case "MAKE_RECORD":
                {
                    var typeId = instruction.GetProperty("type").GetString()!;
                    var descriptor = table.Require(typeId, currentPath);
                    if (descriptor.Kind != TevScriptTypeKindV3.Record) Fail(currentPath, $"MAKE_RECORD requires record type, got {typeId}");
                    var fields = instruction.GetProperty("fields").EnumerateArray().Select(item => item.GetString()!).ToArray();
                    if (fields.Length != descriptor.Fields.Count || fields.Distinct(StringComparer.Ordinal).Count() != fields.Length)
                        Fail(currentPath, "MAKE_RECORD fields must equal descriptor field set exactly");
                    var byName = descriptor.Fields.ToDictionary(item => item.Name, item => item.TypeId, StringComparer.Ordinal);
                    if (fields.Any(name => !byName.ContainsKey(name))) Fail(currentPath, "MAKE_RECORD references unknown field");
                    for (var index = fields.Length - 1; index >= 0; --index) Pop(byName[fields[index]]);
                    stack.Add(typeId);
                    break;
                }
                case "LOAD_FIELD":
                {
                    var recordType = instruction.GetProperty("record_type").GetString()!;
                    var field = instruction.GetProperty("field").GetString()!;
                    var resultType = instruction.GetProperty("result_type").GetString()!;
                    var descriptor = table.Require(recordType, currentPath);
                    if (descriptor.Kind != TevScriptTypeKindV3.Record || descriptor.FieldType(field) != resultType)
                        Fail(currentPath, $"LOAD_FIELD descriptor mismatch for {recordType}.{field}");
                    Pop(recordType);
                    stack.Add(resultType);
                    break;
                }
                case "MAKE_VARIANT":
                {
                    var typeId = instruction.GetProperty("type").GetString()!;
                    var variant = instruction.GetProperty("variant").GetString()!;
                    var payloadType = table.VariantPayloadType(typeId, variant);
                    var expectedArgc = payloadType is null ? 0 : 1;
                    if (instruction.GetProperty("argc").GetInt32() != expectedArgc)
                        Fail(currentPath, $"MAKE_VARIANT {typeId}.{variant} expects argc={expectedArgc}");
                    if (payloadType is not null) Pop(payloadType);
                    stack.Add(typeId);
                    break;
                }
                case "TEST_VARIANT":
                {
                    var typeId = instruction.GetProperty("type").GetString()!;
                    table.VariantPayloadType(typeId, instruction.GetProperty("variant").GetString()!);
                    Pop(typeId);
                    stack.Add("Bool");
                    break;
                }
                case "LOAD_VARIANT_PAYLOAD":
                {
                    var typeId = instruction.GetProperty("type").GetString()!;
                    var variant = instruction.GetProperty("variant").GetString()!;
                    var payloadType = table.VariantPayloadType(typeId, variant);
                    if (payloadType is null) Fail(currentPath, $"{typeId}.{variant} is payload-free and cannot be loaded");
                    if (payloadType != instruction.GetProperty("payload_type").GetString()) Fail(currentPath, "LOAD_VARIANT_PAYLOAD result type mismatch");
                    Pop(typeId);
                    stack.Add(payloadType!);
                    break;
                }
                case "JUMP_IF_FALSE":
                {
                    Pop("Bool");
                    var target = instruction.GetProperty("target").GetInt32();
                    if (target <= pc) Fail(currentPath, "backward/self jump is forbidden");
                    Merge(incoming, target, stack, initialized, currentPath, count);
                    if (pc + 1 >= count) Fail(currentPath, "conditional fallthrough exits handler");
                    Merge(incoming, pc + 1, stack, initialized, currentPath, count);
                    continue;
                }
                case "JUMP":
                {
                    var target = instruction.GetProperty("target").GetInt32();
                    if (target <= pc) Fail(currentPath, "backward/self jump is forbidden");
                    Merge(incoming, target, stack, initialized, currentPath, count);
                    continue;
                }
                case "RETURN":
                    if (stack.Count != 0) Fail(currentPath, $"RETURN requires empty stack, found [{string.Join(',', stack)}]");
                    reachedReturn = true;
                    continue;
                default:
                    Fail(currentPath, $"unknown V3 opcode {op}");
                    break;
            }

            if (pc + 1 >= count) Fail(currentPath, "reachable control flow falls off handler");
            Merge(incoming, pc + 1, stack, initialized, currentPath, count);
        }
        if (!reachedReturn) Fail(path, "no reachable RETURN");
    }

    private static Dictionary<string, string> BindingMap(JsonElement array)
    {
        var result = new Dictionary<string, string>(StringComparer.Ordinal);
        foreach (var item in array.EnumerateArray()) result.Add(item.GetProperty("name").GetString()!, item.GetProperty("type").GetString()!);
        return result;
    }

    private sealed record CapabilitySignature(string[] Parameters, string ReturnType, string Kind);

    private static Dictionary<string, CapabilitySignature> CapabilityMap(JsonElement array)
    {
        var result = new Dictionary<string, CapabilitySignature>(StringComparer.Ordinal);
        foreach (var item in array.EnumerateArray())
            result.Add(
                item.GetProperty("capability_id").GetString()!,
                new CapabilitySignature(
                    item.GetProperty("parameters").EnumerateArray().Select(value => value.GetString()!).ToArray(),
                    item.GetProperty("return_type").GetString()!,
                    item.GetProperty("kind").GetString()!));
        return result;
    }

    private static Dictionary<string, string[]> EventMap(JsonElement array)
    {
        var result = new Dictionary<string, string[]>(StringComparer.Ordinal);
        foreach (var item in array.EnumerateArray())
            result.Add(item.GetProperty("event_id").GetString()!, item.GetProperty("parameters").EnumerateArray().Select(value => value.GetString()!).ToArray());
        return result;
    }

    private static void Merge(FlowState?[] incoming, int target, List<string> stack, HashSet<string> initialized, string source, int instructionCount)
    {
        if (target < 0 || target >= instructionCount) Fail(source, "control flow must target an instruction, not handler exit");
        var current = incoming[target];
        if (current is null)
        {
            incoming[target] = new FlowState(stack.ToArray(), new HashSet<string>(initialized, StringComparer.Ordinal));
            return;
        }
        if (!current.Stack.SequenceEqual(stack, StringComparer.Ordinal))
            Fail(source, $"CFG merge stack mismatch at instruction {target}: [{string.Join(',', current.Stack)}] vs [{string.Join(',', stack)}]");
        current.Initialized.IntersectWith(initialized);
    }

    private static void RequireStorable(TevScriptTypeTableV3 table, string typeId, string path)
    {
        if (!table.IsStorable(typeId)) Fail(path, $"type {typeId} is not storable");
    }

    private static string[] PureSignature(string functionId, string returnType) => (functionId, returnType) switch
    {
        ("vec2", "Vec2") => new[] { "Rat", "Rat" },
        ("vec3", "Vec3") => new[] { "Rat", "Rat", "Rat" },
        ("min" or "max", "Int") => new[] { "Int", "Int" },
        ("min" or "max", "Rat") => new[] { "Rat", "Rat" },
        _ => throw new TevScriptV3Exception("TEVS_IR_V3_FLOW_INVALID", $"CALL_PURE: invalid pure intrinsic signature {functionId}->{returnType}"),
    };

    private static bool BinarySignature(string op, string left, string right, string result, TevScriptTypeTableV3 table)
    {
        if (op is "AND" or "OR") return left == "Bool" && right == "Bool" && result == "Bool";
        if (op is "EQEQ" or "NE")
        {
            if (result != "Bool") return false;
            if (left == right && table.IsStorable(left)) return true;
            return left != right && left is "Int" or "Rat" && right is "Int" or "Rat";
        }
        if (op is "LT" or "LE" or "GT" or "GE") return left == right && left is "Int" or "Rat" && result == "Bool";
        if (op is "PLUS" or "MINUS")
            return left == "Int" && right == "Int" && result == "Int"
                || left == "Rat" && right == "Rat" && result == "Rat"
                || result is "Vec2" or "Vec3" && left == result && right == result;
        if (op == "STAR")
            return left == "Int" && right == "Int" && result == "Int"
                || left == "Rat" && right == "Rat" && result == "Rat"
                || left is "Vec2" or "Vec3" && right == "Rat" && result == left
                || right is "Vec2" or "Vec3" && left == "Rat" && result == right;
        if (op == "SLASH")
            return left == "Rat" && right == "Rat" && result == "Rat"
                || left is "Vec2" or "Vec3" && right == "Rat" && result == left;
        return false;
    }

    private static void Fail(string path, string message) => throw new TevScriptV3Exception("TEVS_IR_V3_FLOW_INVALID", $"{path}: {message}");
}
