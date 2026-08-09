using System;
using System.Collections.Generic;
using System.Linq;
using System.Numerics;

namespace Marcbeacve.TevScript.Core
{
    internal static class TevScriptIrValidator
    {
        private const int MaxEntities = 128;
        private const int MaxStatesPerEntity = 256;
        private const int MaxHandlersPerEntity = 256;
        private const int MaxLocalsPerHandler = 256;
        private const int MaxArguments = 64;
        private const int MaxInstructionsPerHandler = 8192;
        private const int MaxEventChain = 128;

        private static readonly HashSet<string> TypeNames =
            new HashSet<string>(StringComparer.Ordinal)
            {
                "Bool", "Int", "Rat", "Text", "Vec2", "Vec3", "Unit"
            };

        private static readonly HashSet<string> ValueTypeNames =
            new HashSet<string>(StringComparer.Ordinal)
            {
                "Bool", "Int", "Rat", "Text", "Vec2", "Vec3"
            };

        private static readonly HashSet<string> CapabilityKinds =
            new HashSet<string>(StringComparer.Ordinal)
            {
                "observation", "effect"
            };

        private static readonly string[] BoundaryFlags =
        {
            "dynamic_code",
            "reflection",
            "unbounded_loops",
            "implicit_physical_effects",
            "runtime_source_compilation",
            "automatic_authority_escalation"
        };

        public static void Validate(Dictionary<string, object> root)
        {
            if (root == null) throw new ArgumentNullException(nameof(root));
            TevJson.RequireExactKeys(
                root,
                "$",
                "schema",
                "language_version",
                "program_id",
                "entities",
                "boundary",
                "semantic_hash",
                "debug",
                "debug_hash");

            if (TevJson.RequireString(root, "schema") != TevScriptProgram.Schema)
                Fail("$.schema", "Expected " + TevScriptProgram.Schema + ".");
            if (TevJson.RequireString(root, "language_version") !=
                TevScriptProgram.LanguageVersion)
            {
                Fail(
                    "$.language_version",
                    "Expected " + TevScriptProgram.LanguageVersion + ".");
            }

            RequireIdentifier(root["program_id"], "$.program_id");
            RequireHash(root["semantic_hash"], "$.semantic_hash");
            RequireHash(root["debug_hash"], "$.debug_hash");

            Dictionary<string, object> boundary = TevJson.RequireObject(
                root["boundary"],
                "$.boundary");
            var boundaryKeys = new List<string>(BoundaryFlags)
            {
                "maximum_event_chain"
            };
            TevJson.RequireExactKeys(
                boundary,
                "$.boundary",
                boundaryKeys.ToArray());
            foreach (string flag in BoundaryFlags)
            {
                if (TevJson.RequireBoolean(
                        boundary[flag],
                        "$.boundary." + flag))
                {
                    Fail(
                        "$.boundary." + flag,
                        "Boundary flag must be false.",
                        "TEVS_CS_BOUNDARY");
                }
            }
            RequireInteger(
                boundary["maximum_event_chain"],
                "$.boundary.maximum_event_chain",
                1,
                MaxEventChain);

            Dictionary<string, object> debug = TevJson.RequireObject(
                root["debug"],
                "$.debug");
            string debugHash = TevJson.RequireString(root, "debug_hash");
            if (!string.Equals(
                    TevJson.Hash(debug),
                    debugHash,
                    StringComparison.Ordinal))
            {
                Fail(
                    "$.debug_hash",
                    "Debug hash does not match.",
                    "TEVS_CS_DEBUG_HASH");
            }

            List<object> entities = RequireArray(
                root["entities"],
                "$.entities",
                1,
                MaxEntities);
            var entityIds = new HashSet<string>(StringComparer.Ordinal);
            for (int index = 0; index < entities.Count; index++)
            {
                string entityId = ValidateEntity(
                    entities[index],
                    "$.entities[" + index + "]");
                if (!entityIds.Add(entityId))
                {
                    Fail(
                        "$.entities[" + index + "].entity_id",
                        "Duplicate entity " + entityId + ".");
                }
            }

            var semantic = new Dictionary<string, object>(StringComparer.Ordinal);
            foreach (KeyValuePair<string, object> item in root)
            {
                if (item.Key != "semantic_hash" &&
                    item.Key != "debug" &&
                    item.Key != "debug_hash")
                {
                    semantic.Add(item.Key, item.Value);
                }
            }
            string semanticHash = TevJson.RequireString(root, "semantic_hash");
            if (!string.Equals(
                    TevJson.Hash(semantic),
                    semanticHash,
                    StringComparison.Ordinal))
            {
                Fail(
                    "$.semantic_hash",
                    "Program semantic hash does not match.",
                    "TEVS_CS_PROGRAM_HASH");
            }
        }

        private static string ValidateEntity(object raw, string path)
        {
            Dictionary<string, object> entity = TevJson.RequireObject(raw, path);
            TevJson.RequireExactKeys(
                entity,
                path,
                "entity_id",
                "states",
                "handlers",
                "capabilities",
                "emitted_events");
            string entityId = RequireIdentifier(
                entity["entity_id"],
                path + ".entity_id");

            var states = new Dictionary<string, string>(StringComparer.Ordinal);
            List<object> rawStates = RequireArray(
                entity["states"],
                path + ".states",
                0,
                MaxStatesPerEntity);
            for (int index = 0; index < rawStates.Count; index++)
            {
                string statePath = path + ".states[" + index + "]";
                Dictionary<string, object> state = TevJson.RequireObject(
                    rawStates[index],
                    statePath);
                TevJson.RequireExactKeys(
                    state,
                    statePath,
                    "name",
                    "type",
                    "initial");
                string name = RequireIdentifier(
                    state["name"],
                    statePath + ".name");
                if (states.ContainsKey(name))
                    Fail(statePath + ".name", "Duplicate state " + name + ".");
                string typeName = RequireTypeName(
                    state["type"],
                    statePath + ".type",
                    false);
                ValidateTypedValue(
                    typeName,
                    state["initial"],
                    statePath + ".initial");
                states.Add(name, typeName);
            }

            var capabilities = new Dictionary<
                string,
                CapabilitySignature>(StringComparer.Ordinal);
            List<object> rawCapabilities = RequireArray(
                entity["capabilities"],
                path + ".capabilities",
                0,
                int.MaxValue);
            for (int index = 0; index < rawCapabilities.Count; index++)
            {
                string capabilityPath =
                    path + ".capabilities[" + index + "]";
                Dictionary<string, object> capability = TevJson.RequireObject(
                    rawCapabilities[index],
                    capabilityPath);
                TevJson.RequireExactKeys(
                    capability,
                    capabilityPath,
                    "capability_id",
                    "parameters",
                    "return_type",
                    "kind");
                string capabilityId = RequireStableId(
                    capability["capability_id"],
                    capabilityPath + ".capability_id");
                if (capabilities.ContainsKey(capabilityId))
                {
                    Fail(
                        capabilityPath + ".capability_id",
                        "Duplicate capability " + capabilityId + ".");
                }
                List<object> rawParameters = RequireArray(
                    capability["parameters"],
                    capabilityPath + ".parameters",
                    0,
                    MaxArguments);
                string[] parameters = new string[rawParameters.Count];
                for (int position = 0;
                    position < rawParameters.Count;
                    position++)
                {
                    parameters[position] = RequireTypeName(
                        rawParameters[position],
                        capabilityPath + ".parameters[" + position + "]",
                        false);
                }
                string returnType = RequireTypeName(
                    capability["return_type"],
                    capabilityPath + ".return_type",
                    true);
                string kind = TevJson.RequireString(
                    capability["kind"],
                    capabilityPath + ".kind");
                if (!CapabilityKinds.Contains(kind))
                    Fail(capabilityPath + ".kind", "Unsupported capability kind.");
                capabilities.Add(
                    capabilityId,
                    new CapabilitySignature(parameters, returnType, kind));
            }

            var events = new Dictionary<string, string[]>(StringComparer.Ordinal);
            List<object> rawEvents = RequireArray(
                entity["emitted_events"],
                path + ".emitted_events",
                0,
                int.MaxValue);
            for (int index = 0; index < rawEvents.Count; index++)
            {
                string eventPath = path + ".emitted_events[" + index + "]";
                Dictionary<string, object> eventDefinition =
                    TevJson.RequireObject(rawEvents[index], eventPath);
                TevJson.RequireExactKeys(
                    eventDefinition,
                    eventPath,
                    "event_id",
                    "parameters");
                string eventId = RequireIdentifier(
                    eventDefinition["event_id"],
                    eventPath + ".event_id");
                if (events.ContainsKey(eventId))
                    Fail(eventPath + ".event_id", "Duplicate emitted event.");
                List<object> rawParameters = RequireArray(
                    eventDefinition["parameters"],
                    eventPath + ".parameters",
                    0,
                    MaxArguments);
                string[] parameters = new string[rawParameters.Count];
                for (int position = 0;
                    position < rawParameters.Count;
                    position++)
                {
                    parameters[position] = RequireTypeName(
                        rawParameters[position],
                        eventPath + ".parameters[" + position + "]",
                        false);
                }
                events.Add(eventId, parameters);
            }

            var handlerIds = new HashSet<string>(StringComparer.Ordinal);
            List<object> handlers = RequireArray(
                entity["handlers"],
                path + ".handlers",
                0,
                MaxHandlersPerEntity);
            for (int handlerIndex = 0;
                handlerIndex < handlers.Count;
                handlerIndex++)
            {
                string handlerPath =
                    path + ".handlers[" + handlerIndex + "]";
                Dictionary<string, object> handler = TevJson.RequireObject(
                    handlers[handlerIndex],
                    handlerPath);
                TevJson.RequireExactKeys(
                    handler,
                    handlerPath,
                    "event_id",
                    "parameters",
                    "locals",
                    "instructions",
                    "instruction_budget");
                string eventId = RequireIdentifier(
                    handler["event_id"],
                    handlerPath + ".event_id");
                if (!handlerIds.Add(eventId))
                    Fail(handlerPath + ".event_id", "Duplicate handler.");

                var parameters = new Dictionary<string, string>(
                    StringComparer.Ordinal);
                List<object> rawParameters = RequireArray(
                    handler["parameters"],
                    handlerPath + ".parameters",
                    0,
                    MaxArguments);
                for (int index = 0; index < rawParameters.Count; index++)
                {
                    string parameterPath =
                        handlerPath + ".parameters[" + index + "]";
                    NameAndType parameter = ValidateNameAndType(
                        rawParameters[index],
                        parameterPath,
                        false);
                    if (parameters.ContainsKey(parameter.Name) ||
                        states.ContainsKey(parameter.Name))
                    {
                        Fail(
                            parameterPath + ".name",
                            "Duplicate or state-shadowing parameter.");
                    }
                    parameters.Add(parameter.Name, parameter.TypeName);
                }

                var locals = new Dictionary<string, string>(
                    StringComparer.Ordinal);
                List<object> rawLocals = RequireArray(
                    handler["locals"],
                    handlerPath + ".locals",
                    0,
                    MaxLocalsPerHandler);
                for (int index = 0; index < rawLocals.Count; index++)
                {
                    string localPath = handlerPath + ".locals[" + index + "]";
                    NameAndType local = ValidateNameAndType(
                        rawLocals[index],
                        localPath,
                        false);
                    if (locals.ContainsKey(local.Name) ||
                        parameters.ContainsKey(local.Name) ||
                        states.ContainsKey(local.Name))
                    {
                        Fail(localPath + ".name", "Duplicate or shadowing local.");
                    }
                    locals.Add(local.Name, local.TypeName);
                }

                List<object> instructions = RequireArray(
                    handler["instructions"],
                    handlerPath + ".instructions",
                    1,
                    MaxInstructionsPerHandler);
                int budget = RequireInteger(
                    handler["instruction_budget"],
                    handlerPath + ".instruction_budget",
                    1,
                    MaxInstructionsPerHandler);
                if (instructions.Count > budget)
                {
                    Fail(
                        handlerPath + ".instruction_budget",
                        "Instruction budget is smaller than instruction count.");
                }
                Dictionary<string, object> finalInstruction =
                    TevJson.RequireObject(
                        instructions[instructions.Count - 1],
                        handlerPath + ".instructions[last]");
                object finalOp;
                if (!finalInstruction.TryGetValue("op", out finalOp) ||
                    !(finalOp is string) ||
                    !string.Equals(
                        (string)finalOp,
                        "RETURN",
                        StringComparison.Ordinal))
                {
                    Fail(
                        handlerPath + ".instructions",
                        "Handler must end in RETURN.");
                }
                for (int index = 0; index < instructions.Count; index++)
                {
                    ValidateInstruction(
                        instructions[index],
                        handlerPath + ".instructions[" + index + "]",
                        index,
                        instructions.Count,
                        states,
                        parameters,
                        locals,
                        capabilities,
                        events);
                }
                TevScriptIrFlowVerifier.Validate(entity, handler, handlerPath);
            }

            return entityId;
        }

        private static void ValidateInstruction(
            object raw,
            string path,
            int index,
            int instructionCount,
            IReadOnlyDictionary<string, string> states,
            IReadOnlyDictionary<string, string> parameters,
            IReadOnlyDictionary<string, string> locals,
            IReadOnlyDictionary<string, CapabilitySignature> capabilities,
            IReadOnlyDictionary<string, string[]> events)
        {
            Dictionary<string, object> instruction =
                TevJson.RequireObject(raw, path);
            object rawOp;
            if (!instruction.TryGetValue("op", out rawOp) || !(rawOp is string))
                Fail(path + ".op", "Expected opcode string.");
            string op = (string)rawOp;

            if (op == "CONST")
            {
                TevJson.RequireExactKeys(instruction, path, "op", "type", "value");
                string typeName = RequireTypeName(
                    instruction["type"], path + ".type", false);
                ValidateTypedValue(typeName, instruction["value"], path + ".value");
                return;
            }

            if (op == "LOAD_STATE" || op == "STORE_STATE" ||
                op == "LOAD_LOCAL" || op == "STORE_LOCAL" ||
                op == "LOAD_PARAM")
            {
                TevJson.RequireExactKeys(instruction, path, "op", "name", "type");
                string name = RequireIdentifier(
                    instruction["name"], path + ".name");
                string typeName = RequireTypeName(
                    instruction["type"], path + ".type", false);
                IReadOnlyDictionary<string, string> nameSpace =
                    op == "LOAD_STATE" || op == "STORE_STATE"
                        ? states
                        : op == "LOAD_LOCAL" || op == "STORE_LOCAL"
                            ? locals
                            : parameters;
                string declaredType;
                if (!nameSpace.TryGetValue(name, out declaredType) ||
                    !string.Equals(
                        declaredType,
                        typeName,
                        StringComparison.Ordinal))
                {
                    Fail(path, op + " references unknown or mismatched name.");
                }
                return;
            }

            if (op == "CONVERT_INT_TO_RAT")
            {
                TevJson.RequireExactKeys(instruction, path, "op");
                return;
            }

            if (op == "UNARY")
            {
                TevJson.RequireExactKeys(
                    instruction, path, "op", "operator", "type");
                string operatorName = TevJson.RequireString(
                    instruction["operator"], path + ".operator");
                if (operatorName != "NOT" && operatorName != "MINUS")
                    Fail(path + ".operator", "Unsupported unary operator.");
                string typeName = RequireTypeName(
                    instruction["type"], path + ".type", false);
                if (operatorName == "NOT" && typeName != "Bool")
                    Fail(path, "NOT must produce Bool.");
                if (operatorName == "MINUS" &&
                    typeName != "Int" && typeName != "Rat")
                {
                    Fail(path, "MINUS must produce Int or Rat.");
                }
                return;
            }

            if (op == "BINARY")
            {
                TevJson.RequireExactKeys(
                    instruction,
                    path,
                    "op",
                    "operator",
                    "left_type",
                    "right_type",
                    "result_type");
                string operatorName = TevJson.RequireString(
                    instruction["operator"], path + ".operator");
                string[] operators =
                {
                    "AND", "OR", "EQEQ", "NE", "LT", "LE", "GT", "GE",
                    "PLUS", "MINUS", "STAR", "SLASH"
                };
                if (!operators.Contains(operatorName, StringComparer.Ordinal))
                    Fail(path + ".operator", "Unsupported binary operator.");
                RequireTypeName(
                    instruction["left_type"], path + ".left_type", false);
                RequireTypeName(
                    instruction["right_type"], path + ".right_type", false);
                RequireTypeName(
                    instruction["result_type"], path + ".result_type", false);
                return;
            }

            if (op == "CALL_PURE")
            {
                TevJson.RequireExactKeys(
                    instruction,
                    path,
                    "op",
                    "function_id",
                    "argc",
                    "return_type");
                string functionId = RequireStableId(
                    instruction["function_id"], path + ".function_id");
                int argc = RequireInteger(
                    instruction["argc"], path + ".argc", 0, MaxArguments);
                string returnType = RequireTypeName(
                    instruction["return_type"], path + ".return_type", true);
                bool valid =
                    (functionId == "vec2" && argc == 2 && returnType == "Vec2") ||
                    (functionId == "vec3" && argc == 3 && returnType == "Vec3") ||
                    ((functionId == "max" || functionId == "min") &&
                        argc == 2 &&
                        (returnType == "Int" || returnType == "Rat"));
                if (!valid)
                    Fail(path, "Pure function signature does not match V0.2.");
                return;
            }

            if (op == "CALL_CAPABILITY")
            {
                TevJson.RequireExactKeys(
                    instruction,
                    path,
                    "op",
                    "capability_id",
                    "argc",
                    "return_type",
                    "kind");
                string capabilityId = RequireStableId(
                    instruction["capability_id"], path + ".capability_id");
                int argc = RequireInteger(
                    instruction["argc"], path + ".argc", 0, MaxArguments);
                string returnType = RequireTypeName(
                    instruction["return_type"], path + ".return_type", true);
                string kind = TevJson.RequireString(
                    instruction["kind"], path + ".kind");
                if (!CapabilityKinds.Contains(kind))
                    Fail(path + ".kind", "Unsupported capability kind.");
                CapabilitySignature signature;
                if (!capabilities.TryGetValue(capabilityId, out signature))
                    Fail(path, "Capability instruction references undeclared capability.");
                if (signature.Parameters.Count != argc ||
                    signature.ReturnType != returnType ||
                    signature.Kind != kind)
                {
                    Fail(path, "Capability instruction does not match declaration.");
                }
                return;
            }

            if (op == "EMIT_EVENT")
            {
                TevJson.RequireExactKeys(
                    instruction,
                    path,
                    "op",
                    "event_id",
                    "argc",
                    "argument_types");
                string eventId = RequireIdentifier(
                    instruction["event_id"], path + ".event_id");
                int argc = RequireInteger(
                    instruction["argc"], path + ".argc", 0, MaxArguments);
                List<object> rawTypes = RequireArray(
                    instruction["argument_types"],
                    path + ".argument_types",
                    0,
                    MaxArguments);
                string[] argumentTypes = new string[rawTypes.Count];
                for (int position = 0; position < rawTypes.Count; position++)
                {
                    argumentTypes[position] = RequireTypeName(
                        rawTypes[position],
                        path + ".argument_types[" + position + "]",
                        false);
                }
                string[] declaredTypes;
                if (argumentTypes.Length != argc ||
                    !events.TryGetValue(eventId, out declaredTypes) ||
                    !argumentTypes.SequenceEqual(
                        declaredTypes,
                        StringComparer.Ordinal))
                {
                    Fail(path, "Event instruction does not match declaration.");
                }
                return;
            }

            if (op == "JUMP" || op == "JUMP_IF_FALSE")
            {
                TevJson.RequireExactKeys(instruction, path, "op", "target");
                int target = RequireInteger(
                    instruction["target"],
                    path + ".target",
                    0,
                    instructionCount);
                if (target <= index)
                    Fail(path + ".target", "Backward or self jumps are forbidden.");
                return;
            }

            if (op == "RETURN")
            {
                TevJson.RequireExactKeys(instruction, path, "op");
                return;
            }

            Fail(
                path + ".op",
                "Unknown opcode " + op + ".",
                "TEVS_CS_OPCODE");
        }

        private static NameAndType ValidateNameAndType(
            object raw,
            string path,
            bool allowUnit)
        {
            Dictionary<string, object> item = TevJson.RequireObject(raw, path);
            TevJson.RequireExactKeys(item, path, "name", "type");
            return new NameAndType(
                RequireIdentifier(item["name"], path + ".name"),
                RequireTypeName(item["type"], path + ".type", allowUnit));
        }

        private static void ValidateTypedValue(
            string typeName,
            object value,
            string path)
        {
            try
            {
                TevScriptValue.Decode(typeName, value);
            }
            catch (Exception error)
            {
                if (error is TevContractException ||
                    error is ArgumentException ||
                    error is InvalidOperationException ||
                    error is DivideByZeroException)
                {
                    Fail(path, "Invalid " + typeName + " value: " + error.Message);
                }
                throw;
            }
        }

        private static List<object> RequireArray(
            object value,
            string path,
            int minimum,
            int maximum)
        {
            List<object> result = TevJson.RequireArray(value, path);
            if (result.Count < minimum || result.Count > maximum)
            {
                Fail(
                    path,
                    "Array count must be in [" + minimum + ", " + maximum + "].");
            }
            return result;
        }

        private static int RequireInteger(
            object value,
            string path,
            int minimum,
            int maximum)
        {
            BigInteger integer = TevJson.RequireInteger(value, path);
            if (integer < minimum || integer > maximum)
            {
                Fail(
                    path,
                    "Integer must be in [" + minimum + ", " + maximum + "].");
            }
            return (int)integer;
        }

        private static string RequireIdentifier(object value, string path)
        {
            string text = TevJson.RequireString(value, path);
            if (text.Length == 0 || !IsAsciiIdentifierStart(text[0]))
                Fail(path, "Expected identifier.");
            for (int index = 1; index < text.Length; index++)
            {
                if (!IsAsciiIdentifierContinue(text[index]))
                    Fail(path, "Expected identifier.");
            }
            return text;
        }

        private static string RequireStableId(object value, string path)
        {
            string text = TevJson.RequireString(value, path);
            if (text.Length == 0 || !IsAsciiIdentifierStart(text[0]))
                Fail(path, "Expected stable identifier.");
            for (int index = 1; index < text.Length; index++)
            {
                char character = text[index];
                if (!IsAsciiIdentifierContinue(character) &&
                    character != '.' && character != ':' &&
                    character != '/' && character != '-')
                {
                    Fail(path, "Expected stable identifier.");
                }
            }
            return text;
        }

        private static string RequireTypeName(
            object value,
            string path,
            bool allowUnit)
        {
            string typeName = TevJson.RequireString(value, path);
            HashSet<string> allowed = allowUnit ? TypeNames : ValueTypeNames;
            if (!allowed.Contains(typeName))
                Fail(path, "Unsupported type " + typeName + ".");
            return typeName;
        }

        private static string RequireHash(object value, string path)
        {
            string text = TevJson.RequireString(value, path);
            if (text.Length != 64)
                Fail(path, "Expected lowercase SHA-256 hexadecimal.");
            for (int index = 0; index < text.Length; index++)
            {
                char character = text[index];
                if (!((character >= '0' && character <= '9') ||
                    (character >= 'a' && character <= 'f')))
                {
                    Fail(path, "Expected lowercase SHA-256 hexadecimal.");
                }
            }
            return text;
        }

        private static bool IsAsciiIdentifierStart(char value)
        {
            return (value >= 'A' && value <= 'Z') ||
                (value >= 'a' && value <= 'z') ||
                value == '_';
        }

        private static bool IsAsciiIdentifierContinue(char value)
        {
            return IsAsciiIdentifierStart(value) ||
                (value >= '0' && value <= '9');
        }

        private static void Fail(
            string path,
            string message,
            string code = "TEVS_CS_IR_CONTRACT")
        {
            throw new TevContractException(code, message, path);
        }

        private sealed class CapabilitySignature
        {
            public CapabilitySignature(
                IReadOnlyList<string> parameters,
                string returnType,
                string kind)
            {
                Parameters = parameters;
                ReturnType = returnType;
                Kind = kind;
            }

            public IReadOnlyList<string> Parameters { get; }
            public string ReturnType { get; }
            public string Kind { get; }
        }

        private sealed class NameAndType
        {
            public NameAndType(string name, string typeName)
            {
                Name = name;
                TypeName = typeName;
            }

            public string Name { get; }
            public string TypeName { get; }
        }
    }
}
