using System;
using System.Collections.Generic;
using System.Linq;

namespace Marcbeacve.TevScript.Core
{
    internal static class TevScriptIrFlowVerifier
    {
        public static void Validate(
            Dictionary<string, object> entity,
            Dictionary<string, object> handler,
            string path)
        {
            var states = ReadNameTypes(
                TevJson.RequireArray(entity, "states"),
                "name",
                "type");
            var parameters = ReadNameTypes(
                TevJson.RequireArray(handler, "parameters"),
                "name",
                "type");
            var locals = ReadNameTypes(
                TevJson.RequireArray(handler, "locals"),
                "name",
                "type");
            var capabilities = ReadCapabilities(
                TevJson.RequireArray(entity, "capabilities"));
            var events = ReadEvents(
                TevJson.RequireArray(entity, "emitted_events"));
            List<object> rawInstructions = TevJson.RequireArray(
                handler,
                "instructions");
            var instructions = rawInstructions
                .Select((item, index) => TevJson.RequireObject(
                    item,
                    path + ".instructions[" + index + "]"))
                .ToList();

            var incoming = new FlowState[instructions.Count];
            incoming[0] = new FlowState(
                new List<string>(),
                new HashSet<string>(StringComparer.Ordinal));
            bool reachedReturn = false;

            for (int pc = 0; pc < instructions.Count; pc++)
            {
                FlowState state = incoming[pc];
                if (state == null) continue;
                var stack = new List<string>(state.Stack);
                var initialized = new HashSet<string>(
                    state.Initialized,
                    StringComparer.Ordinal);
                Dictionary<string, object> instruction = instructions[pc];
                string op = TevJson.RequireString(instruction, "op");
                string currentPath = path + ".instructions[" + pc + "]";

                Action<string> pop = expected =>
                {
                    if (stack.Count == 0)
                    {
                        Fail(
                            currentPath,
                            "stack underflow; expected " + expected);
                    }
                    int index = stack.Count - 1;
                    string actual = stack[index];
                    stack.RemoveAt(index);
                    if (!string.Equals(actual, expected, StringComparison.Ordinal))
                    {
                        Fail(
                            currentPath,
                            "stack type mismatch; expected " + expected +
                            ", got " + actual);
                    }
                };

                switch (op)
                {
                    case "CONST":
                        stack.Add(TevJson.RequireString(instruction, "type"));
                        break;
                    case "LOAD_STATE":
                        stack.Add(states[TevJson.RequireString(instruction, "name")]);
                        break;
                    case "STORE_STATE":
                        pop(states[TevJson.RequireString(instruction, "name")]);
                        break;
                    case "LOAD_LOCAL":
                    {
                        string name = TevJson.RequireString(instruction, "name");
                        if (!initialized.Contains(name))
                        {
                            Fail(
                                currentPath,
                                "local '" + name + "' is not definitely initialized");
                        }
                        stack.Add(locals[name]);
                        break;
                    }
                    case "STORE_LOCAL":
                    {
                        string name = TevJson.RequireString(instruction, "name");
                        pop(locals[name]);
                        initialized.Add(name);
                        break;
                    }
                    case "LOAD_PARAM":
                        stack.Add(parameters[
                            TevJson.RequireString(instruction, "name")]);
                        break;
                    case "CONVERT_INT_TO_RAT":
                        pop("Int");
                        stack.Add("Rat");
                        break;
                    case "UNARY":
                    {
                        string result = TevJson.RequireString(instruction, "type");
                        string operatorName = TevJson.RequireString(
                            instruction,
                            "operator");
                        pop(operatorName == "NOT" ? "Bool" : result);
                        stack.Add(result);
                        break;
                    }
                    case "BINARY":
                    {
                        string operatorName = TevJson.RequireString(
                            instruction,
                            "operator");
                        string left = TevJson.RequireString(
                            instruction,
                            "left_type");
                        string right = TevJson.RequireString(
                            instruction,
                            "right_type");
                        string result = TevJson.RequireString(
                            instruction,
                            "result_type");
                        if (!BinarySignature(operatorName, left, right, result))
                        {
                            Fail(
                                currentPath,
                                "binary operator/type contract is not a V0.2 lowering");
                        }
                        pop(right);
                        pop(left);
                        stack.Add(result);
                        break;
                    }
                    case "CALL_PURE":
                    {
                        string functionId = TevJson.RequireString(
                            instruction,
                            "function_id");
                        string returnType = TevJson.RequireString(
                            instruction,
                            "return_type");
                        string[] expected;
                        if (functionId == "vec2")
                            expected = new[] { "Rat", "Rat" };
                        else if (functionId == "vec3")
                            expected = new[] { "Rat", "Rat", "Rat" };
                        else if (functionId == "max" || functionId == "min")
                            expected = new[] { returnType, returnType };
                        else
                        {
                            Fail(
                                currentPath,
                                "unknown pure function '" + functionId + "'");
                            return;
                        }
                        for (int index = expected.Length - 1; index >= 0; index--)
                            pop(expected[index]);
                        if (returnType != "Unit") stack.Add(returnType);
                        break;
                    }
                    case "CALL_CAPABILITY":
                    {
                        string capabilityId = TevJson.RequireString(
                            instruction,
                            "capability_id");
                        CapabilityFlowSignature signature = capabilities[capabilityId];
                        for (int index = signature.Parameters.Length - 1;
                            index >= 0;
                            index--)
                        {
                            pop(signature.Parameters[index]);
                        }
                        if (signature.ReturnType != "Unit")
                            stack.Add(signature.ReturnType);
                        break;
                    }
                    case "EMIT_EVENT":
                    {
                        string eventId = TevJson.RequireString(
                            instruction,
                            "event_id");
                        string[] expected = events[eventId];
                        for (int index = expected.Length - 1; index >= 0; index--)
                            pop(expected[index]);
                        break;
                    }
                    case "JUMP_IF_FALSE":
                    {
                        pop("Bool");
                        int target = TevScriptProgram.RequireInt32(
                            instruction["target"],
                            currentPath + ".target");
                        Merge(
                            incoming,
                            target,
                            stack,
                            initialized,
                            currentPath,
                            instructions.Count);
                        if (pc + 1 >= instructions.Count)
                            Fail(currentPath, "conditional fallthrough exits the handler");
                        Merge(
                            incoming,
                            pc + 1,
                            stack,
                            initialized,
                            currentPath,
                            instructions.Count);
                        continue;
                    }
                    case "JUMP":
                    {
                        int target = TevScriptProgram.RequireInt32(
                            instruction["target"],
                            currentPath + ".target");
                        Merge(
                            incoming,
                            target,
                            stack,
                            initialized,
                            currentPath,
                            instructions.Count);
                        continue;
                    }
                    case "RETURN":
                        if (stack.Count != 0)
                        {
                            Fail(
                                currentPath,
                                "RETURN requires empty stack, found [" +
                                string.Join(",", stack.ToArray()) + "]");
                        }
                        reachedReturn = true;
                        continue;
                    default:
                        Fail(currentPath, "unknown opcode '" + op + "'");
                        break;
                }

                if (pc + 1 >= instructions.Count)
                    Fail(currentPath, "reachable control flow falls off the handler");
                Merge(
                    incoming,
                    pc + 1,
                    stack,
                    initialized,
                    currentPath,
                    instructions.Count);
            }

            if (!reachedReturn) Fail(path, "no reachable RETURN");
        }

        private static void Merge(
            FlowState[] incoming,
            int target,
            List<string> stack,
            HashSet<string> initialized,
            string source,
            int instructionCount)
        {
            if (target < 0 || target >= instructionCount)
            {
                Fail(
                    source,
                    "control flow must target an instruction, not handler exit");
            }
            var next = new FlowState(
                new List<string>(stack),
                new HashSet<string>(initialized, StringComparer.Ordinal));
            FlowState current = incoming[target];
            if (current == null)
            {
                incoming[target] = next;
                return;
            }
            if (!current.Stack.SequenceEqual(next.Stack, StringComparer.Ordinal))
            {
                Fail(
                    source,
                    "CFG merge stack mismatch at instruction " + target);
            }
            var intersection = new HashSet<string>(
                current.Initialized,
                StringComparer.Ordinal);
            intersection.IntersectWith(next.Initialized);
            incoming[target] = new FlowState(
                new List<string>(current.Stack),
                intersection);
        }

        private static bool BinarySignature(
            string operatorName,
            string left,
            string right,
            string result)
        {
            if (operatorName == "AND" || operatorName == "OR")
                return left == "Bool" && right == "Bool" && result == "Bool";
            if (operatorName == "EQEQ" || operatorName == "NE")
                return result == "Bool" && left == right;
            if (operatorName == "LT" || operatorName == "LE" ||
                operatorName == "GT" || operatorName == "GE")
            {
                return left == right && (left == "Int" || left == "Rat") && result == "Bool";
            }
            if (operatorName == "PLUS" || operatorName == "MINUS")
            {
                return (left == "Int" && right == "Int" && result == "Int") ||
                    (left == "Rat" && right == "Rat" && result == "Rat") ||
                    (left == right && result == left &&
                        (result == "Vec2" || result == "Vec3"));
            }
            if (operatorName == "STAR")
            {
                return (left == "Int" && right == "Int" && result == "Int") ||
                    (left == "Rat" && right == "Rat" && result == "Rat") ||
                    ((left == "Vec2" || left == "Vec3") &&
                        right == "Rat" && result == left) ||
                    ((right == "Vec2" || right == "Vec3") &&
                        left == "Rat" && result == right);
            }
            if (operatorName == "SLASH")
            {
                return (left == "Rat" && right == "Rat" && result == "Rat") ||
                    ((left == "Vec2" || left == "Vec3") &&
                        right == "Rat" && result == left);
            }
            return false;
        }

        private static Dictionary<string, string> ReadNameTypes(
            List<object> raw,
            string nameField,
            string typeField)
        {
            var result = new Dictionary<string, string>(StringComparer.Ordinal);
            foreach (object item in raw)
            {
                Dictionary<string, object> obj = TevJson.RequireObject(item, nameField);
                result.Add(
                    TevJson.RequireString(obj, nameField),
                    TevJson.RequireString(obj, typeField));
            }
            return result;
        }

        private static Dictionary<string, CapabilityFlowSignature> ReadCapabilities(
            List<object> raw)
        {
            var result = new Dictionary<string, CapabilityFlowSignature>(
                StringComparer.Ordinal);
            foreach (object item in raw)
            {
                Dictionary<string, object> obj = TevJson.RequireObject(
                    item,
                    "capability");
                string id = TevJson.RequireString(obj, "capability_id");
                string[] parameters = TevJson.RequireArray(obj, "parameters")
                    .Select(value => (string)value)
                    .ToArray();
                result.Add(
                    id,
                    new CapabilityFlowSignature(
                        parameters,
                        TevJson.RequireString(obj, "return_type")));
            }
            return result;
        }

        private static Dictionary<string, string[]> ReadEvents(List<object> raw)
        {
            var result = new Dictionary<string, string[]>(StringComparer.Ordinal);
            foreach (object item in raw)
            {
                Dictionary<string, object> obj = TevJson.RequireObject(item, "event");
                result.Add(
                    TevJson.RequireString(obj, "event_id"),
                    TevJson.RequireArray(obj, "parameters")
                        .Select(value => (string)value)
                        .ToArray());
            }
            return result;
        }

        private static void Fail(string path, string message)
        {
            throw new TevContractException(
                "TEVS_IR_FLOW_INVALID",
                message,
                path);
        }

        private sealed class FlowState
        {
            public FlowState(List<string> stack, HashSet<string> initialized)
            {
                Stack = stack;
                Initialized = initialized;
            }

            public List<string> Stack { get; }
            public HashSet<string> Initialized { get; }
        }

        private sealed class CapabilityFlowSignature
        {
            public CapabilityFlowSignature(string[] parameters, string returnType)
            {
                Parameters = parameters;
                ReturnType = returnType;
            }

            public string[] Parameters { get; }
            public string ReturnType { get; }
        }
    }
}
