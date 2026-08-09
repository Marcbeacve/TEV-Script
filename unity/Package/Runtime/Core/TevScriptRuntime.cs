using System;
using System.Collections.Generic;
using System.Linq;
using System.Numerics;

namespace Marcbeacve.TevScript.Core
{
    public sealed partial class TevScriptRuntime
    {
        private readonly TevScriptProgram _program;
        private readonly Dictionary<string, ITevScriptCapability> _capabilities;
        private readonly Dictionary<string, RuntimeEntity> _entities;
        private readonly List<TevScriptEvent> _emitted =
            new List<TevScriptEvent>();

        public TevScriptRuntime(
            TevScriptProgram program,
            IEnumerable<ITevScriptCapability> capabilities = null)
        {
            _program = program ?? throw new ArgumentNullException(nameof(program));
            _capabilities = new Dictionary<string, ITevScriptCapability>(
                StringComparer.Ordinal);
            if (capabilities != null)
            {
                foreach (ITevScriptCapability capability in capabilities)
                {
                    if (capability == null)
                    {
                        throw new ArgumentException(
                            "Capabilities cannot contain null.",
                            nameof(capabilities));
                    }
                    string capabilityId = TevScriptId.RequireStableId(
                        capability.CapabilityId,
                        "TEVS_RUNTIME_CAPABILITY_BINDING_ID");
                    if (_capabilities.ContainsKey(capabilityId))
                    {
                        throw new TevContractException(
                            "TEVS_CS_CAPABILITY_DUPLICATE",
                            "Duplicate capability " + capabilityId + ".");
                    }
                    _capabilities.Add(capabilityId, capability);
                }
            }

            _entities = program.Entities.ToDictionary(
                item => item.EntityId,
                item => new RuntimeEntity(item),
                StringComparer.Ordinal);
        }

        public IReadOnlyList<TevScriptEvent> EmittedEvents
        {
            get { return _emitted.AsReadOnly(); }
        }

        public IReadOnlyList<TevScriptEvent> Invoke(
            string entityId,
            string eventId,
            params TevScriptValue[] arguments)
        {
            entityId = TevScriptId.RequireIdentifier(
                entityId,
                "TEVS_RUNTIME_INVOCATION_ID");
            eventId = TevScriptId.RequireIdentifier(
                eventId,
                "TEVS_RUNTIME_INVOCATION_ID");
            RuntimeEntity entity;
            if (!_entities.TryGetValue(entityId, out entity))
            {
                throw new TevContractException(
                    "TEVS_CS_ENTITY_UNKNOWN",
                    "Unknown entity " + entityId + ".");
            }

            int start = _emitted.Count;
            var queue = new Queue<PendingEvent>();
            queue.Enqueue(new PendingEvent(
                eventId,
                Array.AsReadOnly(arguments ?? new TevScriptValue[0])));
            int processed = 0;

            while (queue.Count != 0)
            {
                processed++;
                if (processed > _program.MaximumEventChain)
                {
                    throw new TevContractException(
                        "TEVS_CS_EVENT_BUDGET",
                        "Event chain exceeds " +
                        _program.MaximumEventChain + ".");
                }

                PendingEvent current = queue.Dequeue();
                TevScriptHandlerDefinition handler;
                if (!entity.Definition.Handlers.TryGetValue(
                        current.EventId,
                        out handler))
                {
                    _emitted.Add(new TevScriptEvent(
                        entityId,
                        current.EventId,
                        current.Arguments));
                    continue;
                }

                Dictionary<string, TevScriptValue> parameters =
                    BindParameters(handler, current.Arguments);
                IReadOnlyList<PendingEvent> generated = ExecuteHandler(
                    entity,
                    handler,
                    parameters);
                foreach (PendingEvent item in generated)
                {
                    _emitted.Add(new TevScriptEvent(
                        entityId,
                        item.EventId,
                        item.Arguments));
                    if (entity.Definition.Handlers.ContainsKey(item.EventId))
                    {
                        queue.Enqueue(item);
                    }
                }
            }

            return _emitted.Skip(start).ToArray();
        }

        public IReadOnlyDictionary<string, TevScriptValue> State(
            string entityId)
        {
            RuntimeEntity entity;
            if (!_entities.TryGetValue(entityId, out entity))
            {
                throw new KeyNotFoundException(entityId);
            }
            return new Dictionary<string, TevScriptValue>(
                entity.State,
                StringComparer.Ordinal);
        }

        public Dictionary<string, object> EncodedState(string entityId)
        {
            RuntimeEntity entity;
            if (!_entities.TryGetValue(entityId, out entity))
            {
                throw new KeyNotFoundException(entityId);
            }
            var result = new Dictionary<string, object>(StringComparer.Ordinal);
            foreach (string name in entity.State.Keys.OrderBy(
                         item => item,
                         StringComparer.Ordinal))
            {
                TevScriptValue value = entity.State[name];
                result.Add(
                    name,
                    new Dictionary<string, object>(StringComparer.Ordinal)
                    {
                        ["type"] = value.TypeName,
                        ["value"] = value.ToCanonicalObject()
                    });
            }
            return result;
        }

        private static Dictionary<string, TevScriptValue> BindParameters(
            TevScriptHandlerDefinition handler,
            IReadOnlyList<TevScriptValue> arguments)
        {
            if (handler.Parameters.Count != arguments.Count)
            {
                throw new TevContractException(
                    "TEVS_CS_EVENT_ARITY",
                    "Event " + handler.EventId + " expects " +
                    handler.Parameters.Count + " arguments.");
            }
            var result = new Dictionary<string, TevScriptValue>(
                StringComparer.Ordinal);
            for (int index = 0; index < handler.Parameters.Count; index++)
            {
                TevScriptParameterDefinition parameter =
                    handler.Parameters[index];
                result.Add(
                    parameter.Name,
                    Widen(arguments[index], parameter.TypeName));
            }
            return result;
        }

        private IReadOnlyList<PendingEvent> ExecuteHandler(
            RuntimeEntity entity,
            TevScriptHandlerDefinition handler,
            IReadOnlyDictionary<string, TevScriptValue> parameters)
        {
            var stack = new List<TevScriptValue>();
            var locals = new Dictionary<string, TevScriptValue>(
                StringComparer.Ordinal);
            var emitted = new List<PendingEvent>();
            int pc = 0;
            int executed = 0;

            while (pc < handler.Instructions.Count)
            {
                executed++;
                if (executed > handler.InstructionBudget)
                {
                    throw new TevContractException(
                        "TEVS_CS_INSTRUCTION_BUDGET",
                        "Handler " + handler.EventId +
                        " exceeded its instruction budget.");
                }

                Dictionary<string, object> instruction =
                    handler.Instructions[pc];
                string op = TevJson.RequireString(instruction, "op");
                switch (op)
                {
                    case "CONST":
                        stack.Add(TevScriptValue.Decode(
                            TevJson.RequireString(instruction, "type"),
                            instruction["value"]));
                        break;
                    case "LOAD_STATE":
                        stack.Add(entity.State[
                            TevJson.RequireString(instruction, "name")]);
                        break;
                    case "STORE_STATE":
                    {
                        string name = TevJson.RequireString(
                            instruction,
                            "name");
                        string typeName = TevJson.RequireString(
                            instruction,
                            "type");
                        entity.State[name] = Widen(Pop(stack), typeName);
                        break;
                    }
                    case "LOAD_LOCAL":
                        stack.Add(locals[
                            TevJson.RequireString(instruction, "name")]);
                        break;
                    case "STORE_LOCAL":
                    {
                        string name = TevJson.RequireString(
                            instruction,
                            "name");
                        string typeName = TevJson.RequireString(
                            instruction,
                            "type");
                        locals[name] = Widen(Pop(stack), typeName);
                        break;
                    }
                    case "LOAD_PARAM":
                        stack.Add(parameters[
                            TevJson.RequireString(instruction, "name")]);
                        break;
                    case "CONVERT_INT_TO_RAT":
                        stack.Add(TevScriptValue.Rat(
                            TevRational.FromInteger(Pop(stack).AsInt())));
                        break;
                    case "UNARY":
                        stack.Add(Unary(
                            TevJson.RequireString(instruction, "operator"),
                            Pop(stack)));
                        break;
                    case "BINARY":
                    {
                        TevScriptValue right = Pop(stack);
                        TevScriptValue left = Pop(stack);
                        stack.Add(Binary(
                            TevJson.RequireString(instruction, "operator"),
                            left,
                            right));
                        break;
                    }
                    case "CALL_PURE":
                    {
                        int count = TevScriptProgram.RequireInt32(
                            instruction["argc"],
                            "argc");
                        TevScriptValue result = CallPure(
                            TevJson.RequireString(
                                instruction,
                                "function_id"),
                            PopArguments(stack, count));
                        if (TevJson.RequireString(
                                instruction,
                                "return_type") != "Unit")
                        {
                            stack.Add(result);
                        }
                        break;
                    }
                    case "CALL_CAPABILITY":
                    {
                        string capabilityId = TevJson.RequireString(
                            instruction,
                            "capability_id");
                        ITevScriptCapability capability;
                        if (!_capabilities.TryGetValue(
                                capabilityId,
                                out capability))
                        {
                            throw new TevContractException(
                                "TEVS_CS_CAPABILITY_MISSING",
                                "Capability " + capabilityId +
                                " is not bound.");
                        }
                        int count = TevScriptProgram.RequireInt32(
                            instruction["argc"],
                            "argc");
                        IReadOnlyList<TevScriptValue> callArguments =
                            PopArguments(stack, count);
                        TevScriptValue result = capability.Invoke(
                            callArguments);
                        string returnType = TevJson.RequireString(
                            instruction,
                            "return_type");
                        if (returnType != "Unit")
                        {
                            stack.Add(Widen(result, returnType));
                        }
                        break;
                    }
                    case "EMIT_EVENT":
                    {
                        int count = TevScriptProgram.RequireInt32(
                            instruction["argc"],
                            "argc");
                        emitted.Add(new PendingEvent(
                            TevJson.RequireString(
                                instruction,
                                "event_id"),
                            PopArguments(stack, count)));
                        break;
                    }
                    case "JUMP_IF_FALSE":
                        if (!Pop(stack).AsBool())
                        {
                            pc = TevScriptProgram.RequireInt32(
                                instruction["target"],
                                "target");
                            continue;
                        }
                        break;
                    case "JUMP":
                        pc = TevScriptProgram.RequireInt32(
                            instruction["target"],
                            "target");
                        continue;
                    case "RETURN":
                        pc = handler.Instructions.Count;
                        continue;
                    default:
                        throw new TevContractException(
                            "TEVS_CS_OPCODE",
                            "Unknown opcode " + op + ".");
                }
                pc++;
            }

            if (stack.Count != 0)
            {
                throw new TevContractException(
                    "TEVS_CS_STACK_LEAK",
                    "Handler " + handler.EventId + " left " +
                    stack.Count + " values on the stack.");
            }
            return emitted.AsReadOnly();
        }

        private static TevScriptValue Unary(
            string op,
            TevScriptValue value)
        {
            switch (op)
            {
                case "NOT":
                    return TevScriptValue.Bool(!value.AsBool());
                case "MINUS":
                    if (value.TypeName == "Int")
                    {
                        return TevScriptValue.Int(
                            BigInteger.Negate(value.AsInt()));
                    }
                    if (value.TypeName == "Rat")
                    {
                        return TevScriptValue.Rat(-value.AsRat());
                    }
                    if (value.TypeName == "Vec2" ||
                        value.TypeName == "Vec3")
                    {
                        TevRational[] vector = value.AsVector()
                            .Select(item => -item)
                            .ToArray();
                        return vector.Length == 2
                            ? TevScriptValue.Vec2(vector[0], vector[1])
                            : TevScriptValue.Vec3(
                                vector[0],
                                vector[1],
                                vector[2]);
                    }
                    break;
            }
            throw new TevContractException(
                "TEVS_CS_UNARY",
                "Operator " + op + " does not accept " +
                value.TypeName + ".");
        }

        private static TevScriptValue Binary(
            string op,
            TevScriptValue left,
            TevScriptValue right)
        {
            switch (op)
            {
                case "AND":
                    return TevScriptValue.Bool(
                        left.AsBool() && right.AsBool());
                case "OR":
                    return TevScriptValue.Bool(
                        left.AsBool() || right.AsBool());
                case "EQEQ":
                    return TevScriptValue.Bool(left.Equals(right));
                case "NE":
                    return TevScriptValue.Bool(!left.Equals(right));
                case "LT":
                    return TevScriptValue.Bool(Compare(left, right) < 0);
                case "LE":
                    return TevScriptValue.Bool(Compare(left, right) <= 0);
                case "GT":
                    return TevScriptValue.Bool(Compare(left, right) > 0);
                case "GE":
                    return TevScriptValue.Bool(Compare(left, right) >= 0);
                case "PLUS":
                    return Add(left, right);
                case "MINUS":
                    return Subtract(left, right);
                case "STAR":
                    return Multiply(left, right);
                case "SLASH":
                    return Divide(left, right);
                default:
                    throw new TevContractException(
                        "TEVS_CS_BINARY",
                        "Unknown binary operator " + op + ".");
            }
        }

        private static TevScriptValue Add(
            TevScriptValue left,
            TevScriptValue right)
        {
            if (left.TypeName == "Int" && right.TypeName == "Int")
            {
                return TevScriptValue.Int(left.AsInt() + right.AsInt());
            }
            if (left.TypeName == "Rat" && right.TypeName == "Rat")
            {
                return TevScriptValue.Rat(left.AsRat() + right.AsRat());
            }
            return VectorBinary(left, right, (a, b) => a + b);
        }

        private static TevScriptValue Subtract(
            TevScriptValue left,
            TevScriptValue right)
        {
            if (left.TypeName == "Int" && right.TypeName == "Int")
            {
                return TevScriptValue.Int(left.AsInt() - right.AsInt());
            }
            if (left.TypeName == "Rat" && right.TypeName == "Rat")
            {
                return TevScriptValue.Rat(left.AsRat() - right.AsRat());
            }
            return VectorBinary(left, right, (a, b) => a - b);
        }

        private static TevScriptValue Multiply(
            TevScriptValue left,
            TevScriptValue right)
        {
            if (left.TypeName == "Int" && right.TypeName == "Int")
            {
                return TevScriptValue.Int(left.AsInt() * right.AsInt());
            }
            if (left.TypeName == "Rat" && right.TypeName == "Rat")
            {
                return TevScriptValue.Rat(left.AsRat() * right.AsRat());
            }
            if (left.TypeName == "Vec2" || left.TypeName == "Vec3")
            {
                return VectorScale(left, right.AsRat());
            }
            if (right.TypeName == "Vec2" || right.TypeName == "Vec3")
            {
                return VectorScale(right, left.AsRat());
            }
            throw new TevContractException(
                "TEVS_CS_MULTIPLY",
                "Unsupported multiplication types.");
        }

        private static TevScriptValue Divide(
            TevScriptValue left,
            TevScriptValue right)
        {
            if (left.TypeName == "Rat" && right.TypeName == "Rat")
            {
                return TevScriptValue.Rat(left.AsRat() / right.AsRat());
            }
            if (left.TypeName == "Vec2" || left.TypeName == "Vec3")
            {
                TevRational divisor = right.AsRat();
                return VectorScale(
                    left,
                    TevRational.One / divisor);
            }
            throw new TevContractException(
                "TEVS_CS_DIVIDE",
                "Unsupported division types.");
        }

        private static TevScriptValue VectorBinary(
            TevScriptValue left,
            TevScriptValue right,
            Func<TevRational, TevRational, TevRational> operation)
        {
            if (left.TypeName != right.TypeName ||
                (left.TypeName != "Vec2" && left.TypeName != "Vec3"))
            {
                throw new TevContractException(
                    "TEVS_CS_VECTOR_OPERAND",
                    "Vector operations require equal vector types.");
            }
            TevRational[] result = left.AsVector()
                .Zip(right.AsVector(), operation)
                .ToArray();
            return result.Length == 2
                ? TevScriptValue.Vec2(result[0], result[1])
                : TevScriptValue.Vec3(result[0], result[1], result[2]);
        }

        private static TevScriptValue VectorScale(
            TevScriptValue vector,
            TevRational scalar)
        {
            TevRational[] result = vector.AsVector()
                .Select(item => item * scalar)
                .ToArray();
            return result.Length == 2
                ? TevScriptValue.Vec2(result[0], result[1])
                : TevScriptValue.Vec3(result[0], result[1], result[2]);
        }

        private static int Compare(
            TevScriptValue left,
            TevScriptValue right)
        {
            if (left.TypeName != right.TypeName)
            {
                throw new TevContractException(
                    "TEVS_CS_COMPARE_TYPE",
                    "Comparison requires equal types.");
            }
            switch (left.TypeName)
            {
                case "Int":
                    return left.AsInt().CompareTo(right.AsInt());
                case "Rat":
                    return left.AsRat().CompareTo(right.AsRat());
                case "Text":
                    return string.CompareOrdinal(
                        left.AsText(),
                        right.AsText());
                default:
                    throw new TevContractException(
                        "TEVS_CS_COMPARE_TYPE",
                        "Type " + left.TypeName +
                        " is not ordered.");
            }
        }

        private static TevScriptValue CallPure(
            string functionId,
            IReadOnlyList<TevScriptValue> arguments)
        {
            switch (functionId)
            {
                case "vec2":
                    return TevScriptValue.Vec2(
                        arguments[0].AsRat(),
                        arguments[1].AsRat());
                case "vec3":
                    return TevScriptValue.Vec3(
                        arguments[0].AsRat(),
                        arguments[1].AsRat(),
                        arguments[2].AsRat());
                case "max":
                    return Compare(arguments[0], arguments[1]) >= 0
                        ? arguments[0]
                        : arguments[1];
                case "min":
                    return Compare(arguments[0], arguments[1]) <= 0
                        ? arguments[0]
                        : arguments[1];
                default:
                    throw new TevContractException(
                        "TEVS_CS_PURE_FUNCTION",
                        "Unknown pure function " + functionId + ".");
            }
        }

        private static TevScriptValue Widen(
            TevScriptValue value,
            string expectedType)
        {
            if (value == null)
            {
                throw new TevContractException(
                    "TEVS_CS_VALUE_NULL",
                    "Runtime values cannot be null.");
            }
            if (value.TypeName == expectedType)
            {
                return value;
            }
            if (value.TypeName == "Int" && expectedType == "Rat")
            {
                return TevScriptValue.Rat(
                    TevRational.FromInteger(value.AsInt()));
            }
            throw new TevContractException(
                "TEVS_CS_VALUE_TYPE",
                "Expected " + expectedType + ", got " +
                value.TypeName + ".");
        }

        private static TevScriptValue Pop(List<TevScriptValue> stack)
        {
            if (stack.Count == 0)
            {
                throw new TevContractException(
                    "TEVS_CS_STACK_UNDERFLOW",
                    "Runtime stack is empty.");
            }
            int index = stack.Count - 1;
            TevScriptValue value = stack[index];
            stack.RemoveAt(index);
            return value;
        }

        private static IReadOnlyList<TevScriptValue> PopArguments(
            List<TevScriptValue> stack,
            int count)
        {
            if (count < 0 || stack.Count < count)
            {
                throw new TevContractException(
                    "TEVS_CS_STACK_UNDERFLOW",
                    "Not enough values for call.");
            }
            if (count == 0)
            {
                return new TevScriptValue[0];
            }
            int start = stack.Count - count;
            TevScriptValue[] result = stack.Skip(start).ToArray();
            stack.RemoveRange(start, count);
            return result;
        }

        private sealed class RuntimeEntity
        {
            public RuntimeEntity(TevScriptEntityDefinition definition)
            {
                Definition = definition;
                State = definition.States.ToDictionary(
                    item => item.Name,
                    item => item.Initial,
                    StringComparer.Ordinal);
            }

            public TevScriptEntityDefinition Definition { get; }
            public Dictionary<string, TevScriptValue> State { get; }
        }

        private sealed class PendingEvent
        {
            public PendingEvent(
                string eventId,
                IReadOnlyList<TevScriptValue> arguments)
            {
                EventId = eventId;
                Arguments = arguments;
            }

            public string EventId { get; }
            public IReadOnlyList<TevScriptValue> Arguments { get; }
        }
    }
}
