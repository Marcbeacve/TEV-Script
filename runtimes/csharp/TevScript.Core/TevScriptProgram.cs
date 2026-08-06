using System;
using System.Collections.Generic;
using System.Linq;
using System.Numerics;

namespace Marcbeacve.TevScript.Core
{
    public sealed class TevScriptProgram
    {
        public const string Schema = "TEV_SCRIPT_PROGRAM_IR_V2";
        public const string LanguageVersion = "0.2.0";

        private TevScriptProgram(
            string programId,
            string semanticHash,
            int maximumEventChain,
            IReadOnlyList<TevScriptEntityDefinition> entities,
            Dictionary<string, object> raw)
        {
            ProgramId = programId;
            SemanticHash = semanticHash;
            MaximumEventChain = maximumEventChain;
            Entities = entities;
            Raw = raw;
        }

        public string ProgramId { get; }
        public string SemanticHash { get; }
        public int MaximumEventChain { get; }
        public IReadOnlyList<TevScriptEntityDefinition> Entities { get; }
        public Dictionary<string, object> Raw { get; }

        public static TevScriptProgram Parse(string json)
        {
            Dictionary<string, object> root = TevJson.RequireObject(
                TevJson.Parse(json),
                "$");
            TevScriptIrValidator.Validate(root);
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
            if (TevJson.RequireString(root, "schema") != Schema)
            {
                throw new TevContractException(
                    "TEVS_CS_PROGRAM_SCHEMA",
                    "Expected " + Schema + ".");
            }
            if (TevJson.RequireString(root, "language_version") !=
                LanguageVersion)
            {
                throw new TevContractException(
                    "TEVS_CS_PROGRAM_LANGUAGE",
                    "Expected language " + LanguageVersion + ".");
            }

            string semanticHash = TevJson.RequireString(root, "semantic_hash");
            string debugHash = TevJson.RequireString(root, "debug_hash");
            Dictionary<string, object> debug = TevJson.RequireObject(root, "debug");
            if (!string.Equals(
                    TevJson.Hash(debug),
                    debugHash,
                    StringComparison.Ordinal))
            {
                throw new TevContractException(
                    "TEVS_CS_DEBUG_HASH",
                    "Program debug hash does not match.");
            }
            var semantic = new Dictionary<string, object>(
                StringComparer.Ordinal);
            foreach (KeyValuePair<string, object> item in root)
            {
                if (item.Key != "semantic_hash" &&
                    item.Key != "debug" &&
                    item.Key != "debug_hash")
                {
                    semantic.Add(item.Key, item.Value);
                }
            }
            if (!string.Equals(
                    TevJson.Hash(semantic),
                    semanticHash,
                    StringComparison.Ordinal))
            {
                throw new TevContractException(
                    "TEVS_CS_PROGRAM_HASH",
                    "Program semantic hash does not match.");
            }

            Dictionary<string, object> boundary =
                TevJson.RequireObject(root, "boundary");
            TevJson.RequireExactKeys(
                boundary,
                "boundary",
                "dynamic_code",
                "reflection",
                "unbounded_loops",
                "implicit_physical_effects",
                "runtime_source_compilation",
                "automatic_authority_escalation",
                "maximum_event_chain");
            string[] boundaryFlags = new string[]
            {
                "dynamic_code",
                "reflection",
                "unbounded_loops",
                "implicit_physical_effects",
                "runtime_source_compilation",
                "automatic_authority_escalation"
            };
            foreach (string flag in boundaryFlags)
            {
                if (TevJson.RequireBoolean(boundary[flag], "boundary." + flag))
                {
                    throw new TevContractException(
                        "TEVS_CS_BOUNDARY",
                        "Boundary flag must be false.",
                        "boundary." + flag);
                }
            }
            int maximumEventChain = RequireInt32(
                boundary["maximum_event_chain"],
                "boundary.maximum_event_chain");
            if (maximumEventChain < 1 || maximumEventChain > 128)
            {
                throw new TevContractException(
                    "TEVS_CS_EVENT_CHAIN_RANGE",
                    "maximum_event_chain must be in [1, 128].",
                    "boundary.maximum_event_chain");
            }

            List<TevScriptEntityDefinition> entities =
                TevJson.RequireArray(root, "entities")
                .Select((item, index) => TevScriptEntityDefinition.Parse(
                    TevJson.RequireObject(item, "entities[" + index + "]")))
                .ToList();
            if (entities.Count == 0 ||
                entities.Select(item => item.EntityId).Distinct().Count() !=
                entities.Count)
            {
                throw new TevContractException(
                    "TEVS_CS_PROGRAM_ENTITIES",
                    "Entities must be non-empty and unique.");
            }
            return new TevScriptProgram(
                TevJson.RequireString(root, "program_id"),
                semanticHash,
                maximumEventChain,
                entities.AsReadOnly(),
                root);
        }

        internal static int RequireInt32(object value, string path)
        {
            BigInteger integer = TevJson.RequireInteger(value, path);
            if (integer < int.MinValue || integer > int.MaxValue)
            {
                throw new TevContractException(
                    "TEVS_CS_INT32",
                    "Value is outside Int32.",
                    path);
            }
            return (int)integer;
        }
    }

    public sealed class TevScriptEntityDefinition
    {
        private TevScriptEntityDefinition(
            string entityId,
            IReadOnlyList<TevScriptStateDefinition> states,
            IReadOnlyDictionary<string, TevScriptHandlerDefinition> handlers,
            IReadOnlyDictionary<string, TevScriptCapabilityDefinition> capabilities,
            IReadOnlyDictionary<string, IReadOnlyList<string>> emittedEvents)
        {
            EntityId = entityId;
            States = states;
            Handlers = handlers;
            Capabilities = capabilities;
            EmittedEvents = emittedEvents;
        }

        public string EntityId { get; }
        public IReadOnlyList<TevScriptStateDefinition> States { get; }
        public IReadOnlyDictionary<string, TevScriptHandlerDefinition> Handlers { get; }
        public IReadOnlyDictionary<string, TevScriptCapabilityDefinition> Capabilities { get; }
        public IReadOnlyDictionary<string, IReadOnlyList<string>> EmittedEvents { get; }

        internal static TevScriptEntityDefinition Parse(
            Dictionary<string, object> raw)
        {
            TevJson.RequireExactKeys(
                raw,
                "entity",
                "entity_id",
                "states",
                "handlers",
                "capabilities",
                "emitted_events");
            string entityId = TevJson.RequireString(raw, "entity_id");
            List<TevScriptStateDefinition> states = TevJson
                .RequireArray(raw, "states")
                .Select((item, index) => TevScriptStateDefinition.Parse(
                    TevJson.RequireObject(item, "states[" + index + "]")))
                .ToList();

            var handlers = new Dictionary<string, TevScriptHandlerDefinition>(
                StringComparer.Ordinal);
            foreach (object item in TevJson.RequireArray(raw, "handlers"))
            {
                TevScriptHandlerDefinition handler =
                    TevScriptHandlerDefinition.Parse(
                        TevJson.RequireObject(item, "handler"));
                if (handlers.ContainsKey(handler.EventId))
                {
                    throw new TevContractException(
                        "TEVS_CS_HANDLER_DUPLICATE",
                        "Duplicate handler " + handler.EventId + ".");
                }
                handlers.Add(handler.EventId, handler);
            }

            var capabilities = new Dictionary<
                string,
                TevScriptCapabilityDefinition>(StringComparer.Ordinal);
            foreach (object item in TevJson.RequireArray(raw, "capabilities"))
            {
                TevScriptCapabilityDefinition capability =
                    TevScriptCapabilityDefinition.Parse(
                        TevJson.RequireObject(item, "capability"));
                capabilities.Add(capability.CapabilityId, capability);
            }

            var emitted = new Dictionary<
                string,
                IReadOnlyList<string>>(StringComparer.Ordinal);
            foreach (object item in TevJson.RequireArray(raw, "emitted_events"))
            {
                Dictionary<string, object> eventRaw =
                    TevJson.RequireObject(item, "emitted_event");
                TevJson.RequireExactKeys(
                    eventRaw,
                    "emitted_event",
                    "event_id",
                    "parameters");
                string eventId = TevJson.RequireString(eventRaw, "event_id");
                emitted.Add(
                    eventId,
                    TevJson.RequireArray(eventRaw, "parameters")
                        .Select((parameter, index) => TevJson.RequireString(
                            parameter,
                            "parameters[" + index + "]"))
                        .ToArray());
            }

            return new TevScriptEntityDefinition(
                entityId,
                states.AsReadOnly(),
                handlers,
                capabilities,
                emitted);
        }
    }

    public sealed class TevScriptStateDefinition
    {
        private TevScriptStateDefinition(
            string name,
            string typeName,
            TevScriptValue initial)
        {
            Name = name;
            TypeName = typeName;
            Initial = initial;
        }

        public string Name { get; }
        public string TypeName { get; }
        public TevScriptValue Initial { get; }

        internal static TevScriptStateDefinition Parse(
            Dictionary<string, object> raw)
        {
            TevJson.RequireExactKeys(raw, "state", "name", "type", "initial");
            string typeName = TevJson.RequireString(raw, "type");
            return new TevScriptStateDefinition(
                TevJson.RequireString(raw, "name"),
                typeName,
                TevScriptValue.Decode(typeName, raw["initial"]));
        }
    }

    public sealed class TevScriptParameterDefinition
    {
        public TevScriptParameterDefinition(string name, string typeName)
        {
            Name = name;
            TypeName = typeName;
        }
        public string Name { get; }
        public string TypeName { get; }
    }

    public sealed class TevScriptHandlerDefinition
    {
        private TevScriptHandlerDefinition(
            string eventId,
            IReadOnlyList<TevScriptParameterDefinition> parameters,
            IReadOnlyList<Dictionary<string, object>> instructions,
            int instructionBudget)
        {
            EventId = eventId;
            Parameters = parameters;
            Instructions = instructions;
            InstructionBudget = instructionBudget;
        }

        public string EventId { get; }
        public IReadOnlyList<TevScriptParameterDefinition> Parameters { get; }
        public IReadOnlyList<Dictionary<string, object>> Instructions { get; }
        public int InstructionBudget { get; }

        internal static TevScriptHandlerDefinition Parse(
            Dictionary<string, object> raw)
        {
            TevJson.RequireExactKeys(
                raw,
                "handler",
                "event_id",
                "parameters",
                "locals",
                "instructions",
                "instruction_budget");
            return new TevScriptHandlerDefinition(
                TevJson.RequireString(raw, "event_id"),
                TevJson.RequireArray(raw, "parameters")
                    .Select(item =>
                    {
                        Dictionary<string, object> parameter =
                            TevJson.RequireObject(item, "parameter");
                        TevJson.RequireExactKeys(
                            parameter,
                            "parameter",
                            "name",
                            "type");
                        return new TevScriptParameterDefinition(
                            TevJson.RequireString(parameter, "name"),
                            TevJson.RequireString(parameter, "type"));
                    })
                    .ToArray(),
                TevJson.RequireArray(raw, "instructions")
                    .Select(item => TevJson.RequireObject(item, "instruction"))
                    .ToArray(),
                TevScriptProgram.RequireInt32(
                    raw["instruction_budget"],
                    "instruction_budget"));
        }
    }

    public sealed class TevScriptCapabilityDefinition
    {
        private TevScriptCapabilityDefinition(
            string capabilityId,
            IReadOnlyList<string> parameters,
            string returnType,
            string kind)
        {
            CapabilityId = capabilityId;
            Parameters = parameters;
            ReturnType = returnType;
            Kind = kind;
        }

        public string CapabilityId { get; }
        public IReadOnlyList<string> Parameters { get; }
        public string ReturnType { get; }
        public string Kind { get; }

        internal static TevScriptCapabilityDefinition Parse(
            Dictionary<string, object> raw)
        {
            TevJson.RequireExactKeys(
                raw,
                "capability",
                "capability_id",
                "parameters",
                "return_type",
                "kind");
            return new TevScriptCapabilityDefinition(
                TevJson.RequireString(raw, "capability_id"),
                TevJson.RequireArray(raw, "parameters")
                    .Select(item => TevJson.RequireString(item, "parameter"))
                    .ToArray(),
                TevJson.RequireString(raw, "return_type"),
                TevJson.RequireString(raw, "kind"));
        }
    }
}
