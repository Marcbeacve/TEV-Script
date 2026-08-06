using System;
using System.Collections.Generic;
using System.Linq;
using System.Numerics;

namespace Marcbeacve.TevScript.Core
{
    public static class TevScriptConformance
    {
        public const string ScenarioSchema =
            "TEV_SCRIPT_CONFORMANCE_SCENARIO_V1";
        public const string ReceiptSchema =
            "TEV_SCRIPT_CONFORMANCE_RECEIPT_V1";

        public static string RunCanonicalReceipt(
            string programJson,
            string scenarioJson)
        {
            if (programJson == null)
                throw new ArgumentNullException(nameof(programJson));
            if (scenarioJson == null)
                throw new ArgumentNullException(nameof(scenarioJson));

            TevScriptProgram program = TevScriptProgram.Parse(programJson);
            Dictionary<string, object> scenario = ParseScenario(scenarioJson);
            string scenarioId = TevJson.RequireString(scenario, "scenario_id");
            string entityId = TevJson.RequireString(scenario, "entity_id");

            TevScriptEntityDefinition scenarioEntity = program.Entities
                .SingleOrDefault(item => string.Equals(
                    item.EntityId,
                    entityId,
                    StringComparison.Ordinal));
            if (scenarioEntity == null)
            {
                throw new TevContractException(
                    "TEVS_CS_CONFORMANCE_ENTITY",
                    "Scenario references unknown entity " + entityId + ".");
            }

            Dictionary<string, object> capabilityBindings =
                TevJson.RequireObject(scenario, "capabilities");
            var trace = new List<Dictionary<string, object>>();
            var boundCapabilities = new List<ITevScriptCapability>();

            foreach (KeyValuePair<
                string,
                TevScriptCapabilityDefinition> item in scenarioEntity.Capabilities)
            {
                string capabilityId = item.Key;
                TevScriptCapabilityDefinition definition = item.Value;
                object rawBinding;
                if (!capabilityBindings.TryGetValue(
                        capabilityId,
                        out rawBinding))
                {
                    throw new TevContractException(
                        "TEVS_CS_CONFORMANCE_CAPABILITY_MISSING",
                        "Scenario lacks capability " + capabilityId + ".");
                }
                Dictionary<string, object> binding = TevJson.RequireObject(
                    rawBinding,
                    "capabilities." + capabilityId);
                string mode = TevJson.RequireString(binding, "mode");
                TevScriptValue constantValue = null;
                if (mode == "trace")
                {
                    TevJson.RequireExactKeys(
                        binding,
                        "capabilities." + capabilityId,
                        "mode");
                }
                else if (mode == "constant")
                {
                    TevJson.RequireExactKeys(
                        binding,
                        "capabilities." + capabilityId,
                        "mode",
                        "value_type",
                        "value");
                    string valueType = TevJson.RequireString(
                        binding,
                        "value_type");
                    constantValue = TevScriptValue.Decode(
                        valueType,
                        binding["value"]);
                }
                else
                {
                    throw new TevContractException(
                        "TEVS_CS_CONFORMANCE_CAPABILITY_MODE",
                        "Unsupported capability mode " + mode + ".");
                }

                string currentId = capabilityId;
                TevScriptCapabilityDefinition currentDefinition = definition;
                TevScriptValue currentConstant = constantValue;
                string currentMode = mode;
                boundCapabilities.Add(new DelegateTevScriptCapability(
                    currentId,
                    arguments =>
                    {
                        if (arguments.Count != currentDefinition.Parameters.Count)
                        {
                            throw new TevContractException(
                                "TEVS_CS_CONFORMANCE_CAPABILITY_ARITY",
                                "Capability argument count does not match declaration.");
                        }
                        var encodedArguments = new object[arguments.Count];
                        for (int index = 0; index < arguments.Count; index++)
                        {
                            encodedArguments[index] = EncodeAsType(
                                currentDefinition.Parameters[index],
                                arguments[index]);
                        }

                        TevScriptValue result = currentMode == "constant"
                            ? currentConstant
                            : TevScriptValue.Unit();
                        object encodedResult = currentDefinition.ReturnType == "Unit"
                            ? null
                            : EncodeAsType(currentDefinition.ReturnType, result);
                        trace.Add(new Dictionary<string, object>(
                            StringComparer.Ordinal)
                        {
                            ["capability_id"] = currentId,
                            ["arguments"] = encodedArguments,
                            ["result"] = encodedResult
                        });
                        return result;
                    }));
            }

            var runtime = new TevScriptRuntime(program, boundCapabilities);
            List<object> invocations = TevJson.RequireArray(
                scenario,
                "invocations");
            for (int invocationIndex = 0;
                invocationIndex < invocations.Count;
                invocationIndex++)
            {
                Dictionary<string, object> invocation = TevJson.RequireObject(
                    invocations[invocationIndex],
                    "invocations[" + invocationIndex + "]");
                List<object> rawArguments = TevJson.RequireArray(
                    invocation,
                    "arguments");
                TevScriptValue[] arguments = new TevScriptValue[rawArguments.Count];
                for (int argumentIndex = 0;
                    argumentIndex < rawArguments.Count;
                    argumentIndex++)
                {
                    Dictionary<string, object> argument = TevJson.RequireObject(
                        rawArguments[argumentIndex],
                        "invocations[" + invocationIndex + "].arguments[" +
                        argumentIndex + "]");
                    string typeName = TevJson.RequireString(argument, "type");
                    arguments[argumentIndex] = TevScriptValue.Decode(
                        typeName,
                        argument["value"]);
                }
                runtime.Invoke(
                    TevJson.RequireString(invocation, "entity_id"),
                    TevJson.RequireString(invocation, "event_id"),
                    arguments);
            }

            var finalStates = new List<object>();
            foreach (TevScriptEntityDefinition entity in program.Entities)
            {
                finalStates.Add(new Dictionary<string, object>(
                    StringComparer.Ordinal)
                {
                    ["entity_id"] = entity.EntityId,
                    ["state"] = runtime.EncodedState(entity.EntityId)
                });
            }

            var emittedEvents = new List<object>();
            foreach (TevScriptEvent emitted in runtime.EmittedEvents)
            {
                TevScriptEntityDefinition entity = program.Entities
                    .Single(item => string.Equals(
                        item.EntityId,
                        emitted.EntityId,
                        StringComparison.Ordinal));
                IReadOnlyList<string> parameterTypes;
                if (!entity.EmittedEvents.TryGetValue(
                        emitted.EventId,
                        out parameterTypes))
                {
                    if (emitted.Arguments.Count != 0)
                    {
                        throw new TevContractException(
                            "TEVS_CS_CONFORMANCE_EVENT_SIGNATURE",
                            "Undeclared emitted event has arguments.");
                    }
                    parameterTypes = new string[0];
                }
                if (parameterTypes.Count != emitted.Arguments.Count)
                {
                    throw new TevContractException(
                        "TEVS_CS_CONFORMANCE_EVENT_ARITY",
                        "Emitted event argument count does not match declaration.");
                }
                object[] encodedArguments = new object[emitted.Arguments.Count];
                for (int index = 0; index < emitted.Arguments.Count; index++)
                {
                    encodedArguments[index] = EncodeAsType(
                        parameterTypes[index],
                        emitted.Arguments[index]);
                }
                emittedEvents.Add(new Dictionary<string, object>(
                    StringComparer.Ordinal)
                {
                    ["entity_id"] = emitted.EntityId,
                    ["event_id"] = emitted.EventId,
                    ["arguments"] = encodedArguments
                });
            }

            var semantic = new Dictionary<string, object>(StringComparer.Ordinal)
            {
                ["schema"] = ReceiptSchema,
                ["scenario_id"] = scenarioId,
                ["program_hash"] = program.SemanticHash,
                ["final_states"] = finalStates,
                ["emitted_events"] = emittedEvents,
                ["capability_trace"] = trace
            };
            string receiptHash = TevJson.Hash(semantic);
            var receipt = new Dictionary<string, object>(
                semantic,
                StringComparer.Ordinal)
            {
                ["receipt_hash"] = receiptHash
            };
            return TevJson.Canonicalize(receipt) + "\n";
        }

        private static Dictionary<string, object> ParseScenario(string json)
        {
            Dictionary<string, object> scenario = TevJson.RequireObject(
                TevJson.Parse(json),
                "$");
            TevJson.RequireExactKeys(
                scenario,
                "$",
                "schema",
                "scenario_id",
                "program",
                "entity_id",
                "capabilities",
                "invocations");
            if (TevJson.RequireString(scenario, "schema") != ScenarioSchema)
            {
                throw new TevContractException(
                    "TEVS_CS_CONFORMANCE_SCENARIO_SCHEMA",
                    "Unexpected conformance scenario schema.");
            }
            RequireNonEmpty(
                TevJson.RequireString(scenario, "scenario_id"),
                "scenario_id");
            RequireNonEmpty(
                TevJson.RequireString(scenario, "program"),
                "program");
            RequireIdentifier(
                TevJson.RequireString(scenario, "entity_id"),
                "entity_id");

            Dictionary<string, object> capabilities = TevJson.RequireObject(
                scenario,
                "capabilities");
            foreach (KeyValuePair<string, object> item in capabilities)
            {
                Dictionary<string, object> binding = TevJson.RequireObject(
                    item.Value,
                    "capabilities." + item.Key);
                string mode = TevJson.RequireString(binding, "mode");
                if (mode == "trace")
                {
                    TevJson.RequireExactKeys(
                        binding,
                        "capabilities." + item.Key,
                        "mode");
                }
                else if (mode == "constant")
                {
                    TevJson.RequireExactKeys(
                        binding,
                        "capabilities." + item.Key,
                        "mode",
                        "value_type",
                        "value");
                    string valueType = RequireTypeName(
                        TevJson.RequireString(binding, "value_type"));
                    TevScriptValue.Decode(valueType, binding["value"]);
                }
                else
                {
                    throw new TevContractException(
                        "TEVS_CS_CONFORMANCE_CAPABILITY_MODE",
                        "Unsupported capability mode " + mode + ".");
                }
            }

            List<object> invocations = TevJson.RequireArray(
                scenario,
                "invocations");
            if (invocations.Count < 1 || invocations.Count > 4096)
            {
                throw new TevContractException(
                    "TEVS_CS_CONFORMANCE_INVOCATION_COUNT",
                    "Invocation count must be in [1, 4096].");
            }
            for (int index = 0; index < invocations.Count; index++)
            {
                string path = "invocations[" + index + "]";
                Dictionary<string, object> invocation = TevJson.RequireObject(
                    invocations[index],
                    path);
                TevJson.RequireExactKeys(
                    invocation,
                    path,
                    "entity_id",
                    "event_id",
                    "arguments");
                RequireIdentifier(
                    TevJson.RequireString(invocation, "entity_id"),
                    path + ".entity_id");
                RequireIdentifier(
                    TevJson.RequireString(invocation, "event_id"),
                    path + ".event_id");
                List<object> arguments = TevJson.RequireArray(
                    invocation,
                    "arguments");
                if (arguments.Count > 64)
                {
                    throw new TevContractException(
                        "TEVS_CS_CONFORMANCE_ARGUMENT_COUNT",
                        "Invocation argument count exceeds 64.",
                        path + ".arguments");
                }
                for (int argumentIndex = 0;
                    argumentIndex < arguments.Count;
                    argumentIndex++)
                {
                    string argumentPath =
                        path + ".arguments[" + argumentIndex + "]";
                    Dictionary<string, object> argument = TevJson.RequireObject(
                        arguments[argumentIndex],
                        argumentPath);
                    TevJson.RequireExactKeys(
                        argument,
                        argumentPath,
                        "type",
                        "value");
                    string typeName = RequireTypeName(
                        TevJson.RequireString(argument, "type"));
                    TevScriptValue.Decode(typeName, argument["value"]);
                }
            }
            return scenario;
        }

        private static object EncodeAsType(
            string expectedType,
            TevScriptValue value)
        {
            if (value == null)
            {
                throw new TevContractException(
                    "TEVS_CS_CONFORMANCE_VALUE_NULL",
                    "Runtime values cannot be null.");
            }
            if (value.TypeName == expectedType)
                return value.ToCanonicalObject();
            if (expectedType == "Rat" && value.TypeName == "Int")
            {
                return TevScriptValue.Rat(
                    TevRational.FromInteger(value.AsInt()))
                    .ToCanonicalObject();
            }
            throw new TevContractException(
                "TEVS_CS_CONFORMANCE_VALUE_TYPE",
                "Expected " + expectedType + ", got " + value.TypeName + ".");
        }

        private static string RequireTypeName(string typeName)
        {
            switch (typeName)
            {
                case "Bool":
                case "Int":
                case "Rat":
                case "Text":
                case "Vec2":
                case "Vec3":
                case "Unit":
                    return typeName;
                default:
                    throw new TevContractException(
                        "TEVS_CS_CONFORMANCE_TYPE",
                        "Unsupported type " + typeName + ".");
            }
        }

        private static void RequireNonEmpty(string value, string path)
        {
            if (string.IsNullOrEmpty(value))
                throw new TevContractException(
                    "TEVS_CS_CONFORMANCE_TEXT",
                    "Expected non-empty text.",
                    path);
        }

        private static void RequireIdentifier(string value, string path)
        {
            if (string.IsNullOrEmpty(value) || !IsIdentifierStart(value[0]))
                throw new TevContractException(
                    "TEVS_CS_CONFORMANCE_IDENTIFIER",
                    "Expected identifier.",
                    path);
            for (int index = 1; index < value.Length; index++)
            {
                if (!IsIdentifierContinue(value[index]))
                    throw new TevContractException(
                        "TEVS_CS_CONFORMANCE_IDENTIFIER",
                        "Expected identifier.",
                        path);
            }
        }

        private static bool IsIdentifierStart(char value)
        {
            return (value >= 'A' && value <= 'Z') ||
                (value >= 'a' && value <= 'z') ||
                value == '_';
        }

        private static bool IsIdentifierContinue(char value)
        {
            return IsIdentifierStart(value) ||
                (value >= '0' && value <= '9');
        }
    }
}
