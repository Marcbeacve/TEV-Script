using System.Numerics;
using System.Text;
using System.Text.Json;

namespace TevScript.Core.V3;

public delegate TevScriptValueV3? TevScriptCapabilityV3(IReadOnlyList<TevScriptValueV3> arguments);

public sealed record TevScriptEmittedEventV3(
    string EntityId,
    string EventId,
    IReadOnlyList<string> ArgumentTypes,
    IReadOnlyList<TevScriptValueV3> Arguments);

public sealed partial class TevScriptRuntimeV3
{
    private sealed class Entity
    {
        public required string Id { get; init; }
        public required Dictionary<string, TevScriptValueV3> State { get; init; }
        public required Dictionary<string, string> StateTypes { get; init; }
        public required Dictionary<string, JsonElement> Handlers { get; init; }
        public required Dictionary<string, string[]> EmittedEventTypes { get; init; }
    }

    private readonly JsonElement _ir;
    private readonly Dictionary<string, TevScriptCapabilityV3> _capabilities;
    private readonly Dictionary<string, Entity> _entities;
    private readonly List<TevScriptEmittedEventV3> _emitted = new();

    public TevScriptRuntimeV3(
        JsonElement ir,
        IReadOnlyDictionary<string, TevScriptCapabilityV3>? capabilities = null,
        string? expectedSourceSemanticHash = null)
    {
        _ir = ir.Clone();
        TypeTable = TevScriptProgramValidatorV3.Validate(_ir, expectedSourceSemanticHash);
        _capabilities = new Dictionary<string, TevScriptCapabilityV3>(StringComparer.Ordinal);
        if (capabilities is not null)
        {
            foreach (var pair in capabilities)
            {
                if (!TevScriptLexicalV3.IsStableIdentifier(pair.Key))
                    throw new TevScriptV3Exception("TEVS_IR_V3_CAPABILITY_BINDING_ID", $"non-canonical capability binding id {pair.Key}");
                _capabilities.Add(pair.Key, pair.Value);
            }
        }
        _entities = new Dictionary<string, Entity>(StringComparer.Ordinal);
        foreach (var rawEntity in _ir.GetProperty("entities").EnumerateArray())
        {
            var id = rawEntity.GetProperty("entity_id").GetString()!;
            var state = new Dictionary<string, TevScriptValueV3>(StringComparer.Ordinal);
            var stateTypes = new Dictionary<string, string>(StringComparer.Ordinal);
            foreach (var rawState in rawEntity.GetProperty("states").EnumerateArray())
            {
                var name = rawState.GetProperty("name").GetString()!;
                var typeId = rawState.GetProperty("type").GetString()!;
                state[name] = TevScriptValueCodecV3.Decode(typeId, rawState.GetProperty("initial"), TypeTable, $"state {id}.{name}");
                stateTypes[name] = typeId;
            }
            var handlers = rawEntity.GetProperty("handlers").EnumerateArray().ToDictionary(
                item => item.GetProperty("event_id").GetString()!,
                item => item.Clone(),
                StringComparer.Ordinal);
            var eventTypes = rawEntity.GetProperty("emitted_events").EnumerateArray().ToDictionary(
                item => item.GetProperty("event_id").GetString()!,
                item => item.GetProperty("parameters").EnumerateArray().Select(value => value.GetString()!).ToArray(),
                StringComparer.Ordinal);
            _entities.Add(id, new Entity
            {
                Id = id,
                State = state,
                StateTypes = stateTypes,
                Handlers = handlers,
                EmittedEventTypes = eventTypes,
            });
        }
    }

    public TevScriptTypeTableV3 TypeTable { get; }
    public string ProgramId => _ir.GetProperty("program_id").GetString()!;
    public string SemanticHash => _ir.GetProperty("semantic_hash").GetString()!;
    public string SourceSemanticHash => _ir.GetProperty("source_semantic_hash").GetString()!;
    public IReadOnlyList<TevScriptEmittedEventV3> Emitted => _emitted.AsReadOnly();

    internal JsonElement IrForCheckpoint => _ir.Clone();
    internal IReadOnlyList<string> EntityIdsForCheckpoint => _entities.Keys.OrderBy(item => item, StringComparer.Ordinal).ToArray();

    internal IReadOnlyDictionary<string, string> StateTypesForCheckpoint(string entityId)
    {
        if (!_entities.TryGetValue(entityId, out var entity))
            throw new TevScriptV3Exception("TEVS_IR_V3_ENTITY_UNKNOWN", $"unknown entity {entityId}");
        return new Dictionary<string, string>(entity.StateTypes, StringComparer.Ordinal);
    }

    internal void RestoreStateForCheckpoint(
        string entityId,
        IReadOnlyDictionary<string, TevScriptValueV3> values)
    {
        if (!_entities.TryGetValue(entityId, out var entity))
            throw new TevScriptV3Exception("TEVS_IR_V3_ENTITY_UNKNOWN", $"unknown entity {entityId}");
        if (values.Count != entity.StateTypes.Count || entity.StateTypes.Keys.Any(name => !values.ContainsKey(name)))
            throw new TevScriptV3Exception("TEVS_CHECKPOINT_V2_STATE_SET", $"checkpoint state set does not exactly match entity {entityId}");
        entity.State.Clear();
        foreach (var name in entity.StateTypes.Keys.OrderBy(item => item, StringComparer.Ordinal))
            entity.State.Add(name, values[name]);
    }

    public IReadOnlyList<TevScriptEmittedEventV3> Invoke(
        string entityId,
        string eventId,
        params TevScriptValueV3[] arguments)
    {
        RequireLocal(entityId, "entity");
        RequireLocal(eventId, "event");
        if (!_entities.TryGetValue(entityId, out var entity))
            throw new TevScriptV3Exception("TEVS_IR_V3_ENTITY_UNKNOWN", $"unknown entity {entityId}");
        var start = _emitted.Count;
        var queue = new Queue<(string EventId, TevScriptValueV3[] Arguments)>();
        queue.Enqueue((eventId, arguments));
        var maximum = _ir.GetProperty("boundary").GetProperty("maximum_event_chain").GetInt32();
        var processed = 0;

        while (queue.Count > 0)
        {
            if (++processed > maximum)
                throw new TevScriptV3Exception("TEVS_IR_V3_EVENT_BUDGET", $"event chain exceeds {maximum}");
            var current = queue.Dequeue();
            if (!entity.Handlers.TryGetValue(current.EventId, out var handler))
            {
                if (!entity.EmittedEventTypes.TryGetValue(current.EventId, out var signature))
                {
                    if (current.Arguments.Length != 0)
                        throw new TevScriptV3Exception(
                            "TEVS_IR_V3_EVENT_SIGNATURE_UNKNOWN",
                            $"unhandled event {current.EventId} has arguments but no portable signature");
                    signature = Array.Empty<string>();
                }
                if (signature.Length != current.Arguments.Length)
                    throw new TevScriptV3Exception("TEVS_IR_V3_EVENT_ARITY", $"event {current.EventId} expects {signature.Length} arguments");
                var coerced = new TevScriptValueV3[signature.Length];
                for (var index = 0; index < signature.Length; ++index)
                    coerced[index] = Normalize(signature[index], current.Arguments[index], $"invoke {entityId}.{current.EventId}[{index}]");
                _emitted.Add(new TevScriptEmittedEventV3(entityId, current.EventId, signature, coerced));
                continue;
            }

            var parameters = handler.GetProperty("parameters").EnumerateArray().ToArray();
            if (parameters.Length != current.Arguments.Length)
                throw new TevScriptV3Exception("TEVS_IR_V3_EVENT_ARITY", $"event {current.EventId} expects {parameters.Length} arguments");
            var parameterValues = new Dictionary<string, TevScriptValueV3>(StringComparer.Ordinal);
            for (var index = 0; index < parameters.Length; ++index)
            {
                var parameter = parameters[index];
                var typeId = parameter.GetProperty("type").GetString()!;
                parameterValues[parameter.GetProperty("name").GetString()!] = Normalize(
                    typeId,
                    current.Arguments[index],
                    $"invoke {entityId}.{current.EventId}[{index}]");
            }
            var generated = ExecuteHandler(entity, handler, parameterValues);
            foreach (var generatedEvent in generated)
            {
                var emitted = new TevScriptEmittedEventV3(
                    entityId,
                    generatedEvent.EventId,
                    generatedEvent.ArgumentTypes,
                    generatedEvent.Arguments);
                _emitted.Add(emitted);
                if (entity.Handlers.ContainsKey(generatedEvent.EventId))
                    queue.Enqueue((generatedEvent.EventId, generatedEvent.Arguments.ToArray()));
            }
        }
        return _emitted.Skip(start).ToArray();
    }

    public IReadOnlyDictionary<string, TevScriptValueV3> State(string entityId)
    {
        if (!_entities.TryGetValue(entityId, out var entity))
            throw new TevScriptV3Exception("TEVS_IR_V3_ENTITY_UNKNOWN", $"unknown entity {entityId}");
        return new Dictionary<string, TevScriptValueV3>(entity.State, StringComparer.Ordinal);
    }

    public string CanonicalStateJson(string entityId)
    {
        if (!_entities.TryGetValue(entityId, out var entity))
            throw new TevScriptV3Exception("TEVS_IR_V3_ENTITY_UNKNOWN", $"unknown entity {entityId}");
        using var stream = new MemoryStream();
        using (var writer = new Utf8JsonWriter(stream, new JsonWriterOptions { Indented = false, SkipValidation = false }))
        {
            writer.WriteStartObject();
            foreach (var name in entity.State.Keys.OrderBy(item => item, StringComparer.Ordinal))
            {
                writer.WritePropertyName(name);
                writer.WriteRawValue(
                    TevScriptValueCodecV3.EncodeCanonical(entity.StateTypes[name], entity.State[name], TypeTable, $"state {entityId}.{name}"),
                    skipInputValidation: false);
            }
            writer.WriteEndObject();
        }
        return Encoding.UTF8.GetString(stream.ToArray());
    }

    public string CanonicalEventArgumentsJson(TevScriptEmittedEventV3 emitted)
    {
        using var stream = new MemoryStream();
        using (var writer = new Utf8JsonWriter(stream, new JsonWriterOptions { Indented = false, SkipValidation = false }))
        {
            writer.WriteStartArray();
            for (var index = 0; index < emitted.ArgumentTypes.Count; ++index)
                writer.WriteRawValue(
                    TevScriptValueCodecV3.EncodeCanonical(
                        emitted.ArgumentTypes[index],
                        emitted.Arguments[index],
                        TypeTable,
                        $"event {emitted.EventId}[{index}]"),
                    skipInputValidation: false);
            writer.WriteEndArray();
        }
        return Encoding.UTF8.GetString(stream.ToArray());
    }

    private sealed record GeneratedEvent(string EventId, string[] ArgumentTypes, TevScriptValueV3[] Arguments);

    private List<GeneratedEvent> ExecuteHandler(
        Entity entity,
        JsonElement handler,
        Dictionary<string, TevScriptValueV3> parameters)
    {
        var instructions = handler.GetProperty("instructions");
        var budget = handler.GetProperty("instruction_budget").GetInt32();
        var stack = new List<TevScriptValueV3>();
        var locals = new Dictionary<string, TevScriptValueV3>(StringComparer.Ordinal);
        var emitted = new List<GeneratedEvent>();
        var pc = 0;
        var executed = 0;
        while (pc < instructions.GetArrayLength())
        {
            if (++executed > budget)
                throw new TevScriptV3Exception("TEVS_IR_V3_INSTRUCTION_BUDGET", $"handler {handler.GetProperty("event_id").GetString()} exceeded instruction budget {budget}");
            var instruction = instructions[pc];
            var op = instruction.GetProperty("op").GetString()!;
            switch (op)
            {
                case "CONST":
                {
                    var typeId = instruction.GetProperty("type").GetString()!;
                    stack.Add(TevScriptValueCodecV3.Decode(typeId, instruction.GetProperty("value"), TypeTable, $"instruction {handler.GetProperty("event_id").GetString()}:{pc}"));
                    break;
                }
                case "LOAD_STATE": stack.Add(entity.State[instruction.GetProperty("name").GetString()!]); break;
                case "STORE_STATE": entity.State[instruction.GetProperty("name").GetString()!] = Pop(stack); break;
                case "LOAD_LOCAL": stack.Add(locals[instruction.GetProperty("name").GetString()!]); break;
                case "STORE_LOCAL": locals[instruction.GetProperty("name").GetString()!] = Pop(stack); break;
                case "LOAD_PARAM": stack.Add(parameters[instruction.GetProperty("name").GetString()!]); break;
                case "CONVERT_INT_TO_RAT":
                {
                    var value = RequireInt(Pop(stack));
                    stack.Add(new TevRatV3(TevRationalV3.FromInteger(value)));
                    break;
                }
                case "UNARY":
                    stack.Add(Unary(instruction.GetProperty("operator").GetString()!, Pop(stack)));
                    break;
                case "BINARY":
                {
                    var right = Pop(stack);
                    var left = Pop(stack);
                    stack.Add(Binary(
                        instruction.GetProperty("operator").GetString()!,
                        instruction.GetProperty("left_type").GetString()!,
                        instruction.GetProperty("right_type").GetString()!,
                        left,
                        right));
                    break;
                }
                case "CALL_PURE":
                {
                    var args = PopArguments(stack, instruction.GetProperty("argc").GetInt32());
                    var result = CallPure(
                        instruction.GetProperty("function_id").GetString()!,
                        instruction.GetProperty("return_type").GetString()!,
                        args);
                    if (result is not null) stack.Add(result);
                    break;
                }
                case "CALL_CAPABILITY":
                {
                    var id = instruction.GetProperty("capability_id").GetString()!;
                    if (!_capabilities.TryGetValue(id, out var capability))
                        throw new TevScriptV3Exception("TEVS_IR_V3_CAPABILITY_MISSING", $"capability {id} is not bound");
                    var args = PopArguments(stack, instruction.GetProperty("argc").GetInt32());
                    var result = capability(args);
                    var returnType = instruction.GetProperty("return_type").GetString()!;
                    if (returnType != "Unit")
                    {
                        if (result is null)
                            throw new TevScriptV3Exception("TEVS_IR_V3_CAPABILITY_COERCION", $"capability {id} returned null for {returnType}");
                        stack.Add(Normalize(returnType, result, $"capability {id} return"));
                    }
                    break;
                }
                case "EMIT_EVENT":
                {
                    var types = instruction.GetProperty("argument_types").EnumerateArray().Select(item => item.GetString()!).ToArray();
                    var args = PopArguments(stack, instruction.GetProperty("argc").GetInt32()).ToArray();
                    for (var index = 0; index < args.Length; ++index)
                        args[index] = Normalize(types[index], args[index], $"emit {instruction.GetProperty("event_id").GetString()}[{index}]");
                    emitted.Add(new GeneratedEvent(instruction.GetProperty("event_id").GetString()!, types, args));
                    break;
                }
                case "MAKE_RECORD":
                {
                    var typeId = instruction.GetProperty("type").GetString()!;
                    var descriptor = TypeTable.Require(typeId);
                    var fields = instruction.GetProperty("fields").EnumerateArray().Select(item => item.GetString()!).ToArray();
                    var values = PopArguments(stack, fields.Length);
                    var byName = fields.Zip(values, (name, value) => (name, value)).ToDictionary(item => item.name, item => item.value, StringComparer.Ordinal);
                    var pairs = descriptor.Fields.Select(field => new KeyValuePair<string, TevScriptValueV3>(field.Name, byName[field.Name])).ToArray();
                    stack.Add(Normalize(typeId, new TevRecordV3(typeId, pairs), "MAKE_RECORD"));
                    break;
                }
                case "LOAD_FIELD":
                {
                    if (Pop(stack) is not TevRecordV3 record)
                        throw new TevScriptV3Exception("TEVS_IR_V3_RUNTIME_RECORD", "LOAD_FIELD received non-record value");
                    stack.Add(record.Field(instruction.GetProperty("field").GetString()!));
                    break;
                }
                case "MAKE_VARIANT":
                {
                    var typeId = instruction.GetProperty("type").GetString()!;
                    var variant = instruction.GetProperty("variant").GetString()!;
                    var value = instruction.GetProperty("argc").GetInt32() == 0
                        ? TevVariantV3.Empty(typeId, variant)
                        : TevVariantV3.WithPayload(typeId, variant, Pop(stack));
                    stack.Add(Normalize(typeId, value, "MAKE_VARIANT"));
                    break;
                }
                case "TEST_VARIANT":
                {
                    if (Pop(stack) is not TevVariantV3 value)
                        throw new TevScriptV3Exception("TEVS_IR_V3_RUNTIME_VARIANT", "TEST_VARIANT received non-variant value");
                    stack.Add(new TevBoolV3(value.Variant == instruction.GetProperty("variant").GetString()));
                    break;
                }
                case "LOAD_VARIANT_PAYLOAD":
                {
                    var variant = instruction.GetProperty("variant").GetString()!;
                    if (Pop(stack) is not TevVariantV3 value || value.Variant != variant || !value.HasPayload || value.Payload is null)
                        throw new TevScriptV3Exception("TEVS_IR_V3_VARIANT_UNWRAP", $"cannot load payload for variant {variant}");
                    stack.Add(value.Payload);
                    break;
                }
                case "JUMP_IF_FALSE":
                    if (!RequireBool(Pop(stack))) { pc = instruction.GetProperty("target").GetInt32(); continue; }
                    break;
                case "JUMP": pc = instruction.GetProperty("target").GetInt32(); continue;
                case "RETURN": pc = instructions.GetArrayLength(); continue;
                default: throw new TevScriptV3Exception("TEVS_IR_V3_OPCODE", $"unknown V3 opcode {op}");
            }
            ++pc;
        }
        if (stack.Count != 0)
            throw new TevScriptV3Exception("TEVS_IR_V3_RUNTIME_STACK_LEAK", $"handler {handler.GetProperty("event_id").GetString()} left {stack.Count} values on stack");
        return emitted;
    }

    private TevScriptValueV3 Normalize(string typeId, TevScriptValueV3 value, string context)
    {
        var canonical = TevScriptValueCodecV3.EncodeCanonical(typeId, value, TypeTable, context);
        var element = TevScriptStrictJsonV3.ParseElement(canonical);
        return TevScriptValueCodecV3.Decode(typeId, element, TypeTable, context);
    }

    private TevScriptValueV3 Binary(
        string op,
        string leftType,
        string rightType,
        TevScriptValueV3 left,
        TevScriptValueV3 right)
    {
        if (op is "AND" or "OR")
        {
            var a = RequireBool(left); var b = RequireBool(right);
            return new TevBoolV3(op == "AND" ? a && b : a || b);
        }
        if (op is "EQEQ" or "NE")
        {
            bool equal;
            if ((leftType == "Int" && rightType == "Rat") || (leftType == "Rat" && rightType == "Int"))
                equal = ToRational(left).Equals(ToRational(right));
            else if (leftType == rightType)
                equal = TevScriptValueCodecV3.ValuesEqual(leftType, left, right, TypeTable);
            else throw new TevScriptV3Exception("TEVS_IR_V3_RUNTIME_BINARY", "invalid equality types");
            return new TevBoolV3(op == "EQEQ" ? equal : !equal);
        }
        if (op is "LT" or "LE" or "GT" or "GE")
        {
            var comparison = ToRational(left).CompareTo(ToRational(right));
            return new TevBoolV3(op switch { "LT" => comparison < 0, "LE" => comparison <= 0, "GT" => comparison > 0, _ => comparison >= 0 });
        }
        if (op is "PLUS" or "MINUS") return AddSubtract(op, left, right);
        if (op == "STAR") return Multiply(left, right);
        if (op == "SLASH") return Divide(left, right);
        throw new TevScriptV3Exception("TEVS_IR_V3_RUNTIME_BINARY", $"unknown binary operator {op}");
    }

    private static TevScriptValueV3 AddSubtract(string op, TevScriptValueV3 left, TevScriptValueV3 right)
    {
        if (left is TevIntV3 a && right is TevIntV3 b) return new TevIntV3(op == "PLUS" ? a.Value + b.Value : a.Value - b.Value);
        if (left is TevRatV3 ar && right is TevRatV3 br) return new TevRatV3(op == "PLUS" ? ar.Value.Add(br.Value) : ar.Value.Subtract(br.Value));
        if (left is TevVectorV3 av && right is TevVectorV3 bv && av.TypeId == bv.TypeId && av.Components.Count == bv.Components.Count)
        {
            var values = av.Components.Zip(bv.Components, (x, y) => op == "PLUS" ? x.Add(y) : x.Subtract(y)).ToArray();
            return new TevVectorV3(av.TypeId, values);
        }
        throw new TevScriptV3Exception("TEVS_IR_V3_RUNTIME_BINARY", "invalid plus/minus operands");
    }

    private static TevScriptValueV3 Multiply(TevScriptValueV3 left, TevScriptValueV3 right)
    {
        if (left is TevIntV3 a && right is TevIntV3 b) return new TevIntV3(a.Value * b.Value);
        if (left is TevRatV3 ar && right is TevRatV3 br) return new TevRatV3(ar.Value.Multiply(br.Value));
        if (left is TevVectorV3 vector && right is TevRatV3 scalar)
            return new TevVectorV3(vector.TypeId, vector.Components.Select(item => item.Multiply(scalar.Value)).ToArray());
        if (right is TevVectorV3 vectorRight && left is TevRatV3 scalarLeft)
            return new TevVectorV3(vectorRight.TypeId, vectorRight.Components.Select(item => scalarLeft.Value.Multiply(item)).ToArray());
        throw new TevScriptV3Exception("TEVS_IR_V3_RUNTIME_BINARY", "invalid multiply operands");
    }

    private static TevScriptValueV3 Divide(TevScriptValueV3 left, TevScriptValueV3 right)
    {
        var divisor = ToRational(right);
        try
        {
            if (left is TevRatV3 rational) return new TevRatV3(rational.Value.Divide(divisor));
            if (left is TevVectorV3 vector)
                return new TevVectorV3(vector.TypeId, vector.Components.Select(item => item.Divide(divisor)).ToArray());
        }
        catch (DivideByZeroException error)
        {
            throw new TevScriptV3Exception("TEVS_IR_V3_DIVIDE_ZERO", error.Message);
        }
        throw new TevScriptV3Exception("TEVS_IR_V3_RUNTIME_BINARY", "invalid divide operands");
    }

    private static TevScriptValueV3 Unary(string op, TevScriptValueV3 value) => (op, value) switch
    {
        ("NOT", TevBoolV3 b) => new TevBoolV3(!b.Value),
        ("MINUS", TevIntV3 i) => new TevIntV3(BigInteger.Negate(i.Value)),
        ("MINUS", TevRatV3 r) => new TevRatV3(r.Value.Negate()),
        _ => throw new TevScriptV3Exception("TEVS_IR_V3_RUNTIME_UNARY", $"invalid unary operand for {op}"),
    };

    private static TevScriptValueV3? CallPure(string functionId, string returnType, IReadOnlyList<TevScriptValueV3> arguments)
    {
        if (functionId is "vec2" or "vec3")
            return new TevVectorV3(returnType, arguments.Select(value => ToRational(value)).ToArray());
        if (functionId is "min" or "max")
        {
            if (arguments.Count != 2) throw new TevScriptV3Exception("TEVS_IR_V3_PURE_ARITY", functionId);
            var comparison = ToRational(arguments[0]).CompareTo(ToRational(arguments[1]));
            return functionId == "max" ? (comparison >= 0 ? arguments[0] : arguments[1]) : (comparison <= 0 ? arguments[0] : arguments[1]);
        }
        throw new TevScriptV3Exception("TEVS_IR_V3_PURE_FUNCTION", $"unknown pure intrinsic {functionId}");
    }

    private static bool RequireBool(TevScriptValueV3 value) => value is TevBoolV3 b
        ? b.Value
        : throw new TevScriptV3Exception("TEVS_IR_V3_RUNTIME_BOOL", "expected Bool");

    private static BigInteger RequireInt(TevScriptValueV3 value) => value is TevIntV3 i
        ? i.Value
        : throw new TevScriptV3Exception("TEVS_IR_V3_RUNTIME_INT", "expected Int");

    private static TevRationalV3 ToRational(TevScriptValueV3 value) => value switch
    {
        TevRatV3 r => r.Value,
        TevIntV3 i => TevRationalV3.FromInteger(i.Value),
        _ => throw new TevScriptV3Exception("TEVS_IR_V3_RUNTIME_NUMBER", "expected Int or Rat"),
    };

    private static TevScriptValueV3 Pop(List<TevScriptValueV3> stack)
    {
        if (stack.Count == 0) throw new TevScriptV3Exception("TEVS_IR_V3_STACK_UNDERFLOW", "not enough values for operation");
        var value = stack[^1]; stack.RemoveAt(stack.Count - 1); return value;
    }

    private static IReadOnlyList<TevScriptValueV3> PopArguments(List<TevScriptValueV3> stack, int count)
    {
        if (count == 0) return Array.Empty<TevScriptValueV3>();
        if (count < 0 || stack.Count < count) throw new TevScriptV3Exception("TEVS_IR_V3_STACK_UNDERFLOW", "not enough values for operation");
        var start = stack.Count - count;
        var result = stack.GetRange(start, count).ToArray();
        stack.RemoveRange(start, count);
        return result;
    }

    private static void RequireLocal(string value, string kind)
    {
        if (!TevScriptLexicalV3.IsLocalIdentifier(value)) throw new TevScriptV3Exception("TEVS_IR_V3_INVOCATION_ID", $"non-canonical {kind} id {value}");
    }
}
